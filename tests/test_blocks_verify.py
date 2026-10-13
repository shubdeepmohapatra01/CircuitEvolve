"""Planted-bug suite for the approximate block verifier (circuitevolve/blocks/verify_block.py, FROZEN)."""
import math

import numpy as np
import pytest

from circuitevolve.blocks import verify_block as vb
from circuitevolve.integrity import FROZEN, frozen_digest

A = [0.37, -1.21, 2.05]


def orig(a):
    return [("h", (0,), None), ("rz", (0,), a[0]), ("cx", (0, 1), None), ("rz", (1,), a[1]),
            ("cx", (1, 2), None), ("rz", (2,), a[2]), ("cx", (0, 1), None), ("t", (1,), None)]


def test_identical_and_reordered_commuting_accepted():
    good = orig(A)
    # rz on q2 commutes with the last cx(0,1) and t q1: move it to the end
    moved = good[:5] + good[6:] + [good[5]]
    for new in (good, moved):
        r = vb.verify_instance(orig(A), new, 3)
        assert r["ok"] and r["dist"] < 1e-14


def test_global_phase_only_difference_accepted():
    new = orig(A)[:1] + [("rz", (0,), A[0] + 2 * math.pi)] + orig(A)[2:]   # = -1 * same
    assert vb.verify_instance(orig(A), new, 3)["ok"]
    minus_i = orig(A) + [("x", (2,), None), ("z", (2,), None), ("x", (2,), None), ("z", (2,), None)]
    assert vb.verify_instance(orig(A), minus_i, 3)["ok"]                    # XZXZ = -I
    # rz(pi/4) vs t: differ by a global phase only
    assert vb.verify_instance([("rz", (0,), math.pi / 4)], [("t", (0,), None)], 1)["ok"]


def test_wrong_angle_sign_rejected():
    new = orig(A)
    new[3] = ("rz", (1,), -A[1])
    r = vb.verify_instance(orig(A), new, 3)
    assert not r["ok"] and r["dist"] > 0.1


def test_dropped_gate_rejected():
    for i in range(len(orig(A))):
        new = orig(A)[:i] + orig(A)[i + 1:]
        assert not vb.verify_instance(orig(A), new, 3)["ok"], f"dropping gate {i} accepted"


def test_swapped_qubits_rejected():
    new = orig(A)
    new[2] = ("cx", (1, 0), None)
    assert not vb.verify_instance(orig(A), new, 3)["ok"]
    new = orig(A)
    new[3] = ("rz", (2,), A[1])
    assert not vb.verify_instance(orig(A), new, 3)["ok"]


def test_relative_phase_rejected():
    for extra in (("z", (0,), None), ("cz", (0, 1), None), ("s", (2,), None)):
        assert not vb.verify_instance(orig(A), orig(A) + [extra], 3)["ok"]


def test_error_budget_boundary():
    for delta, ok in ((2e-7, False), (3e-8, False), (1e-9, True)):
        new = orig(A)
        new[1] = ("rz", (0,), A[0] + delta)
        r = vb.verify_instance(orig(A), new, 3)
        assert r["ok"] is ok, (delta, r["dist"])
        assert abs(r["dist"] - abs(delta) / 2) < 1e-12        # ||rz(d) - e^{i.}I|| = |sin(d/4)|*2 ~ d/2


def test_resolution_below_hilbert_schmidt_floor():
    # 1 - |Tr|/N cannot see 1e-9; our distance does
    U = vb.unitary([("rz", (0,), 0.3)], 1)
    V = vb.unitary([("rz", (0,), 0.3 + 4e-9)], 1)
    assert 1.5e-9 < vb.distance(U, V)["op"] < 2.5e-9


def test_rule_wrong_only_for_some_angles_rejected():
    def o(a):
        return [("rz", (0,), a[0]), ("cx", (0, 1), None), ("rz", (0,), a[1])]

    # instance has a0 == a1: rz(2 a0) is right at the instance, wrong in general
    inst = [0.4, 0.4]

    def bad(a):
        return [("rz", (0,), 2 * a[0]), ("cx", (0, 1), None)]

    def good(a):
        return [("rz", (0,), a[0] + a[1]), ("cx", (0, 1), None)]

    r = vb.verify_rule(o, bad, 2, inst, 2)
    assert r["instance_ok"] and not r["ok"] and r["fails"] >= 30
    r = vb.verify_rule(o, good, 2, inst, 2)
    assert r["ok"] and r["max_dist"] < 1e-13

    # right for a0 in (0, pi) only: rz(|a0|)
    def absval(a):
        return [("rz", (0,), abs(a[0])), ("cx", (0, 1), None), ("rz", (0,), a[1])]
    r = vb.verify_rule(o, absval, 2, [0.4, 1.0], 2)
    assert r["instance_ok"] and not r["ok"]


def test_rule_needs_32_samples_and_handles_errors():
    def o(a):
        return [("rz", (0,), a[0])]
    with pytest.raises(ValueError):
        vb.verify_rule(o, o, 1, [0.1], 1, samples=8)

    def boom(a):
        raise ZeroDivisionError
    r = vb.verify_rule(o, boom, 1, [0.1], 1)
    assert not r["ok"] and r["fails"] == 33


def test_exact_mode():
    hssh = [("h", (0,), None), ("s", (0,), None), ("s", (0,), None), ("h", (0,), None)]
    assert vb.verify_exact(hssh, [("x", (0,), None)], 1)["ok"]                  # HZH = X
    assert not vb.verify_exact([("t", (0,), None)], [("tdg", (0,), None)], 1)["ok"]
    ccz = [("cx", (1, 2), None), ("tdg", (2,), None), ("cx", (0, 2), None), ("t", (2,), None),
           ("cx", (1, 2), None), ("tdg", (2,), None), ("cx", (0, 2), None), ("t", (1,), None),
           ("t", (2,), None), ("cx", (0, 1), None), ("t", (0,), None), ("tdg", (1,), None),
           ("cx", (0, 1), None)]
    swapped = [(g, tuple({0: 1, 1: 0}.get(q, q) for q in qs), a) for g, qs, a in ccz]
    assert vb.verify_exact(ccz, swapped, 3)["ok"]                               # CCZ is symmetric
    assert not vb.verify_exact(ccz, ccz[:-1], 3)["ok"]
    # global phase omega: T X T X = omega * I
    assert vb.verify_exact([("t", (0,), None), ("x", (0,), None), ("t", (0,), None), ("x", (0,), None)],
                           [], 1)["ok"]
    assert not vb.verify_exact([("rz", (0,), 0.1)], [("rz", (0,), 0.1)], 1)["ok"]  # not Clifford+T
    # agrees with approximate mode
    assert vb.verify_instance(ccz, swapped, 3)["ok"]


def test_qubit_convention_matches_bqskit():
    from bqskit import Circuit
    from bqskit.ir.gates import CNOTGate, RZGate, U3Gate
    c = Circuit(3)
    c.append_gate(U3Gate(), (0,), [0.3, 0.2, -0.4])
    c.append_gate(CNOTGate(), (0, 2))
    c.append_gate(RZGate(), (2,), [0.7])
    c.append_gate(CNOTGate(), (2, 1))
    ops = [("u3", (0,), (0.3, 0.2, -0.4)), ("cx", (0, 2), None), ("rz", (2,), 0.7), ("cx", (2, 1), None)]
    assert np.allclose(np.array(c.get_unitary()), vb.unitary(ops, 3), atol=1e-12)


def test_circuit_check_statevector_detects_error():
    rng = np.random.default_rng(1)
    n = 11
    ops = []
    for _ in range(60):
        q = int(rng.integers(n))
        ops += [("h", (q,), None), ("rz", (q,), float(rng.normal())), ("cx", (q, (q + 1) % n), None)]
    same = vb.circuit_check(ops, list(ops), n)
    assert same["method"] == "statevector" and same["dist"] < 1e-12
    bad = list(ops)
    bad[1] = ("rz", (bad[1][1][0],), bad[1][2] + 1e-3)
    assert vb.circuit_check(ops, bad, n)["dist"] > 1e-4
    small_ops = [op for op in ops if all(q < 4 for q in op[1])]
    small = vb.circuit_check(small_ops, small_ops, 4)
    assert small["method"] == "unitary"


def test_verify_block_is_frozen():
    assert "blocks/verify_block.py" in FROZEN
    assert len(frozen_digest()) == 64
