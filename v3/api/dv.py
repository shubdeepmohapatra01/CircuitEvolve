"""DV circuit helpers for rules: the Clifford+Rz op list (name, qubits, angle) used by the judge.

A dv_angle circuit is `Circuit(n, ops)`; ops are (name, qubits, angle) over h s sdg x z t tdg cx cz rz with
angle only for rz. `rotation(op)` gives the Z-rotation angle of t / tdg / rz (None for Cliffords);
`with_ops(c, ops)` builds the result circuit, turning rz at multiples of pi/4 into Clifford/T gates.
Toffoli-level (dv_recon) circuits are `IRCircuit` objects (circuitevolve/ir.py, re-exported here): `.n_qubits`,
`.n_cbits`, `.gates` = list of `IRGate(name, qubits, cbit=None, cond=None)`, `.add(name, *qubits, cond=None)`,
`.measure(q) -> cbit`, `.copy()`. Gate names: x z h s sdg t tdg cx cz ccx ccz, measure, and the gadgets
and_compute (temporary logical AND into a CLEAN target, 4 T) / and_uncompute (measurement-based, 0 T) - see
IR_ARITY / IR_GADGETS. Extra ancilla qubits are appended as indices n, n+1, ... (they must start and end in |0>;
contract "relaxed"). `is_angle_circuit` / `is_ir_circuit` tell the two kinds apart.
"""
from __future__ import annotations

import math

from circuitevolve.core.circuit import Circuit, normalize
from circuitevolve.ir import ARITY as IR_ARITY, GADGETS as IR_GADGETS, Circuit as IRCircuit, Gate as IRGate

CLIFFORD_1Q = ("h", "s", "sdg", "x", "z")
CLIFFORD_2Q = ("cx", "cz")


def is_angle_circuit(c) -> bool:
    return isinstance(c, Circuit)


def is_ir_circuit(c) -> bool:
    return isinstance(c, IRCircuit)


def ir_with_gates(c: IRCircuit, gates, n_qubits: int | None = None, n_cbits: int | None = None) -> IRCircuit:
    """New IRCircuit with the given gates (registers kept; n_qubits may grow for appended ancillas)."""
    out = IRCircuit(c.n_qubits if n_qubits is None else n_qubits, c.n_cbits if n_cbits is None else n_cbits,
                    list(gates), {k: list(v) for k, v in c.registers.items()})
    return out


def rotation(op):
    g, _, a = op
    if g == "t":
        return math.pi / 4
    if g == "tdg":
        return -math.pi / 4
    if g == "rz":
        return float(a)
    return None


def with_ops(c: Circuit, ops) -> Circuit:
    return Circuit(c.n, normalize(list(ops)), dict(c.meta))


__all__ = ["Circuit", "CLIFFORD_1Q", "CLIFFORD_2Q", "IRCircuit", "IRGate", "IR_ARITY", "IR_GADGETS",
           "is_angle_circuit", "is_ir_circuit", "ir_with_gates", "rotation", "with_ops"]
