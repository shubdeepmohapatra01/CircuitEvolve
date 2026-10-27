"""Recompress a run of Pauli rotations to the dimension of the Lie algebra their axes generate (Euler collapse,
Gaussian resynthesis and their controlled versions in one rule). Approximate (numerical refit, <= 1e-10)."""
import math

import numpy as np
from scipy.optimize import least_squares

from v4.api import Precondition, Rule
from v4.api import dv, pauli

FIT_D = 8           # largest closure dimension we try to refit numerically
FIT_Q = 4           # largest segment support (dense matrices are 2^FIT_Q square)
MAX_FITS = 2        # fit attempts per trigger call
MAX_MATCHES = 1     # the judge verifies each application on the whole circuit (slow), so keep the list short
TOL = 1e-10
QTR = math.pi / 4
_INV = {"h": "h", "s": "sdg", "sdg": "s", "x": "x", "z": "z", "cx": "cx", "cz": "cz"}
_CL = set(dv.CLIFFORD_1Q) | set(dv.CLIFFORD_2Q)


# ----------------------------------------------------------------------------------------------- Pauli closure
def _anti(a, b):
    return bin((a[0] & b[1]) ^ (a[1] & b[0])).count("1") & 1


def _close_add(L, e, cap):
    """Add axis e to the commutator-closed set L (in place). Returns False if |L| would exceed cap."""
    queue = [e]
    while queue:
        n = queue.pop()
        if n in L:
            continue
        if len(L) >= cap:
            return False
        L.add(n)
        for f in list(L):
            if _anti(n, f):
                queue.append((n[0] ^ f[0], n[1] ^ f[1]))
    return True


# ----------------------------------------------------------------------------------------------- dense helpers
def _gmat(name, angle):
    r = 1 / math.sqrt(2)
    if name == "rz":
        return np.diag([np.exp(-0.5j * angle), np.exp(0.5j * angle)])
    return {"h": np.array([[r, r], [r, -r]], complex), "s": np.diag([1, 1j]), "sdg": np.diag([1, -1j]),
            "x": np.array([[0, 1], [1, 0]], complex), "z": np.diag([1, -1]).astype(complex),
            "t": np.diag([1, np.exp(1j * QTR)]), "tdg": np.diag([1, np.exp(-1j * QTR)]),
            "cx": np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], complex),
            "cz": np.diag([1, 1, 1, -1]).astype(complex)}[name]


def _dense(ops, sup):
    k = len(sup)
    pos = {q: j for j, q in enumerate(sup)}
    D = 1 << k
    T = np.eye(D, dtype=complex).reshape((2,) * k + (D,))
    for name, qs, a in ops:
        m = len(qs)
        g = _gmat(name, a).reshape((2,) * (2 * m))
        ax = [k - 1 - pos[q] for q in qs]
        T = np.tensordot(g, T, axes=(list(range(m, 2 * m)), ax))
        T = np.moveaxis(T, list(range(m)), ax)
    return T.reshape(D, D)


def _dist(A, B):
    """phase-aligned operator distance min_phi ||A - e^{i phi} B||."""
    t = np.trace(B.conj().T @ A)
    ph = t / abs(t) if abs(t) > 1e-14 else 1.0
    return float(np.linalg.norm(A - ph * B, 2))


def _pauli_tables(axis, sup):
    k = len(sup)
    xm = zm = 0
    for j, q in enumerate(sup):
        xm |= ((axis[0] >> q) & 1) << j
        zm |= ((axis[1] >> q) & 1) << j
    idx = np.arange(1 << k)
    perm = idx ^ xm
    ph = np.ones(1 << k, complex)
    for j in range(k):
        xb, zb = (xm >> j) & 1, (zm >> j) & 1
        if zb:
            ph = ph * (1 - 2 * ((perm >> j) & 1))
        if xb and zb:
            ph = ph * 1j
    return perm, ph


def _model(seq_tabs, theta, D):
    M = np.eye(D, dtype=complex)
    for (perm, ph), th in zip(seq_tabs, theta):
        c, s = math.cos(th / 2), math.sin(th / 2)
        M = c * M - 1j * s * (ph[:, None] * M[perm])
    return M


def _fit(seq, init, V, sup):
    D = V.shape[0]
    tabs_by = {a: _pauli_tables(a, sup) for a in set(seq)}
    tabs = [tabs_by[a] for a in seq]
    n = len(seq)

    def res(p):
        R = _model(tabs, p[:n], D) - np.exp(1j * p[n]) * V
        return np.concatenate([R.real.ravel(), R.imag.ravel()])

    rng = np.random.RandomState(12345)
    starts = [np.array(init, float)] + [rng.uniform(-math.pi, math.pi, n) for _ in range(1)]
    best = None
    for th0 in starts:
        W0 = _model(tabs, th0, D)
        t = np.trace(V.conj().T @ W0)
        p0 = np.concatenate([th0, [float(np.angle(t))]])
        r = least_squares(res, p0, method="lm", xtol=1e-15, ftol=1e-15, gtol=1e-15, max_nfev=12 * (n + 1))
        if best is None or r.cost < best[0]:
            best = (r.cost, r.x[:n].copy())
        if r.cost < 1e-24:
            break
    return best[1], tabs


# ----------------------------------------------------------------------------------------------- lowering
def _gadget(axis, theta, sup_all):
    x, z = axis
    qs = [q for q in range(max(sup_all) + 1) if (x | z) >> q & 1]
    pre, post = [], []
    for q in qs:
        xb, zb = (x >> q) & 1, (z >> q) & 1
        if xb and zb:
            pre += [("sdg", (q,), None), ("h", (q,), None)]
            post = [("h", (q,), None), ("s", (q,), None)] + post
        elif xb:
            pre.append(("h", (q,), None))
            post = [("h", (q,), None)] + post
    t = qs[0]
    lad = [("cx", (q, t), None) for q in qs[1:]]
    return pre + lad + [("rz", (t,), float(theta))] + lad[::-1] + post


def _cost(angles):
    g = nt = 0
    for a in angles:
        m = round(a / QTR)
        if abs(a - m * QTR) < TOL:
            nt += m & 1
        else:
            g += 1
    return (g, nt)


def _reduce(th):
    th = math.fmod(th, 2 * math.pi)
    if th > math.pi:
        th -= 2 * math.pi
    if th <= -math.pi:
        th += 2 * math.pi
    return th


_SEG_CACHE = {}
_TRIG_CACHE = {}


def _try_segment(ops, a, b, L, firsts, seq_angles):
    key = tuple(ops[a:b + 1])
    if key not in _SEG_CACHE:
        if len(_SEG_CACHE) > 4096:
            _SEG_CACHE.clear()
        _SEG_CACHE[key] = _try_segment_raw(ops, a, b, L, firsts, seq_angles)
    return _SEG_CACHE[key]


def _try_segment_raw(ops, a, b, L, firsts, seq_angles):
    span = ops[a:b + 1]
    sup = sorted({q for _, qs, _ in span for q in qs})
    if len(sup) > FIT_Q:
        return None
    cl = [o for o in span if o[0] in _CL]
    U = _dense(span, sup)
    C = _dense(cl, sup) if cl else np.eye(1 << len(sup), dtype=complex)
    V = C.conj().T @ U
    old = _cost([dv.rotation(o) for o in span if dv.rotation(o) is not None])
    rest = sorted(L - set(firsts))
    base = list(firsts) + rest
    d = len(base)
    nrot = sum(1 for o in span if dv.rotation(o) is not None)
    for sweeps in (1, 2):
        seq = base * sweeps
        if len(seq) >= nrot:
            break
        init = [seq_angles.get(a_, 0.0) if i < d else 0.0 for i, a_ in enumerate(seq)]
        th, tabs = _fit(seq, init, V, sup)
        keep = []
        for ax, t in zip(seq, th):
            t = _reduce(float(t))
            m = round(t / QTR)
            if abs(t - m * QTR) < TOL:
                if m % 8 == 0:
                    continue
                t = m * QTR
            elif abs(t) < TOL:
                continue
            keep.append((ax, t))
        if _cost([t for _, t in keep]) >= old:
            continue
        W = _model([_pauli_tables(ax, sup) for ax, _ in keep], [t for _, t in keep], V.shape[0])
        if _dist(W, V) > TOL:
            continue
        new = []
        for ax, t in keep:
            new += _gadget(ax, t, sup)
        new += cl
        if _dist(_dense(new, sup), U) > 1e-9:
            continue
        return tuple(new)
    return None


# ----------------------------------------------------------------------------------------------- trigger / apply
def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    key = (c.n, tuple(c.ops))
    if key not in _TRIG_CACHE:
        if len(_TRIG_CACHE) > 16:
            _TRIG_CACHE.clear()
        _TRIG_CACHE[key] = _find_matches(c)
    return list(_TRIG_CACHE[key])


def _find_matches(c):
    ops = list(c.ops)
    rp = [i for i, o in enumerate(ops) if dv.rotation(o) is not None]
    out, fits, s = [], 0, 0
    while s < len(rp) and fits < MAX_FITS and len(out) < MAX_MATCHES:
        L, firsts, seq_angles = set(), [], {}
        cl, sup = [], set()
        best = None
        prev = rp[s]
        ok = True
        for k in range(s, len(rp)):
            pos = rp[k]
            for o in ops[prev:pos + 1] if k > s else [ops[pos]]:
                sup.update(o[1])
                if o[0] in _CL:
                    cl.append(o)
            prev = pos + 1
            if len(sup) > FIT_Q or len(cl) > 120:
                break
            q = ops[pos][1][0]
            p = (0, 1 << q, 1)
            for g, qs, _ in reversed(cl):
                p = pauli.conjugate(p, _INV[g], qs)
            ax = (p[0], p[1])
            if not _close_add(L, ax, FIT_D):
                break
            if ax not in firsts:
                firsts.append(ax)
            seq_angles[ax] = seq_angles.get(ax, 0.0) + p[2] * dv.rotation(ops[pos])
            if len(L) < k - s + 1:
                best = (k, len(L), list(firsts), set(L), dict(seq_angles))
        if best is None:
            s += 1
            continue
        k, _, fs, LL, sa = best
        fits += 1
        new = _try_segment(ops, rp[s], rp[k], LL, fs, sa)
        if new is None:
            s += 1
            continue
        out.append((rp[s], rp[k], tuple(ops[rp[s]:rp[k] + 1]), new))
        s = k + 1
    return out


def apply_match(c, m):
    if not dv.is_angle_circuit(c):
        return c
    a, b, orig, new = m
    ops = list(c.ops)
    if tuple(ops[a:b + 1]) != tuple(orig):
        return c
    return dv.with_ops(c, ops[:a] + list(new) + ops[b + 1:])


RULE = Rule(
    name="pauli_subalgebra_dimension_recompression",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="Litinski 1808.02892 (Pauli-rotation normal form); Khaneja-Glaser 2001 (Cartan factorisation); Euler collapse",
    idea="Push Cliffords out of a run of rotations so it becomes an ordered product of Pauli exponentials; the product "
         "lies in the compact group of the Lie algebra generated by the axes (closure under products of anticommuting "
         "pairs), of dimension d. If d is smaller than the number of rotations, refit the run as at most d (or 2d) "
         "rotations on the closure basis by least squares, snap/drop angles, accept only at distance <= 1e-10 with "
         "fewer non-Clifford rotations.",
    precondition=Precondition(families=("dv_angle",), needs=("rotations",),
        note="refits a run of rotations; needs rotations"),
    trigger=find_matches,
    apply=apply_match,
)
