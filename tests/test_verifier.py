"""Verifier: one correct case and one planted bug per rule tag."""
import numpy as np
import pytest

from circuitevolve.circuit import Circuit, Gate
from circuitevolve.verifier import Req, check, verify


def C(n, spec, nc=0):
    return Circuit(n, [Gate(*s) if isinstance(s, tuple) else s for s in spec], nc)


CCX_7T = [("h", (2,)), ("cx", (1, 2)), ("tdg", (2,)), ("cx", (0, 2)), ("t", (2,)), ("cx", (1, 2)), ("tdg", (2,)),
          ("cx", (0, 2)), ("t", (1,)), ("t", (2,)), ("h", (2,)), ("cx", (0, 1)), ("t", (0,)), ("tdg", (1,)),
          ("cx", (0, 1))]


def gidney_and(c0, c1, a):
    """Gidney's temporary logical-AND: a (fresh |0>) <- c0 AND c1 with 4 T gates."""
    return [("h", (a,)), ("t", (a,)), ("cx", (c0, a)), ("cx", (c1, a)), ("cx", (a, c0)), ("cx", (a, c1)),
            ("tdg", (c0,)), ("tdg", (c1,)), ("t", (a,)), ("cx", (a, c0)), ("cx", (a, c1)), ("h", (a,)), ("s", (a,))]


MEASURED_UNCOMPUTE = [("h", (3,)), Gate("measure", (3,), cbit=0), Gate("cz", (0, 1), cond=0), Gate("x", (3,), cond=0)]


# ---- exact -----------------------------------------------------------------------------------------
def test_exact_accepts_ccx_decomposition():
    v = verify(C(3, [("ccx", (0, 1, 2))]), C(3, CCX_7T))
    assert v.ok and v.mode == "dense" and v.dist < 1e-12


def test_exact_rejects_one_flipped_t():
    bad = list(CCX_7T)
    bad[2] = ("t", (2,))
    assert not verify(C(3, [("ccx", (0, 1, 2))]), C(3, bad)).ok


def test_global_phase_is_ignored():
    assert verify(C(1, [("z", (0,))]), C(1, [("rz", (0,), np.pi)])).ok


# ---- approx ----------------------------------------------------------------------------------------
def test_approx_within_and_beyond_budget():
    old, new = C(1, [("rz", (0,), 0.3)]), C(1, [("rz", (0,), 0.3 + 1e-3)])
    assert not verify(old, new, Req()).ok                    # exact tag refuses it
    v = verify(old, new, Req(eps=1e-3))
    assert v.ok and 4e-4 < v.dist < 6e-4                     # measured distance ~ delta/2 is what gets charged
    assert not verify(old, new, Req(eps=1e-4)).ok


# ---- clean ancilla ---------------------------------------------------------------------------------
def test_ancilla_compute_use_uncompute():
    old = C(3, [("ccz", (0, 1, 2))])
    new = C(4, [("ccx", (0, 1, 3)), ("cz", (3, 2)), ("ccx", (0, 1, 3))])
    assert verify(old, new, Req(ancillas=1)).ok
    assert not verify(old, new, Req()).ok                    # extra qubit not allowed by req


def test_ancilla_left_with_garbage_is_rejected():
    old = C(3, [("ccz", (0, 1, 2))])
    new = C(4, [("ccx", (0, 1, 3)), ("cz", (3, 2))])        # forgot to uncompute: ancilla depends on input
    assert not verify(old, new, Req(ancillas=1)).ok


def test_ancilla_may_end_in_fixed_nonzero_state():
    """A catalyst/phase-gradient-style register: left in a state that does not depend on the input."""
    assert verify(C(1, [("s", (0,))]), C(2, [("h", (1,)), ("s", (0,))]), Req(ancillas=1)).ok


def test_gidney_and_is_exact_on_fresh_ancilla():
    old = C(3, [("ccz", (0, 1, 2))])
    new = C(4, gidney_and(0, 1, 3) + [("cz", (3, 2)), ("ccx", (0, 1, 3))])
    assert verify(old, new, Req(ancillas=1)).ok


# ---- measurement -----------------------------------------------------------------------------------
def test_gidney_measured_uncompute_4T_ccz():
    old = C(3, [("ccz", (0, 1, 2))])                        # 7 T
    new = C(4, gidney_and(0, 1, 3) + [("cz", (3, 2))] + MEASURED_UNCOMPUTE, nc=1)   # 4 T
    assert verify(old, new, Req(ancillas=1, measure=True)).ok
    assert not verify(old, new, Req(ancillas=1)).ok          # measurement not allowed by req


def test_measured_uncompute_missing_correction_is_rejected():
    old = C(3, [("ccz", (0, 1, 2))])
    bad = [g for g in MEASURED_UNCOMPUTE if not (isinstance(g, Gate) and g.name == "cz")]
    new = C(4, gidney_and(0, 1, 3) + [("cz", (3, 2))] + bad, nc=1)
    assert not verify(old, new, Req(ancillas=1, measure=True)).ok


def test_condition_on_unmeasured_bit_is_refused():
    new = C(2, [Gate("x", (0,), cond=0)], nc=1)
    v = verify(C(2, []), new, Req(measure=True))
    assert not v.ok and v.mode == "refused"


# ---- locality and large supports -------------------------------------------------------------------
def test_only_the_changed_segment_is_simulated():
    prefix = [("h", (q,)) for q in range(20)] + [("cx", (q, q + 1)) for q in range(19)]
    old = C(20, prefix + [("ccx", (5, 6, 7))] + prefix)
    new = C(20, prefix + [("h", (7,)), ("cx", (6, 7)), ("tdg", (7,)), ("cx", (5, 7)), ("t", (7,)), ("cx", (6, 7)),
                          ("tdg", (7,)), ("cx", (5, 7)), ("t", (6,)), ("t", (7,)), ("h", (7,)), ("cx", (5, 6)),
                          ("t", (5,)), ("tdg", (6,)), ("cx", (5, 6))] + prefix)
    v = verify(old, new)
    assert v.ok and v.support == 3 and v.mode == "dense"


def test_sampled_mode_on_wide_segment():
    old = C(10, [("h", (q,)) for q in range(10)] + [("t", (q,)) for q in range(10)])
    good = C(10, [("h", (q,)) for q in reversed(range(10))] + [("t", (q,)) for q in reversed(range(10))])
    bad = C(10, [("h", (q,)) for q in reversed(range(10))] + [("t", (q,)) for q in reversed(range(9))] + [("s", (0,))])
    v = verify(old, good)
    assert v.ok and v.mode == "sampled"
    assert not verify(old, bad).ok


def test_removing_qubits_is_refused():
    assert not verify(C(2, [("cx", (0, 1))]), C(1, [])).ok


# ---- many-site rules (check = blockwise) -----------------------------------------------------------
def _measured_ccz(a, b, c, anc, bit):
    seq = gidney_and(a, b, anc) + [("cz", (anc, c)), ("h", (anc,)), Gate("measure", (anc,), cbit=bit),
                                   Gate("cz", (a, b), cond=bit), Gate("x", (anc,), cond=bit)]
    return [Gate(*s) if isinstance(s, tuple) else s for s in seq]


def _wide(sites):
    filler = [("h", (q,)) for q in range(20)] + [("cx", (q, q + 1)) for q in range(19)]
    old, new = list(filler), list(filler)
    for k, (a, b, c) in enumerate(sites):
        old += [("ccz", (a, b, c))] + filler
        new += _measured_ccz(a, b, c, 20 + k, k) + filler
    return C(20, old), C(20 + len(sites), new, nc=len(sites))


def test_many_site_rule_on_wide_circuit():
    old, new = _wide([(0, 1, 2), (7, 9, 11), (15, 18, 19)])
    v = check(old, new, Req(ancillas=3, measure=True))
    assert v.ok and v.mode == "blockwise", v
    assert not check(old, new, Req(ancillas=2, measure=True)).ok


def test_many_site_rule_with_one_bad_site():
    old, new = _wide([(0, 1, 2), (7, 9, 11), (15, 18, 19)])
    i = max(k for k, g in enumerate(new.gates) if g.name == "cz" and g.cond == 1)
    new.gates[i] = Gate("cz", (7, 11), cond=1)               # wrong correction at the middle site
    assert not check(old, new, Req(ancillas=3, measure=True)).ok


# ---- benchmark-declared clean ancillas (zero_init) ------------------------------------------------
def _ladder_old():
    """tof_4-like: q2 is a clean ancilla holding q0 AND q1 while it is used, then uncomputed."""
    return C(4, [("ccx", (0, 1, 2)), ("cx", (2, 3)), ("ccx", (0, 1, 2))])


def _ladder_new():
    """Compute the AND into the clean ancilla with 4 T, use it, uncompute by measurement (0 T)."""
    return C(4, gidney_and(0, 1, 2) + [("cx", (2, 3)), ("h", (2,)), Gate("measure", (2,), cbit=0),
                                       Gate("cz", (0, 1), cond=0), Gate("x", (2,), cond=0)], nc=1)


def test_zero_init_ancilla_allows_measured_uncompute():
    assert check(_ladder_old(), _ladder_new(), Req(measure=True), zero_init=[2]).ok


def test_without_zero_init_the_same_rewrite_is_rejected():
    assert not check(_ladder_old(), _ladder_new(), Req(measure=True)).ok


def test_zero_init_not_assumed_after_qubit_was_touched():
    old, new = _ladder_old(), _ladder_new()
    old.gates.insert(0, Gate("cx", (3, 2)))
    new.gates.insert(0, Gate("cx", (3, 2)))                # q2 no longer |0> when the rewrite starts
    assert not check(old, new, Req(measure=True), zero_init=[2]).ok


def test_zero_init_when_shared_prefix_touches_the_ancilla():
    """Old and new both start with `h t`: the shared prefix must not hide that t starts in |0>."""
    old = C(4, [("h", (2,)), ("ccz", (0, 1, 2)), ("h", (2,)), ("cx", (2, 3)), ("ccx", (0, 1, 2))])
    new = C(4, gidney_and(0, 1, 2) + [("cx", (2, 3)), ("h", (2,)), Gate("measure", (2,), cbit=0),
                                      Gate("cz", (0, 1), cond=0), Gate("x", (2,), cond=0)], nc=1)
    assert new.gates[0] == old.gates[0]
    assert check(old, new, Req(measure=True), zero_init=[2]).ok
