# Evolving the optimizer program (`circuitevolve/evolve_opt/`)

Pivot after the block smoke (0 verified LLM block rewrites, `results/blocks/SMOKE_REPORT.md`): the LLM no
longer rewrites blocks; it **evolves the optimizer program** (OpenEvolve / AlphaEvolve style). The frozen
verifier still decides validity. Fitness is measured against the best classical result.

## Program interface

An optimizer program is Python source defining

```python
def optimize(circ, tools, budget):
    ...
    return <circuit handle>
```

* `circ` is an opaque handle on the ORIGINAL qseed circuit (U3+CX; shor via qiskit opt0). Handles have no
  public attributes; every tool returns a new handle.
* `tools` is the fixed toolbox (`toolbox.py`, `toolbox.API_DOC` is the text shown to the LLM):
  queries (`stats`, `t_count`, `rz_count`, `cx_count`, `gate_count`, `better`, `best`, `gridsynth_t`,
  `error_used`, `error_left`, `time_left`, `tket_passes`); exact passes (`lower`, `pyzx_full_reduce`,
  `pyzx_teleport_reduce`, `pyzx_clifford_simp`, `pyzx_basic`, `tket(c, passes)` with 15 TKET passes,
  `phase_fold`, `resynth_1q`, `fold_resynth`, `canonicalize`); partitioning + block resynthesis
  (`block_optimize(c, method, block_size, max_gates, passes)`: QuickPartitioner blocks rewritten by
  fold / resynth / pyzx / TKET, a block kept only if strictly cheaper and within 1e-8 by the frozen
  `verify_block.verify_instance`); approximation (`approx_round(c, allowance)`).
* `budget` = `{time_s, error_budget, eps_rz, numeric_slack, n}`. Programs do not see the circuit name.
* The returned handle must be a Clifford+Rz tool output (not the raw input).

Tools are deterministic and cached on disk by (tool, parameters, input ops); a cache hit charges the CPU
seconds of the original call, so a program's charged runtime does not depend on what ran before.
Charged CPU above `time_s` (300 s per circuit in the experiments) raises `BudgetError` → the circuit fails.

## Static checks (`sandbox.static_check`, parent side, `ast` only)

Top level: function definitions, literal constants, docstring; `optimize(circ, tools, budget)` required.
Refused: import, class, global/nonlocal, async, yield, with, del, decorators; any name/attribute/argument
starting with `_`; string constants containing `__`; the names open, exec, eval, compile, getattr, setattr,
delattr, globals, locals, vars, dir, type, object, super, `__import__`, input, print, breakpoint, help, ...;
attribute access except `tools.<public API name>` and list/dict methods (append, extend, insert, pop, get,
items, keys, values, copy, index, count, sort, reverse); attribute assignment; rebinding `tools`;
> 20,000 characters or > 3,000 AST nodes.

## Sandbox (`sandbox.run_program`)

One fresh interpreter (`.venv/bin/python -m circuitevolve.evolve_opt.child`) per (program, circuit), own
session; the child re-runs the static check and `exec`s with a whitelisted `__builtins__` (len, range, min,
max, abs, sum, sorted, enumerate, zip, list, dict, tuple, set, float, int, bool, round, any, all, reversed,
str, isinstance, Exception, ValueError). The parent's watchdog kills the session at the wall-time limit
(2 × time_s + 90 s) or when the child's RSS exceeds the memory cap (4 GB default; psutil polling, because
macOS does not enforce RLIMIT_AS). The child never reads benchmark files: the parent passes the original ops.

## Verification and error accounting (`evaluate.verify_output`, parent side)

Total error budget per circuit: **1e-6** (phase-aligned operator norm). Split:

| share | amount | who accounts |
|---|---|---|
| synthesis | #rz(output) × eps_rz, eps_rz = **1e-9 fixed** | parent (counts rz itself) |
| numeric slack of exact passes | 1e-8 | reserved; pyzx's Fraction angles give ~1e-11, measured |
| approximation | remainder = 1e-6 − 1e-8 − #rz × 1e-9 | toolbox ledger (`approx_round`, `block_optimize`) |

eps_rz is fixed at the baseline's 1e-9 so that no gain can come from re-splitting the budget between
synthesis and approximation; the best-classical reference uses 1e-9 per rotation as well.

Parent checks for every output: gate set {h,x,z,s,sdg,t,tdg,cx,cz,rz}, qubit range, finite angles; frozen
`verify_block.circuit_check` against the ORIGINAL circuit (dense unitary for n ≤ 10; four Haar-random
statevectors for 10 < n ≤ 20); then

* n ≤ 10: bound = max(d_unitary, ledger) + #rz × 1e-9 (d_unitary is the operator-norm distance itself);
* n > 10: bound = ledger + 1e-8 + #rz × 1e-9, and the measured statevector distance (a lower bound on the
  operator distance) must be ≤ ledger + 1e-8 — this catches wrong outputs and unaccounted approximation;
  the bound relies on the ledger, which only toolbox calls can change (programs cannot reach `_` state).

Valid iff bound ≤ 1e-6. T is recomputed by the parent (gridsynth, eps 1e-9, angles reduced to [−π, π]).
Verification is serialised by a lock: running the numpy distance computation in parallel threads returned
wrong distances (heisenberg_8: 0.74 instead of 3.5e-14), see CHANGELOG 2026-10-11.

## Fitness (lexicographic)

1. valid on all circuits of the set (otherwise no fitness);
2. geometric mean over circuits of T(program) / T(best classical), where best classical = min over pyzx
   full_reduce and TKET FullPeepholeOptimise of min(raw-angle, canonical-angle) T at eps_rz 1e-9
   (`results/evolve_opt/baseline_dev.json`, same definition as phase 0 / the block pipeline);
3. total charged CPU seconds.

## Evolution loop (`evolve.run_evolution`)

MAP-Elites grid per island (program AST size × FAST runtime, 5 × 5), 2 islands with migration, parent =
island best (p = 0.5) or a random island elite, two inspirations (best full-dev program + a random elite).
The LLM answers with SEARCH/REPLACE diffs or a full rewrite; parsing is literal (string matching, fence
extraction, `ast.parse`), nothing is executed in the parent. Cascade: FAST subset (6 circuits), then the full
dev set (17) if the FAST geomean is within 2 % of the best. Evaluation cache keyed by the source hash
(+ toolbox / evaluator versions and the frozen-verifier digest). Every call is logged to
`results/evolve_opt/<tag>/calls.jsonl`; candidate sources to `programs/`.

Playbook: `search/playbook.py` with `evidence="improvement"` (now the default): a candidate rule is promoted
when the rate of prompts whose child beat its parent (strictly lower FAST geomean) is credibly higher when
the rule is shown than when hidden; the raw-pass gate is still available as `evidence="pass"`.

## Classical control (`control.run_control`)

Random and greedy (first-improvement hill-climbing from the seed pipeline) search over pass-sequence
genomes (1–3 start pipelines, then up to 8 steps from 30 tool calls/parameter settings), compiled into
ordinary programs (`programs.genome_source`) and evaluated through the same sandbox, verifier, cascade and
cache, at a matched number of program evaluations.

## Commands

```
.venv/bin/python -m pytest -q tests/test_evolve_opt.py
# one LLM seed (platform python kernel, environment circuitevolve-dev):
from experiments.evolve_opt_run import run_seed
run_seed(seed=0, llm=host.llm, model=host.reasoning_model(), n_calls=120)
# controls (terminal):
.venv/bin/python experiments/evolve_opt_run.py control --mode random --seed 0 --evals 120
```
