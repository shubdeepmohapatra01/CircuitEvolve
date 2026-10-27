"""P5: `branch_kraus` must agree with the FROZEN simulator wherever both can run.

This is the test that matters most in the whole build, because `v4/judge/kraus.py` is a NEW simulator
that can ACCEPT a rewrite. Its planted-bug controls (`v4/tools/planted_gate.py`) check that it rejects
what it should; these check that it computes the same thing the frozen `circuitevolve.sim.run` computes,
branch by branch, on every exact circuit where the frozen one is defined.

That cross-check is not a formality - it found two real errors. The first version of this module
hand-implemented the two gadgets, and both were wrong:

  * `and_uncompute` expands (frozen, `ir.Circuit.expand`) to `h t; measure t -> c; cz(a,b) if c; x t if c`.
    The hand-rolled version omitted the final conditional `x`, which is what returns the target to |0>.
    So the ancilla sat in |1> on the outcome-1 branch and this module's own ancilla-return and
    phase-consistency checks reported it: a CORRECT rewrite came back with a branch-coefficient spread of
    1.96 against a state distance of 2.8e-15, and a rule that had admitted was rejected.
  * `and_compute` is Gidney's specific 13-gate Clifford+T sequence, equal to a Toffoli only on the
    t = |0> subspace, not as a unitary.

Both are gone: the module expands with the frozen definition and simulates primitives only.

THE TWO CONVENTIONS. `circuitevolve/sim.py` uses bit q of a basis index for qubit q (LSB); the matrices
in `blocks/verify_block.py` - and therefore this module - use qubit 0 as the MOST significant index.
Every comparison here remaps BOTH the input index and the output amplitudes. Getting that wrong is what
made the first run of this very test report 24 mismatches out of 32 when the code was already correct.
"""
from __future__ import annotations

import numpy as np
import pytest

from circuitevolve.ir import Circuit as IRC
from circuitevolve.sim import run as frozen_run
from v4.judge import kraus as K


def lsb_to_msb(idx: int, n: int) -> int:
    """sim.py's basis index (bit q = qubit q) -> verify_block's (qubit 0 most significant)."""
    return sum(((idx >> q) & 1) << (n - 1 - q) for q in range(n))


def _frozen_state(c: IRC, x_lsb: int, m: tuple, n: int) -> np.ndarray:
    v = np.zeros(1 << n, dtype=complex)
    for idx, amp in (frozen_run(c, x_lsb, m).get(m) or {}).items():
        v[lsb_to_msb(idx, n)] = complex(amp)
    return v


def _both_gadgets(n: int = 4) -> IRC:
    c = IRC(n)
    c.add("h", 0)
    c.add("h", 1)
    c.add("and_compute", 0, 1, 3)
    c.add("cx", 3, 2)
    c.add("and_uncompute", 0, 1, 3)
    return c


def _cliffordt(n: int = 3) -> IRC:
    c = IRC(n)
    for g, qs in (("h", (0,)), ("t", (0,)), ("cx", (0, 1)), ("tdg", (1,)), ("s", (2,)),
                  ("cz", (1, 2)), ("h", (2,)), ("ccz", (0, 1, 2)), ("x", (1,)), ("sdg", (0,))):
        c.add(g, *qs)
    return c


def _toffoli_level(n: int = 4) -> IRC:
    c = IRC(n)
    c.add("h", 0)
    c.add("ccx", 0, 1, 2)
    c.add("ccz", 1, 2, 3)
    c.add("cx", 2, 3)
    c.add("h", 0)
    return c


@pytest.mark.parametrize("build,n", [(_both_gadgets, 4), (_cliffordt, 3), (_toffoli_level, 4)])
def test_branch_simulator_agrees_with_the_frozen_one(build, n):
    c = build(n)
    M = K.n_branch_points(c)
    branches = [tuple((i >> b) & 1 for b in range(M)) for i in range(1 << M)]
    checked = 0
    for x in range(1 << n):
        for m in branches:
            mine, _ = K.run_branch(c, lsb_to_msb(x, n), m, n)
            want = _frozen_state(c, x, m, n)
            assert np.allclose(mine, want, atol=1e-10), \
                (x, m, float(np.abs(mine - want).max()))
            checked += 1
    assert checked == (1 << n) * (1 << M)


def test_gadgets_are_expanded_by_the_frozen_definition_not_reimplemented():
    """The conditional `x` that returns the uncompute target to |0> must be present."""
    c = IRC(3)
    c.add("and_uncompute", 0, 1, 2)
    e = K.expand(c)
    names = [(g.name, g.cond) for g in e.gates]
    assert [n for n, _ in names] == ["h", "measure", "cz", "x"], names
    assert names[2][1] is not None and names[3][1] is not None, \
        "the cz AND the x must both be classically conditioned on the measurement"
    assert K.n_branch_points(c) == 1


def test_and_compute_is_not_a_plain_toffoli():
    """Gidney's compute equals a Toffoli only on the t = |0> subspace, which is why hand-rolling it as
    one was wrong. Shown by simulating it on an input where the target is NOT |0>."""
    c = IRC(3)
    c.add("and_compute", 0, 1, 2)
    n = 3
    toffoli = np.eye(8)
    toffoli[[6, 7]] = toffoli[[7, 6]]
    differs = 0
    for x in range(8):
        mine, _ = K.run_branch(c, lsb_to_msb(x, n), (), n)
        e = np.zeros(8, dtype=complex)
        e[lsb_to_msb(x, n)] = 1.0
        if not np.allclose(mine, toffoli @ e, atol=1e-10):
            differs += 1
    assert differs > 0, "and_compute coincided with a Toffoli on every input, which it should not"


def test_a_correct_ancilla_rewrite_with_a_continuous_angle_verifies():
    """What P5 exists for: ancillas TOGETHER WITH a continuous angle, which the frozen `relaxed` mode
    cannot express at all. The cx-rz-cx parity identity, exact, ancilla returned to |0>."""
    import circuitevolve.ir as ir
    ref_ops = [("h", (0,), None), ("cx", (0, 1), None), ("rz", (1,), 0.7)]
    ref = K.reference_state_of(ref_ops, 2)
    cand = IRC(3)
    cand.add("h", 0)
    cand.add("cx", 0, 1)
    g = ir.Gate("rz", (1,))
    object.__setattr__(g, "angle", 0.7)
    cand.gates.append(g)
    v = K.check(cand, ref, 2, 1e-9)
    assert v.ok and v.certified and v.distance < 1e-12, (v.reason, v.distance)
    assert v.leak < 1e-12 and v.n_branches == 1


def test_an_ancilla_left_entangled_is_rejected_by_the_ancilla_return_check():
    import circuitevolve.ir as ir
    ref_ops = [("h", (0,), None), ("cx", (0, 1), None), ("rz", (1,), 0.7)]
    ref = K.reference_state_of(ref_ops, 2)
    bad = IRC(3)
    bad.add("h", 0)
    bad.add("cx", 0, 1)
    g = ir.Gate("rz", (1,))
    object.__setattr__(g, "angle", 0.7)
    bad.gates.append(g)
    bad.add("h", 2)
    bad.add("cx", 2, 1)
    v = K.check(bad, ref, 2, 1e-9)
    assert not v.ok
    assert "ancilla population left outside" in v.reason
    assert abs(v.leak - 2 ** -0.5) < 1e-9, v.leak      # the leak our PKAC measurement also saw at k=4


def test_too_wide_is_reported_as_skipped_not_as_a_failure():
    import circuitevolve.ir as ir
    ref = K.reference_state_of([("h", (0,), None)], 1)
    big = IRC(K.MAX_QUBITS + 1)
    big.add("h", 0)
    v = K.check(big, ref, 1, 1e-9)
    assert not v.ok and v.method == "skipped" and "not numerically verifiable" in v.reason
