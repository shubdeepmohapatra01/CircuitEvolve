"""P0: the scaffold does not change what the judge decides, only how often it decides it.

Covered here:
  * `v4.api.pauli.conjugate` is bit-identical to v3's on every gate and every input (the flat lookup
    tables are an optimisation, not a change);
  * `frames()` agrees with conjugating each rotation back through the prefix by hand;
  * the cached `judge.dv.circuit_check` returns exactly what the frozen `core.verifier.check_circuit`
    returns, on real suite circuits and on a perturbed one;
  * `verify_memo` agrees with `verify`, and a cached approx verdict is re-decided against a tighter eps;
  * `check_frozen()` is a no-op after the first call in a process;
  * the declared preconditions are SOUND: a precondition may only exclude a circuit whose trigger
    matches nowhere (otherwise the free pre-pass would silently drop real matches);
  * the two contract tags round-trip with v3's single word.
"""
from __future__ import annotations

import itertools
import json
import math

import pytest

from circuitevolve.core import verifier as _core_verifier
from circuitevolve.v2 import verify as _v2_verify
from v4 import book as B, contracts
from v4.api import describe, pauli as P
from v4.judge import dv as J
from v4.judge.frozen import check_frozen, frozen_state
from v4.paths import MANIFEST

ANGLE = ("qft_8", "qpe_8", "tfim_6")
ALL_DV = [c["label"] for c in json.loads(MANIFEST.read_text())["circuits"] if c["domain"] == "dv"]


def test_conjugate_bit_identical_to_v3():
    import v3.api.pauli as P3
    for g in P.CLIFFORDS:
        nq = 2 if g in ("cx", "cz") else 1
        for x, z, s in itertools.product(range(1 << 4), range(1 << 4), (1, -1)):
            for qs in itertools.permutations(range(4), nq):
                assert P.conjugate((x, z, s), g, qs) == P3.conjugate((x, z, s), g, qs)


def test_conjugate_rejects_non_clifford():
    with pytest.raises(ValueError):
        P.conjugate(P.z_on(0), "t", (0,))


@pytest.mark.parametrize("label", ANGLE)
def test_frames_matches_backward_conjugation(label):
    """One forward sweep must give the same front-frame Paulis as v3's per-rotation backward pass."""
    inv = {"s": "sdg", "sdg": "s"}
    ops = J.load(label).ops
    recs = P.frames(ops)
    assert recs is not None
    for r in recs:
        prefix = [(inv.get(g, g), qs) for g, qs, _ in ops[:r.pos] if g in P.CLIFFORDS]
        p = P.z_on(ops[r.pos][1][0])
        for gi, qi in reversed(prefix):
            p = P.conjugate(p, gi, qi)
        assert p == r.p, (label, r.pos)


def test_frames_returns_none_on_foreign_gate():
    assert P.frames([("ccz", (0, 1, 2), None)]) is None


@pytest.mark.parametrize("label", ANGLE)
def test_cached_circuit_check_identical_to_frozen(label):
    c = J.load(label)
    ops, n = _v2_verify._ops_and_n(c)
    pert = [(g, q, (a + 1e-3 if g == "rz" else a)) for g, q, a in ops]
    for cand in (ops, pert):
        a = _core_verifier.check_circuit(ops, cand, n, 1e-9)
        b = J.check_circuit(ops, cand, n, 1e-9)
        assert set(a) == set(b)
        for k in a:                      # NaN == NaN is False, so compare with repr for floats
            assert repr(a[k]) == repr(b[k]), (label, k, a[k], b[k])


def test_verify_memo_agrees_and_redecides():
    c = J.load("qft_8")
    ops, n = _v2_verify._ops_and_n(c)
    pert = ([(g, q, (a + 1e-4 if g == "rz" else a)) for g, q, a in ops], n)
    loose = J.verify_memo(pert, c, mode="approx", eps=1.0)
    assert loose.ok and loose.distance > 0
    tight = J.verify_memo(pert, c, mode="approx", eps=loose.distance / 2)
    assert not tight.ok and tight.distance == loose.distance      # same measurement, stricter decision
    direct = J.verify(pert, c, mode="approx", eps=loose.distance / 2)
    assert direct.ok == tight.ok


def test_check_frozen_is_once_per_process():
    check_frozen()
    assert frozen_state()["checked"]
    assert check_frozen() == 0


@pytest.mark.parametrize("label", ALL_DV)
def test_preconditions_are_sound(label):
    """A precondition may only exclude circuits on which the trigger matches nowhere."""
    circ = J.load(label)
    d = describe(circ)
    for r in B.book():
        if r.precondition.excludes(d):
            assert r.trigger(circ) == [], (label, r.name)


def test_contract_tags_round_trip():
    for word in ("exact", "approx", "relaxed"):
        e, res = contracts.from_legacy(word)
        assert contracts.to_legacy(e, res) == word
    assert contracts.hatched("measured") and not contracts.hatched("unitary")


def test_descriptor_counts_off_grid_rotations():
    d = describe(J.load("qft_8"))
    assert d.family == "dv_angle" and d.qubits == 8
    assert d.nonclifford_rz == 48 and d.toffoli == 0


def test_ledger_bound_never_exceeds_total():
    from v4.ledger import Ledger
    L = Ledger(1e-3)
    assert L.draw("a", 3e-4) and not L.draw("b", 3e-4)
    assert L.bound(100) <= 1e-3 + 1e-18
    L.refund("a", 3e-4)
    assert L.spent == 0.0 and L.draw("b", 5e-4)


def test_opcode_budget_catches_a_hang():
    from v4.caps import run_capped
    def hang():
        while True:
            pass
    out, rep = run_capped(hang, budget=50_000)
    assert out is None and rep["exceeded"] and rep["opcodes"] >= 50_000


def test_on_grid_agrees_with_frozen_classifier():
    from circuitevolve.blocks.circuit_io import classify_angle
    from v4.api import dv
    for k in range(-8, 9):
        assert dv.on_grid(k * math.pi / 4) and classify_angle(k * math.pi / 4) is not None
    assert not dv.on_grid(0.1) and classify_angle(0.1) is None
