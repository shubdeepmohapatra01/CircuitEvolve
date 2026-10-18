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


def test_cuccaro_cascade_refuses_until_p33(tmp_path):
    """cuccaro_4 raw routes [reconstruction, angle]; the reconstruction plugin is reserved
    until P3.3, so execution refuses with a clear message instead of guessing."""
    with pytest.raises(NotImplementedError, match="P3.3"):
        optimize(CUCCARO_4, 1e-3, _nones(), runs_dir=tmp_path, n_calls=1, batch=1)


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
