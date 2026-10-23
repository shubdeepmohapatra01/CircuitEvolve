"""Convex-DAG block re-synthesis (LEAP-style deepening + Clifford pinning) minimising non-pi/4 angles."""
import itertools
import sys
import time
import math

import numpy as np
from scipy.optimize import least_squares

from v3.api import Rule
from v3.api import dv

QP = math.pi / 4
CAP_CX = {1: 0, 2: 3, 3: 3}
MAX_MATCHES = 400
MAX_3Q = 8
WORK_MAX = 40000.0       # deterministic work budget (weighted fit evaluations) per input circuit
_STATE = {"work": 0.0, "n": -1, "len": 0}
_W = {1: 0.3, 2: 1.0, 3: 4.0}
FIT_TOL = 1e-10          # Frobenius residual for "fits"
PIN_TOL = 5e-11
D_TOL = 1e-10

_CACHE = {}              # (k, local ops) -> replacement local ops or None
_I2 = np.eye(2, dtype=complex)
_H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
_FIXED_1Q = {
    "h": _H,
    "s": np.diag([1, 1j]).astype(complex),
    "sdg": np.diag([1, -1j]).astype(complex),
    "x": np.array([[0, 1], [1, 0]], dtype=complex),
    "z": np.diag([1, -1]).astype(complex),
    "t": np.diag([1, np.exp(1j * QP)]),
    "tdg": np.diag([1, np.exp(-1j * QP)]),
}
_EMB = {}


def _kron_at(M, q, k):
    mats = [_I2] * k
    mats[q] = M
    out = np.array([[1.0 + 0j]])
    for m in mats:
        out = np.kron(out, m)
    return out


def _emb1(name, q, k):
    key = (name, q, k)
    if key not in _EMB:
        _EMB[key] = _kron_at(_FIXED_1Q[name], q, k)
    return _EMB[key]


def _zdiag(q, k):
    key = ("zd", q, k)
    if key not in _EMB:
        N = 1 << k
        _EMB[key] = np.array([1.0 - 2.0 * ((b >> (k - 1 - q)) & 1) for b in range(N)])
    return _EMB[key]


def _emb2(name, a, b, k):
    key = (name, a, b, k)
    if key not in _EMB:
        N = 1 << k
        M = np.zeros((N, N), dtype=complex)
        for s in range(N):
            ba = (s >> (k - 1 - a)) & 1
            bb = (s >> (k - 1 - b)) & 1
            if name == "cx":
                t = s ^ ((1 << (k - 1 - b)) if ba else 0)
                M[t, s] = 1
            else:
                M[s, s] = -1 if (ba and bb) else 1
        _EMB[key] = M
    return _EMB[key]


def _op_matrix(op, k):
    g, qs, a = op
    if g == "rz":
        z = _zdiag(qs[0], k)
        return np.diag(np.exp(-0.5j * a * z))
    if g in ("cx", "cz"):
        return _emb2(g, qs[0], qs[1], k)
    return _emb1(g, qs[0], k)


def _unitary(ops, k):
    M = np.eye(1 << k, dtype=complex)
    for op in ops:
        M = _op_matrix(op, k) @ M
    return M


def _dist(V, U):
    ph = np.vdot(U, V)
    ph = ph / abs(ph) if abs(ph) > 1e-300 else 1.0
    return float(np.linalg.norm(V - ph * U, 2))


def _is_clifford_angle(a, tol=1e-12):
    return abs(a - round(a / QP) * QP) <= tol


def _count_generic(ops, tol=1e-12):
    return sum(1 for g, _, a in ops if g == "rz" and not _is_clifford_angle(a, tol))


def _count_2q(ops):
    return sum(1 for g, _, _ in ops if g in ("cx", "cz"))


# ----------------------------------------------------------------------------------------- ansatz fit
def _structure(k, pairs):
    """Factor list in circuit order: ('rz', q, pidx) | ('fix', matrix)."""
    f, p = [], 0

    def layer(q):
        nonlocal p
        f.append(("rz", q, p)); f.append(("fix", _emb1("h", q, k)))
        f.append(("rz", q, p + 1)); f.append(("fix", _emb1("h", q, k)))
        f.append(("rz", q, p + 2))
        p += 3

    for q in range(k):
        layer(q)
    for (a, b) in pairs:
        f.append(("fix", _emb2("cz", a, b, k)))
        layer(a)
        layer(b)
    return f, p


class _Fit:
    def __init__(self, k, pairs, U):
        self.k, self.pairs, self.U = k, pairs, U
        self.fac, self.P = _structure(k, pairs)
        self.N = 1 << k

    def build(self, theta, grad=False):
        N = self.N
        mats = []
        for ft in self.fac:
            if ft[0] == "rz":
                z = _zdiag(ft[1], self.k)
                mats.append(np.diag(np.exp(-0.5j * theta[ft[2]] * z)))
            else:
                mats.append(ft[1])
        m = len(mats)
        pre = [np.eye(N, dtype=complex)]
        for M in mats:
            pre.append(M @ pre[-1])
        if not grad:
            return pre[-1], None
        suf = [None] * (m + 1)
        suf[m] = np.eye(N, dtype=complex)
        for j in range(m - 1, -1, -1):
            suf[j] = suf[j + 1] @ mats[j]
        dV = {}
        for j, ft in enumerate(self.fac):
            if ft[0] == "rz":
                z = _zdiag(ft[1], self.k)
                dV[ft[2]] = (suf[j + 1] * (-0.5j * z)[None, :]) @ pre[j + 1]
        return pre[-1], dV

    def run(self, theta0, phi0, free, maxfev):
        """Optimise the 'free' angle indices (+ global phase); returns (theta, phi, residual_norm)."""
        free = list(free)
        theta0 = np.array(theta0, dtype=float)
        U = self.U

        def unpack(x):
            th = theta0.copy()
            th[free] = x[:-1]
            return th, x[-1]

        w = _W[self.k]

        def res(x):
            _STATE["work"] += 0.5 * w
            th, ph = unpack(x)
            V, _ = self.build(th)
            R = np.exp(1j * ph) * V - U
            return np.concatenate([R.real.ravel(), R.imag.ravel()])

        def jac(x):
            _STATE["work"] += 0.5 * w * (1 + len(free) / 12.0)
            th, ph = unpack(x)
            V, dV = self.build(th, grad=True)
            e = np.exp(1j * ph)
            cols = [e * dV[i] for i in free] + [1j * e * V]
            return np.array([np.concatenate([c.real.ravel(), c.imag.ravel()]) for c in cols]).T

        x0 = np.concatenate([theta0[free], [phi0]])
        m = 2 * self.N * self.N
        method = "lm" if len(x0) <= m else "trf"
        try:
            sol = least_squares(res, x0, jac=jac, method=method, xtol=1e-15, ftol=1e-15, gtol=1e-15,
                                max_nfev=maxfev)
        except Exception:  # noqa: BLE001
            return theta0, phi0, 1e9
        th, ph = unpack(sol.x)
        return th, ph, float(np.linalg.norm(sol.fun))


def _phase0(fit, theta):
    V, _ = fit.build(theta)
    return float(np.angle(np.vdot(fit.U, V)))   # tr(U^dag V) = e^{i a}  -> e^{-i a} V ~ U


def _pin_loop(fit, theta, phi):
    P = fit.P
    pinned = set()
    for sweep in range(2):
        if _STATE["work"] > WORK_MAX:
            break
        order = sorted((i for i in range(P) if i not in pinned),
                       key=lambda i: abs(theta[i] - round(theta[i] / QP) * QP))
        got = 0
        for i in order:
            m = round(theta[i] / QP) * QP
            t2 = theta.copy()
            t2[i] = m
            rest = [j for j in range(P) if j not in pinned and j != i]
            if abs(theta[i] - m) < 1e-9:
                V, _ = fit.build(t2)
                r = float(np.linalg.norm(np.exp(1j * phi) * V - fit.U))
                if r <= PIN_TOL:
                    theta, pinned, got = t2, pinned | {i}, got + 1
                    continue
            t3, p3, r = fit.run(t2, phi, rest, 40)
            if r <= PIN_TOL:
                theta, phi = t3, p3
                theta[i] = m
                pinned.add(i)
                got += 1
        if not got:
            break
        gen = sum(1 for i in range(P) if i not in pinned and not _is_clifford_angle(theta[i], 1e-9))
        if gen == 0:
            break
    return theta, phi, pinned


def _emit(k, pairs, theta, own):
    ops = []
    p = 0

    def layer(q):
        nonlocal p
        for x, h in ((theta[p], True), (theta[p + 1], True), (theta[p + 2], False)):
            if abs(x - round(x / QP) * QP) < 1e-9:
                x = round(x / QP) * QP
            ops.append(("rz", (q,), float(x)))
            if h:
                ops.append(("h", (q,), None))
        p += 3

    for q in range(k):
        layer(q)
    for (a, b) in pairs:
        ops.append(("cz", (a, b), None))
        layer(a)
        layer(b)
    norm = dv.with_ops(dv.Circuit(k, []), ops).ops
    # cancel adjacent h h on a wire
    out, stacks = [], {q: [] for q in range(k)}
    for op in norm:
        g, qs, a = op
        if g == "h" and stacks[qs[0]] and out[stacks[qs[0]][-1]] is not None \
                and out[stacks[qs[0]][-1]][0] == "h":
            out[stacks[qs[0]].pop()] = None
            continue
        out.append(op)
        for q in qs:
            stacks[q].append(len(out) - 1)
    return [o for o in out if o is not None]


def _synth(k, local_ops):
    U = _unitary(local_ops, k)
    r_B = _count_generic(local_ops)
    c_B = _count_2q(local_ops)
    cmax = min(c_B, CAP_CX[k])
    rng = np.random.default_rng(20261023)
    pairs_in_B = []
    for g, qs, _ in local_ops:
        if g in ("cx", "cz"):
            pr = tuple(sorted(qs))
            if pr not in pairs_in_B:
                pairs_in_B.append(pr)
    own_seq = [tuple(sorted(qs)) for g, qs, _ in local_ops if g in ("cx", "cz")]
    if k == 1:
        pairs_in_B = []

    prefix, ptheta = [], None
    fits = []
    for d in range(cmax + 1):
        cands = [prefix + [pr] for pr in pairs_in_B] if d > 0 else [[]]
        if d == c_B and d > 0 and own_seq[:d] not in cands and len(own_seq) == d:
            cands.append(list(own_seq))
        best = None
        for seq in cands:
            fit = _Fit(k, seq, U)
            starts = []
            if ptheta is not None:
                th = np.concatenate([ptheta, rng.normal(0, 0.3, fit.P - len(ptheta))])
                starts.append(th)
            nrand = 1 if d == 0 else (2 if d < cmax else 5)
            for _ in range(nrand):
                starts.append(rng.uniform(-math.pi, math.pi, fit.P))
            if d == 0 and not starts:
                starts.append(np.zeros(fit.P))
            found = 0
            for th0 in starts:
                th, ph, r = fit.run(th0, _phase0(fit, th0), range(fit.P), 150 + 60 * d)
                if best is None or r < best[0]:
                    best = (r, seq, th, ph, fit)
                if r <= FIT_TOL:
                    fits.append((seq, th, ph, fit))
                    found += 1
                    if found >= (2 if k > 1 else 1):
                        break
            if fits:
                break
        if fits:
            break
        prefix, ptheta = best[1], best[2]
    if not fits:
        return None

    bestv = None
    for seq, th, ph, fit in fits[:1]:
        th2, ph2, pinned = _pin_loop(fit, th, ph)
        for attempt in (0,):
            rep = _emit(k, seq, th2, own_seq)
            r_V, c_V = _count_generic(rep), _count_2q(rep)
            if r_V < r_B and c_V <= c_B:
                d_B = _dist(_unitary(rep, k), U)
                if d_B <= D_TOL and (bestv is None or r_V < bestv[0]):
                    bestv = (r_V, rep)
    return bestv[1] if bestv else None


# --------------------------------------------------------------------------------------------- blocks
def _preds(ops, n):
    last = [-1] * n
    out = []
    for i, (g, qs, a) in enumerate(ops):
        ps = []
        for q in qs:
            if last[q] >= 0 and last[q] not in ps:
                ps.append(last[q])
        out.append(ps)
        for q in qs:
            last[q] = i
    return out


def _blocks_1q(ops, n):
    res, cur = [], {}
    for i, (g, qs, a) in enumerate(ops):
        if len(qs) == 1:
            cur.setdefault(qs[0], []).append(i)
        else:
            for q in qs:
                if q in cur:
                    res.append(((q,), cur.pop(q)))
    for q, v in sorted(cur.items()):
        res.append(((q,), v))
    return res


def _blocks_for(ops, preds, S, cap):
    Sset = set(S)
    N = len(ops)
    inB = [0] * N
    reach = [0] * N
    epoch = 1
    cur, cx = [], 0
    res = []
    for i in range(N):
        g, qs, a = ops[i]
        ps = preds[i]
        if Sset.issuperset(qs):
            tainted = False
            for p in ps:
                if inB[p] != epoch and reach[p] == epoch:
                    tainted = True
                    break
            is2 = len(qs) == 2
            if tainted or (is2 and cx >= cap):
                if cur:
                    res.append((S, cur))
                epoch += 1
                cur, cx = [], 0
            cur.append(i)
            inB[i] = epoch
            cx += is2
            continue
        for p in ps:
            if inB[p] == epoch or reach[p] == epoch:
                reach[i] = epoch
                break
    if cur:
        res.append((S, cur))
    return res


def _key_of(ops, positions, S):
    loc = {q: j for j, q in enumerate(S)}
    return len(S), tuple((ops[i][0], tuple(loc[q] for q in ops[i][1]), ops[i][2]) for i in positions)


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    ops, n = c.ops, c.n
    if len(ops) == 0:
        return []
    if n != _STATE["n"] or abs(len(ops) - _STATE["len"]) > 80:
        _STATE["work"] = 0.0
    _STATE["n"], _STATE["len"] = n, len(ops)
    preds = _preds(ops, n)
    pairs = sorted({tuple(sorted(qs)) for g, qs, _ in ops if g in ("cx", "cz")})
    pairset = set(pairs)
    subsets = [(p[0], p[1]) for p in pairs]
    for t in itertools.combinations(range(n), 3):
        if sum(1 for pr in itertools.combinations(t, 2) if pr in pairset) >= 2:
            subsets.append(t)
    blocks = list(_blocks_1q(ops, n))
    for S in subsets:
        blocks.extend(_blocks_for(ops, preds, S, CAP_CX[len(S)]))
    cands, seen = [], set()
    for S, pos in blocks:
        sup = set()
        for i in pos:
            sup.update(ops[i][1])
        if tuple(sorted(sup)) != tuple(S):
            continue
        r_B = sum(1 for i in pos if ops[i][0] == "rz" and not _is_clifford_angle(ops[i][2]))
        if r_B < 2:
            continue
        if len(S) > 1 and not any(len(ops[i][1]) == 2 for i in pos):
            continue
        key = tuple(pos)
        if key in seen:
            continue
        seen.add(key)
        ck = _key_of(ops, pos, S)
        if ck in _CACHE and _CACHE[ck] is None:
            continue
        cands.append((-r_B, len(S), pos[0], tuple(pos), tuple(S), tuple(ops[i] for i in pos)))
    cands.sort(key=lambda t: t[:3])
    out, n3 = [], 0
    t0 = time.perf_counter()
    for _, k, _, pos, S, bops in cands:
        if k == 3:
            n3 += 1
            if n3 > MAX_3Q:
                continue
        ck = (k, bops_local(S, bops))
        if ck not in _CACHE:
            if _STATE["work"] > WORK_MAX:
                continue
            _CACHE[ck] = _synth(*ck)
        if _CACHE[ck] is None:
            continue
        out.append((pos, S, bops))
        if len(out) >= MAX_MATCHES:
            break
    sys.stderr.write("TRIGGER n_ops=%d cands=%d out=%d work=%.0f t=%.1fs\n"
                     % (len(ops), len(cands), len(out), _STATE["work"], time.perf_counter() - t0))
    return out


def bops_local(S, bops):
    loc = {q: j for j, q in enumerate(S)}
    return tuple((g, tuple(loc[q] for q in qs), a) for g, qs, a in bops)


def apply_match(c, m):
    if not dv.is_angle_circuit(c):
        return c
    pos, S, bops = m
    ops = list(c.ops)
    if any(i >= len(ops) for i in pos) or tuple(ops[i] for i in pos) != tuple(bops):
        return c
    k = len(S)
    ck = _key_of(ops, pos, S)
    if ck not in _CACHE:
        if _STATE["work"] > WORK_MAX:
            return c
        _CACHE[ck] = _synth(*ck)
    rep = _CACHE[ck]
    if rep is None:
        return c
    sys.stderr.write("APPLY k=%d r_B=%d r_V=%d work=%.0f\n" % (k, _count_generic(ck[1]), _count_generic(rep),
                                                                _STATE["work"]))
    new = [(g, tuple(S[q] for q in qs), a) for g, qs, a in rep]
    inblock = set(pos)
    p0, pmax = pos[0], pos[-1]
    marked, anc = set(), set()
    for i in range(pmax, p0 - 1, -1):
        g, qs, _ = ops[i]
        if i in inblock or any(q in marked for q in qs):
            if i not in inblock:
                anc.add(i)
            marked.update(qs)
    before = ops[:p0]
    middle = [ops[i] for i in range(p0, pmax + 1) if i not in inblock]
    A = [ops[i] for i in range(p0, pmax + 1) if i in anc]
    rest = [ops[i] for i in range(p0, pmax + 1) if i not in inblock and i not in anc]
    return dv.with_ops(c, before + A + new + rest + ops[pmax + 1:])


RULE = Rule(
    name="convex_dag_block_leap_resynthesis",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="BQSKit partitioning (Younis et al. 2021); LEAP (Smith et al. 2022); QUEST (Patel et al. 2022)",
    idea="Collect convex DAG blocks on <= 3 qubits (disjoint-support ops commute, so a convex block can be made "
         "contiguous exactly), re-synthesize each by LEAP-style incremental deepening over Euler layers and cz, "
         "then pin angles to multiples of pi/4 whenever a refit keeps the residual at zero, so the block uses "
         "fewer non-Clifford rotations with no more two-qubit gates. Accept only at distance <= 1e-10.",
    trigger=find_matches,
    apply=apply_match,
)
