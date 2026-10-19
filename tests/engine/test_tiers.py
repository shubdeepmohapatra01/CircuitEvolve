"""Playbook tiers + graduated library (PLAN_P1 P1.4): loading, provenance, hash checks, no-op."""
from __future__ import annotations

import hashlib
import json

import pytest

from circuitevolve.blocks import REPO
from circuitevolve.engine.graduate import INDEX, apply_graduated, load_graduated, load_index
from circuitevolve.search.playbook import Playbook

PB = REPO / "playbooks"
# P2.2 seeded state = the committed pre-campaign file; the live family file is MUTATED by
# angle_campaign1 arm-A learning (by protocol), so seed/inheritance invariants are checked on the
# sha-recorded snapshot (6876d37c..., identical to playbooks/families/dv.windows.json at d054cea).
DV_SEEDED = REPO / "results" / "engine" / "angle_campaign1" / "A_playbook_at_start.json"


def test_family_playbooks_load():
    dv = Playbook.load(PB / "families" / "dv.windows.json")
    cv = Playbook.load(PB / "families" / "cvdv.bosonic.json")
    assert len(dv.rules) > 0 and len(cv.rules) > 0
    assert all(r.origin == "seed" for r in cv.rules)                 # converted rulebook insights


def test_dv_family_playbook_is_dev_v1_plus_seeds_only():
    """P1 copied dev_v1 verbatim; P2.2 appended seed rules ONLY — the inherited stage-1 rules
    must remain byte-identical and every addition must be origin='seed' (PLAN_P2 section 2)."""
    a = json.loads((PB / "dev_v1.json").read_text())
    b = json.loads(DV_SEEDED.read_text())
    inherited = {r["id"]: r for r in a["rules"]}
    extra = []
    for r in b["rules"]:
        if r["id"] in inherited and r["origin"] != "seed":
            assert r == inherited[r["id"]], f"inherited rule {r['id']} was modified"
        else:
            extra.append(r)
    assert len(b["rules"]) == len(a["rules"]) + len(extra)
    assert extra and all(r["origin"] == "seed" and r["status"] in ("candidate", "active") for r in extra)
    assert all("[seed" in r["text"] or "[harvest" in r["text"] for r in extra), "seed provenance marker required"
    assert a["settings"] == b["settings"]                            # A/B thresholds not weakened


def test_cvdv_seeds_have_traceable_provenance():
    """Every cvdv seed is either verbatim rulebook text ([cvdv rulebook #N]) or a certified
    literature harvest ([harvest arXiv:...], P2.2b — certificate numbers in the rule text,
    full record in results/engine/harvest_*.{md,json})."""
    md = (REPO / "cvdv" / "rulebook" / "playbook.md").read_text()
    cv = Playbook.load(PB / "families" / "cvdv.bosonic.json")
    assert all(r.origin == "seed" and r.status in ("candidate", "active") for r in cv.rules)
    for r in cv.rules:
        if r.text.startswith("[cvdv rulebook #"):
            head = r.text.split("] ", 1)[1][:60]
            assert " ".join(head.split()) in " ".join(md.split()), r.text[:50]
        elif r.text.startswith("[harvest arXiv:"):
            assert "certified" in r.text, "harvest seed must cite its certificate in-text"
            reports = list((REPO / "results" / "engine").glob("harvest_cvdv_*.json"))
            assert reports, "harvest seed present but no harvest report found"
        else:
            raise AssertionError(f"cvdv seed without recognized provenance marker: {r.text[:60]}")


def test_graduated_index_loads_with_hash_check():
    """P1 froze the library empty; P2.3 graduated G1 (same-Pauli merge) into dv.windows.
    cvdv.bosonic remains empty until a certified rule earns promotion in a campaign."""
    idx = load_index()
    dv = load_graduated("dv.windows")
    assert [g.id for g in dv] == ["G1"] and dv[0].kind == "pass"
    assert load_graduated("cvdv.bosonic") == []
    assert set(idx["families"]) == {"dv.windows", "cvdv.bosonic"}


def test_graduated_empty_rule_list_is_identity():
    state = [("h", (0,), None), ("rz", (0,), 0.3)]
    out, reports = apply_graduated(state, [], n=1)
    assert out is state and reports == []


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
