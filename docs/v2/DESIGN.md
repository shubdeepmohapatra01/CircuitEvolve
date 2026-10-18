# CircuitEvolve v2 — design (one page)

**Goal.** Lower T-count of fault-tolerant compilations below the best *reused* classical baseline
(pyzx / TKET / BQSKit-FT, skill `bqskit-ft-reference-baseline`) with the LLM in two roles, every output checked by
one verifier interface, and unitary-preserving results kept apart from results that use ancillas + measurement.

## Tiers

1. **Compilation strategy (tier 1).** Input: a LOGICAL circuit (Toffoli / multi-controlled / rotation level, e.g.
   the Nam et al. arithmetic suite or a qseed circuit). The LLM labels subroutines (adder, multi-controlled X,
   QFT, Trotter step, ...) and picks or writes a construction per subroutine (Gidney temporary-AND adder, relative-
   phase Toffolis, dyadic phase fixing on rotation blocks, ...). Accepted iff `verify(candidate, logical, mode)`
   passes; the Verdict's mode decides which results column it goes in.
2. **Optimization (tier 2).** The LLM writes executable rewrite rules (pattern -> replacement code). A matcher
   applies a rule wherever it matches; *each application* is verified (window-level exact/approx check plus the
   whole-circuit check). A rule-library version is frozen only if it beats the previous version on the
   development circuits; held-out circuits are evaluated with the frozen library.

## Verifier: `circuitevolve/v2/verify.py`

`verify(candidate, reference, mode, eps) -> Verdict(ok, mode, distance, bound, reason, method, certified, ...)`

| mode | accepts | decided by | proof? |
|---|---|---|---|
| `exact` | same qubits, U_cand = c U_ref, Clifford+T / Toffoli-level | frozen `sim.run` over D[ω], one global c for all basis inputs | yes if exhaustive (default up to 2^14 inputs); large permutation-like circuits: sampled inputs, `certified=False` |
| `approx` | phase-aligned operator distance <= eps | `core/verifier.check_circuit` -> frozen `verify_block.circuit_check` | n <= 10 dense (bound); 11-20 statevector (lower bound, `certified=False`); > 20 refused |
| `relaxed` | clean ancillas, measurement, feed-forward; K_m\|x,0> = c_m\|f(x),0>, same c_m for all valid x, Σ\|c_m\|² = 1 | frozen `sim.run` branch-wise (semantics of the frozen adder verifier L1/L2) | yes if inputs and branches exhaustive |

* References are `ReferenceSpec`s: a measurement-free circuit (Toffoli-level allowed), a basis-map function
  (permutation references for arithmetic, e.g. `adder_reference(n)`), or numeric ops (approx only). Valid inputs
  can be restricted (`zero_qubits`, e.g. a clean carry-out) only in relaxed mode.
* Invariant 1 kept: `approx` on two Clifford+T circuits is routed to `exact`; floating point never accepts them.
* Failure reasons are diagnoses (wrong output / ancilla not returned / relative phase between inputs / branch
  probability), written to be fed back to the LLM.
* Frozen files are imported, never edited; `verify.FROZEN_DIGEST` + `check_integrity()` guard each run.

## Metric: `circuitevolve/v2/metric.py`

T-count = explicit T/Tdg (+ 7 per ccx/ccz, 4 per and_compute, via frozen `cost.py`) + 1 per odd-π/4 Rz + gridsynth
T of every other Rz at eps_rz = eps_synth / N_Rz (BQSKit convention, `core/metric.BqskitTMetric`). Also qubits,
ancillas (qubits − data qubits), measurements, T-depth, CNOTs. Fitness is lexicographic (T, qubits, T-depth).
Error split for approximate tier-2 rewrites follows `core/ledger.py` (eps/2 rewrites, eps/2 synthesis) unless a
track documents another split; the total stays <= eps.

## Baselines: `circuitevolve/v2/baselines.py` (reused, never recomputed)

| source | T column | eps key | validity |
|---|---|---|---|
| stage-1 `stage1_baselines_v2.csv` | `t_count_canon` | total eps ("0.001", "1e-05") | measured within eps and bound <= eps (B2: nominal rounding, valid); B3, B2ft invalid |
| `reference_pipelines.csv` | `t_count` | `eps_rz=1e-9` (old per-rotation convention) | status ok |
| `published_baselines.csv` | per method column | the paper's own setting | context only (never the bar) |
| `results/v2/baselines_new.csv` (Benchmarks track) | `t_count` | total eps | unless notes start with INVALID |

`best_classical(circuit, eps, arms='all'|'primary')` never mixes eps settings; 'all' (default) includes the
supplementary B3m/B3g arms and is the strongest valid bar.

## Isolation

New code `circuitevolve/v2/`, tests `tests/v2/` (picked up by the existing `testpaths = tests`), results
`results/v2/` (append-only), docs `docs/v2/`. Existing `core`, `legacy`, `blocks`, results and notebooks are only
read. Every change is logged in `results/CHANGELOG.md`.
