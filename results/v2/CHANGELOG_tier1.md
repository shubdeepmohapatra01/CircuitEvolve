# CHANGELOG - v2 tier 1 (compilation strategy)

## 2026-10-14 - tier 1 v1: recognizer, plan format, compiler, dev run `dev_v1`

- Added `circuitevolve/v2/tier1/` (recognize, plan, compile, control, prompt, loop), `experiments/v2_tier1_dev.py`,
  `experiments/v2_tier1_report.py`, `tests/v2/test_tier1.py` (25 tests), `docs/v2/TIER1.md`. No existing file edited;
  frozen verifier digest unchanged before/after the run. Full suite: 295 passed.
- Dev run `dev_v1` (16 DEV circuits; shor_12 skipped: rotation-dominated, no rotation route, no comparable baseline):
  8 LLM calls per circuit (128 calls, 905,089 input + 58,206 output tokens), control at the same evaluation budget.
  Result: LLM never beats the control (exact 16 equal; relaxed 13 equal, 2 worse, 1 no valid plan). Relaxed
  constructions beat the best classical exact T on 10/16 circuits (both arms). Outputs in `results/v2/tier1/`
  (DEV_REPORT.md, dev_results.csv, dev_v1_*.csv/json, logs/, plans/, circuits/, summaries/, FROZEN.md).
