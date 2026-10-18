"""Playbook tiers + graduated library (PLAN_P1 P1.4): loading, provenance, hash checks, no-op."""
from __future__ import annotations

import hashlib
import json

import pytest

from circuitevolve.blocks import REPO
from circuitevolve.engine.graduate import INDEX, apply_graduated, load_graduated, load_index
from circuitevolve.search.playbook import Playbook

PB = REPO / "playbooks"


def test_family_playbooks_load():
    dv = Playbook.load(PB / "families" / "dv.windows.json")
    cv = Playbook.load(PB / "families" / "cvdv.bosonic.json")
    assert len(dv.rules) > 0 and len(cv.rules) > 0
    assert all(r.origin == "seed" for r in cv.rules)                 # converted rulebook insights


def test_dv_family_playbook_is_verbatim_copy():
    a = json.loads((PB / "dev_v1.json").read_text())
    b = json.loads((PB / "families" / "dv.windows.json").read_text())
    assert a == b                                                    # content unchanged in P1


def test_cvdv_seeds_are_verbatim_rulebook_text():
    md = (REPO / "cvdv" / "rulebook" / "playbook.md").read_text()
    cv = Playbook.load(PB / "families" / "cvdv.bosonic.json")
    for r in cv.rules:
        body = r.text.split("] ", 1)[1]                              # strip "[cvdv rulebook #N] "
        head = body[:60]
        assert " ".join(head.split()) in " ".join(md.split()), r.text[:50]


def test_graduated_index_loads_and_is_empty():
    idx = load_index()
    assert all(v == [] for v in idx["families"].values())
    assert load_graduated("dv.windows") == []
    assert load_graduated("cvdv.bosonic") == []


def test_graduated_empty_library_is_identity():
    state = [("h", (0,), None), ("rz", (0,), 0.3)]
    assert apply_graduated(state, []) is state


def test_graduated_index_tamper_detected(tmp_path):
    idx = json.loads(INDEX.read_text())
    idx["families"]["dv.windows"] = [dict(id="fake", family="dv.windows", kind="pass", path="x.py",
                                          sha256="0" * 64, provenance_rule_id="R0", verified_by="deadbeef")]
    p = tmp_path / "index.json"
    p.write_text(json.dumps(idx))                                    # entries changed, hash not updated
    with pytest.raises(RuntimeError, match="tampered"):
        load_index(p)


def test_graduated_file_drift_detected(tmp_path):
    fam = {"dv.windows": [dict(id="g1", family="dv.windows", kind="pass",
                               path="playbooks/graduated/index.json",  # any existing file
                               sha256="0" * 64, provenance_rule_id="R1", verified_by="deadbeef")]}
    idx = {"format": "circuitevolve.engine.graduated/0", "families": fam,
           "index_sha256_of_entries": hashlib.sha256(json.dumps(fam, sort_keys=True).encode()).hexdigest()}
    p = tmp_path / "index.json"
    p.write_text(json.dumps(idx))
    with pytest.raises(RuntimeError, match="changed since freeze"):
        load_graduated("dv.windows", p)
