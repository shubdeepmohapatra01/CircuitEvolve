"""Engine contract tests on a synthetic domain (PLAN_P1 P1.1): acceptance is engine-owned.

A FakePlugin over integer lists (cost = sum) exercises every acceptance path — accept, metric
reject, verifier reject, ledger reject, decline, round-robin exhaustion, archive dedup/cap,
append-only tag refusal — with no DV machinery involved. Plus the lexicographic-floor property
of the DV plugin's improves().
"""
from __future__ import annotations

import random
from dataclasses import dataclass

import pytest

from circuitevolve.core.ledger import Ledger
from circuitevolve.engine import DomainPlugin, EvolveLoop


@dataclass
class FakeTask:
    i: int
    state: list
    key: str = ""
    order: int = 0
    index: int = 0

    def __post_init__(self):
        self.key = f"slot{self.i}"
        self.order = self.index = self.i


class FakePlugin(DomainPlugin):
    name, actions, primary, n = "fake", ("set",), "t", 1
    meta = {"name": "fake", "source": "unit"}

    def __init__(self, start):
        self._start = list(start)

    def start_state(self):
        return list(self._start)

    def flat_state(self, m):
        return list(m.state)

    def digest(self, state):
        return repr(state)

    def select_tasks(self, m, k, rng):
        fresh = [i for i in range(len(m.state)) if f"slot{i}" not in m.tried]
        if not fresh:
            m.tried.clear()
            fresh = list(range(len(m.state)))
        return [FakeTask(i, list(m.state)) for i in fresh[:k]]

    def build_prompt(self, task, rules, feedback, allowance):
        return f"slot {task.i} value {task.state[task.i]} allowance {allowance:.1e} rules {len(rules)}"

    def parse(self, text):
        if text.strip() == "NONE":
            return [], [], True
        if text.startswith("SET "):
            _, i, v = text.split()
            return [("set", (int(i), int(v)))], [], False
        return [], ["unparseable"], False

    def materialize(self, task, action, payload, call_id):
        return dict(ok=True, cand=payload, crec=dict(action="set", set=list(payload)), label=f"set {payload[0]}")

    def verify(self, task, cand, allowance):
        i, v = cand
        if v < 0:
            return dict(ok=False, mode="exact", dist=0.0, charge=0.0, reason="negative value")
        charge = 1.0 if v == 99 else 1e-9      # v=99: deliberately unpayable
        return dict(ok=True, mode="approx", dist=charge, charge=charge, reason="")

    def global_check(self, state, bound):
        return None

    def frozen_digest(self):
        return "fake-digest"

    def apply(self, cur, task, cand):
        i, v = cand
        out = list(cur)
        out[i] = v
        return out

    def cost(self, state, ledger):
        return dict(t=sum(state))

    def cost_key(self, cost):
        return (cost["t"],)

    def improves(self, new, old):
        return new["t"] < old["t"]


def _loop(start, responses, **kw):
    resp = list(responses)

    def complete(prompts):
        return [resp.pop(0) if resp else "NONE" for _ in prompts]

    led = Ledger(1e-3)
    return EvolveLoop(FakePlugin(start), 1e-3, complete, led, **{**dict(n_calls=len(responses), batch=1), **kw})


def test_accept_reject_decline_paths():
    s = _loop([5, 7], ["SET 0 2", "SET 0 9", "SET 1 -3", "SET 1 99", "garbage", "NONE"]).run()
    st = s["stats"]
    assert st["accepted"] == 1 and s["t_before"] == 12 and s["t_after"] == 9       # only SET 0 2 improves
    assert st["rejected_metric"] == 1                                              # SET 0 9 worsens
    assert st["rejected_verifier"] == 1                                            # negative value
    assert st["rejected_ledger"] == 1                                              # charge 1.0 > remaining
    assert st["parse_errors"] == 1 and st["declined"] == 1
    assert s["ledger"]["window_spent"] == pytest.approx(1e-9)


def test_zero_accepts_reproduce_input():
    s = _loop([3, 4], ["NONE"] * 4).run()
    assert s["t_after"] == s["t_before"] == 7 and s["stats"]["accepted"] == 0
    assert s["ledger"]["window_spent"] == 0.0


def test_archive_dedup_and_cap():
    # every call improves slot alternately; archive must stay capped and deduped
    seq = [f"SET {i % 2} {9 - i}" for i in range(8)]
    lp = _loop([9, 9], seq, archive_size=3)
    lp.run()
    assert len(lp.archive) <= 3
    assert len({m.digest for m in lp.archive}) == len(lp.archive)
    assert lp.archive[0].cost["t"] == min(m.cost["t"] for m in lp.archive)


def test_round_robin_reselects_after_exhaustion():
    lp = _loop([1, 2], ["NONE"] * 6, batch=2)
    lp.run()
    assert lp.stats["proposal_calls"] == 6                      # tried marks cleared, selection restarts


def test_append_only_tag_refused(tmp_path):
    (tmp_path / "x.jsonl").write_text("")
    with pytest.raises(FileExistsError):
        _loop([1], ["NONE"], tag="x", runs_dir=tmp_path).run()


def test_frozen_digest_guard():
    """A plugin whose frozen digest differs between run start and end must abort the run."""

    class Mutating(FakePlugin):
        def __init__(self):
            super().__init__([1])
            self._d = iter(["digest-at-start", "digest-at-end"])

        def frozen_digest(self):
            return next(self._d)

    with pytest.raises(RuntimeError):
        EvolveLoop(Mutating(), 1e-3, lambda ps: ["NONE"] * len(ps), Ledger(1e-3), n_calls=1).run()


def test_dv_improves_lexicographic_floor():
    """DV improves() may never report improvement when the primary (T) worsens."""
    from circuitevolve.core.metric import improves as dv_improves

    rng = random.Random(0)
    for _ in range(2000):
        old = dict(t=rng.randrange(0, 50), rz=rng.randrange(0, 9), cx=rng.randrange(0, 9),
                   gates=rng.randrange(0, 20), t_gs=0, t_fixed=0, eps_rz=1e-5)
        new = dict(t=rng.randrange(0, 50), rz=rng.randrange(0, 9), cx=rng.randrange(0, 9),
                   gates=rng.randrange(0, 20), t_gs=0, t_fixed=0, eps_rz=1e-5)
        if dv_improves(new, old):
            assert new["t"] <= old["t"], (old, new)
