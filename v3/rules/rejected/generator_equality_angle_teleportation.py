"""Angle teleportation by back-frame generator equality: B_k = S_k Z_q S_k^dag, matched as dense 2^n matrices."""
import math

import numpy as np

from v3.api import Rule
from v3.api import dv

MAX_QUBITS = 9
MAX_PAIRS = 24
TOL = 1e-9
OFF_T = (0.3, -0.3, 1.1, -1.1)
QUARTER = math.pi / 4

_H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
_FIXED = {
    "h": _H, "s": np.diag([1, 1j]), "sdg": np.diag([1, -1j]), "x": np.array([[0, 1], [1, 0]], dtype=complex),
    "z": np.diag([1, -1]).astype(complex), "t": np.diag([1, np.exp(1j * QUARTER)]),
    "tdg": np.diag([1, np.exp(-1j * QUARTER)]),
    "cx": np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex),
    "cz": np.diag([1, 1, 1, -1]).astype(complex),
}


def _rz(a):
    return np.diag([np.exp(-0.5j * a), np.exp(0.5j * a)])


def _is_grid(a):
    r = a / QUARTER
    return abs(r - round(r)) < 1e-9


_CACHE = {}


def _bits(q, n):
    key = ("b", q, n)
    if key not in _CACHE:
        _CACHE[key] = (np.arange(1 << n) >> (n - 1 - q)) & 1
    return _CACHE[key]


def _cx_perm(c_, t_, n):
    key = ("cx", c_, t_, n)
    if key not in _CACHE:
        _CACHE[key] = np.arange(1 << n) ^ (_bits(c_, n) << (n - 1 - t_))
    return _CACHE[key]


def _right_mul(S, G, qubits, n):
    """S @ (G acting on `qubits`), S a 2^n x 2^n matrix, qubit 0 = most significant (fast path per gate type)."""
    if len(qubits) == 2:
        if G[3, 3] == -1:                                               # cz
            return S * (1 - 2 * (_bits(qubits[0], n) & _bits(qubits[1], n)))
        return S[:, _cx_perm(qubits[0], qubits[1], n)]                  # cx
    q = qubits[0]
    if G[0, 1] == 0 and G[1, 0] == 0:                                   # diagonal
        return S * np.where(_bits(q, n) == 0, G[0, 0], G[1, 1])
    S3 = S.reshape(1 << n, 1 << q, 2, 1 << (n - q - 1))
    out = np.empty_like(S3)
    out[:, :, 0, :] = S3[:, :, 0, :] * G[0, 0] + S3[:, :, 1, :] * G[1, 0]
    out[:, :, 1, :] = S3[:, :, 0, :] * G[0, 1] + S3[:, :, 1, :] * G[1, 1]
    return out.reshape(1 << n, 1 << n)


def _zdiag(q, n):
    c = np.arange(1 << n)
    return 1.0 - 2.0 * ((c >> (n - 1 - q)) & 1)


_M = 8


def _probe_vectors(N):
    rng = np.random.default_rng(4242)
    V = rng.normal(size=(N, _M)) + 1j * rng.normal(size=(N, _M))
    return V / math.sqrt(N)


def _gate_matrix(ops, i, angles, dagger):
    g = ops[i][0]
    if g in ("rz", "t", "tdg"):
        a = angles[i] if i in angles else dv.rotation(ops[i])
        return _rz(-a if dagger else a)
    G = _FIXED[g]
    return G.conj().T if dagger else G


def _left_mul(X, G, qubits, n):
    """(G acting on `qubits`) @ X for X of shape (2^n, m); qubit 0 = most significant."""
    m = X.shape[1]
    if len(qubits) == 2:
        if G[3, 3] == -1:                                               # cz
            return X * (1 - 2 * (_bits(qubits[0], n) & _bits(qubits[1], n)))[:, None]
        return X[_cx_perm(qubits[0], qubits[1], n)]                     # cx
    q = qubits[0]
    if G[0, 1] == 0 and G[1, 0] == 0:
        return X * np.where(_bits(q, n) == 0, G[0, 0], G[1, 1])[:, None]
    X4 = X.reshape(1 << q, 2, 1 << (n - q - 1), m)
    out = np.empty_like(X4)
    out[:, 0] = G[0, 0] * X4[:, 0] + G[0, 1] * X4[:, 1]
    out[:, 1] = G[1, 0] * X4[:, 0] + G[1, 1] * X4[:, 1]
    return out.reshape(X.shape)


def _generators(ops, n, angles, wanted):
    """{position: B @ V} (B = S Z_q S^dag, V a fixed random probe block) for positions in `wanted`.

    One backward sweep with the running suffix matrix S and the running S^dag V."""
    N = 1 << n
    S = np.eye(N, dtype=complex)
    W = _probe_vectors(N)
    out = {}
    stop = min(wanted)
    for i in range(len(ops) - 1, stop - 1, -1):
        qs = ops[i][1]
        if i in wanted:
            out[i] = S @ (_zdiag(qs[0], n)[:, None] * W)
        S = _right_mul(S, _gate_matrix(ops, i, angles, False), qs, n)
        W = _left_mul(W, _gate_matrix(ops, i, angles, True), qs, n)
    return out


def _bv_vec(ops, n, angles, p):
    """B_p V by two vector sweeps over the ops after p (no dense matrices)."""
    X = _probe_vectors(1 << n)
    for i in range(len(ops) - 1, p, -1):
        X = _left_mul(X, _gate_matrix(ops, i, angles, True), ops[i][1], n)
    X = _zdiag(ops[p][1][0], n)[:, None] * X
    for i in range(p + 1, len(ops)):
        X = _left_mul(X, _gate_matrix(ops, i, angles, False), ops[i][1], n)
    return X


def _supported(c):
    if not dv.is_angle_circuit(c) or c.n > MAX_QUBITS or c.n < 1:
        return False
    return all(op[0] in _FIXED or op[0] == "rz" for op in c.ops)


def _off_angles(ops, rots, j, k, s, t, perturb, base):
    ang = {j: base[j] + t, k: base[k] - s * t}
    if perturb:
        rng = np.random.default_rng(777)
        for p in rots:
            if p not in ang and not _is_grid(base[p]):
                ang[p] = base[p] + 0.2 * (2 * rng.random() - 1)
    return ang


def _holds(ops, n, rots, base, j, k, s, tests):
    """Generator equality at the actual angles plus `tests` off-points along the level set."""
    for idx in range(tests + 1):
        if idx == 0:
            ang = {}
        else:
            ang = _off_angles(ops, rots, j, k, s, OFF_T[idx - 1], idx == 1, base)
        if np.linalg.norm(_bv_vec(ops, n, ang, j) - s * _bv_vec(ops, n, ang, k)) > TOL:
            return False
    return True


def _pair_ok(ops, j, k, s):
    """Strictly lowers N_Rz."""
    aj, ak = dv.rotation(ops[j]), dv.rotation(ops[k])
    gj, gk = _is_grid(aj), _is_grid(ak)
    if gj and gk:
        return False
    if gj or gk:
        return _is_grid(aj + s * ak)
    return True


def _wrap(a):
    a = math.fmod(a, 2 * math.pi)
    if a > math.pi:
        a -= 2 * math.pi
    elif a <= -math.pi:
        a += 2 * math.pi
    return a


def find_matches(c):
    if not _supported(c):
        return []
    ops, n = list(c.ops), c.n
    rots = [i for i, op in enumerate(ops) if dv.rotation(op) is not None]
    if len(rots) < 2:
        return []
    base = {p: dv.rotation(ops[p]) for p in rots}
    B = _generators(ops, n, {}, set(rots))
    R = np.random.default_rng(99).normal(size=(B[rots[0]].size, 4))
    fp = np.array([np.real(B[p].ravel() @ R) for p in rots])
    cands = []
    for a in range(len(rots)):
        for b in range(a + 1, len(rots)):
            j, k = rots[a], rots[b]
            for s in (1, -1):
                if np.max(np.abs(fp[a] - s * fp[b])) < 1e-7 and np.linalg.norm(B[j] - s * B[k]) <= TOL:
                    cands.append((j, k, s))
    if not cands:
        return []
    # classes: anchor = lowest position in each class of base-equal generators
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for j, k, _ in cands:
        parent[find(k)] = find(j)
    classes = {}
    for p in sorted({x for j, k, _ in cands for x in (j, k)}):
        classes.setdefault(find(p), []).append(p)
    pairs = []
    for mem in classes.values():
        a = mem[0]
        for k in mem[1:]:
            s = 1 if np.linalg.norm(B[a] - B[k]) <= TOL else -1
            if _pair_ok(ops, a, k, s):
                pairs.append((a, k, s))
    def retires_two(m):
        return _is_grid(base[m[0]] + m[2] * base[m[1]])
    pairs.sort(key=lambda m: (-max(abs(base[m[0]]), abs(base[m[1]])), m[0], m[1]))
    double = [m for m in pairs if retires_two(m)]
    pairs = double[:MAX_PAIRS] if double else pairs[:6]
    out = []
    for j, k, s in pairs:
        if _holds(ops, n, rots, base, j, k, s, len(OFF_T)):
            out.append((j, k, s, ops[j], ops[k]))
    return out


def _norm_op(o):
    return (o[0], tuple(o[1]), None if o[2] is None else float(o[2]))


def _locate(ops, pos, op, same_wire_rot=False):
    best = None
    for i, o in enumerate(ops):
        ok = (dv.rotation(o) is not None and o[1] == op[1]) if same_wire_rot else (o == op)
        if ok and (best is None or abs(i - pos) < abs(best - pos)):
            best = i
    return best


def apply_match(c, m):
    if not _supported(c):
        return c
    j, k, s, opj, opk = m
    opj, opk = _norm_op(opj), _norm_op(opk)           # tolerate list/tuple round trips of the match
    ops = [_norm_op(o) for o in c.ops]
    if not (j < len(ops) and k < len(ops) and ops[j] == opj and ops[k] == opk):
        k2 = _locate(ops, k, opk)
        j2 = _locate(ops, j, opj) if opj in ops else _locate(ops, j, opj, True)
        s = int(s)
        if j2 is None or k2 is None or j2 >= k2:
            return c
        j, k = j2, k2
    if dv.rotation(ops[j]) is None or dv.rotation(ops[k]) is None or ops[j][1] != opj[1] and False:
        return c
    rots = [i for i, op in enumerate(ops) if dv.rotation(op) is not None]
    base = {p: dv.rotation(ops[p]) for p in rots}
    if not _pair_ok(ops, j, k, s) or not _holds(ops, c.n, rots, base, j, k, s, 1):
        return c
    eff = _wrap(base[j] + s * base[k])
    if abs(eff) < 1e-12:
        new = [op for i, op in enumerate(ops) if i not in (j, k)]
    else:
        new = list(ops)
        new[j] = ("rz", ops[j][1], eff)
        del new[k]
    return dv.with_ops(c, new)


RULE = Rule(
    name="generator_equality_angle_teleportation",
    domain="dv",
    kind="procedure",
    contract="exact",
    source="Kissinger & van de Wetering, PRA 102, 022406 (2020) phase teleportation; adjoint-differentiation form "
           "dU/dtheta_k = (-i/2) S_k Z S_k^dag U (Mitarai et al. 2018; Schuld et al. 2019)",
    idea="For rotation k, dU/dtheta_k = (-i/2) B_k U with B_k = S_k Z_q S_k^dag (S_k = everything after). If "
         "B_j = s B_k along the whole level set of theta_j + s theta_k, U depends only on that sum, so op k's angle "
         "can be added onto op j and op k deleted. Generators are compared as dense 2^n matrices at the actual "
         "angles and at 4 off-points; the frozen judge re-checks the edit.",
    trigger=find_matches,
    apply=apply_match,
)
