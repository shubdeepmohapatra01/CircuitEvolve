#!/usr/bin/env bash
# Genesis and our compiler (both ISAs) on the small benchmarks under PYTHONHASHSEED = 0..7.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; cd "$HERE"; mkdir -p results/isa_sweep
B="kerr_small boseHubbard_small z2Higgs_small heisenberg_small electronicVibration_small"
for h in 0 1 2 3 4 5 6 7; do
  PYTHONHASHSEED=$h OUT=isa_sweep/genesis_hs$h SEED=0 ./scripts/run_genesis_batch.sh $B > /dev/null 2>&1
done
for h in 0 1 2 3 4 5 6 7; do
  PYTHONHASHSEED=$h python experiments/compare_isas.py results/isa_sweep/hs$h.csv results/isa_sweep/genesis_hs$h > results/isa_sweep/hs$h.log 2>&1 &
done
wait
python - <<'PY'
import glob, pandas as pd
df = pd.concat([pd.read_csv(f) for f in sorted(glob.glob("results/isa_sweep/hs*.csv"))])
df.to_csv("results/compare_isas_small_nmax3.csv", index=False)
print(df.groupby(["benchmark", "compiler", "isa"])[["total", "two_op", "duration"]].agg(["median", "min", "max"]).to_string())
PY
