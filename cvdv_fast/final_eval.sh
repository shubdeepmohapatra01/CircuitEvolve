#!/bin/bash
# Frozen-book final evaluation: hash check, then book (seeds + accepted) on all 5 benchmarks with whole-circuit check.
cd "$(dirname "$0")/.."
export PYTHONHASHSEED=0
PY=~/.claude-science/conda/envs/cvdv-opt/bin/python
(cd cvdv_fast && shasum -a 256 -c judge/FROZEN.sha256) || { echo "FROZEN CHECK FAILED"; exit 1; }
rm -rf cvdv_fast/results/final
for b in kerr_small boseHubbard_small z2Higgs_small heisenberg_small electronicVibration_small; do
  ( $PY cvdv_fast/run_book.py final $b > cvdv_fast/results/final_$b.log 2>&1 ) &
done; wait
grep -h -v -i warn cvdv_fast/results/final_*.log
