"""optimize() B0 identity (PLAN_P1 P1.4): the routed, no-domain-named entry point with zero
accepted rewrites reproduces B0's t_count_canon exactly — same gate as test_core_stage1, now
through router + engine."""
from __future__ import annotations

import csv

import pytest

from circuitevolve.blocks import REPO
from circuitevolve.engine.run import optimize

EPS = 1e-3
B0_CSV = REPO / "results" / "bqskit_baselines" / "stage1" / "stage1_baselines_v2.csv"


def _nones():
    return lambda prompts: ["NONE"] * len(prompts)


@pytest.mark.parametrize("name", ["qft_8", "tfim_6"])
def test_optimize_zero_accepts_equals_b0(name, tmp_path):
    rows = {(r["circuit"], float(r["eps_total"]), r["arm"]): r for r in csv.DictReader(B0_CSV.open())}
    b0 = int(rows[(name, EPS, "B0")]["t_count_canon"])
    s = optimize(name, EPS, _nones(), runs_dir=tmp_path, n_calls=1, batch=1)
    assert s["routing"]["family"] == "dv.windows" and s["routing"]["contract"] == "approx"
    assert s["stats"]["accepted"] == 0
    assert s["t_before"] == s["t_after"] == b0
    assert s["ledger"]["bound"] <= EPS
    assert s["final_check_vs_original"]["ok"]
