"""Free-fermion (Gaussian) re-synthesis.   Usage: ./py technique.py IN.qasm OUT.qasm

If every non-Clifford rotation of the circuit, after pulling Cliffords out of the way, is a Pauli rotation of the
Jordan-Wigner form  exp(-i t/2 * i*g_a*g_b)  (a quadratic Majorana term, e.g. XX, YY, XY, Z, Z..ZX..), the
non-Clifford part is a Gaussian unitary = one orthogonal matrix R in SO(2n).  R is re-decomposed into at most
n(2n-1) nearest-plane Givens rotations (one rz each) plus a free Clifford.  Otherwise the input is copied.
"""
import math, shutil, sys
import numpy as np
from scipy.linalg import expm
from qiskit import QuantumCircuit, qasm2, transpile
from qiskit.quantum_info import Clifford, Pauli, Operator
from qiskit.synthesis import synth_clifford_full

BASIS = ["h", "x", "z", "s", "sdg", "cx", "rz"]
HALF = math.pi / 2


def is_clifford_angle(t, tol=1e-9):
    return abs(t / HALF - round(t / HALF)) < tol


def n_arbitrary(qc):
    c = 0
    for g in qc.data:
        if g.operation.name == "rz":
            k = float(g.operation.params[0]) / (math.pi / 4)
            if abs(k - round(k)) > 1e-9:
                c += 1
    return c


def rotations_and_clifford(qc):
    """Return (list of [Pauli(no phase), theta], final Clifford) with circuit = Clifford . prod rotations."""
    n = qc.num_qubits
    cl = Clifford(QuantumCircuit(n))
    rots = []
    for ins in qc.data:
        nm = ins.operation.name
        if nm in ("barrier", "measure"):
            continue
        qs = [qc.find_bit(q).index for q in ins.qubits]
        sub = QuantumCircuit(n)
        if nm == "rz":
            th = float(ins.operation.params[0])
            kk = int(round(th / HALF))
            th -= kk * HALF
            for _ in range(kk % 4):
                sub.s(qs[0])
            if abs(th) > 1e-9:
                z = Pauli("".join("Z" if i == qs[0] else "I" for i in reversed(range(n))))
                P = z.evolve(cl)
                sign = -1 if P.phase == 2 else 1
                rots.append((Pauli((P.z, P.x)), sign * th))
        elif nm in ("t", "tdg"):
            raise ValueError("t gate")
        else:
            getattr(sub, nm)(*qs)
        cl = cl.compose(Clifford(sub))
    return rots, cl


def majoranas(n):
    gam = []
    for j in range(n):
        for c in "XY":
            d = {i: "Z" for i in range(j)}
            d[j] = c
            gam.append(Pauli("".join(d.get(i, "I") for i in reversed(range(n)))))
    return gam


def K(N, a, b):
    M = np.zeros((N, N)); M[a, b] = 1; M[b, a] = -1
    return M


def pair_info(gam, N):
    """label of Pauli(no phase) of g_a g_b  ->  (a, b, sg) with  i*g_a*g_b = sg * Pauli."""
    d = {}
    for a in range(N):
        for b in range(a + 1, N):
            ph = gam[a].dot(gam[b])
            lab = ph.to_label()
            sg = 1 if lab.startswith("-i") else (-1 if lab.startswith("i") else 0)
            if sg == 0:
                continue
            key = Pauli((ph.z, ph.x)).to_label()
            d[key] = (a, b, sg)
    return d


def build(qc):
    n = qc.num_qubits
    N = 2 * n
    rots, cl = rotations_and_clifford(qc)
    if not rots:
        return None
    gam = majoranas(n)
    info = pair_info(gam, N)
    M = np.eye(N)
    for P, th in rots:
        key = Pauli((P.z, P.x)).to_label()
        if key not in info:
            return None                      # not quadratic in Majoranas -> technique does not apply
        a, b, sg = info[key]
        M = expm(sg * th * K(N, a, b)) @ M
    R = M.T
    new_arb_max = N * (N - 1) // 2
    if len(rots) <= new_arb_max:
        return None                          # nothing to gain
    for s_ in (1, -1):
        Rc = R.copy(); steps = []
        for c in range(N - 1):
            for r in range(N - 1, c, -1):
                x, y = Rc[r - 1, c], Rc[r, c]
                t = -math.atan2(y, x)
                Rot = np.eye(N)
                Rot[r-1, r-1] = Rot[r, r] = math.cos(t); Rot[r, r-1] = math.sin(t); Rot[r-1, r] = -math.sin(t)
                Rc = Rot @ Rc
                steps.append((r - 1, r, s_ * t))
        D = np.diag(Rc)
        if not np.allclose(Rc, np.diag(D), atol=1e-7):
            return None
        neg = [i for i in range(N) if D[i] < 0]
        seq = [(a, b, -phi) for a, b, phi in steps] + [(neg[i], neg[i+1], math.pi) for i in range(0, len(neg), 2)]
        M2 = np.eye(N)
        for a, b, phi in seq:
            M2 = expm(phi * K(N, a, b)) @ M2        # same convention as M above with sg folded in below
        # sign of generator per pair is applied when emitting; compare in the +K convention of the step list
        # (steps were built so that exp(phi*K) with phi=-s_*t undoes Rot); check reconstruction directly:
        if np.allclose(M2.T, R, atol=1e-7):
            return seq, cl, gam, info, N, n
    return None


def emit(seq, cl, gam, info, N, n):
    out = QuantumCircuit(n)
    inv = {v[:2]: (k, v[2]) for k, v in info.items()}
    for a, b, phi in seq:
        key, sg = inv[(a, b)]
        Pu = Pauli(key)
        th = sg * phi
        if is_clifford_angle(th):
            th = round(th / HALF) * HALF
        qs = [i for i in range(n) if Pu.x[i] or Pu.z[i]]
        for i in qs:
            if Pu.x[i] and Pu.z[i]: out.sdg(i); out.h(i)
            elif Pu.x[i]: out.h(i)
        for u, v in zip(qs, qs[1:]): out.cx(u, v)
        out.rz(th, qs[-1])
        for u, v in reversed(list(zip(qs, qs[1:]))): out.cx(u, v)
        for i in qs:
            if Pu.x[i] and Pu.z[i]: out.h(i); out.s(i)
            elif Pu.x[i]: out.h(i)
    out.compose(synth_clifford_full(cl), inplace=True)
    return transpile(out, basis_gates=BASIS, optimization_level=0)


def equivalent(a, b):
    A, B = Operator(a).data, Operator(b).data
    return abs(np.trace(A.conj().T @ B)) / A.shape[0] > 1 - 1e-9 and np.allclose(abs(np.vdot(A, B)) / A.shape[0], 1, atol=1e-9)


def main(src, dst):
    qc = QuantumCircuit.from_qasm_file(src)
    try:
        if qc.num_qubits > 10 or any(g.operation.name in ("t", "tdg") for g in qc.data):
            raise ValueError
        res = build(qc)
        if res is None:
            raise ValueError
        out = emit(*res)
        if n_arbitrary(out) >= n_arbitrary(qc) or not equivalent(qc, out):
            raise ValueError
        qasm2.dump(out, dst)
        print(f"applied: arbitrary rotations {n_arbitrary(qc)} -> {n_arbitrary(out)}")
    except Exception as e:  # not applicable / failed verification
        shutil.copy(src, dst)
        print("not applied, copied input", repr(e))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
