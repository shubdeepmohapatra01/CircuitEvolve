"""QASM import, exact Clifford+Rz lowering, and conversions between op lists and bqskit circuits.

The lowering code is ported from experiments/bqskit_baselines/bygate_exact.py (phase 0, 'minrz'):
every maximal run of 1q gates is merged and rewritten as C0 RZ(a1) C1 ... RZ(ak) Ck with Clifford Ci
and the minimal k in {0,1,2,3}. RZ angles within ANGLE_TOL of a multiple of pi/4 become Clifford/T.
"""
from __future__ import annotations

import itertools
import math
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import REPO

QASM_DIR = REPO / "benchmarks" / "bqskit_qseed" / "qasm"
WORK = REPO / ".cache" / "blocks" / "work"   # scratch (gitignored), not results
ANGLE_TOL = 1e-10
S2 = 1 / math.sqrt(2)
H = np.array([[S2, S2], [S2, -S2]], complex)
S = np.diag([1, 1j]).astype(complex)
PAULI = [np.array([[0, 1], [1, 0]], complex), np.array([[0, -1j], [1j, 0]], complex),
         np.diag([1, -1]).astype(complex)]
DISCRETE = {0: [], 1: ["t"], 2: ["s"], 3: ["s", "t"], 4: ["z"], 5: ["z", "t"], 6: ["sdg"], 7: ["tdg"]}
# evaluation circuits must not be touched during development (task brief)
EVAL_FORBIDDEN = re.compile(r"^(add_\d+|hhl_6|mult_16|qft_32|shor_16)$")


def bench_path(name: str) -> Path:
    """'qft_5' or 'qft/qft_5' or a path -> QASM path. Refuses evaluation circuits."""
    if name.endswith(".qasm"):
        p = Path(name)
    else:
        stem = name.split("/")[-1]
        fam = stem.rsplit("_", 1)[0]
        p = QASM_DIR / fam / f"{stem}.qasm"
    if EVAL_FORBIDDEN.match(p.stem):
        raise PermissionError(f"{p.stem} is an evaluation circuit; not allowed in development")
    return p


def rz(a: float) -> np.ndarray:
    return np.diag([np.exp(-0.5j * a), np.exp(0.5j * a)])


def phase_dist(A, B) -> float:
    tr = np.trace(B.conj().T @ A)
    ph = tr / abs(tr) if abs(tr) > 1e-300 else 1.0
    return float(np.linalg.norm(A - ph * B) / math.sqrt(A.shape[0]))


def phase_eq(A, B, tol=1e-9) -> bool:
    return phase_dist(A, B) < tol


@lru_cache(None)
def cliffords():
    """The 24 single-qubit Cliffords mod phase as shortest words over {h, s} (time order)."""
    out = [("", np.eye(2, dtype=complex))]
    frontier = list(out)
    while frontier:
        nxt = []
        for w, M in frontier:
            for g, G in (("h", H), ("s", S)):
                M2 = G @ M
                if not any(phase_eq(M2, X) for _, X in out):
                    out.append((w + g, M2))
                    nxt.append((w + g, M2))
        frontier = nxt
    assert len(out) == 24
    return tuple(out)


def bloch(U):
    return np.array([[0.5 * np.real(np.trace(PAULI[i] @ U @ PAULI[j] @ U.conj().T))
                      for j in range(3)] for i in range(3)])


def decompose_1q(U, tol: float = 1e-9):
    """(k, seq): seq time-ordered ('C', word over h,s) / ('RZ', angle); product = U up to phase,
    k = number of RZ, minimal."""
    U = np.asarray(U, complex)
    C = cliffords()
    for w, M in C:
        if phase_eq(M, U, tol):
            return 0, [("C", w)]
    R = np.abs(bloch(U))
    if np.any(np.abs(R - 1) < 1e-7):
        for (wa, A), (wb, B) in itertools.product(C, C):
            V = B.conj().T @ U @ A.conj().T
            if abs(V[0, 1]) < tol and abs(V[1, 0]) < tol:
                a = float(np.angle(V[1, 1] / V[0, 0]))
                if phase_eq(B @ rz(a) @ A, U, tol):
                    return 1, [("C", wa), ("RZ", a), ("C", wb)]
    if np.any(R < 1e-7):
        for (wa, A), (wb, B) in itertools.product(C, C):
            V = B.conj().T @ U @ A.conj().T
            if abs(abs(V[0, 0]) - S2) < tol and abs(abs(V[0, 1]) - S2) < tol:
                a = float(np.angle(V[0, 1] / V[0, 0]))
                b = float(np.angle(V[1, 0] / V[0, 0]))
                if phase_eq(B @ rz(b) @ H @ rz(a) @ A, U, tol):
                    return 2, [("C", wa), ("RZ", a), ("C", "h"), ("RZ", b), ("C", wb)]
    V = U / np.sqrt(np.linalg.det(U))
    b = 2 * math.atan2(abs(V[1, 0]), abs(V[1, 1]))
    p = float(np.angle(V[1, 1]))
    m = -math.pi / 2 - float(np.angle(V[1, 0]))
    a, c = p + m, p - m
    if not phase_eq(rz(c) @ H @ rz(b) @ H @ rz(a), U, 1e-7):
        raise AssertionError("Euler decomposition failed")
    return 3, [("C", ""), ("RZ", a), ("C", "h"), ("RZ", b), ("C", "h"), ("RZ", c), ("C", "")]


def classify_angle(a: float, tol: float = ANGLE_TOL):
    """k in 0..7 if a = k*pi/4 within tol, else None."""
    x = a / (math.pi / 4)
    r = round(x)
    return int(r) % 8 if abs(x - r) * math.pi / 4 <= tol else None


def emit_rz(ops: list, q: int, a: float) -> None:
    """Append rz(a) on q; a multiple of pi/4 becomes Clifford/T gates (exact up to ANGLE_TOL)."""
    d = classify_angle(a)
    if d is None:
        ops.append(("rz", (q,), float(a)))
    else:
        ops.extend((g, (q,), None) for g in DISCRETE[d])


def seq_to_ops(seq, q: int) -> list:
    ops = []
    for kind, val in seq:
        if kind == "C":
            ops.extend((g, (q,), None) for g in val)
        else:
            emit_rz(ops, q, val)
    return ops


# ------------------------------------------------------------------------------ bqskit conversions
def _gate_tables():
    from bqskit.ir.gates import (CNOTGate, CZGate, HGate, RZGate, SdgGate, SGate, SqrtXGate,
                                 SwapGate, TdgGate, TGate, U3Gate, XGate, ZGate)
    to_bq = dict(h=HGate(), s=SGate(), sdg=SdgGate(), t=TGate(), tdg=TdgGate(), z=ZGate(), x=XGate(),
                 cx=CNOTGate(), cz=CZGate(), sx=SqrtXGate(), swap=SwapGate())
    from_bq = {type(v): k for k, v in to_bq.items()}
    return to_bq, from_bq, RZGate, U3Gate


def ops_to_bqskit(ops, n: int):
    from bqskit import Circuit
    to_bq, _, RZGate, U3Gate = _gate_tables()
    c = Circuit(n)
    for g, qs, a in ops:
        if g == "rz":
            c.append_gate(RZGate(), qs, [a])
        elif g == "u3":
            c.append_gate(U3Gate(), qs, list(a))
        else:
            c.append_gate(to_bq[g], qs)
    return c


def bqskit_to_ops(circ, location=None) -> list:
    """bqskit Circuit -> ops. `location` maps local qudit index -> global qubit (for blocks)."""
    from bqskit.ir.gates import U1Gate, U2Gate
    _, from_bq, RZGate, U3Gate = _gate_tables()
    loc = location if location is not None else list(range(circ.num_qudits))
    ops = []
    for op in circ:
        qs = tuple(loc[q] for q in op.location)
        g = op.gate
        if isinstance(g, RZGate):
            ops.append(("rz", qs, float(op.params[0])))
        elif isinstance(g, U3Gate):
            ops.append(("u3", qs, tuple(float(x) for x in op.params)))
        elif isinstance(g, U2Gate):
            ops.append(("u3", qs, (math.pi / 2, float(op.params[0]), float(op.params[1]))))
        elif isinstance(g, U1Gate):
            ops.append(("u3", qs, (0.0, 0.0, float(op.params[0]))))
        elif type(g) in from_bq:
            ops.append((from_bq[type(g)], qs, None))
        elif op.num_qudits == 1:
            ops.append(("unitary", qs, np.array(op.get_unitary())))
        else:
            raise ValueError(f"unsupported gate {g}")
    return ops


# ------------------------------------------------------------------------------ QASM import
CCP_DEF = "gate ccp(t) a,b,c { cp(t/2) b,c; cx a,b; cp(-t/2) b,c; cx a,b; cp(t/2) a,c; }\n"


def load_u3cx(name: str):
    """qseed QASM -> (bqskit Circuit over 1q gates + CX, note). Barriers stripped; circuits with
    other multi-qubit gates (shor_*) lowered exactly by qiskit transpile opt 0 to {u3, cx}."""
    from bqskit import Circuit
    from bqskit.ir.gates import CNOTGate
    path = bench_path(name)
    raw = path.read_text()
    WORK.mkdir(parents=True, exist_ok=True)
    if re.search(r"^barrier", raw, re.M):
        raw = re.sub(r"^barrier[^;]*;\n", "", raw, flags=re.M)
        path = WORK / f"{path.stem}_nobarrier.qasm"
        path.write_text(raw)
    c = Circuit.from_file(str(path))
    if all(op.num_qudits == 1 or op.gate == CNOTGate() for op in c):
        return c, ""
    from qiskit import QuantumCircuit, transpile
    from qiskit.qasm2 import dumps
    txt = raw
    if "ccp" in txt:
        txt = txt.replace('include "qelib1.inc";\n', 'include "qelib1.inc";\n' + CCP_DEF, 1)
    qc = transpile(QuantumCircuit.from_qasm_str(txt), basis_gates=["u3", "cx"], optimization_level=0)
    tmp = WORK / f"{path.stem}_u3cx_qiskit_o0.qasm"
    tmp.write_text(dumps(qc))
    return Circuit.from_file(str(tmp)), "qiskit transpile opt0 -> u3,cx"


def lower_minrz(circ) -> list:
    """bqskit Circuit over {1q, CX} -> exact Clifford+Rz ops (minimal RZ per merged 1q run)."""
    from bqskit.ir.gates import CNOTGate
    from bqskit.passes import GroupSingleQuditGatePass
    from .runtime import run_passes
    c = circ.copy()
    run_passes(c, [GroupSingleQuditGatePass()])
    ops = []
    for op in c:
        if op.num_qudits == 1:
            _, seq = decompose_1q(np.array(op.get_unitary()))
            ops.extend(seq_to_ops(seq, op.location[0]))
        else:
            assert op.gate == CNOTGate(), f"non-CNOT multi-qubit gate {op.gate}"
            ops.append(("cx", tuple(op.location), None))
    return ops


def ops_to_qasm(ops, n: int) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{n}];"]
    for g, qs, a in ops:
        args = ",".join(f"q[{q}]" for q in qs)
        if g == "rz":
            lines.append(f"rz({float(a)!r}) {args};")
        elif g == "u3":
            lines.append(f"u3({a[0]!r},{a[1]!r},{a[2]!r}) {args};")
        else:
            lines.append(f"{g} {args};")
    return "\n".join(lines) + "\n"


def qasm_to_ops(text: str) -> tuple[list, int]:
    """Parse the restricted QASM that ops_to_qasm writes (and pyzx/tket emit in our basis)."""
    n, ops = 0, []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"qreg\s+\w+\[(\d+)\];", line)
        if m:
            n += int(m.group(1))
            continue
        m = re.match(r"(\w+)(?:\(([^)]*)\))?\s+(.+);$", line)
        if not m or m.group(1) in ("OPENQASM", "include", "creg", "measure", "barrier"):
            continue
        g, arg, qs = m.group(1), m.group(2), [int(x) for x in re.findall(r"\[(\d+)\]", m.group(3))]
        if g == "rz":
            ops.append(("rz", tuple(qs), float(arg)))
        elif g == "u3":
            ops.append(("u3", tuple(qs), tuple(float(x) for x in arg.split(","))))
        else:
            ops.append((g, tuple(qs), None))
    return ops, n
