"""P2.2a seed discipline: seeds are candidates under the normal A/B machinery — shown to some
prompts and hidden from others, never auto-active, credit only through measured improvement."""
from __future__ import annotations

import random

from circuitevolve.blocks import REPO
from circuitevolve.search.playbook import Playbook

# P2.2 seeded state = the committed pre-campaign file; the live family file is MUTATED by
# angle_campaign1 arm-A learning (by protocol), so seed/inheritance invariants are checked on the
# sha-recorded snapshot (6876d37c..., identical to playbooks/families/dv.windows.json at d054cea).
TARGET = REPO / "results" / "engine" / "angle_campaign1" / "A_playbook_at_start.json"


def _pb():
    return Playbook.load(TARGET)


def test_seeds_present_and_candidate_only():
    pb = _pb()
    seeds = [r for r in pb.rules if r.origin == "seed"]
    assert len(seeds) >= 6
    assert all(r.status == "candidate" for r in seeds), "a seed may only become active via A/B stats"
    assert all("[seed" in r.text for r in seeds)


def test_seeds_enter_ab_exposure_like_any_candidate():
    pb = _pb()
    rng = random.Random(7)
    shown_counts = {r.id: 0 for r in pb.rules if r.origin == "seed"}
    n = 200
    for _ in range(n):
        texts, shown, hidden = pb.select(rng)
        for rid in shown_counts:
            if rid in shown:
                shown_counts[rid] += 1
    for rid, c in shown_counts.items():
        assert 0 < c < n, f"seed {rid} must be A/B split (shown {c}/{n}) — not always-on, not never-on"


def test_seed_credit_only_on_improvement():
    """Recording a shown-but-not-improving prompt must not add improvement credit to a seed."""
    pb = _pb()
    rid = next(r.id for r in pb.rules if r.origin == "seed")
    r = pb.get(rid)
    before = (r.with_improvements, r.with_prompts)
    pb.record([rid], [], n_props=1, n_pass=0, improved=False)
    assert r.with_improvements == before[0] and r.with_prompts == before[1] + 1