#!/bin/bash
# Final Table-3 By-Gate runs (append-only: each tag writes a new CSV under results/bqskit_baselines/table3/)
set -e
cd "$(dirname "$0")"
PY=.venv/bin/python
W=../../results/bqskit_baselines/work
$PY make_aqft.py 32 17
$PY run_bygate_exact.py --method paramzsx --tag table3/paramzsx_qseed
$PY run_bygate_exact.py --method paramzsx --tag table3/paramzsx_aqft32_d17 --circuits $W/aqft32_d17_u3cx.qasm
$PY run_bygate_exact.py --method minrz --tag table3/minrz_qseed
$PY run_bygate_exact.py --method minrz --tag table3/minrz_aqft32_d17 --circuits $W/aqft32_d17_u3cx.qasm
$PY shor_param_convention.py shor/shor_16 > ../../results/bqskit_baselines/table3/shor16_param_convention.json
for s in 0 1 2; do
  $PY run_table3.py --workflow shipped --seed $s --tag table3/bqskitft_shipped_seed$s
done
