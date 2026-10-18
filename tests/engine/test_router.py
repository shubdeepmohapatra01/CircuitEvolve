"""Tier-0 router v1 (PLAN_P3 P3.2): method predicates + cascade, deterministic table,
append-only decision log. Updated from the /0 single-binding tests (PLAN_P3 §2)."""
from __future__ import annotations

import json

import pytest

from circuitevolve.blocks import REPO
from circuitevolve.engine import router as R
from circuitevolve.engine.router import NeedsTriage, features_of, load_table, route

QFT8 = (REPO / "results" / "bqskit_baselines" / "stage1" / "inputs" / "qft_8_tket.qasm").read_text()
ADDER = ('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[4];\n'
         "ccx q[0],q[1],q[2];\ncx q[0],q[1];\nccx q[0],q[1],q[3];\n")
CLIFFORD = 'OPENQASM 2.0;\nqreg q[2];\nh q[0];\ncx q[0],q[1];\ns q[1];\n'
CUCCARO_4 = str(REPO / "benchmarks" / "nam_arith" / "generated" / "cuccaro_4.qasm")


def test_rotation_dominated_routes_to_single_angle_stage():
    c = route(QFT8, log=False)
    assert [b.method for b in c] == ["angle"]
    b = c[0]
    assert b.family == "dv.windows" and b.plugin == "dv_windows" and b.contract == "approx"
    assert b.features["toffolis"] == 0 and b.features["rz_nonclifford"] > 0
    assert b.playbook == "playbooks/families/dv.windows.json"
    assert b.graduated_family == "dv.windows"


def test_terms_route_to_cvdv():
    c = route({"terms": [{"kind": "n2", "theta": 0.785}]}, log=False)
    assert [b.method for b in c] == ["cvdv"]
    assert c[0].family == "cvdv.bosonic" and c[0].contract == "certified_subspace"


def test_toffoli_circuit_routes_reconstruction_then_angle():
    c = route(ADDER, log=False)
    assert [b.method for b in c] == ["reconstruction", "angle"]
    assert c[0].contract == "relaxed" and c[0].rank < c[1].rank
    assert c[0].evidence["toffolis"] == 2 and c[0].evidence["fires"]


def test_cuccaro_4_raw_routes_reconstruction_then_angle():
    c = route(CUCCARO_4, log=False)
    assert [b.method for b in c] == ["reconstruction", "angle"]
    assert c[0].evidence["pairs"] >= 1          # recognizer evidence on the RAW form


def test_clifford_only_returns_empty_cascade():
    assert route(CLIFFORD, log=False) == []


def test_routing_is_deterministic():
    f1, f2 = features_of(QFT8), features_of(QFT8)
    assert f1 == f2
    assert [b.method for b in route(QFT8, log=False)] == \
           [b.method for b in route(QFT8, log=False)]


def test_manifest_override_is_honored_and_labeled():
    c = route(QFT8, manifest={"family": "dv.windows"}, log=False)
    assert [b.method for b in c] == ["angle"] and c[0].reason == "manifest override"
    c2 = route(QFT8, manifest={"method": "angle"}, log=False)
    assert [b.method for b in c2] == ["angle"]


def test_unknown_override_refuses():
    with pytest.raises(NeedsTriage):
        route(QFT8, manifest={"family": "arithmetic"}, log=False)


def test_decisions_are_logged_append_only(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "LOG", tmp_path / "routing_log.jsonl")
    route(QFT8)
    route(ADDER)
    route(CLIFFORD)
    lines = (tmp_path / "routing_log.jsonl").read_text().splitlines()
    assert len(lines) == 3
    one, two, three = (json.loads(x) for x in lines)
    assert [s["method"] for s in one["cascade"]] == ["angle"] and "features" in one
    assert [s["method"] for s in two["cascade"]] == ["reconstruction", "angle"]
    assert two["evidence"]["toffolis"] == 2                 # predicate evidence in the log row
    assert three["cascade"] == [] and "pure-Clifford" in three["reason"]
    assert one["table"] == "circuitevolve.engine.router/1"


def test_table_schema():
    t = load_table()
    assert t["format"] == "circuitevolve.engine.router/1"
    assert set(t["methods"]) == {"reconstruction", "angle", "cvdv"}
    for _, row in t["methods"].items():
        assert row["contract"] in ("approx", "exact", "relaxed", "certified_subspace")
        assert "predicate" in row and "playbook" in row and "rank" in row
    # frozen names (PLAN_P3 §2): recorded state keeps resolving
    assert t["methods"]["angle"]["family"] == "dv.windows"
    assert t["methods"]["angle"]["graduated_family"] == "dv.windows"
    assert t["methods"]["angle"]["playbook"] == "playbooks/families/dv.windows.json"
    assert t["methods"]["cvdv"]["family"] == "cvdv.bosonic"
    assert t["methods"]["reconstruction"]["rank"] < t["methods"]["angle"]["rank"]
