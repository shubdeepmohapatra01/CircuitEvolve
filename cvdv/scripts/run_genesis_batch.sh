#!/usr/bin/env bash
# Run Genesis on the Table-5 benchmarks (one process each, in parallel), --stats on.
# Output: results/genesis_baseline/<name>/{*.cvdvqasm, stats.json, log.txt}
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; G="$HERE/third_party/genesis"
NAMES="${*:-kerr_1 heisenberg_1 heisenberg_2 heisenberg_3 boseHubbard_1 boseHubbard_2 boseHubbard_3 z2Higgs_1 z2Higgs_2 z2Higgs_3 electronicVibration_1 electronicVibration_2 electronicVibration_3 hubbardHolstein_1 kerr_small heisenberg_small boseHubbard_small z2Higgs_small electronicVibration_small hubbardHolstein_small}"
for n in $NAMES; do
  (
    W="$HERE/results/${OUT:-genesis_baseline}/$n"; mkdir -p "$W"; WD="$(mktemp -d)"
    cp -R "$G"/src "$G"/generated "$WD"/; cp "$HERE/scripts/run_genesis.py" "$WD"/; mkdir -p "$WD/benchmark" "$WD/output"
    cp "$G/benchmark/$n.ham" "$WD/benchmark/"
    printf '[{"input_file":"benchmark/%s.ham","output_file":"output/%s.cvdvqasm"}]' "$n" "$n" > "$WD/job.json"
    START=$(date +%s)
    (cd "$WD" && python run_genesis.py --batch-json job.json --stats --seed ${SEED:-0} > "$W/log.txt" 2>&1)
    echo "exit=$? wall_s=$(( $(date +%s) - START ))" >> "$W/log.txt"
    cp "$WD"/output/*.cvdvqasm "$WD"/output/*.mapping.json "$W"/ 2>/dev/null; cp "$WD"/compilation_stats_*.json "$W/stats.json" 2>/dev/null
    rm -rf "$WD"; echo "done $n"
  ) &
done
wait
