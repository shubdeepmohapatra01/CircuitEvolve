"""Exact gate-level ('By Gate') Clifford+RZ lowering with the minimal number of RZ per 1q gate.

For every maximal run of single-qubit gates (merged into one 2x2 unitary U by BQSKit's
GroupSingleQuditGatePass) we write U = C_0 RZ(a_1) C_1 ... RZ(a_k) C_k with Clifford C_i and the
minimal k in {0,1,2,3}, decided exactly from U's Bloch rotation R (3x3):
  k = 0  iff R is a signed permutation (U Clifford)
  k <= 1 iff U maps some stabiliser axis onto a stabiliser axis      (some |R_ij| = 1)
  k <= 2 iff U maps some stabiliser axis into a stabiliser plane      (some R_ij = 0)
  k = 3  otherwise (Euler RZ.RX.RZ).
No gate is dropped and no angle is approximated except: an RZ angle within ANGLE_TOL of a
multiple of pi/4 is emitted as the corresponding Clifford(+T) gate (|error| <= ANGLE_TOL).
Every remaining RZ is then synthesised with gridsynth at eps_rz, so the total error bound is
#RZ * eps_rz + (#rounded angles) * ANGLE_TOL/2 — the same accounting as arXiv:2409.00433 Table 3
(eps_total = #RZ * 1e-9 in its By Gate row).

Multi-qubit gates must already be CNOT (use `lower_to_u3cx`). Correctness of the rewrite is
checked against the input unitary for n <= 10 qubits.
"""
from __future__ import annotations

import itertools
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

ANGLE_TOL = 1e-10
S2 = 1 / math.sqrt(2)
H = np.array([[S2, S2], [S2, -S2]], complex)
S = np.diag([1, 1j]).astype(complex)
PAULI = [np.array([[0, 1], [1, 0]], complex), np.array([[0, -1j], [1j, 0]], complex),
         np.diag([1, -1]).astype(complex)]


def rz(a: float) -> np.ndarray:
    return np.diag([np.exp(-0.5j * a), np.exp(0.5j * a)])


def phase_dist(A, B) -> float:
    """min_phi ||A - e^{i phi} B||_F / sqrt(2): ~ |delta|/2 for A = B.RZ(delta); resolves ~1e-15
    (unlike 1 - |tr|/2, which only resolves |delta| >~ 1e-7 and silently drops small angles)."""
    tr = np.trace(B.conj().T @ A)
    ph = tr / abs(tr) if abs(tr) > 1e-300 else 1.0
    return float(np.linalg.norm(A - ph * B) / math.sqrt(2))


def phase_eq(A, B, tol=1e-9) -> bool:
    return phase_dist(A, B) < tol


@lru_cache(None)
def cliffords() -> tuple[tuple[str, np.ndarray], ...]:
    """The 24 single-qubit Cliffords mod phase as shortest words over {h, s} (BFS)."""
    out: list[tuple[str, np.ndarray]] = [('', np.eye(2, dtype=complex))]
    frontier = list(out)
    while frontier:
        nxt = []
        for w, M in frontier:
            for g, G in (('h', H), ('s', S)):
                M2 = G @ M  # word read left-to-right in time order: apply w then g
                if not any(phase_eq(M2, X) for _, X in out):
                    out.append((w + g, M2))
                    nxt.append((w + g, M2))
        frontier = nxt
    assert len(out) == 24
    return tuple(out)


def bloch(U: np.ndarray) -> np.ndarray:
    return np.array([[0.5 * np.real(np.trace(PAULI[i] @ U @ PAULI[j] @ U.conj().T))
                      for j in range(3)] for i in range(3)])


def _angle_of_diag(D: np.ndarray) -> float:
    """D ~ RZ(a) up to phase -> a in (-pi, pi]."""
    return float(np.angle(D[1, 1] / D[0, 0]))


def decompose_1q(U: np.ndarray, tol: float = 1e-9):
    """Return (k, seq) with seq a time-ordered list of ('C', word) / ('RZ', angle)
    such that the product equals U up to global phase, k = #RZ minimal."""
    U = np.asarray(U, complex)
    C = cliffords()
    for w, M in C:
        if phase_eq(M, U, tol):
            return 0, [('C', w)]
    R = np.abs(bloch(U))
    if np.any(np.abs(R - 1) < 1e-7):
        # find Cliffords A, B with U = B . RZ(a) . A  (time order: A, RZ, B)
        for (wa, A), (wb, B) in itertools.product(C, C):
            V = B.conj().T @ U @ A.conj().T
            if abs(V[0, 1]) < tol and abs(V[1, 0]) < tol:
                a = _angle_of_diag(V)
                if phase_eq(B @ rz(a) @ A, U, tol):
                    return 1, [('C', wa), ('RZ', a), ('C', wb)]
    if np.any(R < 1e-7):
        for (wa, A), (wb, B) in itertools.product(C, C):
            V = B.conj().T @ U @ A.conj().T  # want V ~ RZ(b) H RZ(a)
            if abs(abs(V[0, 0]) - S2) < tol and abs(abs(V[0, 1]) - S2) < tol:
                # RZ(b) H RZ(a) ~ [[1, e^{ia}], [e^{ib}, -e^{i(a+b)}]] / sqrt2 (up to phase)
                a = float(np.angle(V[0, 1] / V[0, 0]))
                b = float(np.angle(V[1, 0] / V[0, 0]))
                if phase_eq(B @ rz(b) @ H @ rz(a) @ A, U, tol):
                    return 2, [('C', wa), ('RZ', a), ('C', 'h'), ('RZ', b), ('C', wb)]
    # Euler: U ~ RZ(c) RX(b) RZ(a), RX(b) = H RZ(b) H.  In SU(2):
    # [1,1] = cos(b/2) e^{i(a+c)/2},  [1,0] = -i sin(b/2) e^{-i(a-c)/2}
    V = U / np.sqrt(np.linalg.det(U))
    b = 2 * math.atan2(abs(V[1, 0]), abs(V[1, 1]))
    p = float(np.angle(V[1, 1]))                 # (a+c)/2
    m = -math.pi / 2 - float(np.angle(V[1, 0]))  # (a-c)/2
    a, c = p + m, p - m
    seq = [('C', ''), ('RZ', a), ('C', 'h'), ('RZ', b), ('C', 'h'), ('RZ', c), ('C', '')]
    if not phase_eq(rz(c) @ H @ rz(b) @ H @ rz(a), U, 1e-7):
        raise AssertionError('Euler decomposition failed')
    return 3, seq


def classify_angle(a: float, tol: float = ANGLE_TOL):
    """Return k (0..7) if a = k pi/4 within tol, else None."""
    x = a / (math.pi / 4)
    r = round(x)
    return int(r) % 8 if abs(x - r) * math.pi / 4 <= tol else None


DISCRETE = {0: '', 1: 't', 2: 's', 3: 'st', 4: 'z', 5: 'zt', 6: 'sdg', 7: 'tdg'}


def lower_circuit(circ):
    """bqskit Circuit over {1q gates, CNOT} -> (ops, stats). ops: list of (name, qubits, angle)."""
    from bqskit.ir.gates import CNOTGate
    from bqskit.passes import GroupSingleQuditGatePass
    from serial_runtime import run_passes
    c = circ.copy()
    run_passes(c, [GroupSingleQuditGatePass()])
    ops = []
    hist = [0, 0, 0, 0]
    rounded = 0
    for op in c:
        if op.num_qudits == 1:
            k, seq = decompose_1q(np.array(op.get_unitary()))
            q = op.location[0]
            nrz = 0
            for kind, val in seq:
                if kind == 'C':
                    ops.extend((g, (q,), None) for g in val)
                else:
                    d = classify_angle(val)
                    if d is None:
                        ops.append(('rz', (q,), val))
                        nrz += 1
                    else:
                        rounded += 1
                        g = DISCRETE[d]
                        if g in ('st', 'zt'):
                            ops.extend([(g[0], (q,), None), ('t', (q,), None)])
                        elif g:
                            ops.append((g, (q,), None))
            hist[nrz] += 1
        else:
            assert op.gate == CNOTGate(), f'non-CNOT multi-qubit gate {op.gate}'
            ops.append(('cx', tuple(op.location), None))
    return ops, dict(k_hist=hist, rounded_angles=rounded)


def ops_to_qasm(ops, n: int) -> str:
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";', f'qreg q[{n}];']
    for g, qs, a in ops:
        args = ', '.join(f'q[{q}]' for q in qs)
        lines.append(f'rz({a!r}) {args};' if g == 'rz' else f'{g} {args};')
    return '\n'.join(lines) + '\n'


def ops_unitary(ops, n: int) -> np.ndarray:
    from bqskit import Circuit
    from bqskit.ir.gates import CNOTGate, HGate, RZGate, SdgGate, SGate, TdgGate, TGate, ZGate
    from bqskit.ir.gates import SqrtXGate
    G = dict(h=HGate(), s=SGate(), sdg=SdgGate(), t=TGate(), tdg=TdgGate(), z=ZGate(), cx=CNOTGate(),
             sx=SqrtXGate())
    c = Circuit(n)
    for g, qs, a in ops:
        if g == 'rz':
            c.append_gate(RZGate(), qs, [a])
        else:
            c.append_gate(G[g], qs)
    return c.get_unitary()


def tcount_ops(ops) -> tuple[int, list[float]]:
    t_fixed = sum(1 for g, _, _ in ops if g in ('t', 'tdg'))
    angles = [a for g, _, a in ops if g == 'rz']
    return t_fixed, angles


def lower_to_u3cx(path: Path, workdir: Path):
    """Load QASM as bqskit Circuit; if it has gates other than 1q/CX (shor_*), lower with qiskit
    (transpile opt 0 to {u3, cx}; ccp defined exactly via cp/cx, see CCP_DEF)."""
    from bqskit import Circuit
    from bqskit.ir.gates import CNOTGate
    import re
    raw = path.read_text()
    if re.search(r'^barrier', raw, re.M):  # qml_*: barriers carry no unitary content
        raw = re.sub(r'^barrier[^;]*;\n', '', raw, flags=re.M)
        workdir.mkdir(parents=True, exist_ok=True)
        path = workdir / f'{path.stem}_nobarrier.qasm'
        path.write_text(raw)
    c = Circuit.from_file(str(path))
    if all(op.num_qudits == 1 or op.gate == CNOTGate() for op in c):
        return c, ''
    from qiskit import QuantumCircuit, transpile
    from qiskit.qasm2 import dumps
    txt = path.read_text()
    if 'ccp' in txt:
        txt = txt.replace('include "qelib1.inc";\n', 'include "qelib1.inc";\n' + CCP_DEF, 1)
    qc = QuantumCircuit.from_qasm_str(txt)
    qc2 = transpile(qc, basis_gates=['u3', 'cx'], optimization_level=0)
    workdir.mkdir(parents=True, exist_ok=True)
    tmp = workdir / f'{path.stem}_u3cx_qiskit_o0.qasm'
    tmp.write_text(dumps(qc2))
    return Circuit.from_file(str(tmp)), 'qiskit transpile opt0 -> u3,cx (ccp via cp/cx identity)'


# Exact identity: CCP(t) = CP(t/2)[b,c] CX[a,b] CP(-t/2)[b,c] CX[a,b] CP(t/2)[a,c]
CCP_DEF = 'gate ccp(t) a,b,c { cp(t/2) b,c; cx a,b; cp(-t/2) b,c; cx a,b; cp(t/2) a,c; }\n'


# ---------------------------------------------------------------------------------------------
# Parameter-direct per-gate lowering ("paper convention", reproduces 2409.00433 Table 3 By Gate)
# U3(theta, phi, lam) = e^{i g} RZ(phi + pi) . SX . RZ(theta + pi) . SX . RZ(lam)   (matrix order)
# i.e. time order: RZ(lam), SX, RZ(theta+pi), SX, RZ(phi+pi). Each 1q gate is lowered on its own
# (no merging of neighbouring 1q gates, no gate removal). RZ angles that are multiples of pi/4
# (within ANGLE_TOL) become Clifford/T gates; every other RZ is one gridsynth call.
# ---------------------------------------------------------------------------------------------
def u3_params_of(op):
    from bqskit.ir.gates import U1Gate, U2Gate, U3Gate, RZGate
    g = op.gate
    if isinstance(g, U3Gate):
        return tuple(op.params)
    if isinstance(g, U2Gate):
        return (math.pi / 2, op.params[0], op.params[1])
    if isinstance(g, (U1Gate, RZGate)):
        return (0.0, 0.0, op.params[0])
    return None


def _emit_rz(ops, q, a):
    d = classify_angle(a)
    if d is None:
        ops.append(('rz', (q,), a))
        return 0
    g = DISCRETE[d]
    if g in ('st', 'zt'):
        ops.extend([(g[0], (q,), None), ('t', (q,), None)])
    elif g:
        ops.append((g, (q,), None))
    return 1


def lower_circuit_paramzsx(circ):
    """bqskit Circuit over {U3/U2/U1/RZ, constant 1q Cliffords, CNOT} -> (ops, stats)."""
    from bqskit.ir.gates import CNOTGate
    ops = []
    rounded = 0
    other_1q = 0
    for op in circ:
        if op.num_qudits == 1:
            q = op.location[0]
            p = u3_params_of(op)
            if p is None:  # constant gate: exact Clifford lookup, else minimal decomposition
                other_1q += 1
                k, seq = decompose_1q(np.array(op.get_unitary()))
                for kind, val in seq:
                    if kind == 'C':
                        ops.extend((g, (q,), None) for g in val)
                    else:
                        rounded += _emit_rz(ops, q, val)
                continue
            th, ph, lam = p
            rounded += _emit_rz(ops, q, lam)
            ops.append(('sx', (q,), None))
            rounded += _emit_rz(ops, q, th + math.pi)
            ops.append(('sx', (q,), None))
            rounded += _emit_rz(ops, q, ph + math.pi)
        else:
            assert op.gate == CNOTGate(), f'non-CNOT multi-qubit gate {op.gate}'
            ops.append(('cx', tuple(op.location), None))
    return ops, dict(rounded_angles=rounded, nonparam_1q=other_1q)
