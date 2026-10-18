"""Fixed commutation table for the tier-2 gate set {h, s, sdg, t, tdg, x, z, cx, cz}.

A gate is described, on each qubit it touches, by its *role*:

    'Z'  block-diagonal in the computational basis of that qubit
         (z, s, sdg, t, tdg on it; either qubit of cz; the control of cx)
    'X'  block-diagonal in the X basis (|+>, |->) of that qubit (x on it; the target of cx)
    'O'  anything else (h)

Two gates commute EXACTLY (as matrices, not merely up to a phase) if they act on disjoint qubits, or are the very
same gate, or every shared qubit has the same role in both and that role is 'Z' or 'X'.

Proof sketch: on the shared qubits S both gates can be written sum_b P_b (x) A_b with P_b the projectors of the
product basis that is Z on the 'Z'-qubits and X on the 'X'-qubits of S; A_b and B_b act on disjoint remaining
qubits, so the products agree. The table is checked against dense matrices for every ordered pair of gates on
<= 3 qubits in tests/v2/test_tier2_rules.py (no false 'commute'). It is a sufficient condition, not a necessary one.
"""
from __future__ import annotations

ONE_Q = ("h", "s", "sdg", "t", "tdg", "x", "z")
TWO_Q = ("cx", "cz")
GATES = ONE_Q + TWO_Q
ARITY = {**{g: 1 for g in ONE_Q}, **{g: 2 for g in TWO_Q}}
DIAG_1Q = frozenset({"z", "s", "sdg", "t", "tdg"})
T_GATES = frozenset({"t", "tdg"})


def roles(g) -> dict:
    """{qubit: role} for a concrete gate (name, qubits)."""
    name, qs = g[0], g[1]
    if name in DIAG_1Q:
        return {qs[0]: "Z"}
    if name == "x":
        return {qs[0]: "X"}
    if name == "h":
        return {qs[0]: "O"}
    if name == "cz":
        return {qs[0]: "Z", qs[1]: "Z"}
    if name == "cx":
        return {qs[0]: "Z", qs[1]: "X"}
    raise ValueError(f"gate {name!r} is not in the tier-2 gate set")


def commute(g1, g2) -> bool:
    """True if the concrete gates g1 = (name, qubits) and g2 commute exactly (sufficient condition)."""
    q1, q2 = g1[1], g2[1]
    if not (set(q1) & set(q2)):
        return True
    if g1[0] == g2[0] and (tuple(q1) == tuple(q2) or (g1[0] == "cz" and set(q1) == set(q2))):
        return True
    r1, r2 = roles(g1), roles(g2)
    for q in set(q1) & set(q2):
        if r1[q] != r2[q] or r1[q] == "O":
            return False
    return True
