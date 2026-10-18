"""Angle-method TKET entry pass (PLAN_P3 §1.3): decompose late, inside the angle method only.

tket_entry(ops, n) applies the SAME pass sequence as blocks/classical.tket_optimise and the
Baselines track (FullPeepholeOptimise -> replace_implicit_wire_swaps -> AutoRebase{CX,H,Rz} ->
RemoveRedundancies), taking core-style op tuples that may additionally contain ccx/ccz/swap,
and returning CORE_GATES ops (rz pi/4 multiples lowered to named Clifford+T gates by emit_rz).
It never runs before reconstruction — the router cascades reconstruction first, and run.py
only calls this inside the angle stage.

read_qasm_ops(text) is the angle-tolerant literal reader (regex, no eval) for inputs outside
the exact-IR pi/4 grid: gates {x,z,h,s,sdg,t,tdg,cx,cz,ccx,ccz,swap} + rz/u1/p(angle literal).
"""
from __future__ import annotations

import math

from ..blocks.circuit_io import emit_rz
from ..core.circuit import ARG_RE, GATE_LINE_RE, QREG_RE
from .router import _parse_angle

_PLAIN = {"x", "z", "h", "s", "sdg", "t", "tdg", "cx", "cz", "ccx", "ccz", "swap", "y", "sx"}
_ANGLED = {"rz", "u1", "p"}
_SKIP = ("OPENQASM", "include", "creg", "barrier", "gate ", "measure")


def read_qasm_ops(text: str) -> tuple[int, list]:
    """OpenQASM 2 -> (n, [(name, qubits, angle|None)]). Literal parsing only; raises on
    anything outside the supported gate set."""
    offs, n, ops = {}, 0, []
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line or line.startswith(_SKIP):
            continue
        m = QREG_RE.match(line)
        if m:
            offs[m.group(1)] = n
            n += int(m.group(2))
            continue
        m = GATE_LINE_RE.match(line)
        if not m:
            raise ValueError(f"cannot parse QASM line {raw!r}")
        g, arg, args = m.group(1).lower(), m.group(2), m.group(3)
        qs = []
        for a in args.split(","):
            am = ARG_RE.match(a.strip())
            if not am or am.group(1) not in offs:
                raise ValueError(f"bad qubit argument {a!r} in {raw!r}")
            qs.append(offs[am.group(1)] + int(am.group(2)))
        if g in _ANGLED:
            ang = _parse_angle(arg or "")
            if ang is None:
                raise ValueError(f"unparseable angle {arg!r} in {raw!r}")
            ops.append(("rz", tuple(qs), float(ang)))
        elif g in _PLAIN:
            ops.append((g, tuple(qs), None))
        else:
            raise ValueError(f"unsupported gate {g!r} in {raw!r}")
    return n, ops


def _emit_qasm(ops, n: int) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{n}];"]
    for g, qs, a in ops:
        if g == "rz":
            lines.append(f"rz({a!r}) q[{qs[0]}];")
        else:
            lines.append(f"{g} " + ",".join(f"q[{q}]" for q in qs) + ";")
    return "\n".join(lines) + "\n"


def tket_entry(ops, n: int) -> list:
    """ccz -> h ccx h, then the frozen Baselines pass sequence, then named-gate lowering.
    Deterministic; gains are attributed as a deterministic entry pass, never as LLM gains."""
    from pytket import OpType
    from pytket.passes import AutoRebase, FullPeepholeOptimise, RemoveRedundancies
    from pytket.qasm import circuit_from_qasm_str

    flat = []
    for g, qs, a in ops:
        if g == "ccz":
            flat += [("h", (qs[2],), None), ("ccx", qs, None), ("h", (qs[2],), None)]
        elif g == "swap":
            a_, b_ = qs
            flat += [("cx", (a_, b_), None), ("cx", (b_, a_), None), ("cx", (a_, b_), None)]
        else:
            flat.append((g, qs, a))
    c = circuit_from_qasm_str(_emit_qasm(flat, n))
    FullPeepholeOptimise().apply(c)
    c.replace_implicit_wire_swaps()
    AutoRebase({OpType.CX, OpType.H, OpType.Rz}).apply(c)
    RemoveRedundancies().apply(c)
    idx = {q: i for i, q in enumerate(c.qubits)}
    out: list = []
    for cmd in c:
        qs = tuple(idx[q] for q in cmd.qubits)
        t = cmd.op.type
        if t == OpType.Rz:
            emit_rz(out, qs[0], math.pi * float(cmd.op.params[0]))
        elif t == OpType.H:
            out.append(("h", qs, None))
        elif t == OpType.CX:
            out.append(("cx", qs, None))
        else:
            raise ValueError(f"unexpected tket op {t}")
    return out
