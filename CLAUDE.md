# CircuitEvolve — standing rules

A verifier-first harness for **LLM-assisted discovery of fault-tolerant circuit constructions**. The
LLM is a mutation operator inside a search loop; an exact verifier decides what survives.

## Current experiment (read `docs/TEST_PLAN.md` first)

**Relaxed-specification adder test.** Starting from a naive ripple-carry (Cuccaro) adder, can search
find an n-bit adder with fewer than **8n** T gates (the floor reached by exact-unitary optimization,
measured with pyzx) and ideally rediscover Gidney's **~4n** temporary-AND adder?

| Reference | T-count | Status |
|---|---|---|
| Naive Cuccaro (7 T per Toffoli) | 14n | measured |
| pyzx full_reduce | 8n | measured n = 1..8 |
| Gidney 2018 (clean ancillas + measurement-based uncompute) | ~4n | published target |

Background: `docs/FTQC_PRIMER.md` (methods by level), `docs/PIPELINE.md` (overall tool design).

## Build phases (do not skip; each ends at a gate)

P0 IR + simulators → P1 verifier + planted-bug suite (gate: 100%) → P2 baselines (gate: 14n/8n/~4n
reproduced) → P3 classical search (go/no-go) → P4 LLM proposer → P5 experiment arms → P6 transfer.
P0–P3 use no LLM.

## Invariants — changing any of these invalidates past results

1. **Exact arithmetic decides every Clifford+T ACCEPT.** The simulator works over the ring Z[ω]/√2^k
   (ω = e^{iπ/4}); floating point is never used to accept a Clifford+T candidate. Rewrites of blocks
   with continuous Rz angles (block optimizer, `blocks/`) are accepted by the APPROXIMATE mode
   `blocks/verify_block.py` with an explicit error budget: phase-aligned operator-norm distance
   ≤ eps_block (default 1e-8) on the instance angles, and for angle-expression rules also on ≥ 32 random
   angle vectors; every reported circuit carries the bound d(input) + Σ block distances + #rz·eps_rz.
   Blocks whose gates are all Clifford+T may be checked exactly (D[ω]) by the same module.
2. **The specification, not the unitary, is the contract.** A candidate must compute the spec's
   function on every valid input (ancillas start in |0⟩), return ancillas to |0⟩, and for every
   measurement branch m apply K_m|x⟩ = c_m|f(x)⟩ with the *same* c_m for all x (phase consistency) and
   Σ_m |c_m|² = 1. See `circuitevolve/verify.py`.
3. **Fitness is lexicographic, never a weighted blend:** correctness gate first, then T-count, then
   qubits, then T-depth.
4. **The verifier is frozen during search.** Search code, prompts and candidates must never modify
   `ir.py`, `sim.py`, `spec.py`, `verify.py`, `cost.py`, `blocks/verify_block.py` or the planted-bug
   suites (`acceptance.py`, `tests/test_blocks_verify.py`). Any change to these
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
  ir.py        Circuit IR: gates, macros (ccx, and_compute, and_uncompute), measurement, classical control
  ring.py      exact arithmetic in Z[ω]/√2^k
  sim.py       sparse exact simulator, branch-wise over measurement outcomes
  spec.py      specifications (adder), register contracts
  verify.py    verifier levels L0–L3
  cost.py      T-count, T-depth, qubits
  baselines/   naive Cuccaro, pyzx, Gidney reference
  search/      representations, mutation operators, search loops (P3+), LLM proposer (P4+)
  blocks/      block optimizer v1: QASM import, best-classical input, BQSKit partitions, block programs,
               approximate verifier (verify_block.py, FROZEN), cost model, rule library, LLM proposer
experiments/   run scripts and configs
tests/         unit tests + verifier acceptance suite (planted bugs)
results/       append-only outputs
```

## Commands

```
.venv/bin/python -m pytest -q          # all tests, including the verifier acceptance suite
.venv/bin/python experiments/baselines.py
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
