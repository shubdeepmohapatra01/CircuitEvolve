# Evaluation report: frozen optimizer programs on the Table-3 circuits and the held-out adder family (2026-10-12)

This is the first and only use of the evaluation circuits: add_17, hhl_6, mult_16, qft_32 and shor_16 (the
arXiv:2409.00433 Table-3 circuits) plus the rest of the held-out adder family, add_41 and add_65. No program,
evaluator or verifier file was changed. Every number below comes from `results/evolve_opt/eval/runs.jsonl`,
`eval/baseline_eval.json`, `eval/bygate_adders.json`, `results/bqskit_baselines/table3_bygate.csv`, the
published-baselines CSV, or the run summaries. The tables are built by `experiments/evolve_opt_eval_report.py`.

## Verdict

* **The LLM-evolved optimizer does not beat the classical pass-search control on the evaluation circuits.**
  - LLM v1 (seed 0) **ties** the best control (greedy s2) on every circuit where any program produced a valid
    output.
  - LLM v2 (seed 2), the program frozen as the LLM champion on dev, is **worse** than the control on hhl_6:
    6,568 vs 6,192 T.
  - Geomean of T / T(best classical) over the 5 circuits where all programs are valid (add_17, hhl_6,
    mult_16, qft_32, add_41): control 0.94191, LLM v1 0.94191, LLM v2
    0.95308, seed program 0.98349.
* **Both the evolved programs and the control beat best classical (min of pyzx and TKET) on exactly one circuit,
  hhl_6.** On the other circuits they reproduce best classical exactly.
  - hhl_6: 8,352 → 6,192 T (−25.9 %) for LLM v1 and for the control, and −21.4 % for LLM v2. The seed program
    (best classical + whole-circuit phase fold) gets −8.0 %.
  - add_17, mult_16, qft_32 and add_41: every program returns exactly the best-classical T-count. No arm found
    anything there.
  - The adder family was held out to test transfer. Nothing transferred to it: no program improves any adder.
* **shor_16 and add_65: no valid output from any program at the 1e-6 budget.** The best-classical output alone
  already has 1,508 RZ (shor_16) and 1,414 RZ (add_65). At eps_rz = 1e-9 that gives error bounds of 1.52e-6 and
  1.42e-6, so it cannot be valid unless a program first removes at least 518 / 424 rotations (at most 990 RZ fit in the budget). None did.
  - The seed program (shor_16, add_65) and the control (shor_16) returned outputs with the best-classical
    T-count and RZ count, which are rejected for their error bound.
  - The two LLM programs (both circuits) and the control (add_65) produced no output at all: time limit, or a
    BudgetError that was not caught.
* **Against the published BQSKit numbers (Table 3).** On the three like-for-like circuits the best program is
  below the published 3Q-block T-count:
  - add_17: −47.2 %;
  - hhl_6: −72.2 %;
  - mult_16: −60.5 %.

  Almost all of this gap is already present in best classical (pyzx / TKET + gridsynth): all of it on add_17
  and mult_16, and −62.5 % of the −72.2 % on hhl_6. It is not a contribution of the evolved programs.
* **Not numerically verified:** qft_32, add_41 and add_65 (n > 20). For these the only guarantees are the
  pass-level ones (exact passes, the error ledger, and the block-level frozen checks inside block_optimize) plus
  error accounting. qft_32 and add_41 are counted as valid by error accounting, not by a whole-circuit check.

![T-count relative to best classical](/Users/shubdeepmohapatra/.claude-science/orgs/4f2e4147-ba5e-4b44-8499-c19c4f626162/artifacts/proj_a726946937e5/38f43ad8-61dd-4e3c-8b96-69ac89dbe879/vc1512c57_eval_comparison.png)

*Figure (results/evolve_opt/eval_comparison.png).*
- *(a) T-count of each frozen program's output divided by the best-classical T-count, at error budget 1e-6. One
  run per program and circuit; the programs are deterministic. Grey bands mark circuits where no program produced
  a valid output.*
- *(b) The same ratio for the published BQSKit Table-3 rows, our reproduction of By Gate on the qseed input, and
  the best valid optimizer program.*
- *Open markers: published inputs that are not like-for-like. QFT-32 was published as an approximate QFT; the
  published Shor-16 figure is a parameter-count convention.*
- *† marks n > 20: not numerically verified.*

## Protocol

* **Programs** (hashes checked against frozen/v1 and frozen/v2 SHA256SUMS before use):
  - seed program and best-classical program (`programs.py`);
  - `frozen/v2/optimizer_llm_evo_s2_v3.py` (LLM v2, sha256 efacca60…, dev 0.97000);
  - `frozen/v1/optimizer_llm_evo_s0_v3.py` (LLM v1, d6ccdcd5…, dev 0.97027);
  - `frozen/v1/optimizer_control_greedy_s2.py` (best control, e9b300fc…, dev 0.96175).
* **Evaluator: unchanged ev-v3, toolbox tb-v1.** This includes the same sandbox, static check, child process,
  4 GB RSS cap and wall limit (2 × time_s + 90 s).
  - Error budget 1e-6, eps_rz 1e-9, numeric slack 1e-8.
  - T is recomputed by the parent with gridsynth at 1e-9.
  - Whole-circuit check by the frozen `verify_block.circuit_check`: dense unitary for n ≤ 10, four Haar-random
    statevectors for 10 < n ≤ 20.
* **Runner: `experiments/evolve_opt_eval.py` (new).** It lifts, in its own process only, the two development
  guards that refuse evaluation circuits (`circuit_io.bench_path` and `evaluate.check_dev`). Everything else calls
  `sandbox.run_program` and `evaluate.verify_output` unchanged.
  - For n > 20, `verify_output` refuses: the check is impossible. The runner then applies the same legality
    checks and the n > 10 error accounting (bound = ledger + 1e-8 + #RZ × 1e-9) without any whole-circuit check,
    and flags the row `numerically_verified = False`.
* **Best-classical reference** (`eval/baseline_eval.json`): `blocks.classical.best_classical` = min over pyzx
  full_reduce and TKET FullPeepholeOptimise of min(raw, canonical) T at 1e-9. This is the same definition as
  `baseline_dev.json`, and the best-classical program reproduces it exactly on all 7 circuits.
* **Per-circuit limits.** The default is 300 s of charged CPU. A limit was raised **identically for every
  program** where a circuit needed more time:
  - shor_16: 1,200 s. At 300 s all five programs, including the best-classical program, exceeded the limit
    (348–354 s).
  - add_41: 1,200 s. At 300 s, LLM v1 hit 301.6 s and the control hit the 690 s wall limit.
  - add_65: 1,800 s. At 300 s all five hit the wall limit.

  All earlier-limit runs are kept in the long table below. The machine was shared with a parallel sub-agent and
  up to 10 concurrent evaluations, so wall-time limits were hit sooner than on an idle machine. Charged CPU
  includes cache hits at their original cost (tool cache, as in development).
* **Run time.** The whole evaluation ran from 00:29 to 02:10 (about 1 h 41 min wall).

## Comparison table (T-count; % vs best classical in parentheses)

| circuit | n | check | limit (s) | BQSKit By Gate / 2Q / 3Q (published) | By Gate (reproduced) | pyzx | TKET | best classical | seed program | control greedy s2 | LLM v1 (s0) | LLM v2 (s2) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| add_17 | 17 | statevector | 300 | 23,562 / 21,924 / 19,912 | 23,520 | 10,508 | 17,721 | 10,508 (pyzx) | 10,508 | 10,508 | 10,508 | 10,508 |
| hhl_6 | 6 | unitary | 300 | 22,571 / 22,201 / 22,265 | 22,887 | 16,362 | 8,352 | 8,352 (tket) | 7,685 (-8.0 %) | 6,192 (-25.9 %) | 6,192 (-25.9 %) | 6,568 (-21.4 %) |
| mult_16 | 16 | statevector | 300 | 100,678 / 98,516 / 82,500 | 100,572 | 32,617 | 100,408 | 32,617 (pyzx) | 32,617 | 32,617 | 32,617 | 32,617 |
| qft_32 | 32 | **none (n>20)** | 300 | 101,480 / 98,640 / 87,248 * | 132,345 | 44,167 | 88,445 | 44,167 (pyzx) | 44,167 | 44,167 | 44,167 | 44,167 |
| shor_16 | 16 | statevector | 1200 | 74,797 / 74,790 / 74,720 * | 437,107 | 140,843 | 334,794 | 140,843 (pyzx) | invalid: 140,843, bound 1.52e-06 | invalid: 140,843, bound 1.52e-06 | no output: time limit | no output: time limit |
| add_41 | 41 | **none (n>20)** | 1200 | – | 160,030 | 60,468 | 112,069 | 60,468 (pyzx) | 60,468 | 60,468 | 60,468 | 60,468 |
| add_65 | 65 | **none (n>20)** | 1800 | – | 422,676 | 132,728 | 278,031 | 132,728 (pyzx) | invalid: 132,728, bound 1.42e-06 | no output: time limit | no output: time limit | no output: BudgetError (error left < 0) |

\* Not like-for-like:
* qft_32: the qseed qft_32 is a **full** QFT. The paper used an approximate QFT; our reconstruction (d ≤ 17)
  matches its 1,080 RZ, see results/bqskit_baselines/REPORT.md.
* shor_16: the published 816 RZ / 74,797 T is a **parameter-count convention** (one RZ per cp / ccp / u1), not a
  valid Clifford+T compilation. A valid By-Gate lowering of the same input has 4,678 RZ / 437,107 T.

**Other notes on the table**
* QAE-50 and QPE-30 from Table 3 are **not available** in the qseed set and are not evaluated.
* For shor_16 and add_65 the best-classical T-count is a reference count only: that output itself exceeds the
  1e-6 budget (1.52e-6 / 1.42e-6).
* pyzx and TKET columns use the evaluator's definition (min of raw and canonical T).
  - The phase-0 values in reference_pipelines.csv differ slightly on three entries: mult_16 pyzx 32,738,
    shor_16 pyzx 141,327 and shor_16 TKET 325,074. The cause is raw-angle counting and a different TKET
    post-processing.
  - The best pipeline (pyzx or TKET) is the same in both on every circuit.
* By Gate (reproduced) for add_41 / add_65 was computed by `experiments/evolve_opt_eval_bygate.py`. It calls
  the phase-0 `run_bygate_exact.run_one(paramzsx)` unchanged, and its add_17 cross-check gives 23,520, the same
  as table3_bygate.csv.

**Geomean T / T(best classical)** (from eval_summary.json)

| program | 5 circuits valid for all (add_17, hhl_6, mult_16, qft_32, add_41) | 3 numerically verified (add_17, hhl_6, mult_16) |
|---|---|---|
| best-classical program | 1.00000 | 1.00000 |
| seed program | 0.98349 | 0.97264 |
| control greedy s2 | 0.94191 | 0.90507 |
| LLM v1 (seed 0) | 0.94191 | 0.90507 |
| LLM v2 (seed 2) | 0.95308 | 0.92303 |

## Per-run detail (final limit per circuit)

**Error bound.** For n ≤ 10, the bound is max(d_unitary, ledger) + #RZ × 1e-9. For n > 10 it is
ledger + 1e-8 + #RZ × 1e-9.

**Check distance.** For n ≤ 10 it is the phase-aligned operator-norm distance. For 10 < n ≤ 20 it is the
maximum over four Haar states of the phase-aligned vector distance, which is a lower bound on the operator
distance.

**Rows marked "none: NOT verified" (n > 20) were not checked against the original circuit.**

| circuit | program | valid | T | RZ | error bound | check method | check distance | charged CPU (s) | % vs best classical | % vs published 3Q |
|---|---|---|---|---|---|---|---|---|---|---|
| add_17 | best_classical_program | yes | 10,508 | 112 | 1.220e-07 | statevector | 7.7e-12 | 2.9 | 0.0 | -47.23 |
| add_17 | seed_program | yes | 10,508 | 112 | 1.220e-07 | statevector | 7.7e-12 | 2.9 | 0.0 | -47.23 |
| add_17 | control_greedy_s2 | yes | 10,508 | 112 | 1.220e-07 | statevector | 7.7e-12 | 11.9 | 0.0 | -47.23 |
| add_17 | llm_v1_s0 | yes | 10,508 | 112 | 1.220e-07 | statevector | 7.5e-12 | 17.8 | 0.0 | -47.23 |
| add_17 | llm_v2_s2 | yes | 10,508 | 112 | 1.220e-07 | statevector | 7.7e-12 | 14.4 | 0.0 | -47.23 |
| hhl_6 | best_classical_program | yes | 8,352 | 89 | 8.900e-08 | unitary | 2.6e-14 | 5.6 | 0.0 | -62.49 |
| hhl_6 | seed_program | yes | 7,685 | 82 | 8.200e-08 | unitary | 2.8e-14 | 6.6 | -7.99 | -65.48 |
| hhl_6 | control_greedy_s2 | yes | 6,192 | 66 | 6.608e-08 | unitary | 7.6e-11 | 23.3 | -25.86 | -72.19 |
| hhl_6 | llm_v1_s0 | yes | 6,192 | 66 | 6.606e-08 | unitary | 6.1e-11 | 35.6 | -25.86 | -72.19 |
| hhl_6 | llm_v2_s2 | yes | 6,568 | 70 | 7.006e-08 | unitary | 6.2e-11 | 32.4 | -21.36 | -70.5 |
| mult_16 | best_classical_program | yes | 32,617 | 349 | 3.590e-07 | statevector | 1.4e-11 | 25.9 | 0.0 | -60.46 |
| mult_16 | seed_program | yes | 32,617 | 349 | 3.590e-07 | statevector | 1.4e-11 | 28.9 | 0.0 | -60.46 |
| mult_16 | control_greedy_s2 | yes | 32,617 | 349 | 3.590e-07 | statevector | 1.4e-11 | 52.7 | 0.0 | -60.46 |
| mult_16 | llm_v1_s0 | yes | 32,617 | 349 | 3.590e-07 | statevector | 1.7e-11 | 76.0 | 0.0 | -60.46 |
| mult_16 | llm_v2_s2 | yes | 32,617 | 349 | 3.590e-07 | statevector | 1.5e-11 | 78.1 | 0.0 | -60.46 |
| qft_32 | best_classical_program | yes | 44,167 | 470 | 4.800e-07 | none: NOT verified | – | 37.6 | 0.0 | -49.38 |
| qft_32 | seed_program | yes | 44,167 | 470 | 4.800e-07 | none: NOT verified | – | 37.8 | 0.0 | -49.38 |
| qft_32 | control_greedy_s2 | yes | 44,167 | 470 | 4.800e-07 | none: NOT verified | – | 126.7 | 0.0 | -49.38 |
| qft_32 | llm_v1_s0 | yes | 44,167 | 470 | 4.800e-07 | none: NOT verified | – | 113.5 | 0.0 | -49.38 |
| qft_32 | llm_v2_s2 | yes | 44,167 | 470 | 4.800e-07 | none: NOT verified | – | 105.5 | 0.0 | -49.38 |
| shor_16 | best_classical_program | no | 140,843 | 1,508 | 1.518e-06 | statevector | 2.6e-11 | 354.4 | – | – |
| shor_16 | seed_program | no | 140,843 | 1,508 | 1.518e-06 | statevector | 2.6e-11 | 356.2 | – | – |
| shor_16 | control_greedy_s2 | no | 140,843 | 1,508 | 1.518e-06 | statevector | 2.6e-11 | 1798.2 | – | – |
| shor_16 | llm_v1_s0 | no | – | – | – | – | – | – | – | – |
| shor_16 | llm_v2_s2 | no | – | – | – | – | – | – | – | – |
| add_41 | best_classical_program | yes | 60,468 | 646 | 6.560e-07 | none: NOT verified | – | 80.2 | 0.0 | – |
| add_41 | seed_program | yes | 60,468 | 646 | 6.560e-07 | none: NOT verified | – | 80.7 | 0.0 | – |
| add_41 | control_greedy_s2 | yes | 60,468 | 646 | 6.560e-07 | none: NOT verified | – | 428.1 | 0.0 | – |
| add_41 | llm_v1_s0 | yes | 60,468 | 646 | 6.560e-07 | none: NOT verified | – | 385.4 | 0.0 | – |
| add_41 | llm_v2_s2 | yes | 60,468 | 646 | 6.560e-07 | none: NOT verified | – | 210.8 | 0.0 | – |
| add_65 | best_classical_program | no | 132,728 | 1,414 | 1.424e-06 | none: NOT verified | – | 412.8 | – | – |
| add_65 | seed_program | no | 132,728 | 1,414 | 1.424e-06 | none: NOT verified | – | 415.3 | – | – |
| add_65 | control_greedy_s2 | no | – | – | – | – | – | – | – | – |
| add_65 | llm_v1_s0 | no | – | – | – | – | – | – | – | – |
| add_65 | llm_v2_s2 | no | – | – | – | – | – | – | – | – |

On the numerically verified circuits the largest whole-circuit check distance over valid outputs is
7.6e-11 (hhl_6, control). The largest error bound among valid outputs is
6.56e-07 (add_41, not numerically verified). The largest bound among numerically
verified valid outputs is 3.59e-07 (mult_16).

### Earlier-limit runs (superseded by the raised limit; kept for the record)

| circuit | limit (s) | program | outcome |
|---|---|---|---|
| shor_16 | 300 | seed_program | failed: BudgetError: time budget exceeded (348.3 s > 300 s charged CPU) line 7 |
| shor_16 | 300 | best_classical_program | failed: BudgetError: time budget exceeded (349.4 s > 300 s charged CPU) line 3 |
| shor_16 | 300 | llm_v2_s2 | failed: BudgetError: time budget exceeded (347.7 s > 300 s charged CPU) line 8 |
| shor_16 | 300 | llm_v1_s0 | failed: BudgetError: time budget exceeded (350.5 s > 300 s charged CPU) line 8 |
| shor_16 | 300 | control_greedy_s2 | failed: BudgetError: time budget exceeded (354.3 s > 300 s charged CPU) line 14 |
| add_41 | 300 | seed_program | valid, T 60,468 |
| add_41 | 300 | best_classical_program | valid, T 60,468 |
| add_41 | 300 | llm_v2_s2 | valid, T 60,468 |
| add_41 | 300 | llm_v1_s0 | failed: BudgetError: time budget exceeded (301.6 s > 300 s charged CPU) line 23 |
| add_41 | 300 | control_greedy_s2 | failed: wall-time limit exceeded (690 s) |
| add_65 | 300 | seed_program | failed: wall-time limit exceeded (690 s) |
| add_65 | 300 | best_classical_program | failed: wall-time limit exceeded (690 s) |
| add_65 | 300 | llm_v2_s2 | failed: wall-time limit exceeded (690 s) |
| add_65 | 300 | llm_v1_s0 | failed: wall-time limit exceeded (690 s) |
| add_65 | 300 | control_greedy_s2 | failed: wall-time limit exceeded (690 s) |

## LLM cost (from the run summaries; the evaluation itself used no LLM calls)

| run | proposer calls | reflector calls | total calls | input tokens | output tokens | run wall (s) |
|---|---|---|---|---|---|---|
| evo_s0_v3_120 | 120 | 7 | 127 | 633,494 | 95,217 | 3,165.1 |
| evo_s1_v3_120 | 120 | 7 | 127 | 544,082 | 76,790 | 1,929.8 |
| evo_s2_v3_120 | 120 | 7 | 127 | 559,287 | 97,256 | 6,729.2 |
| **total, 3 seeds** | 360 | 21 | 381 | 1,736,863 | 269,263 | 11,824.1 |
| invalidated pilot evo_s0_120 (reported separately, not part of any comparison) | 120 | 7 | 127 | 565,236 | 85,435 | 2,494.8 |
| live smoke smoke_live_8 (not part of any comparison) | 8 | 1 | 9 | 23,376 | 4,913 | 155.2 |

* Model: `host.reasoning_model()` via make_api_backend, thinking off (DEV_REPORT).
* "Run wall" is the whole evolution run, including program evaluation, not LLM time alone.
* Reflector calls are counted as LLM calls (CLAUDE.md invariant 7).
* The six classical control runs used 0 LLM calls. Each used 121 program evaluations, matched to the ~120 per
  LLM seed.
* For the same program-evaluation budget, the LLM arm cost 381 calls and
  2,006,126 tokens. On evaluation it reached at best a tie with a
  zero-LLM control.

## Reading

1. **Evaluation confirms the development result.** On dev every LLM seed was slightly worse than every control
   run. On evaluation, the dev-selected LLM champion (v2) is worse than the control on the only circuit that
   moves (hhl_6), and v1 ties it. The dev ranking v2 < v1 (0.97000 vs 0.97027) did not hold on evaluation, which
   is consistent with that 0.03 % difference being noise.
2. **All gains come from one mechanism on one kind of circuit.** The gain on hhl_6 comes from alternating ZX /
   TKET rewriting with phase folding, the same mechanism behind hhl_8 and qpe_8 on dev. The control's pass
   sequence finds it as well as the LLM programs do.
   - On the arithmetic circuits (add, mult) and the QFT, pyzx full_reduce already sets the floor and no program
     goes below it.
   - The adder family, held out to test transfer, shows no gain from any program.
3. **Robustness on larger inputs favours the control.** The LLM programs begin with a long unguarded prefix
   (pyzx, TKET, teleport_reduce, several folds, pyzx of the TKET output) before any `time_left()` check.
   - On shor_16 and add_65 this prefix alone runs past the limit (BudgetError or wall limit).
   - LLM v2 also calls block_optimize without checking `error_left()`. On add_65 this raised an uncaught
     BudgetError, because the RZ count had already used up the budget.
   - The control program wraps every step in try/except. It returns the best circuit so far. On shor_16 its
     output was still rejected for its error bound.
4. **Comparison with BQSKit.** The published Table-3 BQSKit T-counts are 1.9–2.7× (3Q blocks) and 2.1–3.1× (By Gate and
   2Q rows) the best-classical T-counts on the like-for-like circuits.
   - BQSKit's By Gate / 2Q / 3Q flows start from the gate-level U3 structure. pyzx's ZX rewriting removes most of
     the rotations before synthesis. The comparison therefore mainly measures pyzx against block resynthesis, not
     the evolved programs.
   - The two comparisons of evolved programs that are actually informative are the ones against best classical
     and against the classical control. Neither shows an LLM advantage.

## Issues and caveats

1. **Error budget versus large circuits.** shor_16 (best classical 1,508 RZ) and add_65 (1,414 RZ) cannot be
   compiled within 1e-6 at eps_rz = 1e-9 without removing rotations first. The fixed eps_rz is a protocol choice
   kept from development: it prevents gains from re-splitting the budget. None of the programs uses approx_round
   or re-allocates budget. These two rows therefore give no information about the programs other than the
   failures themselves.
2. **Not numerically verified: qft_32, add_41, add_65.** Their validity rests on error accounting only, as
   described in the Verdict and Protocol sections.
3. **The time limit is not enforced on outputs.** The control returned an output on shor_16 with 1,798 s of
   charged CPU at a 1,200 s limit. Its generated program catches the BudgetError raised inside a tool call
   (`except Exception`), and the parent does not compare charged_s with time_s.
   - The same holds in development.
   - It does not affect any verdict here: that output was rejected for its error bound.
4. **Shared machine.** Wall-time limits were reached sooner because a parallel sub-agent was running and up to
   10 evaluations ran at once. Raising the limits identically for every program removed every time failure of
   the seed and best-classical programs. The remaining time failures are the LLM programs and the control on
   shor_16 / add_65.
5. **Seeds and statistics.** There is one frozen program per arm, and the programs are deterministic. The
   comparison involves 2 LLM programs, 1 control and 1 changing circuit, so no confidence interval is possible.
   The equality on 4 of 5 valid circuits is exact, not statistical.
6. **Development guards.** `circuit_io.bench_path` and `evaluate.check_dev` still refuse the evaluation circuits.
   They were lifted only inside the evaluation runner's process.

## Next steps

1. Re-weight the development split toward circuits where the floor is not set by pyzx (hhl, qpe, rotation-heavy
   simulation circuits). On the arithmetic and QFT circuits there is nothing to find with this toolbox.
2. Make budget re-allocation (approx_round, rotation merging below eps) part of the search space, or report
   shor_16 / add_65 at a budget where best classical is valid. Either change must be applied identically to every
   arm and recorded as a protocol change.
3. Give LLM proposals the control's robustness by construction, through a wrapper or a playbook rule: guard every
   step with try/except and `time_left()` / `error_left()`.
4. Enforce charged_s ≤ time_s in the parent. This needs an evaluator version bump, CHANGELOG and tests.
5. Add a scalable whole-circuit check for n > 20, for example a per-qubit light-cone or tensor-network
   equivalence check, before claiming anything about qft_32 / add_* beyond error accounting.

## Files

* `results/evolve_opt/eval_table.csv`: one row per circuit, all methods.
* `results/evolve_opt/eval_table_long.csv`: one row per run, including the earlier-limit rows.
* `results/evolve_opt/eval_summary.json`: geomeans and LLM cost.
* `results/evolve_opt/eval_comparison.png`: the figure.
* `results/evolve_opt/eval/`: runs.jsonl, the logs, baseline_eval.json, bygate_adders.json, and the output
  circuits (outputs/*.json.gz).
* `experiments/evolve_opt_eval.py`, `experiments/evolve_opt_eval_bygate.py`, `experiments/evolve_opt_eval_report.py`.
