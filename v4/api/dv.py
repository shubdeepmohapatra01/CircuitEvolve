"""DV circuits for rules: the Clifford+Rz op list and the Toffoli-level IR.

A dv_angle circuit is `Circuit(n, ops)`; ops are (name, qubits, angle) over h s sdg x z t tdg cx cz rz, with
angle only for rz. A dv_recon circuit is an `IRCircuit` (gates x z h s sdg t tdg cx cz ccx ccz, `measure`,
classically controlled gates and the gadgets `and_compute` (4 T) / `and_uncompute` (measurement-based, 0 T)).

v3 exposed `rotation`, `with_ops`, `ir_with_gates` and the two predicates. v4 adds what every v3 rule
re-derived by hand:

    on_grid(theta)        is theta a multiple of pi/4 (so the frozen metric prices it exactly, 0 gridsynth T)
    reduce_angle(theta)   fold into (-pi, pi]
    is_clifford(op) / is_rotation(op)
    segments(ops, cut)    maximal runs of ops that contain no `cut` gate (default: Hadamard-free segments)
    touched(ops)          qubits an op list touches
    commutes(op1, op2)    disjoint support, or both diagonal
    append_ancillas(c, k) IRCircuit with k extra qubits appended (they must start and end in |0>)
    count_t(c)            T-count of an EXACT circuit under the frozen convention (7 T per Toffoli)
"""
from __future__ import annotations

import math

from circuitevolve.core.circuit import CORE_GATES, Circuit, normalize
from circuitevolve.ir import ARITY as IR_ARITY, GADGETS as IR_GADGETS, Circuit as IRCircuit, Gate as IRGate

CLIFFORD_1Q = ("h", "s", "sdg", "x", "z")
CLIFFORD_2Q = ("cx", "cz")
DIAGONAL = ("z", "s", "sdg", "t", "tdg", "rz", "cz", "ccz")
QUARTER = math.pi / 4
GRID_TOL = 1e-9


def is_angle_circuit(c) -> bool:
    return isinstance(c, Circuit)


def is_ir_circuit(c) -> bool:
    return isinstance(c, IRCircuit)


def on_grid(theta, tol: float = GRID_TOL) -> bool:
    """True if theta is a multiple of pi/4 within tol: such a rotation is a Clifford/T gate and costs no
    gridsynth T. `None` (a Clifford op's angle) counts as on-grid."""
    if theta is None:
        return True
    r = float(theta) / QUARTER
    return abs(r - round(r)) * QUARTER <= tol


def reduce_angle(theta: float) -> float:
    """Fold an angle into (-pi, pi]."""
    t = math.fmod(float(theta), 2 * math.pi)
    if t > math.pi:
        t -= 2 * math.pi
    elif t <= -math.pi:
        t += 2 * math.pi
    return t


def rotation(op):
    """The Z-rotation angle of t / tdg / rz; None for Clifford ops."""
    g, _, a = op
    if g == "t":
        return QUARTER
    if g == "tdg":
        return -QUARTER
    if g == "rz":
        return float(a)
    return None


def is_rotation(op) -> bool:
    return rotation(op) is not None


def is_clifford(op) -> bool:
    g = op[0]
    return g in CLIFFORD_1Q or g in CLIFFORD_2Q or (g == "rz" and on_grid(op[2]))


def is_diagonal(op) -> bool:
    return op[0] in DIAGONAL


def touched(ops) -> set:
    return {q for op in ops for q in op[1]}


def commutes(a, b) -> bool:
    """Sufficient (not necessary) commutation test: disjoint support, or both diagonal in Z."""
    if not (set(a[1]) & set(b[1])):
        return True
    return is_diagonal(a) and is_diagonal(b)


def segments(ops, cut=("h",)) -> list:
    """Maximal index ranges (lo, hi) of ops with no `cut` gate inside. Hadamard-free segments by default:
    the phase polynomial is an exact invariant within one of them (see v4.api.phasepoly)."""
    out, lo = [], 0
    for i, op in enumerate(ops):
        if op[0] in cut:
            if i > lo:
                out.append((lo, i))
            lo = i + 1
    if lo < len(ops):
        out.append((lo, len(ops)))
    return out


def with_ops(c: Circuit, ops) -> Circuit:
    """Result circuit; rz at multiples of pi/4 become Clifford / T gates (frozen `normalize`)."""
    return Circuit(c.n, normalize(list(ops)), dict(c.meta))


def ir_with_gates(c: IRCircuit, gates, n_qubits: int | None = None, n_cbits: int | None = None) -> IRCircuit:
    """New IRCircuit with the given gates (registers kept; n_qubits may grow for appended ancillas)."""
    return IRCircuit(c.n_qubits if n_qubits is None else n_qubits,
                     c.n_cbits if n_cbits is None else n_cbits, list(gates),
                     {k: list(v) for k, v in c.registers.items()})


def append_ancillas(c: IRCircuit, k: int) -> tuple:
    """(circuit with k extra qubits, the new qubit indices). The ancillas must start and end in |0>."""
    base = c.n_qubits
    return ir_with_gates(c, list(c.gates), n_qubits=base + int(k)), list(range(base, base + int(k)))


def count_t(c) -> int:
    """T-count of an EXACT circuit under the frozen convention (ccx / ccz = 7 T). Raises for continuous rz."""
    from circuitevolve.v2 import metric as _m, verify as _v
    return int(_m.measure(_v.as_ir(c))["t_count"])


__all__ = ["Circuit", "IRCircuit", "IRGate", "IR_ARITY", "IR_GADGETS", "CORE_GATES", "CLIFFORD_1Q",
           "CLIFFORD_2Q", "DIAGONAL", "QUARTER", "append_ancillas", "commutes", "count_t", "ir_with_gates",
           "is_angle_circuit", "is_clifford", "is_diagonal", "is_ir_circuit", "is_rotation", "normalize",
           "on_grid", "reduce_angle", "rotation", "segments", "touched", "with_ops"]
