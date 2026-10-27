"""Measurement-based uncomputation of an AND (Toffoli/CCZ-on-|0>-ancilla).

Pattern: a zero_init ancilla `a` is written by H a; ccz(x,y,a); H a (an AND-gate compute),
used afterward only as a control (diagonal use), then uncomputed by an identical
H a; ccz(x,y,a); H a with the same (x,y). We replace the second occurrence with the
Jones/Gidney trick: H a; measure a -> m; if m==1: cz(x,y); reset a. This is exact because
after the compute, a holds |AND(x,y)>; measuring it in the X basis collapses that AND and
the classical correction (CZ conditioned on the outcome) exactly fixes the phase kickback,
restoring a to |0> with zero T cost (CZ is Clifford), instead of paying another Toffoli.
"""
from __future__ import annotations

from dataclasses import replace

from circuitevolve.circuit import Circuit, Gate
from circuitevolve.verifier import Req


def _and_write_indices(gates, a):
    """Find indices (h_i, ccz_i, h_j) of an H a; ccz(..,a); H a block touching only `a`
    (plus the ccz controls), anywhere in gates. Returns list of (start, end, ctrl_set)."""
    hits = []
    i = 0
    n = len(gates)
    while i < n - 2:
        g0 = gates[i]
        if g0.name == "h" and g0.qubits == (a,) and g0.cond is None:
            g1 = gates[i + 1]
            if g1.name in ("ccz", "ccx") and a in g1.qubits and g1.cond is None:
                others = tuple(q for q in g1.qubits if q != a)
                if len(others) == 2 and g1.qubits[-1] == a:
                    # must be ccz-style (target==a with AND semantics); ccx also works if a is target
                    g2 = gates[i + 2]
                    if g2.name == "h" and g2.qubits == (a,) and g2.cond is None:
                        hits.append((i, i + 2, g1.name, frozenset(others)))
        i += 1
    return hits


def rewrite(c: Circuit) -> tuple[Circuit, Req]:
    gates = list(c.gates)
    n_gates = len(gates)

    for a in c.zero_init:
        blocks = _and_write_indices(gates, a)
        if len(blocks) < 2:
            continue

        # try every pair (first compute, later uncompute) with matching control set
        found = None
        for bi in range(len(blocks)):
            start1, end1, gname1, ctrl1 = blocks[bi]
            for bj in range(bi + 1, len(blocks)):
                start2, end2, gname2, ctrl2 = blocks[bj]
                if gname1 != gname2 or ctrl1 != ctrl2:
                    continue
                # check: between end1+1 .. start2-1, `a` appears only as control (diagonal use),
                # and the controls x,y (ctrl1) are untouched in between.
                ok = True
                for k in range(end1 + 1, start2):
                    gk = gates[k]
                    if a in gk.qubits:
                        # allowed only if diagonal gate with a as one of >=2 qubits (control-like),
                        # i.e. a ccz/cz/ccx-as-control... require it's a ccz/cz and a is not the
                        # "target" in an X-basis sense. We require gate name in diagonal set.
                        if gk.name not in ("ccz", "cz", "z", "s", "sdg", "t", "tdg", "rz"):
                            ok = False
                            break
                        if gk.cond is not None:
                            ok = False
                            break
                    if any(q in ctrl1 for q in gk.qubits) and gk.name not in (
                        "ccz", "cz", "z", "s", "sdg", "t", "tdg", "rz",
                    ):
                        # a control qubit touched by a non-diagonal gate invalidates the match
                        if a not in gk.qubits:
                            ok = False
                            break
                if not ok:
                    continue
                found = (start1, end1, start2, end2, ctrl1, gname2)
                break
            if found:
                break

        if not found:
            continue

        start1, end1, start2, end2, ctrl1, gname2 = found
        x, y = tuple(sorted(ctrl1))

        new_gates = []
        new_gates.extend(gates[:start2])          # everything up to (not incl) the H a of uncompute block
        new_gates.append(Gate("h", (a,)))          # H a
        m_bit = c.nc                                # fresh classical bit
        new_gates.append(Gate("measure", (a,), cbit=m_bit))
        new_gates.append(Gate("cz", (x, y), cond=m_bit))
        new_gates.append(Gate("reset", (a,)))
        new_gates.extend(gates[end2 + 1:])          # rest of circuit after the H a; ccz; H a block

        new_c = Circuit(c.n, new_gates, c.nc + 1, c.zero_init)
        return new_c, Req(eps=0.0, ancillas=0, measure=True)

    return c, Req()
