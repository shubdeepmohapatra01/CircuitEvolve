"""Candidate rule: numerically re-instantiate <= 3-qubit blocks to minimise the NUMBER of non-Clifford rotations."""
import math

import numpy as np
from scipy.optimize import least_squares

from v3.api import Rule
from v3.api import dv

PI4 = math.pi / 4
TWO_PI = 2 * math.pi
TOL_FIT = 1e-11          # Frobenius residual accepted by the optimiser
TOL_D = 1e-10            # operator-norm distance accepted for a block
WORK_LIMIT = 60_000    # deterministic cap on residual evaluations per trigger() call
BLOCK_WORK = 1_200     # ... and per block

_H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
_FIXED = {"h": _H, "s": np.diag([1, 1j]), "sdg": np.diag([1, -1j]),
          "x": np.array([[0, 1], [1, 0]], dtype=complex), "z": np.diag([1, -1]).astype(complex),
          "t": np.diag([1, np.exp(1j * PI4)]), "tdg": np.diag([1, np.exp(-1j * PI4)])}
_TWO = {"cx": np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex),
        "cz": np.diag([1, 1, 1, -1]).astype(complex)}


class _Budget(Exception):
    pass


def _rz(a):
    return np.diag([np.exp(-0.5j * a), np.exp(0.5j * a)])


def _gd(v):
    m = v / PI4
    return abs(m - round(m)) * PI4


def _is_grid(a):
    return _gd(a) < 1e-9


def _noncliff(op):
    a = dv.rotation(op)
    return a is not None and not _is_grid(a)


def _apply(T, M, qs):
    if len(qs) == 1:
        return np.moveaxis(np.tensordot(M, T, axes=([1], [qs[0]])), 0, qs[0])
    a, b = qs
    out = np.tensordot(M.reshape(2, 2, 2, 2), T, axes=([2, 3], [a, b]))
    return np.moveaxis(out, [0, 1], [a, b])


def _dense(ops, local, k):
    D = 1 << k
    T = np.eye(D, dtype=complex).reshape((2,) * k + (D,))
    for g, qs, a in ops:
        lq = [local[q] for q in qs]
        if g in _TWO:
            T = _apply(T, _TWO[g], lq)
        else:
            T = _apply(T, _rz(a) if g == "rz" else _FIXED[g], lq)
    return T.reshape(D, D)


def _euler(x, y, z):
    # rz(z) h rz(y) h rz(x) = Rz(z) Rx(y) Rz(x), written out
    cs, sn = math.cos(y / 2), math.sin(y / 2)
    p, m = np.exp(-0.5j * (z + x)), np.exp(-0.5j * (z - x))
    return np.array([[p * cs, -1j * m * sn], [-1j * np.conj(m) * sn, np.conj(p) * cs]])


class _BlockBudget(Exception):
    pass


class _Fitter:
    def __init__(self, U, k, pairs, counter):
        self.U, self.k, self.pairs, self.counter = U, k, pairs, counter
        self.D = 1 << k
        ident = np.eye(self.D, dtype=complex).reshape((2,) * k + (self.D,))
        self.P = [_apply(ident, _TWO[nm], [a, b]).reshape(self.D, self.D) for nm, a, b in pairs]

    def build(self, th, c):
        k = self.k
        V = np.eye(self.D, dtype=complex)
        for l in range(c + 1):
            base = l * 3 * k
            L = _euler(*th[base:base + 3])
            for w in range(1, k):
                L = np.kron(L, _euler(*th[base + 3 * w:base + 3 * w + 3]))
            V = L @ V
            if l < c:
                V = self.P[l] @ V
        return V

    def resid(self, th, c):
        self.counter[0] += 1
        if self.counter[0] > WORK_LIMIT:
            raise _Budget()
        if self.counter[0] > self.counter[1]:
            raise _BlockBudget()
        V = self.build(th, c)
        t = np.vdot(self.U, V)
        ph = t / abs(t) if abs(t) > 1e-14 else 1.0
        R = V - ph * self.U
        return np.concatenate([R.real.ravel(), R.imag.ravel()])

    def fit(self, x0, c, fixed):
        free = np.where(~fixed)[0]
        if len(free) == 0:
            return x0, float(np.linalg.norm(self.resid(x0, c)))
        x = x0.copy()

        def f(y):
            x[free] = y
            return self.resid(x, c)

        sol = least_squares(f, x0[free], method="trf", xtol=1e-15, ftol=1e-15, gtol=1e-15, max_nfev=40)
        x[free] = sol.x
        return x, float(np.linalg.norm(self.resid(x, c)))

    def snap(self, x, c):
        m = len(x)
        fixed = np.zeros(m, bool)
        x = x.copy()
        near = [i for i in range(m) if _gd(x[i]) < 1e-6]
        if near:
            y = x.copy()
            f1 = fixed.copy()
            for i in near:
                y[i] = round(y[i] / PI4) * PI4
                f1[i] = True
            y2, res = self.fit(y, c, f1)
            if res < TOL_FIT:
                x, fixed = y2, f1
        try:
            while True:
                free = [i for i in range(m) if not fixed[i]]
                if not free:
                    break
                order = sorted(free, key=lambda i: (_gd(x[i]), i))[:3]
                ok = False
                for i in order:
                    y = x.copy()
                    y[i] = round(y[i] / PI4) * PI4
                    f2 = fixed.copy()
                    f2[i] = True
                    y2, res = self.fit(y, c, f2)
                    if res < TOL_FIT:
                        x, fixed, ok = y2, f2, True
                        break
                if not ok:
                    break
        except _BlockBudget:
            pass
        return x


def _euler_start(U):
    det = U[0, 0] * U[1, 1] - U[0, 1] * U[1, 0]
    U2 = U / np.sqrt(det) if abs(det) > 1e-12 else U
    a, b, c10 = U2[0, 0], U2[0, 1], U2[1, 0]
    beta = 2 * math.atan2(abs(b), abs(a))
    s = -2 * np.angle(a)
    dl = 2 * (np.angle(c10) + math.pi / 2)
    if abs(a) > 1e-9 and abs(c10) > 1e-9:
        alpha, gamma = (s + dl) / 2, (s - dl) / 2
    elif abs(a) <= 1e-9:
        alpha, gamma = dl, 0.0
    else:
        alpha, gamma = s, 0.0
    return np.array([gamma, beta, alpha])


def _wire_ops(q, x, y, z):
    def rzop(a):
        a = a % TWO_PI
        if min(a, TWO_PI - a) < 1e-10:
            return None
        kk = round(a / PI4)
        if abs(a - kk * PI4) < 1e-10:
            a = kk * PI4
        return ("rz", (q,), float(a))
    ox, oy, oz = rzop(x), rzop(y), rzop(z)
    out = []
    if ox:
        out.append(ox)
    if oy:
        out += [("h", (q,), None), oy, ("h", (q,), None)]
    if oz:
        out.append(oz)
    return out


def _emit(x, c, qlist, pairs):
    k = len(qlist)
    ops = []
    for l in range(c + 1):
        base = l * 3 * k
        for w in range(k):
            ops += _wire_ops(qlist[w], *x[base + 3 * w:base + 3 * w + 3])
        if l < c:
            nm, a, b = pairs[l]
            ops.append((nm, (qlist[a], qlist[b]), None))
    return ops


def _blocks(ops):
    n = len(ops)
    used = [False] * n
    out = []
    start = 0
    while True:
        while start < n and used[start]:
            start += 1
        if start >= n:
            break
        S, F, idxs = set(), set(), []
        i = start
        while i < n:
            q = set(ops[i][1])
            if not used[i] and not (q & F) and len(S | q) <= 3:
                S |= q
                idxs.append(i)
            elif q & S:
                break
            else:
                F |= q
            i += 1
        for j in idxs:
            used[j] = True
        out.append((tuple(idxs), tuple(sorted(S))))
    return out


def _own_start(bops, local, k, pairs):
    """Layer parameters that reproduce the block itself in the template with c = c_B (exact up to phase)."""
    layers, cur = [], [np.eye(2, dtype=complex) for _ in range(k)]
    for g, qs, a in bops:
        if g in _TWO:
            layers.append(cur)
            cur = [np.eye(2, dtype=complex) for _ in range(k)]
        else:
            w = local[qs[0]]
            cur[w] = (_rz(a) if g == "rz" else _FIXED[g]) @ cur[w]
    layers.append(cur)
    return np.concatenate([_euler_start(M) for L in layers for M in L])


def _starts(rng, m, k, own):
    K = 0 if own is not None else 2 if m <= 18 else 1
    xs = [] if own is None else [own]
    for _ in range(K):
        xs.append(rng.uniform(0, TWO_PI, m))
    return xs


def _attempt(fitter, c, rng, own=None):
    m = 3 * fitter.k * (c + 1)
    best, conv = None, 0
    try:
        for x0 in _starts(rng, m, fitter.k, own):
            x, res = fitter.fit(np.asarray(x0, float), c, np.zeros(m, bool))
            if res >= TOL_FIT:
                continue
            conv += 1
            xs = fitter.snap(x, c)
            r = sum(0 if _is_grid(v) else 1 for v in xs)
            if best is None or r < best[0]:
                best = (r, xs)
            if r == 0 or conv >= 2:
                break
    except _BlockBudget:
        pass
    return best


def _try_block(ops, idxs, S, counter, seed):
    bops = [ops[i] for i in idxs]
    k = len(S)
    local = {q: j for j, q in enumerate(S)}
    r_B = sum(1 for o in bops if _noncliff(o))
    if r_B < 2:
        return None
    pairs = [(g, local[qs[0]], local[qs[1]]) for g, qs, _ in bops if g in _TWO]
    c_B = len(pairs)
    if c_B > 4:
        return None
    U = _dense(bops, local, k)
    fitter = _Fitter(U, k, pairs, counter)
    rng = np.random.default_rng(seed)
    counter[1] = counter[0] + BLOCK_WORK
    top = _attempt(fitter, c_B, rng, _own_start(bops, local, k, pairs))
    if top is None or top[0] >= r_B:
        return None
    chosen = (top[0], c_B, top[1])
    if k <= 2:
        for c in range(c_B):
            res = _attempt(fitter, c, rng)
            if res is not None and res[0] <= top[0]:
                chosen = (res[0], c, res[1])
                break
    _, c, x = chosen
    repl = _emit(x, c, list(S), pairs)
    V = _dense(repl, local, k)
    t = np.vdot(U, V)
    ph = t / abs(t)
    d = np.linalg.norm(V - ph * U, 2)
    r_new = sum(1 for o in repl if _noncliff(o))
    if d > TOL_D or r_new >= r_B or c > c_B:
        return None
    return tuple(idxs), tuple(bops), tuple(repl)


def find_matches(circ):
    if not dv.is_angle_circuit(circ):
        return []
    ops = [(g, tuple(qs), a) for g, qs, a in circ.ops]
    counter = [0, 0]
    out = []
    try:
        for bi, (idxs, S) in enumerate(_blocks(ops)):
            m = _try_block(ops, idxs, S, counter, 12345 + bi)
            if m is not None:
                out.append(m)
    except _Budget:
        pass
    return out


def apply_match(circ, match):
    idxs, orig, repl = match
    ops = list(circ.ops)
    if not idxs or idxs[-1] >= len(ops) or any(tuple(ops[i]) != tuple(o) for i, o in zip(idxs, orig)):
        return circ
    drop, last = set(idxs), idxs[-1]
    new = []
    for j, op in enumerate(ops):
        if j == last:
            new.extend(repl)
        elif j not in drop:
            new.append(op)
    return dv.with_ops(circ, new)


RULE = Rule(
    name="rotation_count_minimal_block_refit",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="BQSKit-style numerical instantiation (QFAST/LEAP/QUEST); KAK decomposition; Ross-Selinger cost model",
    idea="Partition into dependency-contiguous blocks of <= 3 qubits; for blocks with >= 2 non-Clifford rotations "
         "fit a template of Euler words and the block's own CX/CZ pattern to the block unitary by least squares, "
         "greedily pinning angles to the pi/4 grid, so that fewer rotations stay non-Clifford at no extra "
         "two-qubit cost. Each accepted block has phase-aligned distance <= 1e-10 and is re-verified by the judge.",
    trigger=find_matches,
    apply=apply_match,
)
