"""Clock-diagonal multiplexor Walsh resynthesis (procedure, approx).

Rotations are moved into the Pauli frame of a span end b (Cliffords pushed to the start of the span, axes obtained by
propagating Z_q forward through the later Cliffords with v3.api.pauli.conjugate tables). A maximal run of rotations whose
axes are Z_S (x) sigma on one qubit s is a block-diagonal unitary V = (+)_j V_j (V_j in SU(2), exact 2x2 products); each
V_j gets ZXZ Euler angles, the three angle vectors are Walsh-transformed and re-emitted as Gray-code CX-ladder
multiplexors, dropping Walsh coefficients while the measured block distance stays <= 8e-7.
"""
from __future__ import annotations

import itertools
import math
from bisect import bisect_left, bisect_right

import numpy as np

from v3.api import Rule
from v3.api import dv, pauli

STRIDE = 3            # span ends tried: every STRIDE-th rotation when nothing fires
MAX_EVALS = 40        # work budget (deterministic) on full Euler/Walsh evaluations per trigger call
WINDOW = 250         # ops looked back from a span end
MAX_MEMBERS = 300
MAX_UNION = 8         # |C| + 1  (k <= 7)
MIN_MEMBERS = 6
DIST_BUDGET = 8e-7
TINY = 1e-12
QPI = math.pi / 4
TWO_PI = 2 * math.pi
SIGMA = {(1, 0): np.array([[0, 1], [1, 0]], dtype=complex),
         (1, 1): np.array([[0, -1j], [1j, 0]], dtype=complex),
         (0, 1): np.array([[1, 0], [0, -1]], dtype=complex)}


# ------------------------------------------------------------------ vectorised Pauli propagation (tables from the API)
def _build_lut(gate, k):
    nk = 1 << (2 * k)
    nx = np.zeros((nk, k), np.int64)
    nz = np.zeros((nk, k), np.int64)
    sg = np.ones(nk, np.int64)
    for key in range(nk):
        x = sum(((key >> (2 * i)) & 1) << i for i in range(k))
        z = sum(((key >> (2 * i + 1)) & 1) << i for i in range(k))
        rx, rz, rs = pauli.conjugate((x, z, 1), gate, tuple(range(k)))
        for i in range(k):
            nx[key, i] = (rx >> i) & 1
            nz[key, i] = (rz >> i) & 1
        sg[key] = rs
    return nx, nz, sg


_LUTS = {g: _build_lut(g, 1) for g in ("h", "s", "sdg", "x", "z")}
_LUTS.update({g: _build_lut(g, 2) for g in ("cx", "cz")})


def _apply_gate(X, Z, S, n, g, qs):
    nxl, nzl, sgl = _LUTS[g]
    xv, zv = X[:n], Z[:n]
    key = np.zeros(n, np.int64)
    mask = 0
    for i, q in enumerate(qs):
        key += ((xv >> q) & 1) << (2 * i)
        key += ((zv >> q) & 1) << (2 * i + 1)
        mask |= 1 << q
    nx = np.zeros(n, np.int64)
    nz = np.zeros(n, np.int64)
    for i, q in enumerate(qs):
        nx |= nxl[key, i] << q
        nz |= nzl[key, i] << q
    X[:n] = (xv & ~mask) | nx
    Z[:n] = (zv & ~mask) | nz
    S[:n] *= sgl[key]


def _axes(ops, rps, b):
    """Axes (x, z, sign) of the rotations at positions rps (ascending, last <= b), each propagated forward through
    every Clifford after it up to and including position b."""
    m = len(rps)
    X = np.zeros(m, np.int64)
    Z = np.zeros(m, np.int64)
    S = np.ones(m, np.int64)
    n = 0
    for i in range(rps[0], b + 1):
        g, qs, _ = ops[i]
        if n < m and rps[n] == i:
            Z[n] = 1 << qs[0]
            n += 1
        elif n:
            _apply_gate(X, Z, S, n, g, qs)
    return X, Z, S


def _pop(v):
    return bin(v).count("1")


def _scan(nq, X, Z, m):
    members, inter, basis = [], [], []
    cand, U = (1 << nq) - 1, 0
    full = (1 << nq) - 1
    for k in range(m - 1, -1, -1):
        x, z = int(X[k]), int(Z[k])
        ok = False
        if _pop(x) <= 1:
            c2 = cand & (z if x == 0 else x)
            u2 = U | x | z
            if c2 and _pop(u2) <= MAX_UNION:
                ok = True
        if ok:
            members.append(k)
            cand, U = c2, u2
            v = (x << nq) | z
            for bv in basis:
                v = min(v, v ^ bv)
            if v:
                basis.append(v)
        else:
            if all(_pop((x & (bv & full)) ^ (z & (bv >> nq))) % 2 == 0 for bv in basis):
                inter.append(k)
            else:
                break
        if len(members) >= MAX_MEMBERS:
            break
    return members, inter


# ------------------------------------------------------------------ angle classes
def _classify(a):
    m = round(a / QPI)
    if abs(a - m * QPI) < TINY:
        return "id" if m % 8 == 0 else ("cliff" if m % 2 == 0 else "t")
    return "gen"


def _cost(angles):
    g = sum(_classify(a) == "gen" for a in angles)
    t = sum(_classify(a) == "t" for a in angles)
    return g, t


# ------------------------------------------------------------------ Euler / Walsh
def _principal(V):
    a, b = V[0, 0], V[0, 1]
    ra, rb = abs(a), abs(b)
    beta = 2 * math.atan2(rb, ra)
    if rb < 1e-10:
        return (-2 * np.angle(a), 0.0, 0.0)
    if ra < 1e-10:
        return (-2 * np.angle(1j * b), math.pi, 0.0)
    sig = -2 * np.angle(a)
    dl = -2 * np.angle(1j * b)
    return ((sig + dl) / 2, beta, (sig - dl) / 2)


def _pick(prev, base):
    al, be, ga = base
    best = None
    for f in (0, 1):
        v = (al + math.pi, -be, ga - math.pi) if f else (al, be, ga)
        opts = []
        for comp in range(3):
            d = (prev[comp] - v[comp]) / TWO_PI
            r = round(d)
            opts.append((r, r + 1 if d > r else r - 1))
        for ns in itertools.product(*opts):
            if sum(ns) % 2:
                continue
            cand = tuple(v[i] + TWO_PI * ns[i] for i in range(3))
            cost = sum(abs(cand[i] - prev[i]) for i in range(3))
            if best is None or cost < best[0] - 1e-15:
                best = (cost, cand)
    return best[1]


def _vprime(c3, H):
    th = c3 @ H                                  # (3, J)
    al, be, ga = th
    cb, sb = np.cos(be / 2), np.sin(be / 2)
    J = th.shape[1]
    V = np.zeros((J, 2, 2), complex)
    V[:, 0, 0] = np.exp(-1j * (al + ga) / 2) * cb
    V[:, 0, 1] = -1j * np.exp(-1j * (al - ga) / 2) * sb
    V[:, 1, 0] = -1j * np.exp(1j * (al - ga) / 2) * sb
    V[:, 1, 1] = np.exp(1j * (al + ga) / 2) * cb
    return V


def _dist(Vp, V):
    d1 = np.linalg.norm(Vp - V, ord=2, axis=(1, 2)).max()
    d2 = np.linalg.norm(Vp + V, ord=2, axis=(1, 2)).max()
    return min(d1, d2)


def _reduce(c):
    c = c - TWO_PI * np.round(c / TWO_PI)
    m = np.round(c / QPI)
    near = np.abs(c - m * QPI) < TINY
    return np.where(near, m * QPI, c)


def _resynth(V, order, principal, H):
    """Branch-lifted Euler angles along `order`, Walsh transform, truncation. -> (c3 kept, dist, (g, t)) or None."""
    J = V.shape[0]
    A = np.zeros((3, J))
    prev = None
    for j in order:
        base = principal[j]
        cur = tuple(base) if prev is None else _pick(prev, base)
        A[:, j] = cur
        prev = cur
    C = _reduce((A @ H.T) / J)                   # c_S = 2^-k sum_j (-1)^{S.j} theta_j      (3, J)
    flat = [(abs(C[sl, S]), sl, S) for sl in range(3) for S in range(J) if abs(C[sl, S]) > TINY]
    flat.sort(key=lambda t: (t[0], t[1], t[2]))

    def kept_for(m):
        out = np.zeros_like(C)
        for _, sl, S in flat[m:]:
            out[sl, S] = C[sl, S]
        return out

    if _dist(_vprime(kept_for(0), H), V) > DIST_BUDGET:
        return None
    lo, hi = 0, len(flat)                         # largest m with dist <= budget
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _dist(_vprime(kept_for(mid), H), V) <= DIST_BUDGET:
            lo = mid
        else:
            hi = mid - 1
    kept = kept_for(lo)
    d = _dist(_vprime(kept, H), V)
    angles = [float(kept[sl, S]) for sl in range(3) for S in range(J) if kept[sl, S] != 0.0]
    return kept, d, _cost(angles)


def _inv_gray(g):
    b = g
    g >>= 1
    while g:
        b ^= g
        g >>= 1
    return b


def _emit_mux(row, s, Cq, out):
    kept = sorted((S for S in range(len(row)) if row[S] != 0.0), key=_inv_gray)
    cur = 0
    for S in kept:
        diff = cur ^ S
        for i in range(len(Cq)):
            if (diff >> i) & 1:
                out.append(("cx", (Cq[i], s), None))
        cur = S
        out.append(("rz", (s,), float(row[S])))
    for i in range(len(Cq)):
        if (cur >> i) & 1:
            out.append(("cx", (Cq[i], s), None))


def _emit_pauli(x, z, sg, a, out):
    supp = [q for q in range(max(x | z, 1).bit_length()) if ((x | z) >> q) & 1]
    piv = supp[-1]
    pre, post = [], []
    for q in supp:
        xb, zb = (x >> q) & 1, (z >> q) & 1
        if xb and zb:
            pre += [("sdg", (q,), None), ("h", (q,), None)]
            post = [("h", (q,), None), ("s", (q,), None)] + post
        elif xb:
            pre.append(("h", (q,), None))
            post = [("h", (q,), None)] + post
    lad = [("cx", (q, piv), None) for q in supp if q != piv]
    out.extend(pre + lad + [("rz", (piv,), float(sg * a))] + lad + post)


def _evaluate(ops, pos, X, Z, S, sub, inters, s, Cq):
    mem = sub[::-1]                                # time order
    k = len(Cq)
    J = 1 << k
    cbit = {q: i for i, q in enumerate(Cq)}
    jarr = np.arange(J)
    pc = np.array([_pop(i) for i in range(J)], np.int64)
    V = np.tile(np.eye(2, dtype=complex), (J, 1, 1))
    old = []
    for lk in mem:
        x, z, sg = int(X[lk]), int(Z[lk]), int(S[lk])
        a = dv.rotation(ops[pos[lk]])
        old.append(a)
        sigma = SIGMA[((x >> s) & 1, (z >> s) & 1)]
        smask = sum(1 << cbit[q] for q in Cq if (z >> q) & 1)
        eps = sg * (1 - 2 * (pc[jarr & smask] & 1))
        M = math.cos(a / 2) * np.eye(2) - 1j * math.sin(a / 2) * eps[:, None, None] * sigma
        V = M @ V
    H = (1 - 2 * (pc[np.bitwise_and.outer(jarr, jarr)] & 1)).astype(float)   # H[S, j]
    principal = [_principal(V[j]) for j in range(J)]
    rev = [int(format(i, f"0{k}b")[::-1], 2) if k else 0 for i in range(J)]
    orders = [list(range(J)), [i ^ (i >> 1) for i in range(J)], rev]
    best = None
    for order in orders:
        r = _resynth(V, order, principal, H)
        if r is not None and (best is None or r[2] < best[2]):
            best = r
    if best is None:
        return None
    kept, dist, (g_new, t_new) = best
    g_old, t_old = _cost(old)
    if not (g_new < g_old and 57 * g_new + t_new < 57 * g_old + t_old):
        return None
    new = []
    _emit_mux(kept[2], s, Cq, new)                 # gamma slot first (applied first)
    if np.any(kept[1] != 0.0):
        new.append(("h", (s,), None))
        _emit_mux(kept[1], s, Cq, new)
        new.append(("h", (s,), None))
    _emit_mux(kept[0], s, Cq, new)
    for lk in sorted(inters, key=lambda i: pos[i]):
        _emit_pauli(int(X[lk]), int(Z[lk]), int(S[lk]), dv.rotation(ops[pos[lk]]), new)
    return new, g_new - g_old


def _try_end(nq, ops, rpos, idx, budget):
    b = rpos[idx]
    first = bisect_left(rpos, max(0, b - WINDOW))
    pos = rpos[first:idx + 1]
    m = len(pos)
    if m < MIN_MEMBERS:
        return None
    X, Z, S = _axes(ops, pos, b)
    members, inter = _scan(nq, X, Z, m)
    if len(members) < MIN_MEMBERS:
        return None
    counts = []
    n = len(members)
    while n >= MIN_MEMBERS:
        counts.append(n)
        n //= 2
    for cnt in counts:
        sub = members[:cnt]
        cand, U = (1 << nq) - 1, 0
        for lk in sub:
            x, z = int(X[lk]), int(Z[lk])
            cand &= (z if x == 0 else x)
            U |= x | z
        if not cand:
            continue
        s = (cand & -cand).bit_length() - 1
        Cq = [q for q in range(nq) if (U >> q) & 1 and q != s]
        if len(Cq) > 7 or cnt <= len(Cq) + 1:
            continue
        a_pos = pos[sub[-1]]
        inters = [i for i in inter if pos[i] > a_pos]
        if budget[0] <= 0:
            return None
        budget[0] -= 1
        res = _evaluate(ops, pos, X, Z, S, sub, inters, s, Cq)
        if res is None:
            continue
        new, delta = res
        skel = [op for op in ops[a_pos:b + 1] if dv.rotation(op) is None]
        return (a_pos, b, tuple(ops[a_pos:b + 1]), tuple(skel + new), delta)
    return None


_CACHE: dict = {}


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    ops = c.ops
    key = (c.n, tuple(ops))
    if key in _CACHE:
        return list(_CACHE[key])
    rpos = [i for i, op in enumerate(ops) if dv.rotation(op) is not None]
    out = []
    idx = len(rpos) - 1
    budget = [MAX_EVALS]
    while idx >= MIN_MEMBERS - 1 and budget[0] > 0:
        res = _try_end(c.n, ops, rpos, idx, budget)
        if res is None:
            idx -= STRIDE
            continue
        out.append(res)
        idx = bisect_left(rpos, res[0]) - 1
    out.reverse()
    if len(_CACHE) > 8:
        _CACHE.clear()
    _CACHE[key] = tuple(out)
    return out


def apply_match(c, m):
    if not dv.is_angle_circuit(c):
        return c
    a, b, orig, repl, _ = m
    ops = list(c.ops)
    L = len(orig)
    if tuple(ops[a:a + L]) != orig:
        starts = sorted(range(0, len(ops) - L + 1), key=lambda i: abs(i - a))
        a = next((i for i in starts if tuple(ops[i:i + L]) == orig), None)
        if a is None:
            return c
    return dv.with_ops(c, ops[:a] + list(repl) + ops[a + L:])


RULE = Rule(
    name="clock_diagonal_multiplexor_walsh_resynthesis",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="Moettoenen et al. PRL 93 130502 (2004); Welch et al. NJP 16 033040 (2014); Litinski arXiv:1808.02892",
    idea="In the Pauli frame of a span end, a run of rotations with axes Z_S (x) sigma on one qubit s is block diagonal "
         "over the computational basis of the Z-qubits C: V = (+)_j V_j, V_j in SU(2) an exact ordered 2x2 product. "
         "Take ZXZ Euler angles of every V_j (branch-lifted for continuity), Walsh-transform the three angle vectors "
         "(exact orthogonal change of basis) and re-emit them as Gray-code CX-ladder multiplexors, dropping Walsh "
         "coefficients while the measured block distance stays <= 8e-7. Spectrally sparse (phase-estimation-style, "
         "linear-in-index) angle functions collapse to O(k) rotations per slot.",
    trigger=find_matches,
    apply=apply_match,
)
