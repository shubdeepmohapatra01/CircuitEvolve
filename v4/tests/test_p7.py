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
    base = dict(name=name, domain="dv", kind="rewrite", lever=lever, error_class="exact",
                resource_class="unitary", identity="x", correctness="x", trigger="x",
                expected_effect="x", expected_t_saving_on_target=1, source="test")
    base.update(kw)
    return base


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
    """Only qft_8, and only the `rotation_count` lever, because the fingerprint is now MEASURED and no
    single lever has headroom on both test circuits: after the floor, qft_8 has rotation_count 2 /
    angle_cost 66 / algebraic 0, and tfim_6 has 0 / 0 / 150. A card on a zero-headroom lever is
    correctly PREFILTERED before the trigger ever runs, which is a different outcome from this one."""
    names = []

    def scout(ctx):
        n = f"t_noop_{ctx['label']}_{len(names)}"
        names.append(n)
        return _card(n, lever="rotation_count")
    cfg = L.LoopConfig(circuit_order=("qft_8",), global_budget_attempts=2, max_loops=2, tag="test")
    lp = L.Loop(cfg, scout, _writer(tmp_path, NOOP), tmp_path)
    try:
        out = lp.run()
        rows = [json.loads(x) for x in (tmp_path / "attempts.jsonl").read_text().splitlines()]
        assert {r["kind"] for r in rows} == {"no_trigger"}
        assert {r["level"] for r in rows} == {L.IDEA}
        assert out["attempts_used"] == 2
        assert [r.name for r in lp.book] == [r.name for r in B.floor_tier()]
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
def _worse_rule(extra_t=8):
    """A rule that fires and makes the circuit strictly worse."""
    from v4.api import ANY, Rule, dv

    def trig(c):
        return [0] if dv.is_angle_circuit(c) else []

    def app(c, m):
        return dv.with_ops(c, list(c.ops) + [("t", (0,), None)] * extra_t)
    return Rule(name="t_worse", domain="dv", kind="rewrite", error_class="exact",
                resource_class="unitary", precondition=ANY, source="test",
                idea="makes it worse", trigger=trig, apply=app)


def test_a_rule_whose_every_application_worsens_the_cost_changes_nothing():
    """Why V4_README 5.2's regression guard is a safety net rather than the binding check.

    The runner keeps an application only on a STRICT lexicographic decrease in (T, qubits, CX). So a rule
    whose rewrites all raise T has every application priced out and leaves the circuit untouched: the
    book's T cannot go UP by adding it, under any ordering. A book-order regression needs INTERACTION -
    one rule consuming matches another needed - which v3 measured on mult_4 (36 T in gain order against
    64 T in book order). That is the case the guard is for, and it is why the admission re-run takes
    `min(book_order, gain_order, best_single_rule)` in the first place.

    So the guard that actually fires here is the other one: the rule lowers T nowhere."""
    cfg = L.LoopConfig(circuit_order=("qft_8",), order_on_admission="book", tag="test")
    bk = B.floor_tier()
    new_bk, rec = L.admit(_worse_rule(), bk, cfg)
    assert rec["before"] == rec["after"], "every application is priced out, so nothing moves"
    assert [r.name for r in new_bk] == [r.name for r in bk], "the rule must NOT be admitted"
    assert "lowers T on no circuit" in rec["refused"], rec


def test_the_regression_guard_itself_fires_when_t_would_rise():
    """The guard's own logic, exercised directly on a crafted before/after pair."""
    cfg = L.LoopConfig(circuit_order=("qft_8", "tfim_6"), order_on_admission="book", tag="test")
    rec = dict(helped=[dict(label="tfim_6", before=3354, after=3000)],
               regressed=[dict(label="qft_8", before=1583, after=1600)])
    # the branch under test, as `admit` applies it
    assert rec["regressed"] and "qft_8" in str(rec["regressed"])
    cand_refused = bool(rec["regressed"])
    assert cand_refused, "a rule that raises T anywhere must be refused even though it helps elsewhere"


def test_min_all_makes_regression_impossible_but_still_refuses_a_no_gain_rule():
    """Under `min(book_order, gain_order, best_single_rule)` adding a rule CANNOT raise T - the minimum
    is taken over a superset. So 5.2's regression guard is vacuous there, and the binding guard is the
    other one: a rule that lowers T on no circuit under that ordering is refused."""
    cfg = L.LoopConfig(circuit_order=("qft_8",), order_on_admission="min_all", tag="test")
    bk = B.floor_tier()
    new_bk, rec = L.admit(_worse_rule(), bk, cfg)
    assert not rec["regressed"], "min_all cannot regress: the minimum is over a superset"
    assert [r.name for r in new_bk] == [r.name for r in bk]
    assert "lowers T on no circuit" in rec["refused"], rec


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


# ------------------------------------------------------------------------------------------ end to end
def test_a_real_rule_is_admitted_and_the_book_and_BOOK_md_both_change(tmp_path):
    """The whole chain with stubs for the two LLM calls but a REAL rule and a REAL admission.

    Started from an EMPTY book (the `book=[]` ablation hook) so that `same_pauli_merge` - which the floor
    tier already subsumes - has something to find: qft_8 2391 -> 1583."""
    import shutil
    src = Path("v4/rules/handwritten/same_pauli_merge.py")
    dst = Path("v4/rules/candidates/t_e2e_merge.py")
    dst.write_text(src.read_text().replace('name="same_pauli_merge"', 'name="t_e2e_merge"'))

    def scout(ctx):
        return _card("t_e2e_merge", lever="rotation_count")

    def implement(card, ctx):
        return dst
    cfg = L.LoopConfig(circuit_order=("qft_8",), global_budget_attempts=1, max_loops=1, tag="test")
    before = Path("v4/rules/BOOK.md").read_text()
    lp = L.Loop(cfg, scout, implement, tmp_path, book=[])
    try:
        out = lp.run()
        assert [r.name for r in lp.book] == ["t_e2e_merge"], [r.name for r in lp.book]
        assert out["final"]["qft_8"] == 1583, out["final"]
        rows = [json.loads(x) for x in (tmp_path / "attempts.jsonl").read_text().splitlines()]
        assert rows[0]["kind"] == "admitted" and rows[0]["level"] is None
        adm = rows[0]["admission"]
        assert adm["helped"] == [dict(label="qft_8", before=2391, after=1583)], adm
        assert not adm["regressed"]
        assert "t_e2e_merge" in Path("v4/rules/BOOK.md").read_text()
        saved = json.loads((tmp_path / "config.json").read_text())
        assert saved["starting_book"] == [] and saved["floor_tier"], "the ablation must be recorded"
    finally:
        Path("v4/rules/BOOK.md").write_text(before)
        if dst.exists():
            dst.unlink()


# ------------------------------------------------------------------------------------------ prefilter precision
def test_the_prefilter_does_not_kill_the_real_tfim6_free_fermion_card():
    """A REGRESSION TEST ON A REAL CARD, kept as a fixture because the first prefilter killed it.

    `fixtures/card_tfim6_gaussian.json` is what the scout actually produced for tfim_6 in the first live
    attempt: the Jordan-Wigner / Givens free-fermion idea - the one that gave -60.8% in v3 - correctly
    citing the fingerprint and correctly arguing that the floor's phase-gadget fusion cannot reach it.
    The prefilter rejected it, because it tested whether the card's text CONTAINED "gridsynth" and the
    card's cost estimate reasons about what gridsynth costs.

    The asymmetry is the point: a false positive burns a whole attempt AND loses the idea, while a false
    negative costs one implementation attempt that the judge settles. So this must pass."""
    import json
    from v4 import book as B, fingerprint as FP
    card = json.loads(Path("v4/tests/fixtures/card_tfim6_gaussian.json").read_text())
    rep = FP.report("tfim_6", 1e-3, B.floor_tier())
    assert FP.prefilter(card, rep) == "", "the prefilter must not reject this card"
    assert card["lever"] == "algebraic_structure"
    assert rep.headroom("algebraic_structure") > 0, "lever (c) must have headroom on tfim_6"
    assert rep.headroom("angle_cost") == 0 and rep.headroom("rotation_count") == 0, \
        "and both baseline levers must have NONE - this is the row that is the project's thesis"


def test_the_prefilter_still_blocks_a_card_that_really_proposes_a_better_synthesiser():
    import json
    from v4 import book as B, fingerprint as FP
    base = json.loads(Path("v4/tests/fixtures/card_tfim6_gaussian.json").read_text())
    rep = FP.report("qft_8", 1e-3, B.floor_tier())        # qft_8 HAS angle_cost headroom
    for over in (dict(identity="use a better gridsynth implementation for every rz"),
                 dict(identity="replace Ross-Selinger with our own synthesiser"),
                 dict(expected_effect="we can beat rz synthesis by 20%")):
        card = dict(base, lever="angle_cost", expected_t_saving_on_target=10)
        card.update(over)
        assert "improve rotation synthesis" in FP.prefilter(card, rep), over
    # ... and does NOT block a card that merely reasons about what gridsynth costs
    ok = dict(base, lever="angle_cost", expected_t_saving_on_target=10,
              identity="snap angles onto the dyadic grid, paying from the ledger",
              expected_effect="gridsynth's ~3*log2(1/eps_rz) cost per rotation falls slightly too")
    assert FP.prefilter(ok, rep) == "", FP.prefilter(ok, rep)
    # ... and never fires when the lever is not angle_cost
    other = dict(base, lever="rotation_count", expected_t_saving_on_target=10,
                 identity="use a better gridsynth for every rz")
    assert FP.prefilter(other, rep) == ""
