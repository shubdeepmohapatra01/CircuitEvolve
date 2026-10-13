# P5 adder statistics: Cuccaro seed, tier B, 3 seeds per arm

*2026-10-11. Row `cuccaro_B` (naive Cuccaro seed, 14n T; tier-B gate vocabulary: Clifford+T, CCX,
measurement with classical control; no AND gadgets). Proposer: the platform's Sonnet-class reasoning
model (`host.reasoning_model()`), thinking disabled, max_tokens 8000, in-platform API backend
(`make_api_backend`), prompt with the new output-format paragraph (`format_rules=True`). k = 4 programs
per call, batch = 4 calls, 60 LLM calls per run, rng_seed 0, 1, 2. Exact verifier unchanged (digest
`60f4fe547646b2ca` in every run). Machine-readable table: `results/P5_adder_stats.csv`; per-run logs
and summaries: `results/llm_runs/cuccaro_B_*_s{0,1,2}_*`.*

## Arms

1. **(i) LLM evo + repair 300**: archive + verifier feedback; each rejected LLM proposal gets up to 300
   random local mutants (the P4 hybrid).
2. **(ii) LLM evo, no repair**: same, `repair_budget = 0`.
3. **(iii) classical MAP-Elites** (P3 operator set, unchanged) with the evaluation budget set to the final
   unique-evaluation count of the arm-(i) run with the same seed (15955 / 16461 / 29805).
4. **(iv) repair-only control** at the same matched evaluation budgets: the arm-(i) loop with the LLM
   replaced by random proposals (each a 2–8-step random mutation of an archive member, parents chosen as
   in llm_search: 50% best, 50% uniform), each rejected proposal followed by the same 300-step repair.
   Proposals of this kind (rather than random templates from scratch) were chosen because random
   templates of seed size essentially never verify, which would make the control trivially weak.

No arm was cut. All 360 step-3 LLM calls returned text (0 errors, 0 retries; 13 responses hit
max_tokens and were parsed as returned).

## Results

| Arm | Seed | Best T/bit | T at n=8 | Qubits n=8 | LLM calls | Evals (unique) | Calls to best | Evals to best | Raw pass rate | Repair success | Parse errors |
|---|---|---|---|---|---|---|---|---|---|---|---|
| (i) LLM evo + repair 300 | 0 | **7** | 56 | 26 | 60 | 15955 | 16 | 7121 | 7.8% | 16.9% | 3 |
| (i) LLM evo + repair 300 | 1 | **12** | 96 | 18 | 60 | 16461 | 28 | 10210 | 5.9% | 5.1% | 2 |
| (i) LLM evo + repair 300 | 2 | **14** | 112 | 18 | 60 | 29805 | — | — (seed) | 0.7% | 2.2% | 2 |
| (ii) LLM evo, no repair | 0 | **8** | 64 | 26 | 60 | 91 | 8 | 18 | 5.6% | n/a | 1 |
| (ii) LLM evo, no repair | 1 | **14** | 112 | 18 | 60 | 149 | — | — (seed) | 0.7% | n/a | 2 |
| (ii) LLM evo, no repair | 2 | **14** | 112 | 18 | 60 | 98 | — | — (seed) | 1.0% | n/a | 3 |
| (iii) classical MAP-Elites, matched evals | 0 | **14** | 112 | 18 | 0 | 15955 | — | — (seed) | 35.1% | n/a | n/a |
| (iii) classical MAP-Elites, matched evals | 1 | **14** | 112 | 18 | 0 | 16461 | — | — (seed) | 32.8% | n/a | n/a |
| (iii) classical MAP-Elites, matched evals | 2 | **14** | 112 | 18 | 0 | 29805 | — | — (seed) | 37.0% | n/a | n/a |
| (iv) repair-only control, matched evals | 0 | **14** | 112 | 18 | 0 | 15955 | — | — (seed) | 4.2% | 7.6% | n/a |
| (iv) repair-only control, matched evals | 1 | **14** | 112 | 18 | 0 | 16461 | — | — (seed) | 1.0% | 9.3% | n/a |
| (iv) repair-only control, matched evals | 2 | **14** | 112 | 18 | 0 | 29805 | — | — (seed) | 1.8% | 5.4% | n/a |

"Raw pass rate" = fraction of new (non-duplicate) proposals that verified before any repair; for
arm (iii) it is the fraction of unique mutants that verified (a different quantity: one-edit mutants of
accepted programs). "Repair success" = fraction of rejected proposals that the 300-step repair turned
into a verifying program. "Evals to best" counts unique verifier evaluations, including repair.

Summary by arm (best T/bit over seeds 0/1/2):

| Arm | Seeds below 14n | Best T/bit per seed | LLM calls | Evals per run |
|---|---|---|---|---|
| (i) LLM evo + repair 300 | 2/3 | 7, 12, 14 | 60 | 15955–29805 |
| (ii) LLM evo, no repair | 1/3 | 8, 14, 14 | 60 | 91–149 |
| (iii) classical, matched evals | 0/3 | 14, 14, 14 | 0 | matched to (i) |
| (iv) repair-only, matched evals | 0/3 | 14, 14, 14 | 0 | matched to (i) |

## Reading

1. **No run reached 4n in 60 calls.** The P4 pilot's 4n (single seed, 120 calls, batch 6, 4n at call 54)
   is therefore not reproduced at this budget; its 8n step came at call 36. The pilot remains a single
   observation. Whether 120 calls would reach 4n in these seeds is untested (the per-session model-token
   allowance, ~2M tokens, was nearly used by this experiment: 1.79M tokens for the 360 step-3 calls).
2. **LLM arms improve on the seed; the controls do not.** 3 of 6 LLM runs went below 14n (7, 12, 8);
   0 of 6 non-LLM runs did at matched evaluations (classical and repair-only both flat at 14n,
   consistent with P3). One-sided Fisher exact test, LLM (6 runs) vs controls (6 runs): p = 0.091;
   arm (i) vs arm (iv): p = 0.20. With 3 seeds per arm this is suggestive, not significant.
3. **Repair is not sufficient on its own.** Arm (iv) spends the same evaluations on the same repair
   procedure, with a similar repair success rate (5–9% vs 2–17% in arm (i)), and never leaves 14n. So
   the improvements in arm (i) depend on the LLM proposals, not on the repair budget alone.
4. **Repair helps, but the evidence is thin.** Arm (i) s0's 7n program was a repaired LLM proposal
   (call 16); arm (i) s1's 12n program was a raw LLM proposal that verified without repair (call 28, checked by
   re-evaluating that response); arm (ii) s0 reached 8n without any repair (call 8). The difference
   between (i) and (ii) (2/3 vs 1/3 seeds improved) is within seed-to-seed noise at n = 3.
5. **Variance between seeds is large.** Within one arm the best result ranged from 7n to 14n; one
   arm-(i) seed (s2) never improved despite the largest evaluation count (29805: more rejected
   proposals, hence more repair). Single-seed comparisons from earlier phases should be read with this
   in mind.
6. **Parse failures are no longer a factor.** 2–3 parse errors per 60-call run (≤ 0.05 per call) with the
   new prompt and parser; non-program blocks (hand traces) are skipped and counted separately.

## Caveats

* Batch size 4 here vs 6 in the P4 pilot, and the prompt now has the output-format paragraph; both
  change the trajectory relative to the pilot, so the pilot run is not a fourth seed of arm (i).
* The three seeds run concurrently and share host round-trips (requests merged into one batch); each
  run's RNG stream and prompts are its own, but model sampling is not seeded, so LLM runs are not
  bit-reproducible.
* Matched budgets are matched in unique verifier evaluations, not wall time or LLM cost; arms (i)/(ii)
  additionally used 60 LLM calls (0.28–0.32M tokens) per run.
