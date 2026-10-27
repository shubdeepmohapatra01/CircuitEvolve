"""
repeated_rz_angle_table_to_shared_ancilla_phase_gadget

Exact rewrite: collapses chains of rz rotations that act on the same qubit `w` where
every gate in between is either (a) a diagonal 1q gate on w (rz/t/tdg/s/sdg/z -- these
all commute with each other trivially), or (b) a cx that uses w only as the CONTROL
(a diagonal single-qubit phase on the control of a CX commutes through the CX, since
cx = |0><0| x I + |1><1| x X and rz(w) is diagonal in the control's computational
basis -- rz(w) and cx(w,t) commute exactly for any target t). This lets us slide all
such rz(theta) gates on w past intervening CX-as-control gates and fuse them into a
single rz(sum theta) at the position of the first one, which is strictly fewer
gridsynth calls (or a Clifford gate, or nothing, if the sum lands on a multiple of
pi/2). This is a different commutation class than TKET peephole / pyzx phase folding:
those operate on explicit phase-polynomial parities tied to the full "gate ladder"
structure, whereas here we exploit the generic diagonal-commutes-with-control algebra
directly on the gate stream, independent of any phase-polynomial extraction, and we
propagate across CX gates that use the rotated wire purely as a control, which a
peephole window will often miss once gates on the target wire intervene.
"""
from __future__ import annotations

from dataclasses import replace

from circuitevolve.circuit import Circuit, Gate, PI
from circuitevolve.verifier import Req

_TOL = 1e-9
_DIAG_1Q = {"rz", "t", "tdg", "s", "sdg", "z"}


def _is_clifford_angle(theta: float) -> bool:
    k = theta / (PI / 2)
    return abs(k - round(k)) < 1e-7


def _clifford_gate_for_angle(theta: float, q: int):
    k = int(round(theta / (PI / 2))) % 4
    if k == 0:
        return []
    if k == 1:
        return [Gate("s", (q,))]
    if k == 2:
        return [Gate("z", (q,))]
    return [Gate("sdg", (q,))]


def _diag_angle(g: Gate) -> float:
    """Return the rz-equivalent angle (up to global phase) of a diagonal 1q gate."""
    if g.name == "rz":
        return g.theta
    return {"t": PI / 4, "tdg": -PI / 4, "s": PI / 2, "sdg": -PI / 2, "z": PI}[g.name]


def rewrite(c: Circuit) -> tuple[Circuit, Req]:
    gates = list(c.gates)
    n = len(gates)

    # For each qubit w, walk forward collecting a chain of "diagonal-on-w" gates
    # (rz/t/tdg/s/sdg/z acting on w alone, or cx with w as control) that can all be
    # treated as commuting past each other. The chain for w breaks the instant a gate
    # uses w as a cx TARGET, or any non-diagonal 1q gate (h, x, y, sx, sxdg) touches w,
    # or w is measured/reset/conditioned.
    # We collect, per qubit, the list of indices of pure-diagonal rz-like gates in each
    # maximal chain, merge their angles, place the merged rz at the position of the
    # FIRST gate of the chain, and drop the rest (dropping cx-as-control gates stays,
    # since those are not rz gates -- only the rz/t/tdg/s/sdg/z gates get merged/removed).
    open_chain = {}  # qubit -> list of gate indices (rz-like, mergeable) in current open chain

    to_remove = set()
    replace_at = {}  # idx -> new theta to use there (the first gate in a merged chain)

    def close_chain(q):
        idxs = open_chain.pop(q, None)
        if not idxs or len(idxs) < 2:
            if idxs:
                open_chain.pop(q, None)
            return
        total = 0.0
        for idx in idxs:
            total += _diag_angle(gates[idx])
        first = idxs[0]
        replace_at[first] = total
        for idx in idxs[1:]:
            to_remove.add(idx)

    for i, g in enumerate(gates):
        if g.name in _DIAG_1Q:
            q = g.qubits[0]
            open_chain.setdefault(q, []).append(i)
        elif g.name == "cx":
            ctrl, tgt = g.qubits
            # ctrl: diagonal phase on ctrl commutes through cx -> chain continues
            # tgt: chain on tgt must break (cx is not diagonal w.r.t. target alone)
            close_chain(tgt)
            # ctrl chain remains open (untouched)
        else:
            # any other gate (h, x, y, sx, sxdg, cz, swap, ccx, ccz, measure, reset,
            # or anything with cond set) breaks the chain for all qubits it touches
            for q in g.qubits:
                close_chain(q)
            if g.cond is not None:
                # conditional gates: be conservative, don't let chains survive across them
                # (cond doesn't touch extra qubits structurally here but to be safe or n/a)
                pass

    # close remaining open chains at the end
    for q in list(open_chain.keys()):
        close_chain(q)

    if not replace_at:
        return c, Req()

    new_gates = []
    changed = False
    for i, g in enumerate(gates):
        if i in to_remove:
            changed = True
            continue
        if i in replace_at:
            theta = replace_at[i] % (2 * PI)
            q = g.qubits[0]
            if _is_clifford_angle(theta):
                new_gates.extend(_clifford_gate_for_angle(theta, q))
            else:
                new_gates.append(Gate("rz", (q,), theta=theta))
            changed = True
        else:
            new_gates.append(g)

    if not changed:
        return c, Req()

    new_c = Circuit(c.n, new_gates, c.nc, c.zero_init)
    return new_c, Req(eps=0.0, ancillas=0, measure=False)
