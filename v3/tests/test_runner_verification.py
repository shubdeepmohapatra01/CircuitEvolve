"""Runner verification (2026-10-20 speed change): window checks per application, whole-circuit check per rule pass
with bisection.

    .venv/bin/python -m pytest -q v3/tests/test_runner_verification.py
"""
from __future__ import annotations

from pathlib import Path

import v3.runner as R
from v3.judge import dv as J
from v3.tools.evaluate import load_rule

HAND = Path(__file__).resolve().parents[1] / "rules" / "handwritten"


def rule(name):
    for d in (HAND, HAND.parent / "candidates", HAND.parent / "rejected", HAND.parent / "accepted"):
        if (d / f"{name}.py").exists():
            return load_rule(d / f"{name}.py")
    raise FileNotFoundError(name)


def test_window_is_the_changed_middle():
    c = J.load("qft_8")
    r = rule("same_pauli_merge")
    i, k, _ = r.trigger(c)[0]
    wo, wn, qs, (p, end_old, end_new) = R.window(c, r.apply(c, (i, k, _)))
    assert p == i and end_old == k + 1 and end_new == k            # op i removed, op k changed
    assert set(qs) == {q for op in c.ops[i:k + 1] for q in op[1]}


def test_correct_rule_passes_window_and_pass_checks():
    res = R.optimize(J.load("qft_8"), [rule("same_pauli_merge")], 1e-3)
    s = res.summary()
    assert s["verify_failures"] == 0 and s["applications"] > 0 and s["whole_checks"] >= 1
    assert all(e["scope"] == "window" for e in res.log if e["accepted"])


def test_planted_bug_caught_by_window_check():
    res = R.optimize(J.load("qft_8"), [rule("same_pauli_merge_planted")], 1e-3)
    fails = [e for e in res.log if not e.get("verified", True)]
    assert fails and fails[0]["scope"] == "window"


def test_pass_check_bisects_when_windows_are_blind(monkeypatch):
    """Simulate a window-extraction bug (every window compared with itself): the whole-circuit check once per pass
    must fail, bisection must name the first corrupted application, and the circuit must be reverted before it."""
    real = R.window

    def blind(old, new):
        w = real(old, new)
        return None if w is None else (w[0], w[0], w[2], w[3])
    monkeypatch.setattr(R, "window", blind)
    c = J.load("qft_8")
    bad = rule("same_pauli_merge_planted")
    res = R.optimize(c, [bad], 1e-3)
    fails = [e for e in res.log if not e.get("verified", True)]
    assert len(fails) == 1 and "bisected" in fails[0]["scope"]
    # the first corrupted application: first accepted entry whose match has (i + k) % 10 == 0
    v = J.verify(res.circuit, c, mode="approx", eps=1e-8)
    assert v.ok, "reverted circuit must verify against the original"
    assert any(not w["ok"] for w in res.whole_checks) and any(w["ok"] for w in res.whole_checks)


def _any(name):
    for d in ("handwritten", "accepted", "retired", "rejected", "candidates"):
        p = HAND.parent / d / f"{name}.py"
        if p.exists():
            return load_rule(p)
    raise FileNotFoundError(name)


def test_superseding_is_directional():
    from v3.tools.evaluate import superseded
    weak, strong = _any("phase_polynomial_rotation_merge"), _any("same_pauli_merge")
    assert [x["rule"] for x in superseded(strong, [weak], 1e-3)] == ["phase_polynomial_rotation_merge"]
    assert superseded(weak, [strong], 1e-3) == []


def test_best_order_is_no_worse_than_either_order():
    weak, strong = _any("phase_polynomial_rotation_merge"), _any("same_pauli_merge")
    c = J.load("qft_8")
    best = R.optimize(c, [weak, strong], 1e-3)
    g = R.optimize(c, [weak, strong], 1e-3, order="gain").cost["t_count"]
    b = R.optimize(c, [weak, strong], 1e-3, order="book").cost["t_count"]
    assert best.cost["t_count"] == min(g, b) and best.order_choice["chosen"] in ("gain", "book")
    assert R.optimize(c, [weak, strong], 1e-3, order="gain").rule_order[0] == "same_pauli_merge"
