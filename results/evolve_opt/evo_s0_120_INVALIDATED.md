# evo_s0_120 — invalidated pilot run (evaluator bug), kept for the record

Run 2026-10-11 20:06-20:47 with eval cache version ev-v2. During this run the parent verified outputs in
one thread while other evaluation threads were spawning sandbox subprocesses. On this machine, forking a
subprocess while another thread runs numpy linear algebra corrupts the numpy result in the parent
(.cache/evolve_opt/rep3.py: 30/30 wrong distances with concurrent Popen, 0/30 without, 0/30 with the lock).
Consequence: some VALID programs were judged invalid (distances 1.0-1.9 reported for circuits that verify at
~1e-15 when re-checked). The reverse error (a wrong output judged valid) was not observed but cannot be
excluded for this run.

Post-hoc re-verification (`evo_s0_120_reverify.jsonl`, stopped after the first 20 unique programs to free
CPU): 8 of 20 programs had a flipped verdict (calls 1, 2, 4, 8, 9, 12, 17, 19), all invalid -> valid, none
valid -> invalid (the seed program itself was judged valid in the run and on re-check).

Fix: sandbox.NUMERIC_LOCK held around Popen and around parent-side verification; eval cache version ev-v3
(regression tests `test_spawning_does_not_corrupt_verification`, `test_parallel_evaluation_matches_serial`).
The run's numbers (best dev 0.96182 at call 103; 127 LLM calls, 565,236 input / 85,435 output tokens) are
NOT used in DEV_REPORT.md comparisons. Seed 0 was re-run with the fixed evaluator as `evo_s0_v3_120`.
