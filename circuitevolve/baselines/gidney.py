"""Ripple-carry adder with temporary logical ANDs (after Gidney 2018, "Halving the cost of quantum
addition"): 4n T, n-1 carry ancillas, measurement-based uncomputation.

Carry recurrence used: c_{i+1} = c_i XOR ((a_i XOR c_i) AND (b_i XOR c_i)), c_0 = 0.
The top carry is computed straight into the carry-out qubit z and kept.
"""
from __future__ import annotations

from ..ir import Circuit


def construct(n: int) -> Circuit:
    """Tier-A form: uses and_compute / and_uncompute gadgets."""
    a = list(range(n))
    b = list(range(n, 2 * n))
    z = 2 * n
    carries = [None] + list(range(2 * n + 1, 3 * n)) + [z]   # c_0 = None (zero), c_1..c_{n-1}, c_n = z
    circ = Circuit(3 * n, registers={"a": a, "b": b, "z": [z]})
    for i in range(n):
        c, nxt = carries[i], carries[i + 1]
        if c is not None:
            circ.add("cx", c, a[i]).add("cx", c, b[i])
        circ.add("and_compute", a[i], b[i], nxt)
        if c is not None:
            circ.add("cx", c, nxt)
    for i in reversed(range(n)):
        c, nxt = carries[i], carries[i + 1]
        if i < n - 1:
            if c is not None:
                circ.add("cx", c, nxt)
            circ.add("and_uncompute", a[i], b[i], nxt)
        if c is not None:
            circ.add("cx", c, a[i])
        circ.add("cx", a[i], b[i])
    return circ


def construct_tier_b(n: int) -> Circuit:
    """Tier-B form: the same circuit written in primitives only (H, S, T, CX, measure, ...)."""
    return construct(n).expand("gadgets")
