"""T-count under the BQSKit convention (circuitevolve/core/metric.BqskitTMetric, eps_synth = eps total) for the
saved baseline circuits that still contain rotations that are not multiples of pi/4 (TKET FullPeepholeOptimise can
emit such angles even on exact Clifford+T input). Writes results/v2/rotations_gridsynth_<tag>.json.

    .venv/bin/python experiments/v2_bench_gridsynth.py results/v2/bench_runs/run2 [eps=1e-3]
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_bench_common import ROOT, counts, read_qasm  # noqa: E402

from circuitevolve.core.metric import BqskitTMetric  # noqa: E402


def main(run_dir, eps="1e-3"):
    eps = float(eps)
    tag = os.path.basename(os.path.normpath(run_dir))
    out = os.path.join(ROOT, "results", "v2", f"rotations_gridsynth_{tag}_eps{eps:g}.json")
    if os.path.exists(out):
        raise SystemExit(f"{out} exists")
    m = BqskitTMetric(eps)
    res = {}
    for p in sorted(glob.glob(os.path.join(run_dir, "circuits", "*.qasm"))):
        n, ops = read_qasm(p)
        c = counts(ops)
        if c["rz_other"] == 0:
            continue
        cost = m.cost(ops)
        key = os.path.basename(p)[:-5]
        res[key] = dict(eps_total=eps, rz_other=c["rz_other"], t_pi4=c["t"], **{k: cost[k] for k in cost})
        print(key, res[key], flush=True)
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:])
