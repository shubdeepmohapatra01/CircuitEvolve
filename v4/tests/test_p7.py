"""P7: the loop, driven by STUB scout / implementer so its control flow is tested without any LLM.

What must hold, from V4_README section 5:
  * the playbook is ONE MUTABLE OBJECT handed along the chain: a rule admitted on circuit A is in the
    book that circuit B is shown;
  * `optimize_memo` means a (book-state, circuit) pair is computed once: the second visit is a cache hit;
  * the five outcomes of 5.3 are classified at the right LEVEL, and a fire-and-fail keeps the idea and
    re-runs the IMPLEMENTER, while an idea-level failure goes back to the SCOUT;
  * admission REFUSES any rule that raises T on any circuit (5.2);
  * a declared precondition excludes a circuit for free and is not counted as a rejection;
  * the global budget and the attempt loop both terminate.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from v4 import book as B, loop as L
from v4.memo import stats as memo_stats


def _cfg(tmp_path, **kw):
    return L.LoopConfig(circuit_order=("qft_8", "tfim_6"), global_budget_attempts=kw.pop("budget", 4),
                        max_loops=kw.pop("loops", 2), tag="test", **kw)


def _card(name, lever="rotation_count", **kw):
    return dict(name=name, domain="dv", kind="rewrite", lever=lever, error_class="exact",
                resource_class="unitary", identity="x", correctness="x", trigger="x",
                expected_effect="x", expected_t_saving_on_target=1, source="test", **kw)


NOOP = '''from v4.api import Precondition, Rule
from v4.api import dv
def _t(c): return []
def _a(c, m): return c
RULE = Rule(name="{name}", domain="dv", kind="rewrite", error_class="exact", resource_class="unitary",
            precondition=Precondition(families=("dv_angle",)),
            source="test", idea="never fires", trigger=_t, apply=_a)
'''

RECON_ONLY = '''from v4.api import Precondition, Rule
from v4.api import dv
def _t(c): return []
def _a(c, m): return c
RULE = Rule(name="{name}", domain="dv", kind="rewrite", error_class="exact", resource_class="unitary",
            precondition=Precondition(families=("dv_recon",), needs=("toffoli",)),
            source="test", idea="recon only", trigger=_t, apply=_a)
'''

FIRE_AND_FAIL = '''from v4.api import Precondition, Rule
from v4.api import dv
def _t(c):
    if not dv.is_angle_circuit(c): return []
    return [i for i, op in enumerate(c.ops) if op[0] == "h"][:2]
def _a(c, m):
    ops = list(c.ops); ops[m] = ("x", ops[m][1], None)        # a WRONG rewrite that does fire
    return dv.with_ops(c, ops)
RULE = Rule(name="{name}", domain="dv", kind="rewrite", error_class="exact", resource_class="unitary",
            precondition=Precondition(families=("dv_angle",)),
            source="test", idea="fires and fails", trigger=_t, apply=_a)
'''


def _writer(tmp_path, template):
    def implement(card, ctx):
        p = Path("v4/rules/candidates") / f"{card['name']}.py"
        p.write_text(template.format(name=card["name"]))
        return p
    return implement


def _cleanup(names):
    for n in names:
        p = Path("v4/rules/candidates") / f"{n}.py"
        if p.exists():
            p.unlink()


# ------------------------------------------------------------------------------------------ outcomes
def test_no_trigger_is_an_idea_level_failure(tmp_path):
    names = []

    def scout(ctx):
        n = f"t_noop_{ctx['label']}_{len(names)}"
        names.append(n)
        return _card(n)
    lp = L.Loop(_cfg(tmp_path, budget=2, loops=1), scout, _writer(tmp_path, NOOP), tmp_path)
    try:
        out = lp.run()
        rows = [json.loads(x) for x in (tmp_path / "attempts.jsonl").read_text().splitlines()]
        assert {r["kind"] for r in rows} == {"no_trigger"}
        assert {r["level"] for r in rows} == {L.IDEA}
        assert out["attempts_used"] == 2
        assert lp.book == B.floor_tier() or [r.name for r in lp.book] == [r.name for r in B.floor_tier()]
    finally:
        _cleanup(names)


def test_precondition_exclusion_is_free_and_not_a_rejection(tmp_path):
    names = []

    def scout(ctx):
        n = f"t_recon_{ctx['label']}"
        names.append(n)
        return _card(n)
    lp = L.Loop(_cfg(tmp_path, budget=1, loops=1), scout, _writer(tmp_path, RECON_ONLY), tmp_path)
    try:
        lp.run()
        rows = [json.loads(x) for x in (tmp_path / "attempts.jsonl").read_text().splitlines()]
        assert rows[0]["kind"] == "excluded" and rows[0]["level"] == L.IDEA
        assert rows[0]["feedback"]["excluded"], "the exclusion reason must be reported back"
    finally:
        _cleanup(names)


def test_fire_and_fail_retries_the_implementer_and_keeps_the_idea(tmp_path):
    """V4_README 5.3 row 3: trigger matches, rewrite fails -> IMPLEMENTATION level, narrow the guard."""
    seen, names = [], []

    def scout(ctx):
        n = "t_firefail"
        names.append(n)
        seen.append("scout")
        return _card(n)

    def implement(card, ctx):
        seen.append(("impl", ctx["try_"], bool(ctx["feedback"])))
        p = Path("v4/rules/candidates") / f"{card['name']}.py"
        p.write_text(FIRE_AND_FAIL.format(name=card["name"]))
        return p
    lp = L.Loop(_cfg(tmp_path, budget=1, loops=1, max_attempts_per_circuit=3), scout, implement,
                tmp_path)
    try:
        lp.run()
        tries = [s for s in seen if isinstance(s, tuple)]
        assert len(tries) == 3, tries                       # the implementer was retried, not the scout
        assert seen.count("scout") == 1
        assert tries[1][2] and tries[2][2], "the retry must carry the failure feedback"
        rows = [json.loads(x) for x in (tmp_path / "attempts.jsonl").read_text().splitlines()]
        assert all(r["level"] == L.IMPL for r in rows), [r["kind"] for r in rows]
    finally:
        _cleanup(names)


def test_prefilter_rejects_a_zero_headroom_card_before_any_code(tmp_path):
    called = []

    def scout(ctx):
        return _card("t_never_written", lever="ancilla_reconstruction")   # 0 on a dv_angle circuit

    def implement(card, ctx):
        called.append(card)
        return None
    lp = L.Loop(_cfg(tmp_path, budget=1, loops=1), scout, implement, tmp_path)
    lp.run()
    assert not called, "the implementer must never be called for a prefiltered card"
    rows = [json.loads(x) for x in (tmp_path / "attempts.jsonl").read_text().splitlines()]
    assert rows[0]["kind"] == "prefiltered" and "headroom" in rows[0]["feedback"]["summary"]


def test_prefilter_rejects_a_rotation_synthesis_card(tmp_path):
    rep = L.FP.report("qft_8", 1e-3, B.floor_tier())
    card = _card("t_gs", lever="angle_cost", identity="use a better gridsynth for every rz")
    assert "rotation synthesis" in L.FP.prefilter(card, rep)


def test_prefilter_rejects_an_overclaimed_gain(tmp_path):
    rep = L.FP.report("qft_8", 1e-3, B.floor_tier())
    card = _card("t_big", lever="rotation_count")
    card["expected_t_saving_on_target"] = rep.current_t + 1
    assert "exceeds the circuit's whole T-count" in L.FP.prefilter(card, rep)


# ------------------------------------------------------------------------------------------ admission
def test_admission_refuses_a_rule_that_raises_t_anywhere():
    """V4_README 5.2. A rule that makes qft_8 worse must not enter the book even if it helps elsewhere."""
    import v4.rules.floor.pauli_frame_rotation_merge as _  # noqa: F401  (ensure the package imports)
    cfg = L.LoopConfig(circuit_order=("qft_8",), tag="test")
    bk = B.floor_tier()

    class Worse:
        name = "t_worse"
        kind = "rewrite"
        tier = "accepted"
        error_class = "exact"
        resource_class = "unitary"
        precondition = __import__("v4.api", fromlist=["ANY"]).ANY
        certificate = "auto"

        def tags(self):
            return dict(error_class="exact", resource_class="unitary")

        def trigger(self, c):
            from v4.api import dv
            if not dv.is_angle_circuit(c):
                return []
            return [0]

        def apply(self, c, m):
            from v4.api import dv
            return dv.with_ops(c, list(c.ops) + [("t", (0,), None)] * 8)
    w = Worse()
    w.trigger, w.apply = w.trigger, w.apply
    new_bk, rec = L.admit(w, bk, cfg)
    assert [r.name for r in new_bk] == [r.name for r in bk], "the rule must NOT be admitted"
    assert rec.get("refused") is None or "never score worse" in rec["refused"]


# ------------------------------------------------------------------------------------------ memo
def test_the_same_book_and_circuit_is_optimised_once():
    from v4.memo import clear, optimize_memo
    clear()
    bk = B.floor_tier()
    a = optimize_memo("tfim_6", bk, 1e-3)
    b = optimize_memo("tfim_6", bk, 1e-3)
    assert a is b
    assert memo_stats()["mem_hits"] >= 1 and memo_stats()["misses"] == 1


def test_circuit_order_is_recorded_as_configuration(tmp_path):
    cfg = _cfg(tmp_path)
    lp = L.Loop(cfg, lambda ctx: None, lambda c, x: None, tmp_path)
    saved = json.loads((tmp_path / "config.json").read_text())
    assert tuple(saved["circuit_order"]) == cfg.circuit_order
    assert saved["eps"] == 1e-3


def test_the_loop_terminates_on_the_global_budget(tmp_path):
    n = []

    def scout(ctx):
        n.append(1)
        return None                       # scout_failed every time: the loop must still stop
    lp = L.Loop(_cfg(tmp_path, budget=5, loops=99), scout, lambda c, x: None, tmp_path)
    out = lp.run()
    assert out["attempts_used"] == 5 and len(n) == 5
