# Optimizer-program evolution — development report (2026-10-11/12)

Scope: development circuits only (benchmarks/split.json v1: 17 dev circuits, FAST subset qft_8, qpe_8,
grover_5, mult_8, tfim_6, qae_11). No evaluation circuit (add_*, hhl_6, mult_16, qft_32, shor_16) was loaded.
Interface, sandbox, verifier and error accounting: docs/EVOLVE_OPT.md. Every number below is read from the
run files named in each section.

## Headline

* **The LLM-evolved optimizer does NOT beat the classical pass-search control.** At about 120 program
  evaluations, LLM seed 0 reached a dev geomean T/T(best classical) of **0.97027**. The six control runs reached
  **0.96175 to 0.96790**, and every control run was below the LLM run.
* Every arm beats best classical (geomean 1.0). The seed program (best classical + whole-circuit phase
  fold) is at 0.98279. All dev gains sit on 5 of 17 circuits (qpe_8, hhl_8, qpe_6, qml_4, qml_13). The other
  12 circuits never moved below best classical, in any arm.
* Only seed 0 of the three requested LLM seeds was run. This session is a sub-agent and cannot spawn
  sub-agents; seeds 1 and 2 must be launched by the parent (commands below).
* A pilot seed-0 run (evo_s0_120) is **invalidated**: an evaluator bug made multi-worker verification
  unreliable (evo_s0_120_INVALIDATED.md). Seed 0 was re-run with the fix as evo_s0_v3_120.

## Arms (matched program evaluations)

| arm | run dir | program evaluations | LLM calls | best dev geomean | found at | best FAST geomean | charged CPU of best (17 circuits) |
|---|---|---|---|---|---|---|---|
| best classical (min pyzx / TKET) | baseline_dev.json | – | 0 | 1.00000 | – | – | – |
| seed program | – | 1 | 0 | 0.98279 | – | 0.97291 | 185.6 s |
| **LLM evolution, seed 0** | evo_s0_v3_120 | 114 FAST (113 dev) | 127 (120 proposer + 7 reflector) | **0.97027** | call 67 | 0.96106 | 515.4 s |
| random control s0 | control_random_s0_120 | 121 (31 dev) | 0 | 0.96319 | eval 105 | 0.96284 | 494.4 s |
| random control s1 | control_random_s1_120 | 121 | 0 | 0.96790 | eval 72 | 0.96365 | 302.1 s |
| random control s2 | control_random_s2_120 | 121 | 0 | 0.96534 | eval 62 | 0.96387 | 212.2 s |
| greedy control s0 | control_greedy_s0_120 | 121 (109 dev) | 0 | 0.96366 | eval 102 | 0.96284 | 337.3 s |
| greedy control s1 | control_greedy_s1_120 | 121 | 0 | 0.96487 | eval 65 | 0.96200 | 224.7 s |
| greedy control s2 | control_greedy_s2_120 | 121 (111 dev) | 0 | **0.96175** | eval 105 | 0.95076 | 314.5 s |

The LLM run had 120 proposer calls. 3 failed to parse, 1 failed the static check and 3 were duplicates,
giving 114 FAST evaluations including the seed. Each control run has 121 evaluations (the seed genome plus
120). Means over the control seeds: random 0.96548, greedy 0.96343 (computed from the rows above).

**Re-verification.** The best programs of all six controls, and the seed program, were re-evaluated under the
fixed evaluator (eval cache ev-v3, bests_reverified_controls.json). All were valid, and their geomeans are
identical to the run values. The LLM run itself used ev-v3. The largest error bound among all best programs
is 5.9e-7, within the 1e-6 budget. Per-circuit verification:
* dense unitary for n ≤ 10;
* statevector for qft_16, qae_11, qae_13, qml_13 and shor_12.

![dev_evolution.png]({{artifact:art_ca06313e-55f6-417f-ac04-5877917a52ac}})

(file: results/evolve_opt/dev_evolution.png)

*(a) Best full-dev geomean found so far vs. number of program evaluations. For the LLM run the x axis is the
proposer call index, which includes the 7 calls that produced no evaluation. One LLM seed; three seeds per
control. (b) Per-circuit T ratio of the final best program of each arm, shown only for circuits where any arm
differs from best classical (on the 12 others every arm is at 1.0).*

## Per-circuit development T (gridsynth eps_rz = 1e-9, ratio to best classical in parentheses)

| circuit | n | best classical (pipeline) | seed program | LLM evo s0 | control min over 6 runs | control greedy s2 (best control) |
|---|---|---|---|---|---|---|
| qft_8 | 8 | 3,091 (pyzx) | 3,091 | 3,091 | 3,091 | 3,091 |
| qft_16 | 16 | 12,477 (pyzx) | 12,477 | 12,477 | 12,477 | 12,477 |
| qpe_6 | 6 | 12,255 (pyzx) | 12,255 | 12,255 | 12,081 (0.9858) | 12,255 |
| qpe_8 | 8 | 24,003 (tket) | 20,357 (0.8481) | 18,913 (0.7879) | 17,729 (0.7386) | 17,729 (0.7386) |
| qae_11 | 11 | 5,911 (pyzx) | 5,911 | 5,911 | 5,911 | 5,911 |
| qae_13 | 13 | 8,251 (pyzx) | 8,251 | 8,251 | 8,251 | 8,251 |
| heisenberg_6 | 6 | 13,900 (tket) | 13,900 | 13,900 | 13,900 | 13,900 |
| heisenberg_8 | 8 | 19,460 (tket) | 19,460 | 19,460 | 19,460 | 19,460 |
| tfim_6 | 6 | 14,720 (tket) | 14,720 | 14,720 | 14,720 | 14,720 |
| tfim_8 | 8 | 20,240 (tket) | 20,240 | 20,240 | 20,240 | 20,240 |
| hubbard_8 | 8 | 7,880 (pyzx) | 7,880 | 7,880 | 7,880 | 7,880 |
| grover_5 | 5 | 11,656 (pyzx) | 11,656 | 11,656 | 11,656 | 11,656 |
| qml_4 | 4 | 2,798 (pyzx) | 2,792 (0.9979) | 2,792 (0.9979) | 2,792 (0.9979) | 2,792 (0.9979) |
| qml_13 | 13 | 10,984 (pyzx) | 10,984 | 10,972 (0.9989) | 10,984 | 10,984 |
| shor_12 | 12 | 37,197 (pyzx) | 37,197 | 37,197 | 37,197 | 37,197 |
| mult_8 | 8 | 6,139 (pyzx) | 6,139 | 6,139 | 6,139 | 6,139 |
| hhl_8 | 8 | 54,914 (tket) | 48,307 (0.8797) | 41,859 (0.7623) | 37,019 (0.6741) | 38,392 (0.6991) |
| **total T** | | 265,876 | 255,617 | 247,713 | | 243,074 |

Source: results/evolve_opt/dev_table.csv (built by experiments/evolve_opt_report.py from the run summaries).

## What the programs do

**LLM best** (frozen/v1/optimizer_llm_evo_s0_v3.py, sha256 d6ccdcd5…). It builds a candidate pool, then
refines the best candidate; each refinement is kept only if cheaper and guarded by `tools.time_left()`.
* Pool: pyzx full_reduce, TKET FullPeepholeOptimise, pyzx teleport_reduce, pyzx clifford_simp; each of them
  phase-folded + 1q-resynthesised; the lowered input folded directly; teleport_reduce applied to both
  classical outputs before folding.
* Refinements: a chain of block_optimize calls (fold_resynth / pyzx / tket, block sizes 3–4), with re-folds
  after clifford_simp and teleport_reduce.

**Best control** (frozen/v1/optimizer_control_greedy_s2.py, sha256 e9b300fc…). Genome:
`starts=[pyzx, tket_fpo]`, steps `[resynth_1q, pyzx_clifford_simp, block:fold_resynth:2:40, pyzx_full_reduce,
tket:PauliSimp, tket:FullPeepholeOptimiseNoSwaps, fold_resynth, resynth_1q]`.

**Why the control wins.** The gains come from repeatedly alternating ZX / TKET rewriting with phase folding,
which re-exposes mergeable rotations on hhl_8 and qpe_8. Random sequences of the 30 step types find these
alternations as easily as the LLM does. The LLM mostly grew a broad "try everything, take the best"
pool around the same primitives, 97 of its 120 proposals were diffs, and its best program was found at call
67, with no dev improvement in the last 53 calls. It also overfit the FAST subset: its best FAST program
(call 117, FAST 0.94829) scores 0.97119 on dev, worse than the dev champion.

## Learned playbook (frozen/v1/playbook.json / .md, from evo_s0_v3_120)

The gate is measured improvement: the fraction of prompts whose child beat its parent, with the rule shown vs
hidden. 19 rules were proposed by 7 reflector calls; 2 are active, 8 are still candidates and 9 were retired.
* Active R3: build a growing candidate pool with `tools.best([...])` over all pipeline variants (each
  fold_resynth'd), then time-guarded block_optimize refinements. This describes the LLM's own best program.
* Active R8: a caution about block_optimize parameter errors on qft_8 / qpe_8.

Most other rules concern output format: verbatim SEARCH blocks, no truncated programs, balanced brackets.
The reflector was repeatedly shown the same small set of failures (the run had only 1 invalid FAST
evaluation), which produced several near-duplicate rules about it (R8, R10, R11, R13). This is a weakness
of the loop: the failure list is not deduplicated across reflections. The playbook contains no rule a
classical search would not also find, and none about circuit structure.

## LLM cost

evo_s0_v3_120: 127 calls (120 proposer, 7 reflector), all successful. 633,494 input + 95,217 output tokens,
model `host.reasoning_model()` via make_api_backend (thinking off), wall time 3,165 s. The 6 control runs used
no LLM calls. Earlier calls that are not part of any comparison:
* live smoke (smoke_live_8): 9 calls, 23,376 input + 4,913 output tokens;
* invalidated pilot (evo_s0_120): 127 calls, 565,236 input + 85,435 output tokens.

## Issues and caveats

1. **Evaluator bug (found and fixed).** On this macOS machine, forking a subprocess in one thread while
   another thread runs numpy linear algebra corrupts the numpy result in the parent. Measured with
   .cache/evolve_opt/rep3.py: 30/30 wrong qft_8 distances (~1.8 instead of 3e-15) with concurrent Popen, and
   0/30 with the fix. The first fix (a verify-only lock, ev-v2) was not enough; the fix that works is
   sandbox.NUMERIC_LOCK held around Popen and around verification (ev-v3). The invalidated pilot had 8 of 20
   re-checked programs with flipped verdicts (all invalid → valid). The six controls ran with one evaluation
   thread, so spawn and verify were sequential; their bests re-verify identically under ev-v3.
   **Any other code in this repo that runs the frozen verifier in threads next to subprocess spawning is
   exposed to the same effect.**
2. **One LLM seed only.** The 3-seed requirement is not met in this session. With one seed, the LLM–control
   gap (0.97027 vs the worst control, 0.96790) cannot be given a confidence interval. Even so, the LLM run is
   below none of the six control runs.
3. **shor_14 was dropped from dev.** Its best classical output already exceeds the 1e-6 budget at eps_rz 1e-9
   (benchmarks/SPLIT.md).
4. **Ledger reliance for n > 10.** For n > 10 the error bound uses the toolbox ledger plus a statevector test,
   which is a lower bound on the operator distance. None of the best programs uses approx_round. Their
   n > 10 outputs are exact up to the 1e-8 numeric slack, and their measured statevector distances are below it.
5. **Charged runtime.** Charged runtime counts CPU seconds of tool calls, with cache hits charged at the
   original cost. It is a tie-breaker only and was never decisive here.

## Next steps for the parent

Launch LLM seeds 1 and 2 with identical settings, each in its own sub-agent: python kernel, environment
`circuitevolve-dev`.
```python
import sys; sys.path.insert(0, "/Users/shubdeepmohapatra/Documents/CircuitEvolve")
import os; os.environ.setdefault("XDG_CONFIG_HOME", "/Users/shubdeepmohapatra/Documents/CircuitEvolve/.venv/xdg")
from experiments.evolve_opt_run import run_seed
s = run_seed(seed=1, llm=host.llm, model=host.reasoning_model(), n_calls=120, batch=4,
             tag="evo_s1_v3_120", reflect_every=16, workers=4)        # seed=2 / tag evo_s2_v3_120 for the other
```
Each seed takes about 55 min wall and about 730k model tokens. After both finish:
1. Run `.venv/bin/python experiments/evolve_opt_verify_bests.py llm evo_s0_v3_120 evo_s1_v3_120 evo_s2_v3_120`.
2. Extend this report in a new section. Do not edit the tables above.
3. If a seed's best dev geomean beats 0.97027, freeze it into **frozen/v2/**. Do not touch v1.

## Frozen artifacts (results/evolve_opt/frozen/v1/, read-only, SHA256SUMS)

| file | sha256 |
|---|---|
| optimizer_llm_evo_s0_v3.py (best LLM-evolved program, dev 0.97027) | d6ccdcd56bcaee77f99be7e5ed6db4caf4f90d4739336c137eca0aa3ed51de3d |
| optimizer_control_greedy_s2.py (best control program, dev 0.96175) | e9b300fc6c642adab0cc19f83e556578101b47b475f838c747a7ac19fe0762e3 |
| playbook.json (evo_s0_v3_120) | c8e953116a3e4081c34a6af789c6e1b9723265c750ae4ab97415ac2d2c66d83f |
| playbook.md | 74821fe0a3b7360c1dac36d564359171ce8bb967f5d4247accc2f8512596ecc4 |

Both optimizers are frozen because the honest evaluation comparison is "LLM-evolved vs best classical vs
best control". Each program's hash equals the hash recorded in its run's summary.json.

## Seeds 1 and 2 (added 2026-10-12; tables above unchanged)

Run by the parent session with the identical command (`run_seed`, n_calls=120, batch=4, reflect_every=16, workers=4).
Re-verified under evaluator ev-v3 (`bests_reverified_llm.json`); all best programs valid on every dev circuit.

| run | best dev geomean (re-verified) | runtime on dev (s) |
|---|---|---|
| evo_s0_v3_120 | 0.97027 | 515 |
| evo_s1_v3_120 | 0.97377 | 428 |
| evo_s2_v3_120 | 0.97000 | 435 |
| LLM mean (3 seeds) | 0.97135 | |
| classical controls (6 runs, `bests_reverified_controls.json`) | 0.96175 - 0.96790 (mean 0.96445) | 168 - 487 |
| seed program / best classical | 0.98279 / 1.0 | 186 / 185 |

Reading: at a matched ~120 program evaluations, LLM-proposed optimizer programs improve on the seed program
(0.983 -> 0.970-0.974) but every seed is worse than every classical pass-search control. The LLM arm does not beat
the control on the development set.

Seed 2 (0.97000) is marginally better than seed 0 (0.97027), so per the freeze rule it is frozen in **frozen/v2/**
(v1 untouched; hashes in frozen/v2/SHA256SUMS). The 0.03% difference is well inside seed-to-seed spread.
