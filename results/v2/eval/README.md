# results/v2/eval - held-out evaluation (append-only)

* `EVAL_REPORT.md` - report (verdict, tables A/B, figure, DEV summary of both tiers, runtime, caveats).
* `eval_results.csv` - one row per held-out circuit x arm x mode (+ `best_classical_ours`, `best_published`,
  `skipped`, `blocked` rows); written by `experiments/v2_eval_report.py` from `per_circuit/`.
* `eval_figure.png` - T / best classical per circuit (`experiments/v2_eval_figure.py`).
* `per_circuit/eval_v1_<c>.json` - raw record per circuit (freeze check, normalization check, baseline bars, all 8
  control evaluations, tier-2 start-circuit selection, every arm with verdict, re-seeded checks, timings).
  For qcla_adder_10 / qcla_com_7 the raw `error` text says "normalization not equivalent"; the verdict method is
  `infeasible` (the check could not be run), not a refutation - see EVAL_REPORT.md.
* `logs/eval_v1_<c>_control.jsonl` - one line per control evaluation.
* `circuits/eval_v1_<c>__<arm>_<mode>.qasm` - every verified output (tier-1: OpenQASM 3 with gadgets expanded;
  tier-2: OpenQASM 2 Clifford+T).
* `run_logs/` - stdout of each circuit process and start/finish timestamps.
