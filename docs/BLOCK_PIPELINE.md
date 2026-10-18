# Block optimizer v1 (`circuitevolve/blocks/`)

> **Legacy (2026-10-13).** The rule library / proposer / pipeline described here now live in
> `circuitevolve/legacy/blocks_v1/` (old paths are aliases). The shared infrastructure stays in `circuitevolve/blocks/`
> and is used by the window core (docs/CORE.md).

Goal: beat the **best classical** Clifford+T compilation (lower T of pyzx `full_reduce` and TKET
`FullPeepholeOptimise`, both followed by gridsynth at eps_rz = 1e-9) by rewriting small blocks with an
LLM, where every accepted rewrite is checked by a frozen verifier with an explicit error budget.

```
qseed QASM (U3+CX; shor via qiskit opt0)            circuit_io.load_u3cx      (eval circuits refused)
  -> exact minrz Clifford+Rz lowering                  circuit_io.lower_minrz    (phase-0 code)
  -> pyzx | TKET, keep the lower T  = INPUT            classical.best_classical
  -> rz angles reduced to [-pi, pi] (global phase)     cost_model.canonicalize
  -> QuickPartitioner(3) (2 optional), windows <= 40   partition.partition
  -> in-block phase folding + 1q minimal-RZ resynth    passes.classical_pass  (no LLM, verified)
  -> structure groups (angles abstracted -> a0..ak)    partition.group
  -> rule library on every block of a known structure  rules.RuleLibrary.apply
  -> LLM proposals, one prompt per distinct structure  proposer.search_structures
  -> reassembly + whole-circuit check vs ORIGINAL       pipeline.run_pipeline / verify_block.circuit_check
```

## Modules

| file | role |
|---|---|
| `verify_block.py` | **FROZEN** (in `integrity.FROZEN`). Approximate verification mode, exact D[ω] mode, whole-circuit check |
| `circuit_io.py` | QASM import, minimal-RZ 1q decomposition, op <-> bqskit conversion, QASM writer/reader |
| `classical.py` | pyzx and TKET pipelines -> op lists, best-classical choice |
| `partition.py` | QuickPartitioner, gate windows, `Block`, structure signatures, reassembly |
| `program.py` | block program text format, literal `ast`-whitelist parser, numerical instantiation of `p_j` |
| `passes.py` | deterministic phase folding and 1q resynthesis |
| `cost_model.py` | gridsynth T counting (cached), `improves()` acceptance order |
| `rules.py` | persistent JSON rule library; verified application to every instance |
| `proposer.py` | prompt builder, candidate evaluation, budgeted per-structure search loop (+ playbook) |
| `pipeline.py` | end-to-end run, error bound |
| `runtime.py` | in-process serial BQSKit runtime (the Compiler needs a localhost socket, blocked here) |

Run: `experiments/blocks_smoke.py::run_smoke` (in-platform backend, see docs/LLM_BACKENDS.md).
Environment: repo `.venv` with the `blocks` extra (`pip install -e .[blocks,dev]`).

## Block program format

```
qubits 3
cx q0 q1
rz(a0 + a3) q1        # exact rewrite in the instance's input angles
rz(-a1/2 + pi/4) q2
rz(p0) q0             # free parameter, fitted per instance (Levenberg-Marquardt, pi/4 snapping)
h q2
```
Gates `h s sdg x z t tdg cx cz rz` on local qubits; angles are `+ - * /` over numbers, `pi`, `a_i`, `p_j`.
The parser walks the `ast` with a whitelist; nothing is `exec`/`eval`'d. rz angles that evaluate to a
multiple of π/4 are emitted as Clifford/T gates.

## Verification (`verify_block.py`, frozen)

* Distance: `d(U,V) = ||U − e^{iφ*}V||₂`, φ* = trace phase. Upper bound on the phase-invariant operator
  distance, so errors add over blocks; computed from the difference matrix (resolves ~1e-15, unlike
  `1 − |Tr|/N`, whose square root bottoms out at ~1e-8). Frobenius/√N also recorded.
* ACCEPT a block rewrite iff `d <= eps_block = 1e-8` on the instance angles. Exact (a_i-only) rules are
  marked `general` only if they also pass on ≥ 32 uniform random angle vectors; parametric templates are
  fitted and verified separately on every instance. Every application to every block is verified on that
  block's own angles, general or not.
* Exact mode for all-Clifford+T blocks: equality up to ω^j over Z[ω]/√2^k with the frozen `sim.py`.
* Whole circuit: dense unitary (n ≤ 10) or 4 Haar-random statevectors (n ≤ 20) against the ORIGINAL
  qseed circuit. Reported bound = d(input, original) [measured] + Σ accepted block distances + #rz·eps_rz.
* Planted-bug suite: `tests/test_blocks_verify.py`.

## Cost and acceptance order

Block / circuit cost = explicit T + Σ gridsynth T(rz) at eps_rz = 1e-9 (pygridsynth 2.0.0, mpmath dps
128, same call as phase 0; each word re-verified). Angles are reduced to [−π, π] before gridsynth, and the
**baseline** is the lower of the phase-0 count (raw angles) and that canonical count — so reducing an
angle mod 2π can never be counted as a gain. A rewrite is an improvement only if T does not increase and
(fewer synthesised rz) or (same rz, fewer explicit T) or (same rz and T, fewer cx/gates). A rewrite whose
only effect is a different gridsynth T for the same number of rotations (±a few T of angle-dependent
noise) is not accepted. Blocks keep their original ops unless an improving rewrite verifies.

## Rule library

`playbooks/blocks/rules.json` (mutable) / `results/blocks/<tag>/rules.json` (snapshot): structure signature
→ replacement program, kind (exact | parametric), `general`, verification record, per-circuit gain. Rules
are applied to every block with that signature, so LLM calls scale with distinct structures.

## Options

`run_pipeline(..., global_fold=True)` runs the phase fold + 1q resynthesis on the whole circuit before
partitioning (accepted only if it improves and the whole-circuit check is <= 1e-8; its distance is added to
the bound). `input_pipeline='tket'|'pyzx'|'minrz'` forces an input (for controls only: gains against a
non-best input are not gains against the best classical result).

## Smoke results (dev circuits, `results/blocks/SMOKE_REPORT.md`)

0 verified LLM improvements in 35 proposer calls (tfim_4, heisenberg_4, qft_5, hhl_8). The only gain is
deterministic: hhl_8 (best classical = TKET, 54,914 T) goes to 51,810 T with the per-block pass and to
48,307 T with `global_fold` (`results/blocks/deterministic_dev.csv`); no change on the pyzx-input circuits.

## Known limitations of v1

* Gains are limited to what fits inside one QuickPartitioner window; no cross-block re-partitioning.
* The per-block pass is weaker than the whole-circuit fold (hhl_8: 554 vs 517 rz).
* Structure signatures are exact gate lists; near-identical structures do not share rules.
* QuickPartitioner is occasionally nondeterministic on identical input (tfim_4: 38 or 40 blocks across
  repeated calls in one process). Reassembly is exact either way, but block/structure counts can vary.
* The playbook evidence gate counts raw verifier passes. For blocks that rewards equivalent (non-improving)
  programs, so improvement-based A/B is needed before an ablation.
* Gridsynth runs serially (one call ~0.01–0.03 s); a spawn pool hangs inside notebook kernels.
