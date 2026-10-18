"""Tier-0 router v0 (PLAN_P1 P1.4): deterministic table, NeedsTriage, append-only decision log."""
from __future__ import annotations

import json

import pytest

from circuitevolve.blocks import REPO
from circuitevolve.engine.router import LOG, NeedsTriage, features_of, load_table, route

QFT8 = (REPO / "results" / "bqskit_baselines" / "stage1" / "inputs" / "qft_8_tket.qasm").read_text()
ADDER = ('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[4];\n'
         "ccx q[0],q[1],q[2];\ncx q[0],q[1];\nccx q[0],q[1],q[3];\n")
CLIFFORD = 'OPENQASM 2.0;\nqreg q[2];\nh q[0];\ncx q[0],q[1];\ns q[1];\n'


def test_rotation_dominated_routes_to_dv_windows():
    b = route(QFT8, log=False)
    assert b.family == "dv.windows" and b.plugin == "dv_windows" and b.contract == "approx"
    assert b.features["toffolis"] == 0 and b.features["rz_nonclifford"] > 0
    assert b.playbook == "playbooks/families/dv.windows.json"


def test_terms_route_to_cvdv():
    b = route({"terms": [{"kind": "n2", "theta": 0.785}]}, log=False)
    assert b.family == "cvdv.bosonic" and b.contract == "certified_subspace"


def test_toffoli_circuit_needs_triage():
    with pytest.raises(NeedsTriage) as e:
        route(ADDER, log=False)
    assert e.value.features["toffolis"] == 2


def test_clifford_only_needs_triage():
    with pytest.raises(NeedsTriage):
        route(CLIFFORD, log=False)


def test_routing_is_deterministic():
    f1, f2 = features_of(QFT8), features_of(QFT8)
    assert f1 == f2
    assert route(QFT8, log=False).family == route(QFT8, log=False).family


def test_manifest_override_is_honored_and_labeled():
    b = route(QFT8, manifest={"family": "dv.windows"}, log=False)
    assert b.reason == "manifest override"


def test_reserved_family_refuses():
    with pytest.raises(NeedsTriage):
        route(QFT8, manifest={"family": "arithmetic"}, log=False)


def test_decisions_are_logged_append_only():
    before = LOG.read_text().count("\n") if LOG.exists() else 0
    route(QFT8)
    with pytest.raises(NeedsTriage):
        route(ADDER)
    lines = LOG.read_text().splitlines()
    assert len(lines) == before + 2
    routed, triaged = json.loads(lines[-2]), json.loads(lines[-1])
    assert routed["family"] == "dv.windows" and "features" in routed
    assert triaged["family"] is None and triaged["features"]["toffolis"] == 2


def test_table_schema():
    t = load_table()
    for fam, row in t["families"].items():
        assert row["contract"] in ("approx", "exact", "relaxed", "certified_subspace")
        assert "precondition" in row and "playbook" in row
