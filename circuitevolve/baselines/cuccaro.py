"""Cuccaro, Draper, Kutin, Moulton (2004) ripple-carry adder: 2n Toffolis, one ancilla."""
from __future__ import annotations

from ..ir import Circuit


def construct(n: int) -> Circuit:
    # qubits: 0 = carry-in ancilla c0, then interleaved (b_i, a_i), last = carry-out z
    c0 = 0
    b = [1 + 2 * i for i in range(n)]
    a = [2 + 2 * i for i in range(n)]
    z = 2 * n + 1
    circ = Circuit(2 * n + 2, registers={"a": a, "b": b, "z": [z]})
    prev = [c0] + a[:-1]

    def maj(x, y, w):
        circ.add("cx", w, y).add("cx", w, x).add("ccx", x, y, w)

    def uma(x, y, w):
        circ.add("ccx", x, y, w).add("cx", w, x).add("cx", x, y)

    for i in range(n):
        maj(prev[i], b[i], a[i])
    circ.add("cx", a[-1], z)
    for i in reversed(range(n)):
        uma(prev[i], b[i], a[i])
    return circ
