# CircuitEvolve

Verifier-first harness for LLM-assisted fault-tolerant (Clifford+T) circuit optimization.
Standing rules: [CLAUDE.md](CLAUDE.md). Core design: [docs/CORE.md](docs/CORE.md).

## The core: mutator, verifier, metric + a selection loop (`circuitevolve/core/`)

| Part | File | Role |
|---|---|---|
| mutator | `core/mutator.py` | LLM proposes a replacement for one window (<= 4 qubits, <= 40 ops) in a literal text format, exact or approximate within the window's error allowance |
| verifier | `core/verifier.py` | frozen `blocks/verify_block.py`: exact D[omega] for Clifford+T windows, operator distance <= allowance otherwise; whole-circuit check against the original circuit |
| metric | `core/metric.py` | T-count under BQSKit's convention (gridsynth at eps_synth / N_Rz, pi/4 multiples exact), rotations, CNOTs |
| loop | `core/loop.py`, `core/ledger.py`, `core/circuit.py` | TKET-pre-optimized input, windows by T-cost, accept on measured improvement, best + 3 diverse circuits, playbook updated on measured T reduction, every LLM call logged |

Error ledger v0: total eps; eps/2 for approximate window rewrites (charged their measured distance),
eps/2 for final rotation synthesis (eps_rz = (eps/2)/N_Rz); reported bound <= eps.

```
python -m venv --system-site-packages .venv && .venv/bin/pip install -e .[dev,blocks]
.venv/bin/python -m pytest -q                                                  # all tests
.venv/bin/python experiments/window_run.py heisenberg_6 1e-3 --tag <new tag>   # claude CLI backend
```
In a Claude Science kernel (environment `circuitevolve-dev`):
`from experiments.window_run import run_api; run_api(host, "heisenberg_6", 1e-3, tag="...", calls=20)`.
Outputs: `results/window_runs/<tag>.jsonl` (one line per LLM call), `<tag>_summary.json`, `<tag>_best.qasm`,
`<tag>_playbook.{json,md}`. Baselines B0-B3 (TKET / pyzx + gridsynth, default BQSKit-FT, published DPF script):
`experiments/bqskit_baselines/`, `results/bqskit_baselines/stage1/`.

## Legacy stacks (archived 2026-10-13, reproducible)

| Stack | Code | Old import path (alias) |
|---|---|---|
| relaxed-spec adder search (P0-P5: exact Z[omega] verifier, slice programs, MAP-Elites, LLM proposer) | `circuitevolve/legacy/adder/` (+ frozen `ir, ring, sim, spec, verify, cost, acceptance` in place) | `circuitevolve.search.{slice,evolve,llm}` |
| block optimizer v1 (structure programs, rule library, proposer, pipeline) | `circuitevolve/legacy/blocks_v1/` | `circuitevolve.blocks.{program,rules,proposer,pipeline}` |
| optimizer-program evolution (OpenEvolve-style programs over a toolbox) | `circuitevolve/legacy/evolve_opt/` | `circuitevolve.evolve_opt.*` |

Old commands still work, e.g. `experiments/acceptance.py`, `experiments/baselines.py`,
`experiments/search_classical.py`, `experiments/search_llm.py`, `experiments/evolve_opt_*.py`; their tests
are in `tests/legacy/`. Docs: `docs/TEST_PLAN.md`, `docs/BLOCK_PIPELINE.md`, `docs/EVOLVE_OPT.md`.
