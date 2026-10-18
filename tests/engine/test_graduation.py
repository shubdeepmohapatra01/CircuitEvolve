"""P2.3 graduation bridge: the frozen same-Pauli merge pass, promote() discipline, pre-opt
integration. The replay record (results/engine/graduation_pmerge.json) is the freeze-time
ground truth the integrated path must reproduce."""
from __future__ import annotations

import json

import pytest

from circuitevolve.blocks import REPO
from circuitevolve.engine.graduate import load_callable, load_graduated, promote

REPLAY = REPO / "results" / "engine" / "graduation_pmerge.json"


def test_library_holds_the_merge_pass():
    rules = load_graduated("dv.windows")
    assert len(rules) == 1
    g = rules[0]
    assert g.kind == "pass" and g.provenance_rule_id == "R29"
    assert "ablation control" in g.evidence and "10.4-14.7%" in g.evidence


def test_replay_record_satisfies_keep_rule():
    rec = json.loads(REPLAY.read_text())
    k = rec["keep"]
    assert k["kept"] and not k["risers"] and not k["bad_checks"]
    assert k["total_t_after"] < k["total_t_before"]
    assert all(r["max_merge_dist"] <= 1e-12 for r in rec["rows"])      # every application verified
    assert all(r["final_check"]["ok"] for r in rec["rows"])


def test_pass_merges_synthetic_equal_frame_pair():
    apply_pass = load_callable(load_graduated("dv.windows")[0])
    ops = [("h", (0,), None), ("cx", (0, 1), None), ("rz", (1,), 0.30), ("cx", (1, 2), None),
           ("h", (2,), None), ("rz", (1,), 0.25), ("rz", (2,), 0.90)]
    out, rep = apply_pass(ops, 3)
    assert rep["merges"] >= 1 and rep["max_merge_dist"] <= 1e-12
    assert sum(1 for g, _, _ in out if g == "rz") < 3


def test_promote_refuses_unproven_candidate(tmp_path):
    idx_copy = tmp_path / "index.json"
    idx_copy.write_text((REPO / "playbooks" / "graduated" / "index.json").read_text())
    with pytest.raises(ValueError, match="without documented evidence"):
        promote("dv.windows", "R30", "pass", "playbooks/graduated/same_pauli_merge.py",
                "deadbeef", evidence="", rule_status="candidate", index_path=idx_copy)


def test_pass_file_tamper_refused(tmp_path):
    g = load_graduated("dv.windows")[0]
    bad = tmp_path / "same_pauli_merge.py"
    bad.write_text((REPO / g.path).read_text() + "\n# drift\n")
    tampered = type(g)(**{**g.__dict__, "path": str(bad.relative_to(REPO)) if bad.is_relative_to(REPO)
                          else "results/CHANGELOG.md"})
    with pytest.raises(RuntimeError, match="changed since freeze"):
        load_callable(tampered)
