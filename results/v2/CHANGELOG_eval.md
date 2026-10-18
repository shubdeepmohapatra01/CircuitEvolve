# CHANGELOG - v2 evaluation track

## 2026-10-14 - held-out evaluation `eval_v1` (no LLM arms, by user decision)

- Added `experiments/v2_eval_heldout.py`, `experiments/v2_eval_report.py`, `experiments/v2_eval_figure.py`,
  `docs/v2/EVAL.md`, `results/v2/eval/` (EVAL_REPORT.md, eval_results.csv, eval_figure.png, README.md, per_circuit/,
  logs/, circuits/, run_logs/). No existing file edited; tier-1/tier-2 code untouched.
- Freeze check before every circuit: 21 FROZEN.md hashes equal, verifier digest bc3eac23... unchanged before/after,
  tier-2 libraries v0 (0 rules, 4f53cda1...) and lex-secondary control (30 rules, 4bef8a90...) re-verified.
- 22 held-out circuits: 18 evaluated; shor_14/shor_16 skipped (no rotation route in tier1-toolbox-v1);
  qcla_adder_10/qcla_com_7 blocked (recognizer normalization leaves unfused h/ccz -> exact check infeasible for n > 14).
- Results: tier-1 control exact = best classical (our runs) on 17/18, worse on gf2^16_mult (pyzx-pass plans timed out
  in verification). Tier-2 v0: T unchanged everywhere (0 applications); lex-secondary: T unchanged, -361 / 17531 gates
  on classical starts, -1338 / 26671 on tier-1 exact outputs. Tier-1 control relaxed (Gidney temporary AND, Jones
  Toffoli, clean AND; always variant V2 + pyzx): below best classical on 15/18 (total 4968 vs 5728 T), at +1..+16 qubits
  and 9..241 measurements. LLM tokens used: 0.
- Full test suite after the run: 295 passed.
