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
    """graduated='off': the engine path reproduces B0 exactly (the P1.4 gate, unchanged)."""
    rows = {(r["circuit"], float(r["eps_total"]), r["arm"]): r for r in csv.DictReader(B0_CSV.open())}
    b0 = int(rows[(name, EPS, "B0")]["t_count_canon"])
    s = optimize(name, EPS, _nones(), runs_dir=tmp_path, n_calls=1, batch=1, graduated="off")
    assert s["routing"]["family"] == "dv.windows" and s["routing"]["contract"] == "approx"
    assert s["stats"]["accepted"] == 0
    assert s["t_before"] == s["t_after"] == b0
    assert s["ledger"]["bound"] <= EPS
    assert s["final_check_vs_original"]["ok"]
    assert s["pre_opt"] is None


@pytest.mark.parametrize("name", ["qft_8", "tfim_6"])
def test_optimize_graduated_on_matches_replay_record(name, tmp_path):
    """graduated='on' (default): zero accepts reproduce the freeze-time replay EXACTLY —
    deterministic pass gains, reported in their own pre_opt section (never as LLM gains)."""
    import json
    rec = json.loads((REPO / "results" / "engine" / "graduation_pmerge.json").read_text())
    row = next(r for r in rec["rows"] if r["name"] == name)
    s = optimize(name, EPS, _nones(), runs_dir=tmp_path, n_calls=1, batch=1)
    assert s["stats"]["accepted"] == 0
    assert s["t_before"] == s["t_after"] == row["t_after"]
    assert s["pre_opt"]["reports"][0]["merges"] == row["merges"]
    assert s["ledger"]["bound"] <= EPS
    assert s["final_check_vs_original"]["ok"]
