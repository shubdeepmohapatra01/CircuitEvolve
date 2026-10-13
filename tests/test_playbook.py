"""Self-evolving playbook: delta parsing, evidence gate, persistence, loop integration (no LLM calls)."""
import random

from circuitevolve.integrity import frozen_digest
from circuitevolve.search.playbook import MAX_RULE_CHARS, Playbook



def _json(s):
    return "Here you go.\n```json\n" + s + "\n```\n"


def test_deltas_validated_and_merged():
    pb = Playbook()
    applied, errs = pb.apply_deltas(_json('[{"op": "add", "text": "Uncompute in reverse order."},'
                                          ' {"op": "add", "text": "' + "x" * (MAX_RULE_CHARS + 1) + '"},'
                                          ' {"op": "retire", "id": "R99"}]'), call=1)
    assert applied == [("add", "R1")] and len(errs) == 2
    assert pb.get("R1").status == "candidate"
    assert pb.apply_deltas("no block", 2)[1] == ["no json block"]
    assert pb.apply_deltas(_json("{not json"), 2)[1][0].startswith("bad json")
    applied, _ = pb.apply_deltas(_json('[{"op": "edit", "id": "R1", "text": "Uncompute in exact reverse order."}]'), 3)
    assert applied == [("edit", "R2")] and pb.get("R2").supersedes == "R1"
    # duplicates are refused
    assert pb.apply_deltas(_json('[{"op": "add", "text": "uncompute in reverse order."}]'), 4)[1] == ["add: duplicate"]


def test_evidence_gate_promotes_and_retires():
    pb = Playbook(min_exposure=8)
    good, bad = pb.add("good"), pb.add("bad")
    for _ in range(10):        # good: 3/4 pass when shown vs 0/4 when hidden; bad: the reverse
        pb.record([good.id], [bad.id], 4, 3, True)
        pb.record([bad.id], [good.id], 4, 0, False)
    changes = dict((rid, new) for rid, new, _ in pb.update_status(call=20))
    assert changes == {good.id: "active", bad.id: "retired"}
    texts, shown, hidden = pb.select(random.Random(0))
    assert texts == ["good"] and shown == hidden == []


def test_edit_supersedes_on_promotion_and_reflector_demotes_active():
    pb = Playbook(min_exposure=2)
    old = pb.add("old", status="active")
    new = pb.add("new", supersedes=old.id)
    for _ in range(6):
        pb.record([new.id], [], 4, 4, True)
        pb.record([], [new.id], 4, 0, False)
    pb.update_status(10)
    assert new.status == "active" and old.status == "retired"
    applied, _ = pb.apply_deltas(_json('[{"op": "retire", "id": "%s", "why": "stale"}]' % new.id), 11)
    assert applied == [("demote", new.id)] and new.status == "candidate" and new.exposures == 0


def test_frozen_playbook_never_changes(tmp_path):
    pb = Playbook()
    pb.add("kept", status="active")
    pb.add("pending")
    p = tmp_path / "pb.json"
    pb.save(p)
    fz = Playbook.load(p, frozen=True)
    assert fz.select(random.Random(0)) == (["kept"], [], [])
    assert fz.apply_deltas(_json('[{"op": "add", "text": "z"}]'), 1) == ([], ["frozen"])
    fz.record(["R2"], [], 4, 4, True)
    assert fz.get("R2").exposures == 0 and fz.update_status(1) == []
    assert Playbook.load(p).to_markdown().count("**R") == 2
