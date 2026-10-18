# CircuitEvolve — standing rules

A verifier-first harness for **LLM-assisted discovery of fault-tolerant circuit constructions**. The
LLM is a mutation operator inside a search loop; an exact verifier decides what survives.

## Current work: the unified engine (read `docs/ENGINE.md` first; window specifics in `docs/CORE.md`)

Since 2026-10-18 there is ONE generic, domain-blind pipeline in `circuitevolve/engine/` (loop, plugin
contract, tier-0 router, playbook tiers, `optimize()` entry point) with domains as plugins under
`circuitevolve/domains/`: `dv_windows` (the stage-1 window core below, behaviorally identical —
golden-equivalence-gated) and `cvdv` (the frozen CV-DV certified compiler, wrapped in place).
The engine owns acceptance, the error-ledger protocol, playbook credit, logging and integrity;
plugins own select/mutate/verify/measure. `core/loop.py` is now a thin shim; everything below about
the window core still holds and runs unchanged.

The window core (`circuitevolve/core/` + the `dv_windows` plugin), for fault-tolerant
(Clifford+T) circuit optimization compared against BQSKit-FT (skill `bqskit-ft-reference-baseline`):

| Part | File | What it does |
|---|---|---|
| mutator | `core/mutator.py` | LLM sees one window (<= 4 qubits, <= 40 ops), its T-cost, its error allowance, playbook rules and recent verifier feedback; returns replacement windows in a literal text format (regex-parsed, never exec/eval) |
| verifier | `core/verifier.py` | wraps the FROZEN `blocks/verify_block.py`: exact D[omega] check for Clifford+T windows, else phase-aligned operator distance <= allowance; whole-circuit check against the ORIGINAL circuit (n <= 20) on every accept |
| metric | `core/metric.py` | T-count under BQSKit's convention: remaining Rz synthesized by gridsynth at eps_rz = eps_synth / N_Rz, pi/4 multiples exact; also rotation and CNOT counts |
| loop | `core/loop.py` (+ `core/ledger.py`, `core/circuit.py`) | start from the TKET-pre-optimized input, windows by T-cost, accept on measured improvement, archive best + 3 others, playbook updated only on measured T reduction, one JSON line per LLM call in `results/window_runs/<tag>.jsonl` |

Error ledger v0 (`core/ledger.py`): total eps per circuit; eps/2 for approximate window rewrites (charged their
measured distance), eps/2 for final synthesis (eps_rz = (eps/2)/N_Rz); bound <= eps. Run:
`experiments/window_run.py`. Stage-1 circuits: qft_8, qpe_8, qae_13, heisenberg_6, tfim_6, hubbard_8, qml_13,
hhl_8 at eps in {1e-3, 1e-5}; arms B0-B3 in `results/bqskit_baselines/stage1/` (Baselines track).

**Legacy (archived 2026-10-13, still reproducible):** the relaxed-specification adder search
(`circuitevolve/legacy/adder/`, P0-P5 below), the block optimizer v1 rule library / proposer / pipeline
(`circuitevolve/legacy/blocks_v1/`) and optimizer-program evolution (`circuitevolve/legacy/evolve_opt/`). Their
old import paths (`circuitevolve.search.{slice,evolve,llm}`, `circuitevolve.blocks.{program,rules,proposer,
pipeline}`, `circuitevolve.evolve_opt.*`) are aliases of the same module objects; their tests are in
`tests/legacy/`. Do not extend them; new work goes into `circuitevolve/core/`.

### Legacy adder experiment (`docs/TEST_PLAN.md`)

**Relaxed-specification adder test.** Starting from a naive ripple-carry (Cuccaro) adder, can search
find an n-bit adder with fewer than **8n** T gates (the floor reached by exact-unitary optimization,
measured with pyzx) and ideally rediscover Gidney's **~4n** temporary-AND adder?

| Reference | T-count | Status |
|---|---|---|
| Naive Cuccaro (7 T per Toffoli) | 14n | measured |
| pyzx full_reduce | 8n | measured n = 1..8 |
| Gidney 2018 (clean ancillas + measurement-based uncompute) | ~4n | published target |

Background: `docs/FTQC_PRIMER.md` (methods by level), `docs/PIPELINE.md` (overall tool design).

Build phases (legacy adder track; each ended at a gate): P0 IR + simulators -> P1 verifier + planted-bug
suite (gate: 100%) -> P2 baselines (gate: 14n/8n/~4n reproduced) -> P3 classical search (go/no-go) -> P4 LLM
proposer -> P5 experiment arms -> P6 transfer. P0-P3 use no LLM.

## Invariants — changing any of these invalidates past results

1. **Exact arithmetic decides every Clifford+T ACCEPT.** The simulator works over the ring Z[ω]/√2^k
   (ω = e^{iπ/4}); floating point is never used to accept a Clifford+T candidate. Rewrites of blocks
   with continuous Rz angles (block optimizer, `blocks/`) are accepted by the APPROXIMATE mode
   `blocks/verify_block.py` with an explicit error budget: phase-aligned operator-norm distance
   ≤ eps_block (default 1e-8) on the instance angles, and for angle-expression rules also on ≥ 32 random
   angle vectors; every reported circuit carries the bound d(input) + Σ block distances + #rz·eps_rz.
   Blocks whose gates are all Clifford+T may be checked exactly (D[ω]) by the same module.
   The window core (`core/verifier.py`) uses the same module with the ledger's allowance eps_w in place of
   eps_block, charges each accepted window its measured distance, and checks a window whose original and
   replacement are both Clifford+T ONLY exactly (no floating-point fallback).
2. **The specification, not the unitary, is the contract.** A candidate must compute the spec's
   function on every valid input (ancillas start in |0⟩), return ancillas to |0⟩, and for every
   measurement branch m apply K_m|x⟩ = c_m|f(x)⟩ with the *same* c_m for all x (phase consistency) and
   Σ_m |c_m|² = 1. See `circuitevolve/verify.py`.
3. **Fitness is lexicographic, never a weighted blend:** correctness gate first, then T-count, then
   qubits, then T-depth.
4. **The verifier is frozen during search.** Search code, prompts and candidates must never modify
   `ir.py`, `sim.py`, `spec.py`, `verify.py`, `cost.py`, `blocks/verify_block.py` or the planted-bug
   suites (`acceptance.py`, `tests/test_blocks_verify.py`). `core/verifier.py` only wraps them; if a needed
   check cannot be expressed through the frozen API, stop and report instead of editing them. Any change to these
   requires re-running `tests/` and the acceptance suite, and is recorded in `results/CHANGELOG.md`.
5. **Results are append-only.** Add rows/files under `results/`; never edit an existing row.
6. **Global phase is unobservable**, but relative phase between inputs is not (invariant 2).
7. **Self-evolving parts change proposals, never acceptance.** The playbook (`search/playbook.py`) and any
   future evolved search code may change between runs; the verifier files may not (`integrity.py` checks a
   digest every run). A playbook learned on development rows is evaluated FROZEN on held-out rows, and
   reflector calls are reported as LLM calls in every budget comparison. Mutable playbooks live in
   `playbooks/`; each run snapshots its final playbook into `results/llm_runs/` (append-only).

## Layout

```
circuitevolve/
  engine/      THE generic pipeline (docs/ENGINE.md): loop.py (domain-blind EvolveLoop), plugin.py
               (DomainPlugin contract), router.py (tier-0, deterministic), run.py (optimize() entry),
               graduate.py (hash-checked graduated-rule library), reflector.py (point-2 seam),
               ledger.py / playbook.py (re-exports of the implementations below)
  domains/     dv_windows/ (window core as plugin), cvdv/ (frozen CV-DV compiler wrapped in place),
               dv_arith/ reserved (point 3)
  core/        window-core parts: circuit.py, mutator.py, verifier.py, metric.py, ledger.py (docs/CORE.md);
               loop.py = back-compat shim over the engine
  llm_backends.py  make_api_backend (host.llm, thinking off), make_cli_backend, make_batch_merger
  locks.py     NUMERIC_LOCK - one process-wide lock: never fork while numpy verification runs
  integrity.py digest of the frozen verifier files, checked at start/end of every run
  ir.py, ring.py, sim.py, spec.py, verify.py, cost.py, acceptance.py   exact Z[omega] stack (FROZEN)
  blocks/      shared Clifford+Rz infrastructure: circuit_io (QASM import, minrz lowering), partition
               (BQSKit windows), cost_model (cached gridsynth), passes (phase folding), classical (TKET /
               pyzx inputs), runtime (in-process BQSKit runtime), verify_block.py (FROZEN approximate mode)
  search/      playbook.py (self-evolving rule file, used by the core); slice/evolve/llm = legacy aliases
  baselines/   naive Cuccaro, pyzx, Gidney reference (used by the frozen acceptance suite)
  legacy/      adder/ (slice search + LLM proposer), blocks_v1/ (rule library, proposer, pipeline),
               evolve_opt/ (optimizer-program evolution) - archived, reproducible, not extended
experiments/   run scripts (window_run.py for the core; others legacy); bqskit_baselines/ = Baselines track
tests/         core + frozen suites; tests/legacy/ for the archived stacks
results/       append-only outputs (window_runs/ for the core)
playbooks/     mutable playbooks: router.json (tier 0), families/ (tier 1: dv.windows incl. 8 primer
               seeds, cvdv.bosonic incl. 2 certified harvest seeds), graduated/ (hash-checked
               executable rules; G1 = same_pauli_merge, dev replay -8.27% T, every application
               re-verified); window_v0.json / dev_v1.json etc. = stage-1 originals (unchanged)
```

## Commands

```
.venv/bin/python -m pytest -q          # all tests (core, frozen verifier suites, tests/legacy/)
.venv/bin/python experiments/window_run.py heisenberg_6 1e-3 --tag <new tag>   # CLI backend
# platform kernel (env circuitevolve-dev): from experiments.window_run import run_api; run_api(host, ...)
```

## Status (2026-10-06)

P0–P3 complete. Acceptance 21/21; baselines exactly 14n / 8n / 4n; classical search GO
(`results/P3_go_no_go.md`): reaches 4n only from the Toffoli-carry seed in tier A; flat at 14n from
Cuccaro (tiers A, B) and from Toffoli-carry in tier B. Those three rows are the LLM targets.

## Status (2026-10-06, later)

P4 pilot done (`results/P4_pilot.md`). Tier A: LLM reaches 4n in its first batch even blinded (recall).
Tier B: only LLM + local repair reaches 4n (call 54); LLM alone 7n, classical 14n. Further LLM runs:
`experiments/search_llm.py` from a terminal where `claude` is logged in.

## Status (2026-10-11)

Self-evolving playbook added (`search/playbook.py`, `--playbook/--reflect-every/--freeze-playbook`).
Terminal CLI run cuccaro_B_evo_repair300_120_cli: 119/120 calls failed (76 exit 1, 43 timeouts) — backend
must be fixed before P5 statistics. Benchmarks for the BQSKit comparison: `benchmarks/bqskit_qseed/`.

## Status (2026-10-11, block optimizer)

Block optimizer v1 in `circuitevolve/blocks/` (docs/BLOCK_PIPELINE.md); approximate verifier
`blocks/verify_block.py` frozen. Dev smoke (`results/blocks/SMOKE_REPORT.md`): LLM found 0 verified
improvements on tfim_4 / heisenberg_4 / qft_5 / hhl_8 (35 proposer calls); deterministic phase folding cuts
hhl_8 (TKET input) from 54,914 to 48,307 T. Evaluation circuits not yet touched.

## Status (2026-10-13, window core)

Older stacks archived to `circuitevolve/legacy/` (aliases keep every old command working; 169 original tests
pass, plus 71 original legacy tests re-run unchanged through the old import paths). New three-part core in
`circuitevolve/core/` (docs/CORE.md), 194 tests pass. Live smoke heisenberg_6 at eps 1e-3 (20 calls, ~35k
tokens): T 8600 -> 8600 (v0 ledger; 8200 = B0 with unspent window budget returned), nothing accepted - the
model declined 19/20 windows and the verifier rejected the 3 candidates it gave (snaps 80x over allowance).
See `results/window_runs/smoke_heisenberg_6_e3_NOTE.md`.
