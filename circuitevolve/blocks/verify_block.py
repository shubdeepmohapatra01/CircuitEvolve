"""Approximate (floating-point) verification mode for continuous-angle blocks.  FROZEN FILE.

Invariant 1: exact mode (verify.py / sim.py over Z[omega]/sqrt2^k) decides Clifford+T
acceptance; THIS module decides acceptance of rewrites of blocks that contain continuous Rz angles,
with an explicit error budget. It is listed in integrity.FROZEN; any change needs tests and an entry
in results/CHANGELOG.md.

Distance used for ACCEPT (documented choice)
-------------------------------------------
    d(U, V) = || U - e^{i phi*} V ||_2 ,   e^{i phi*} = Tr(V^dag U) / |Tr(V^dag U)|

the spectral (operator) norm after aligning the global phase with the trace phase.
  * Global phase is ignored (invariant 6); relative phases are not.
  * d is an UPPER bound on the phase-invariant operator distance min_phi ||U - e^{i phi} V||_2, so
    errors add soundly: a circuit made of blocks is within sum_b d_b of the original, plus
    #rz * eps_rz after gridsynth (whose eps is also an operator-norm bound).
  * d is computed from the difference matrix, so it resolves ~1e-15. The Hilbert-Schmidt cost
    1 - |Tr(U^dag V)|/N (bqskit's instantiation cost) loses half the digits to cancellation: its square
    root cannot resolve distances below ~1e-8, which is the size of our budget.
Every record also carries the phase-aligned Frobenius distance ||U - e^{i phi*} V||_F / sqrt(N) (<= d).

Acceptance rules
----------------
  * instance check: d(block(instance angles), rewrite(instance angles)) <= eps_block (default 1e-8);
  * a rewrite stated as a RULE over the instance angles a_i is general only if the same bound holds
    at the instance angles AND on >= 32 random angle vectors (uniform in (-pi, pi]). Exact identities
    give ~1e-15, so a rule that is right only for some angle values is caught;
  * blocks whose every gate is in {x,z,h,s,sdg,t,tdg,cx,cz} (all angles multiples of pi/4) can be
    checked EXACTLY with the D[omega] simulator (sim.py): equality up to a global phase omega^j.
Whole-circuit check (reassembly): dense unitary for n <= 10, otherwise Haar-random statevectors for
n <= 20 (max over states of 1 - |<a|b>| and of the phase-aligned vector distance).
"""
from __future__ import annotations

import math

import numpy as np

EPS_BLOCK = 1e-8
N_RANDOM_SAMPLES = 32
EXACT_GATES = frozenset({"x", "z", "h", "s", "sdg", "t", "tdg", "cx", "cz"})

_S2 = 1 / math.sqrt(2)
_FIXED = {
    "id": np.eye(2, dtype=complex),
    "x": np.array([[0, 1], [1, 0]], complex),
    "y": np.array([[0, -1j], [1j, 0]], complex),
    "z": np.diag([1, -1]).astype(complex),
    "h": np.array([[_S2, _S2], [_S2, -_S2]], complex),
    "s": np.diag([1, 1j]).astype(complex),
    "sdg": np.diag([1, -1j]).astype(complex),
    "t": np.diag([1, np.exp(1j * math.pi / 4)]),
    "tdg": np.diag([1, np.exp(-1j * math.pi / 4)]),
    "sx": 0.5 * np.array([[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]], complex),
    "sxdg": 0.5 * np.array([[1 - 1j, 1 + 1j], [1 + 1j, 1 - 1j]], complex),
    # two-qubit gates: the first listed qubit is the most significant index of the matrix
    "cx": np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], complex),
    "cz": np.diag([1, 1, 1, -1]).astype(complex),
    "swap": np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], complex),
}


def gate_matrix(name: str, angle=None) -> np.ndarray:
    """Matrix of one op. rz(a) = diag(e^{-ia/2}, e^{ia/2}); u3(th, ph, la) as in OpenQASM 2;
    'unitary' takes an explicit matrix in the angle slot."""
    if name == "rz":
        a = float(angle)
        return np.diag([np.exp(-0.5j * a), np.exp(0.5j * a)])
    if name == "u3":
        th, ph, la = (float(x) for x in angle)
        c, s = math.cos(th / 2), math.sin(th / 2)
        return np.array([[c, -np.exp(1j * la) * s],
                         [np.exp(1j * ph) * s, np.exp(1j * (ph + la)) * c]], complex)
    if name == "unitary":
        return np.asarray(angle, complex)
    return _FIXED[name]


def _apply(state: np.ndarray, M: np.ndarray, qubits, n: int) -> np.ndarray:
    """state: tensor with axes (q0, ..., q_{n-1}, batch). Apply M to `qubits` (listed order)."""
    k = len(qubits)
    if len(set(qubits)) != k or any(not 0 <= q < n for q in qubits):
        raise ValueError(f"bad qubits {qubits} for n={n}")
    G = M.reshape((2,) * (2 * k))
    out = np.tensordot(G, state, axes=(list(range(k, 2 * k)), list(qubits)))
    # out axes: [qubits..., remaining qubits in order..., batch]
    rest = [q for q in range(n) if q not in qubits]
    perm = [0] * (n + 1)
    for j, q in enumerate(qubits):
        perm[q] = j
    for j, q in enumerate(rest):
        perm[q] = k + j
    perm[n] = n
    return np.transpose(out, perm)


def apply_ops(state: np.ndarray, ops, n: int) -> np.ndarray:
    for op in ops:
        name, qs = op[0], tuple(op[1])
        ang = op[2] if len(op) > 2 else None
        state = _apply(state, gate_matrix(name, ang), qs, n)
    return state


def unitary(ops, n: int) -> np.ndarray:
    """Dense 2^n x 2^n unitary; qubit 0 is the most significant bit (bqskit / matrix convention)."""
    dim = 1 << n
    st = np.eye(dim, dtype=complex).reshape((2,) * n + (dim,))
    st = apply_ops(st, ops, n)
    return st.reshape(dim, dim)


def distance(U: np.ndarray, V: np.ndarray) -> dict:
    tr = np.trace(V.conj().T @ U)
    ph = tr / abs(tr) if abs(tr) > 1e-300 else 1.0
    D = U - ph * V
    return dict(op=float(np.linalg.norm(D, 2)), fro=float(np.linalg.norm(D) / math.sqrt(U.shape[0])))


def verify_instance(orig_ops, new_ops, n: int, eps: float = EPS_BLOCK) -> dict:
    """Accept iff d(orig, new) <= eps. Both op lists are concrete (numeric angles)."""
    d = distance(unitary(orig_ops, n), unitary(new_ops, n))
    return dict(ok=bool(d["op"] <= eps), dist=d["op"], fro=d["fro"], eps=eps, mode="approx-instance")


def verify_rule(orig_fn, new_fn, k: int, instance_angles, n: int, eps: float = EPS_BLOCK,
                samples: int = N_RANDOM_SAMPLES, seed: int = 0) -> dict:
    """General-rule check. orig_fn(a) / new_fn(a) map an angle vector (len k) to concrete op lists.
    Accept iff d <= eps at the instance angles AND at `samples` (>= 32) random angle vectors."""
    if samples < N_RANDOM_SAMPLES:
        raise ValueError("rules need >= 32 random angle samples")
    rng = np.random.default_rng(seed)
    pts = [list(instance_angles)] + [[float(x) for x in rng.uniform(-math.pi, math.pi, size=k)]
                                     for _ in range(samples)]
    dists = []
    for a in pts:
        try:
            dists.append(distance(unitary(orig_fn(a), n), unitary(new_fn(a), n))["op"])
        except (ValueError, ZeroDivisionError, OverflowError):
            dists.append(float("inf"))
    fails = sum(1 for d in dists if not d <= eps)          # NaN counts as a failure
    worst = max(range(len(dists)), key=lambda i: dists[i] if dists[i] == dists[i] else float("inf"))
    return dict(ok=fails == 0, instance_ok=bool(dists[0] <= eps), dist=dists[0],
                max_dist=dists[worst], worst_sample=worst, fails=fails, samples=samples, eps=eps,
                mode="approx-rule")


# ------------------------------------------------------------------------------ exact D[omega] mode
def is_exact_block(ops) -> bool:
    return all(op[0] in EXACT_GATES for op in ops)


def verify_exact(orig_ops, new_ops, n: int) -> dict:
    """Exact equality up to a global phase omega^j over Z[omega]/sqrt2^k (frozen sim.py)."""
    from ..ir import Circuit
    from ..sim import run
    if not (is_exact_block(orig_ops) and is_exact_block(new_ops)):
        return dict(ok=False, mode="exact", reason="non-Clifford+T gate")
    A, B = Circuit(n), Circuit(n)
    # sim.py labels qubit q as bit q of the index, our matrices use qubit 0 = MSB. Equality of two
    # circuits does not depend on the labelling as long as both sides use the same one.
    for c, ops in ((A, orig_ops), (B, new_ops)):
        for op in ops:
            c.add(op[0], *op[1])
    cand = set(range(8))
    for x in range(1 << n):
        (sa,) = run(A, x).values()
        (sb,) = run(B, x).values()
        ka = {k for k, v in sa.items() if not v.is_zero()}
        kb = {k for k, v in sb.items() if not v.is_zero()}
        if ka != kb:
            return dict(ok=False, mode="exact", reason=f"support differs on input {x}")
        cand = {j for j in cand if all(sb[k].times_omega(j) == sa[k] for k in ka)}
        if not cand:
            return dict(ok=False, mode="exact", reason=f"amplitudes differ on input {x}")
    return dict(ok=True, mode="exact", phase_omega_power=min(cand), dist=0.0)


# ------------------------------------------------------------------------------ whole circuits
def circuit_check(ops_a, ops_b, n: int, n_states: int = 4, seed: int = 0,
                  dense_max: int = 10, sv_max: int = 20) -> dict:
    """Compare two whole circuits (op lists with numeric angles).
    n <= dense_max: phase-aligned operator distance of the full unitaries.
    n <= sv_max: Haar-random input states psi; reports max over states of 1 - |<A psi|B psi>| and of
    the phase-aligned vector distance ||A psi - e^{i.} B psi|| (a lower bound on the operator distance)."""
    if n <= dense_max:
        d = distance(unitary(ops_a, n), unitary(ops_b, n))
        return dict(method="unitary", n=n, dist=d["op"], fro=d["fro"])
    if n > sv_max:
        return dict(method="skipped", n=n)
    rng = np.random.default_rng(seed)
    dim = 1 << n
    psi = rng.normal(size=(dim, n_states)) + 1j * rng.normal(size=(dim, n_states))
    psi /= np.linalg.norm(psi, axis=0)
    st = psi.reshape((2,) * n + (n_states,))
    A = apply_ops(st.copy(), ops_a, n).reshape(dim, n_states)
    B = apply_ops(st.copy(), ops_b, n).reshape(dim, n_states)
    ov = np.einsum("ij,ij->j", A.conj(), B)
    # ||A - cB||^2 = 2 - 2 Re(c <A|B>), minimised by c = conj(<A|B>) / |<A|B>|
    vd = [float(np.linalg.norm(A[:, j] - (ov[j].conj() / abs(ov[j])) * B[:, j])) for j in range(n_states)]
    return dict(method="statevector", n=n, n_states=n_states,
                one_minus_overlap=float(max(1 - abs(o) for o in ov)), dist=max(vd))
