"""P3.2 gates: cascade execution through optimize() — pure-Clifford pass-through (b),
cuccaro_4 raw cascade routing (c), predicate evidence in the log (d is in test_router),
TKET entry pass inside the angle method only (§1.3), reserved-method execution refusal."""
from __future__ import annotations

import pytest

from circuitevolve.blocks import REPO
from circuitevolve.engine.run import optimize

CLIFFORD = 'OPENQASM 2.0;\nqreg q[2];\nh q[0];\ncx q[0],q[1];\ns q[1];\n'
CUCCARO_4 = str(REPO / "benchmarks" / "nam_arith" / "generated" / "cuccaro_4.qasm")

# 1 ccx among 29 t gates: naive-T share 7/36 < 0.2, no pair, no MCX -> reconstruction does
# NOT fire; angle fires (non-Clifford content) and must decompose the Toffoli at its door.
MIXED_LOW_SHARE = ("OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[4];\n"
                   "ccx q[0],q[1],q[2];\n" + "".join(f"t q[{i % 4}];\n" for i in range(29)))


def _nones():
    return lambda prompts: ["NONE"] * len(prompts)


def test_pure_clifford_returns_input_unchanged(tmp_path):
    s = optimize(CLIFFORD, 1e-3, _nones(), runs_dir=tmp_path, n_calls=1, batch=1)
    assert s["status"] == "unchanged"
    assert s["t_before"] == s["t_after"] == 0
    assert s["stages"] == [] and s["routing"]["cascade"] == []
    assert "pure-Clifford" in s["routing"]["reason"]


def test_cuccaro_cascade_beats_angle_only(tmp_path):
    """P3.3 gate (c), fake-LLM e2e on cuccaro_4: reconstruction (scripted control route) then
    angle (G1 pass + declining loop) — final T strictly below the angle-only arm on the same
    input, per-stage attribution correct, contracts separated."""
    import csv
    from circuitevolve.v2.tier1.control import control_plans
    from circuitevolve.v2.tier1.recognize import load_logical, summarize
    rows = {r["name"]: r for r in csv.DictReader(
        open(REPO / "benchmarks" / "nam_arith" / "MANIFEST.csv"))}
    dz = [int(x) for x in str(rows["cuccaro_4"].get("zero_init_qubits") or "").split()]
    _, lc = load_logical(CUCCARO_4, name="cuccaro_4")
    s = summarize(lc, declared_zero=dz, name="cuccaro_4")
    plans = iter([p.to_json() for _, _, p in control_plans(lc, s, 2)])   # V1, V2 (pyzx)

    def complete(prompts):          # control plans for the reconstruction stage, NONE after
        return [next(plans, "NONE") for _ in prompts]

    cascade = optimize(CUCCARO_4, 1e-3, complete, manifest={"declared_zero": dz},
                       runs_dir=tmp_path / "c", n_calls=2, batch=1)
    angle_only = optimize(CUCCARO_4, 1e-3, _nones(), manifest={"method": "angle"},
                          runs_dir=tmp_path / "a", n_calls=1, batch=1)
    # cascade shape + per-stage attribution
    assert [x["method"] for x in cascade["routing"]["cascade"]] == ["reconstruction", "angle"]
    st0, st1 = cascade["stages"]
    assert st0["method"] == "reconstruction" and st0["contract"] == "relaxed"
    assert st0["t_before"] == 56 and st0["t_after"] == 16 and st0["verified"]
    assert st1["method"] == "angle" and st1["contract"] == "approx"
    assert st1["t_before"] == 16 and st1["verified"]
    # the angle-only arm decomposes at its door (TKET entry) and declines: T stays at the twin
    assert angle_only["tket_entry"]["fired"] and angle_only["stats"]["accepted"] == 0
    # gate: cascade strictly below angle-only on the same input
    assert cascade["t_after"] < angle_only["t_after"]
    assert cascade["t_after"] == 16


def test_angle_tket_entry_fires_on_toffoli_input(tmp_path):
    s = optimize(MIXED_LOW_SHARE, 1e-3, _nones(), runs_dir=tmp_path, n_calls=1, batch=1)
    assert [x["method"] for x in s["routing"]["cascade"]] == ["angle"]
    assert s["tket_entry"]["fired"] and s["tket_entry"]["why"] == "input contains Toffolis"
    assert s["stats"]["accepted"] == 0
    assert s["final_check_vs_original"]["ok"]       # vs the decomposed entry form (§1.5)
    assert s["stages"][0]["method"] == "angle" and s["stages"][0]["contract"] == "approx"


def test_stage1_summary_shape_unchanged(tmp_path):
    """Single-stage pure-rotation run: pre-/1 top-level summary shape intact + new sections."""
    s = optimize("tfim_6", 1e-3, _nones(), runs_dir=tmp_path, n_calls=1, batch=1, graduated="off")
    assert s["routing"]["family"] == "dv.windows" and s["routing"]["contract"] == "approx"
    assert "tket_entry" not in s                    # stage-1 named inputs: entry pass OFF
    assert [x["method"] for x in s["routing"]["cascade"]] == ["angle"]
    assert len(s["stages"]) == 1 and s["stages"][0]["verified"]
    assert s["stages"][0]["t_before"] == s["t_before"] and s["stages"][0]["t_after"] == s["t_after"]
