# circuitevolve/v2 — two-tier LLM-assisted FT compilation

Design (one page): [docs/v2/DESIGN.md](../../docs/v2/DESIGN.md). Results: [results/v2/](../../results/v2/README.md).

## Two tiers

| Tier | What the LLM does | What decides acceptance |
|---|---|---|
| **1. Compilation strategy** | Reads a *logical* circuit (Toffoli / multi-controlled / rotation level), recognizes subroutines (adder, multi-controlled gate, QFT, Trotter step, ...) and picks or writes the best known construction for each (e.g. Gidney's temporary-AND adder instead of pyzx on Toffoli adders; dyadic phase fixing on rotation blocks). | `verify.verify(candidate, logical_reference, mode, eps)` against the LOGICAL circuit. |
| **2. Optimization** | Writes EXECUTABLE rewrite rules (pattern -> replacement), not text hints. Rules are applied wherever they match. | Every single application is verified; a rule-library version is kept only if it beats the previous version on the development circuits. |

## One verifier, three labelled modes (`verify.py`)

`verify(candidate, reference, mode, eps=0.0) -> Verdict(ok, mode, distance, bound, reason, method, certified, ...)`

| mode | contract | machinery (all imported, none edited) |
|---|---|---|
| `exact` | candidate == reference as unitaries on the SAME qubits, up to one global phase; Clifford+T / Toffoli-level only | frozen `sim.run` over D[ω] = Z[ω, 1/√2]; exhaustive over basis inputs (a proof), sampled basis inputs for large permutation-like circuits (`certified=False`) |
| `approx` | phase-aligned operator distance <= eps (continuous Rz) | `core/verifier.check_circuit` -> frozen `blocks/verify_block.circuit_check`; dense n <= 10 (bound), statevector n <= 20 (lower bound only, `certified=False`) |
| `relaxed` | extra clean ancillas, mid-circuit measurement + classical feed-forward allowed: for every valid input and every branch m, K_m\|x> = c_m \|f(x)> with ancillas back in \|0> and the SAME c_m for all x, sum_m \|c_m\|^2 = 1 | frozen `sim.run` branch-wise, exactly (the semantics of the frozen adder verifier `verify.py` L1/L2) |

`Verdict.unitary_preserving` is True for `exact` / `approx` and False for `relaxed`; reports must keep the two
groups in separate columns. Floating point never accepts a Clifford+T candidate (CLAUDE.md invariant 1): `approx`
on two Clifford+T circuits is routed to `exact`.

References are `verify.ReferenceSpec` objects (`from_circuit`, `from_function`, `from_ops`); valid inputs may be
restricted (e.g. clean output qubits in |0>) only in `relaxed` mode.

## Metric (`metric.py`)

`measure(c, eps=None, data_qubits=None)` -> `t_count` (explicit T/Tdg + odd π/4 Rz + gridsynth T of every other
Rz at eps_rz = eps / N_Rz, BQSKit convention via `core/metric.BqskitTMetric`), `t_fixed`, `t_gs`, `rz`, `qubits`,
`ancillas`, `measurements`, `t_depth`, `cx`, `gates`. Fitness is lexicographic (T, qubits, T-depth): `fitness_key`.

## Baselines (`baselines.py`)

`table()` and `best_classical(circuit, eps)` over the REUSED numbers (never recomputed):
`results/bqskit_baselines/stage1/stage1_baselines_v2.csv` (`t_count_canon`, valid arms only),
`results/bqskit_baselines/reference_pipelines.csv` (old per-rotation eps_rz = 1e-9 convention, separate key),
`results/v2/reused/published_baselines.csv` (context only), plus `results/v2/baselines_new.csv` when the
Benchmarks track has written it.

## Isolation rules

- All new code lives here, new results in `results/v2/` (append-only), new docs in `docs/v2/`, tests in `tests/v2/`.
- Import from `circuitevolve.{ir,sim,ring,spec,verify,cost}`, `blocks/*`, `core/*` freely; never edit them.
  `integrity.frozen_digest()` must be unchanged before and after every v2 run.
- Existing baseline numbers are reused, never recomputed.
