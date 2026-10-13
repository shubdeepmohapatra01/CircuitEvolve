"""LEGACY: the playbook inside the adder llm_search loop (prompt rendering, reflection). Moved from
tests/test_playbook.py on 2026-10-13, test bodies unchanged; pure playbook tests stay there."""
import random

from circuitevolve.integrity import frozen_digest
from circuitevolve.legacy.adder.llm import OPEN_NAMES, _rename_prog, build_prompt, llm_search
from circuitevolve.search.playbook import MAX_RULE_CHARS, Playbook
from circuitevolve.legacy.adder.slice import CUCCARO, GIDNEY_A, to_source



def _json(s):
    return "Here you go.\n```json\n" + s + "\n```\n"


def test_prompt_carries_rules_only_when_given():
    base = build_prompt(CUCCARO, (14.0, 112, 18, 9, 6), [], [], False, "A", 4)
    withr = build_prompt(CUCCARO, (14.0, 112, 18, 9, 6), [], [], False, "A", 4,
                         rules_text=Playbook.render(["Keep the work wire clean."]))
    assert "Lessons" not in base and "Keep the work wire clean." in withr


def test_loop_with_playbook_reflects_and_keeps_verifier_frozen():
    good = "ok\n```python\n" + to_source(_rename_prog(GIDNEY_A, OPEN_NAMES)) + "```\n"
    seen_rules = []

    def proposer(prompts):
        seen_rules.extend("Lessons" in p for p in prompts)
        return [good for _ in prompts]

    def reflector(prompts):
        assert len(prompts) == 1 and "Current playbook" in prompts[0]
        return [_json('[{"op": "add", "text": "Use the cout wire as a clean target for the AND."}]')]

    pb = Playbook(ab_fraction=1.0)
    digest = frozen_digest()
    _, _, stats, best = llm_search(CUCCARO, "A", proposer, n_calls=6, batch=2, playbook=pb,
                                   reflect_every=1, reflect_complete=reflector)
    # batch 1 evaluates one new program -> reflection; batches 2-3 only repeat it (duplicates are not evidence)
    assert best == GIDNEY_A and stats["reflect_calls"] == 1 and stats["rules_added"] == 1
    assert stats["reflect_skipped_no_evidence"] == 2
    assert len(pb.live()) == 1 and any(seen_rules) and stats["verifier_digest"] == digest[:16]


def test_loop_without_playbook_is_unchanged():
    def fake(prompts):
        return [RuntimeError("x") if i == 0 else "```python\n" + to_source(GIDNEY_A) + "```" for i, _ in enumerate(prompts)]
    r1 = llm_search(CUCCARO, "A", fake, n_calls=3, batch=3)
    r2 = llm_search(CUCCARO, "A", fake, n_calls=3, batch=3)
    assert r1[2]["accepted"] == r2[2]["accepted"] == 1 and "reflect_calls" not in r1[2]


def test_reflection_skipped_without_evidence_and_blinded_cues_refused():
    calls = []

    def failing(prompts):
        return [RuntimeError("down") for _ in prompts]

    def reflector(prompts):
        calls.append(1)
        return [_json('[{"op": "add", "text": "x"}]')]

    pb = Playbook()
    _, _, stats, _ = llm_search(CUCCARO, "A", failing, n_calls=4, batch=2, playbook=pb, reflect_every=1,
                                reflect_complete=reflector)
    assert calls == [] and stats["reflect_skipped_no_evidence"] == 2 and pb.rules == []
    pbb = Playbook(blinded=True, banned_words=("carry",))
    applied, errs = pbb.apply_deltas(_json('[{"op": "add", "text": "Propagate the Carry on w."}]'), 1)
    assert applied == [] and errs == ["add: banned word 'carry'"]
