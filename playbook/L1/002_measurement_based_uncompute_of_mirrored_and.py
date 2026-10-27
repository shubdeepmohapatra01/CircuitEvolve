"""Generalize measurement-based AND-uncompute to a *mirrored* H-sandwiched AND pair,
even when other gates (including ones using the same ancilla as a spectator/control)
occur between the two blocks. Pattern: H a; CCZ(c1,c2,a); H a  ... stuff ...
H a; CCZ(c1,c2,a); H a, where `a` is zero-initialized before the first block and the
two CCZ's share the same control pair. The first block computes a <- AND(c1,c2) in the
Hadamard basis; the second, run on the same restored controls, is its uncompute. That
second block can be replaced by: H a; measure a -> fresh cbit; classically-controlled
CZ(c1,c2) (or Z if one control) conditioned on the outcome; reset a -- the standard
measurement-based AND-uncompute identity -- erasing a Toffoli-equivalent for the cost
of one measurement and a Clifford correction.
"""
from __future__ import annotations

from circuitevolve.circuit import Circuit, Gate
from circuitevolve.verifier import Req


def _is_and_block(gates, i, a):
    """Check gates[i:i+3] == H a; CCZ(*,*,a); H a  (ccz symmetric, a among its qubits)."""
    if i + 2 >= len(gates):
        return None
    g0, g1, g2 = gates[i], gates[i + 1], gates[i + 2]
    if g0.name != "h" or g0.qubits != (a,) or g0.cond is not None:
        return None
    if g1.name != "ccz" or a not in g1.qubits or g1.cond is not None:
        return None
    if g2.name != "h" or g2.qubits != (a,) or g2.cond is not None:
        return None
    controls = tuple(q for q in g1.qubits if q != a)
    return controls


def rewrite(c: Circuit) -> tuple[Circuit, Req]:
    gates = c.gates
    n = len(gates)

    for i in range(n):
        if gates[i].name != "h":
            continue
        a = gates[i].qubits[0]
        if a not in c.zero_init:
            continue
        controls1 = _is_and_block(gates, i, a)
        if controls1 is None:
            continue
        block1_end = i + 3  # exclusive

        # Find a later matching AND-block on the same ancilla `a` with the same control
        # set. Gates strictly between block1 and that block may touch `a` (e.g. as a
        # spectator/control in another gate) -- we don't require idleness here, only
        # that the second occurrence is itself a clean H-sandwiched AND block with the
        # same controls; the verifier simulates the whole changed span for correctness.
        found = None
        for j in range(block1_end, n):
            g = gates[j]
            if g.name != "h" or g.qubits != (a,) or g.cond is not None:
                continue
            controls2 = _is_and_block(gates, j, a)
            if controls2 is not None and frozenset(controls2) == frozenset(controls1):
                found = (j, controls2)
                break
        if found is None:
            continue

        j, controls2 = found
        block2_end = j + 3  # exclusive

        fresh_cbit = c.nc
        new_gates = []
        new_gates.extend(gates[:j])  # everything up to block2 (incl. block1), unchanged
        # Replace block2 (H a; CCZ; H a) with: H a; measure a; cond-CZ/Z(controls); reset a
        new_gates.append(Gate("h", (a,)))
        new_gates.append(Gate("measure", (a,), cbit=fresh_cbit))
        ctrl_sorted = tuple(sorted(controls2))
        if len(ctrl_sorted) == 2:
            new_gates.append(Gate("cz", ctrl_sorted, cond=fresh_cbit))
        elif len(ctrl_sorted) == 1:
            new_gates.append(Gate("z", ctrl_sorted, cond=fresh_cbit))
        new_gates.append(Gate("reset", (a,)))
        new_gates.extend(gates[block2_end:])

        new_c = Circuit(c.n, new_gates, c.nc + 1, c.zero_init)
        return new_c, Req(eps=0.0, ancillas=0, measure=True)

    return c, Req()
