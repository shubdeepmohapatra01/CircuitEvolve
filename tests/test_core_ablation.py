"""Playbook-ablation support in the window core (fake LLM only).

* `WindowLoop(seeded_ties=True)`: windows of equal T-cost are ordered by a seed-dependent hash; the set of windows
  and the T-cost order are unchanged, the same seed gives the same order, and the default keeps stage-1 order.
* A FROZEN playbook shows ACTIVE rules only, consumes no loop RNG, triggers no reflector call and is not modified,
  so a frozen-playbook run and a no-playbook run with the same seed make the same number of LLM calls and draw
  the same parent-selection random numbers.
"""
from __future__ import annotations

import json

from circuitevolve.core.circuit import Circuit, load_input
from circuitevolve.core.loop import WindowLoop
from circuitevolve.core.verifier import check_circuit
from circuitevolve.search.playbook import Playbook

EPS = 1e-3


def _qft4():
    c = load_input("qft_4", prefer_baseline_file=False)
    return c


def _loop(circ, seed, seeded_ties, **kw):
    lp = WindowLoop(circ, list(circ.ops), EPS, lambda ps: ["NONE"] * len(ps), seed=seed, seeded_ties=seeded_ties,
                    check_whole=False, **kw)
    m = lp._member(list(circ.ops), lp.ledger0)
    return lp, m


def _order(lp, m):
    ws = lp._choose_windows(m, 1000)
    return [(t, w.index) for t, w, _, _ in ws]


def test_seeded_ties_reorder_only_equal_cost_windows():
    circ = _qft4()
    base = _order(*_loop(circ, 0, False))
    assert base == sorted(base, key=lambda x: (-x[0], x[1]))          # default: stage-1 order (T-cost, index)
    orders = {s: _order(*_loop(circ, s, True)) for s in range(6)}
    for s, o in orders.items():
        assert sorted(o) == sorted(base)                                # same windows
        assert [t for t, _ in o] == [t for t, _ in base]                # same T-cost sequence
        assert o == _order(*_loop(circ, s, True))                       # deterministic per seed
    ties = any(base[i][0] == base[i + 1][0] for i in range(len(base) - 1))
    if ties:
        assert len({tuple(o) for o in orders.values()}) > 1             # seeds actually change tie order


def _pb_with(tmp_path, n_active=2, n_cand=2):
    pb = Playbook()
    for i in range(n_active):
        pb.add(f"active rule {i}", 0, status="active")
    for i in range(n_cand):
        pb.add(f"candidate rule {i}", 0)
    p = tmp_path / "pb.json"
    pb.save(p)
    return Playbook.load(p, frozen=True), p


def test_frozen_playbook_shows_active_only_and_consumes_no_rng(tmp_path):
    import random
    pb, p = _pb_with(tmp_path)
    r = random.Random(7)
    st = r.getstate()
    texts, shown, hidden = pb.select(r)
    assert texts == ["active rule 0", "active rule 1"] and shown == [] and hidden == []
    assert r.getstate() == st
    before = p.read_text()
    pb.record([], [], 3, 1, True)
    assert pb.update_status(10) == [] and pb.apply_deltas('```json\n[{"op":"add","text":"x"}]\n```', 1)[1] == ["frozen"]
    pb.save(tmp_path / "pb2.json")
    a, b = json.loads(before), json.loads((tmp_path / "pb2.json").read_text())
    assert a["rules"] == b["rules"]


def test_frozen_playbook_run_matches_no_playbook_run_in_calls_and_rng(tmp_path):
    circ = _qft4()
    seen = {}

    def fake(tag):
        def complete(prompts):
            seen.setdefault(tag, []).extend(prompts)
            return ["NONE"] * len(prompts)
        return complete
    pb, _ = _pb_with(tmp_path)
    runs = {}
    for tag, playbook in (("none", None), ("frozen", pb)):
        lp = WindowLoop(circ, list(circ.ops), EPS, fake(tag), playbook=playbook, seed=3, seeded_ties=True,
                        n_calls=10, batch=5, reflect_every=2, check_whole=False, runs_dir=tmp_path, tag=f"ab_{tag}")
        s = lp.run()
        runs[tag] = (s, lp.rng.getstate())
    (s0, r0), (s1, r1) = runs["none"], runs["frozen"]
    assert s0["calls"] == s1["calls"] == 10 and s0["stats"]["reflect_calls"] == s1["stats"]["reflect_calls"] == 0
    assert s0["stats"]["proposal_calls"] == s1["stats"]["proposal_calls"] == 10
    assert r0 == r1                                                     # identical parent-selection RNG stream
    assert all("active rule 0" in p and "candidate rule" not in p for p in seen["frozen"])
    assert not any("active rule" in p for p in seen["none"])
    assert s0["t_after"] == s0["t_before"] == s1["t_after"]
    assert check_circuit(list(circ.ops), list(circ.ops), circ.n, bound=1e-12)["ok"]
