"""Tier 2 evolution loop: acceptance rule, pruning, rejection reasons, control proposer, fake-LLM end-to-end."""
from circuitevolve.v2.tier2 import evolve as E
from circuitevolve.v2.tier2.apply import cost
from circuitevolve.v2.tier2.enumerate_ids import candidate_pool
from circuitevolve.v2.tier2.rules import Library, Rule, parse_rules, parse_seq


def _starts():
    a = [("h", (0,)), ("t", (0,)), ("cx", (0, 1)), ("t", (0,)), ("h", (1,)), ("h", (1,))]
    b = [("h", (0,)), ("t", (1,)), ("cx", (0, 1)), ("tdg", (1,))]
    out = {}
    for name, g in (("A", a), ("B", b)):
        t, tot = cost(g)
        out[name] = dict(gates=g, n=2, t=t, gates_total=tot)
    return out


def test_step_accepts_only_t_reduction_and_prunes_unused():
    S = _starts()
    lib = Library([], "v0")
    ev = E.evaluate(lib, S)
    hh = Rule("hh", parse_seq("h a; h a"), ())
    lib1, ev1, rec, recs = E.step(lib, ev, S, [hh], 1, "test", "v1")
    assert not rec["accepted"] and "unchanged" in rec["reason"]          # gate-only rule: T unchanged
    tt = Rule("tt", parse_seq("t a; t a"), parse_seq("s a"))
    zz = Rule("zz", parse_seq("z a; z a"), ())                          # verified but never applied -> pruned
    bad = Rule("bad", parse_seq("t a; t a"), parse_seq("sdg a"))
    lib2, ev2, rec, recs = E.step(lib, ev, S, [tt, zz, bad], 2, "test", "v1")
    assert rec["accepted"] and ev2["total_t"] == ev["total_t"] - 2
    assert [r.name for r in lib2.rules] == ["tt"] and rec.get("pruned_unused") == 1
    assert any("REJECTED by verifier" in r["outcome"] for r in recs)
    assert lib2.parent_sha == lib.sha256
    # lex mode accepts gate-only gains
    lib3, ev3, rec, _ = E.step(lib2, ev2, S, [Rule("hh2", parse_seq("h a; h a"), ())], 3, "test", "v2", mode="lex")
    assert rec["accepted"] and ev3["total_g"] < ev2["total_g"]


def test_windows_are_convex_and_small():
    import random
    S = _starts()
    W = E.sample_windows(S, 2, random.Random(0))
    assert W and all(len(w["Q"]) <= 4 and len(w["gates"]) <= 20 for w in W)
    p = E.build_prompt(Library([], "v0"), S, W, "")
    assert "RULE" in p and "card 07" in p


def test_control_proposer_prefers_matching_t_rules():
    pool = candidate_pool(specs=((1, 3),))
    prop = E.ControlProposer(pool, seed=0)
    rules, mc = prop.propose(2, _starts())
    assert rules[0].cost_delta()[0] > 0 and max(mc.values()) > 0
