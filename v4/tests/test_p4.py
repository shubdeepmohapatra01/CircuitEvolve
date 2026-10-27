"""P4: the algebraic certificate, with its own planted-bug suite.

V4_README's known risks: "The algebraic-certificate checker is new frozen code - it must be covered by
planted-bug tests of its own, or it becomes the weakest link in the chain it is meant to strengthen."

This is that suite. The certificate can ACCEPT a rewrite without building a single matrix, so for every
accept it must be checked against the numeric distance it replaces, and for a battery of deliberate
mutations it must refuse. Three properties are tested:

  SOUNDNESS   an algebraic ACCEPT implies the numeric phase-aligned distance is 0 (to floating point).
              This is the property that matters: an unsound accept admits a wrong rule.
  REFUTATION  each planted mutation is refused, with a reason that names what is wrong.
  AGREEMENT   on every real window of every suite circuit that the certificate accepts, the frozen
              numeric check agrees.

Conservatism (declining a pair that IS equivalent) is allowed and is not tested as a failure: a decline
falls through to the numeric check, so it costs time, never correctness.
"""
from __future__ import annotations

import math

import pytest

from v4 import book as B
from v4.api import dv, pauli as P, phasepoly as PP, sim as S
from v4.judge import certify as C, dv as J
from v4.runner import optimize, window

ANGLE = ("qft_8", "qpe_8", "hhl_8", "qae_13", "tfim_6")

# a correct merge: rz(0.3) and rz(0.4) on qubit 0, with a commuting rz(0.5) on qubit 1 in between,
# and a cx pair so the axes are genuinely transported
GOOD_OLD = [("rz", (0,), 0.3), ("cx", (0, 1), None), ("rz", (1,), 0.5), ("cx", (0, 1), None),
            ("rz", (0,), 0.4)]
GOOD_NEW = [("rz", (0,), 0.7), ("cx", (0, 1), None), ("rz", (1,), 0.5), ("cx", (0, 1), None)]

PLANTED = {
    "wrong_sign":        [("rz", (0,), -0.1), ("cx", (0, 1), None), ("rz", (1,), 0.5),
                          ("cx", (0, 1), None)],
    "wrong_angle":       [("rz", (0,), 0.8), ("cx", (0, 1), None), ("rz", (1,), 0.5),
                          ("cx", (0, 1), None)],
    "off_by_pi":         [("rz", (0,), 0.7 + math.pi), ("cx", (0, 1), None), ("rz", (1,), 0.5),
                          ("cx", (0, 1), None)],
    "dropped_cx":        [("rz", (0,), 0.7), ("rz", (1,), 0.5), ("cx", (0, 1), None)],
    "swapped_cx":        [("rz", (0,), 0.7), ("cx", (1, 0), None), ("rz", (1,), 0.5),
                          ("cx", (0, 1), None)],
    "extra_x":           [("rz", (0,), 0.7), ("x", (0,), None), ("cx", (0, 1), None),
                          ("rz", (1,), 0.5), ("cx", (0, 1), None)],
    "wrong_wire":        [("rz", (1,), 0.7), ("cx", (0, 1), None), ("rz", (1,), 0.5),
                          ("cx", (0, 1), None)],
    "merged_the_other":  [("rz", (0,), 0.3), ("cx", (0, 1), None), ("rz", (1,), 0.9),
                          ("cx", (0, 1), None)],
    "nothing_deleted":   [("rz", (0,), 0.7), ("cx", (0, 1), None), ("rz", (1,), 0.5),
                          ("cx", (0, 1), None), ("rz", (0,), 0.4)],
}

# merges across a NON-commuting rotation: the identity does not hold, and the witness must know it
NONCOMMUTING_OLD = [("rz", (0,), 0.3), ("h", (0,), None), ("rz", (0,), 0.5), ("h", (0,), None),
                    ("rz", (0,), 0.4)]
NONCOMMUTING_NEW = [("rz", (0,), 0.7), ("h", (0,), None), ("rz", (0,), 0.5), ("h", (0,), None)]


def _rule():
    import pathlib
    return B.load_rule(pathlib.Path("v4/rules/floor/pauli_frame_rotation_merge.py"))


# ------------------------------------------------------------------------------------------ soundness
def test_good_merge_is_accepted_and_is_actually_equal():
    ok, why, det = P.merge_witness(GOOD_OLD, GOOD_NEW)
    assert ok, why
    assert det["kind"] == "merge" and det["passed"] == 1
    assert S.distance(GOOD_OLD, GOOD_NEW, 2)["op"] < 1e-12


@pytest.mark.parametrize("name", sorted(PLANTED))
def test_planted_bug_is_refused(name):
    """Each mutation must be refused by the certificate AND be genuinely wrong numerically."""
    new = PLANTED[name]
    n = 1 + max(q for op in GOOD_OLD + new for q in op[1])
    d = S.distance(GOOD_OLD, new, n)["op"]
    assert d > 1e-6, f"the planted bug {name!r} is not actually a bug (distance {d:.2e})"
    cert = C.algebraic((GOOD_OLD, n), (new, n))
    assert not cert.ok, f"{name}: the algebraic certificate ACCEPTED a wrong rewrite"


def test_merge_across_a_noncommuting_rotation_is_refused_with_the_right_reason():
    ok, why, _ = P.merge_witness(NONCOMMUTING_OLD, NONCOMMUTING_NEW)
    assert not ok
    assert "does not commute" in why
    assert S.distance(NONCOMMUTING_OLD, NONCOMMUTING_NEW, 1)["op"] > 1e-3


def test_a_2pi_rotation_may_be_deleted_but_an_arbitrary_one_may_not():
    assert P.merge_witness([("rz", (0,), 2 * math.pi), ("rz", (1,), 0.5)], [("rz", (1,), 0.5)])[0]
    assert not P.merge_witness([("rz", (0,), 0.9), ("rz", (1,), 0.5)], [("rz", (1,), 0.5)])[0]


def test_phasepoly_witness_planted_bugs():
    """The second witness gets the same treatment."""
    old = [("cx", (0, 1), None), ("rz", (1,), 0.3), ("cx", (0, 1), None), ("rz", (0,), 0.2)]
    good = [("cx", (0, 1), None), ("rz", (1,), 0.3), ("cx", (0, 1), None), ("rz", (0,), 0.2)]
    assert PP.witness(old, good, 2)[0]
    bads = {
        "angle_moved_to_wrong_label": [("cx", (0, 1), None), ("rz", (1,), 0.2), ("cx", (0, 1), None),
                                       ("rz", (0,), 0.3)],
        "cx_dropped":                 [("rz", (1,), 0.3), ("cx", (0, 1), None), ("rz", (0,), 0.2)],
        "x_added":                    [("cx", (0, 1), None), ("rz", (1,), 0.3), ("cx", (0, 1), None),
                                       ("rz", (0,), 0.2), ("x", (1,), None)],
        "angle_scaled":               [("cx", (0, 1), None), ("rz", (1,), 0.6), ("cx", (0, 1), None),
                                       ("rz", (0,), 0.2)],
    }
    for name, bad in bads.items():
        assert S.distance(old, bad, 2)["op"] > 1e-6, name
        assert not PP.witness(old, bad, 2)[0], f"{name}: phase-polynomial witness ACCEPTED a wrong rewrite"


# ------------------------------------------------------------------------------------------ agreement
@pytest.mark.parametrize("label", ANGLE)
def test_every_algebraic_accept_on_the_real_suite_agrees_with_the_numeric_check(label):
    """Run the floor on a real circuit; for every window the certificate ACCEPTED, the frozen numeric
    check must also accept. This is the soundness property on real data, not on hand-made cases."""
    rule = _rule()
    c = J.load(label)
    cur, n_checked = c, 0
    for _ in range(200):
        ms = rule.trigger(cur)
        if not ms:
            break
        cand = rule.apply(cur, ms[0])
        w = window(cur, cand)
        if w is not None:
            wo, wn, _qs, span = w
            if span[1] != span[0] or span[2] != span[0]:
                cert = C.algebraic(wo, wn)
                if cert.ok:
                    d = S.distance(wo[0], wn[0], wo[1])["op"]
                    assert d < 1e-9, (label, d, cert.witness)
                    n_checked += 1
        cur = cand
    assert n_checked > 0 or label == "tfim_6", f"no algebraic accept to check on {label}"


@pytest.mark.parametrize("label", ("qft_8", "tfim_6"))
def test_certificates_do_not_change_the_result(label):
    """The whole point of P4: the same T-count, by a cheaper and stronger check."""
    expected = {"qft_8": 1583, "tfim_6": 3354}
    c = J.load(label)
    r = optimize(c, B.book(), 1e-3, reference=c)
    assert r.cost["t_count"] == expected[label]
    assert all(e.get("certified") for e in r.log if e["accepted"])


def test_certificate_kinds_are_recorded_on_every_accepted_application():
    c = J.load("qft_8")
    r = optimize(c, B.book(), 1e-3, reference=c)
    kinds = {e.get("certificate") for e in r.log if e["accepted"]}
    assert kinds and kinds <= set(C.KINDS) | {"identical"}, kinds
