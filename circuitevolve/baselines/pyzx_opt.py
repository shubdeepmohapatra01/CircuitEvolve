"""Bridge to pyzx: exact-unitary ZX optimization (full_reduce + extract) as a baseline.

The output is converted back into our IR and must still pass our verifier: pyzx is treated as an
untrusted optimizer like any other.
"""
from __future__ import annotations

from fractions import Fraction

import pyzx as zx

from ..ir import Circuit

_ZPHASE = {0: [], 1: ["t"], 2: ["s"], 3: ["s", "t"], 4: ["z"], 5: ["z", "t"], 6: ["sdg"], 7: ["tdg"]}


def to_pyzx(circ: Circuit) -> "zx.Circuit":
    c = zx.Circuit(circ.n_qubits)
    m = {"x": "NOT", "z": "Z", "h": "HAD", "cx": "CNOT", "cz": "CZ", "ccx": "TOF", "ccz": "CCZ"}
    for g in circ.gates:
        if g.cond is not None or g.name in ("measure", "and_compute", "and_uncompute"):
            raise ValueError("pyzx bridge handles measurement-free, gadget-free circuits only")
        if g.name in m:
            c.add_gate(m[g.name], *g.qubits)
        elif g.name in ("s", "sdg", "t", "tdg"):
            c.add_gate("ZPhase", g.qubits[0], phase=Fraction({"s": 1, "sdg": 3, "t": 1, "tdg": 7}[g.name],
                                                               {"s": 2, "sdg": 2, "t": 4, "tdg": 4}[g.name]))
        else:
            raise ValueError(g.name)
    return c


def _zphase(out: Circuit, q: int, phase) -> None:
    k = Fraction(phase) * 4
    if k.denominator != 1:
        raise ValueError(f"non-Clifford+T phase {phase}")
    for name in _ZPHASE[int(k) % 8]:
        out.add(name, q)


def from_pyzx(zc: "zx.Circuit", registers: dict) -> Circuit:
    out = Circuit(zc.qubits, registers={k: list(v) for k, v in registers.items()})
    for g in zc.gates:
        n = g.name
        if n in ("ZPhase", "Z", "S", "T"):
            ph = getattr(g, "phase", {"Z": 1, "S": Fraction(1, 2), "T": Fraction(1, 4)}.get(n))
            if getattr(g, "adjoint", False):
                ph = -ph
            _zphase(out, g.target, ph)
        elif n == "XPhase":
            out.add("h", g.target)
            _zphase(out, g.target, g.phase)
            out.add("h", g.target)
        elif n == "HAD":
            out.add("h", g.target)
        elif n == "NOT":
            out.add("x", g.target)
        elif n == "CNOT":
            out.add("cx", g.control, g.target)
        elif n == "CZ":
            out.add("cz", g.control, g.target)
        elif n == "SWAP":
            a, b = g.control, g.target
            out.add("cx", a, b).add("cx", b, a).add("cx", a, b)
        else:
            raise ValueError(f"unsupported pyzx gate {n}")
    return out


def optimize(circ: Circuit) -> Circuit:
    zc = to_pyzx(circ).to_basic_gates()
    g = zc.to_graph()
    zx.full_reduce(g)
    ext = zx.extract_circuit(g.copy()).to_basic_gates()
    return from_pyzx(ext, circ.registers)
