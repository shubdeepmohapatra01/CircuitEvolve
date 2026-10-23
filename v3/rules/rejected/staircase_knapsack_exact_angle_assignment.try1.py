"""Staircase-knapsack allocation of exact Clifford+T words to the surviving non-grid rz (one global, last pass).

Every rz is replaced by an exact Clifford+T word (Ross-Selinger style: u in Z[omega]/sqrt2^k near the target found by a
4-D lattice enumeration, t from the norm equation, word by Kliuchnikov-Maslov-Mosca exact synthesis). Words are
cached per (reduced angle, accuracy level), so each angle's T-count-vs-accuracy staircase is built once. The
per-rotation accuracies are then chosen greedily along the staircases and the largest prefix of steps whose MEASURED
phase-aligned operator distance stays within 0.9 * 5e-4 is kept (bisection over the prefix).
"""
import heapq
import itertools
import math

import numpy as np
from sympy import factorint
from sympy.ntheory import sqrt_mod

from v3.api import Rule
from v3.api import dv

EPS_APPROX = 5e-4            # eps / 2 at eps = 1e-3 (the approximate half of the ledger)
SAFETY = 0.9
MIN_RZ = 8
MAX_DISTINCT = 150
MAX_MEASURED_QUBITS = 12
MAX_BUILDS = 24

_S2 = 1.0 / math.sqrt(2.0)
_W = complex(math.cos(math.pi / 4), math.sin(math.pi / 4))
_G = {
    "h": np.array([[1, 1], [1, -1]], dtype=complex) * _S2,
    "x": np.array([[0, 1], [1, 0]], dtype=complex),
    "z": np.diag([1, -1]).astype(complex),
    "s": np.diag([1, 1j]),
    "sdg": np.diag([1, -1j]),
    "t": np.diag([1, _W]),
    "tdg": np.diag([1, _W.conjugate()]),
}
_TPOW = {0: [], 1: ["t"], 2: ["s"], 3: ["s", "t"], 4: ["z"], 5: ["z", "t"], 6: ["sdg"], 7: ["tdg"]}
_SPOW = {0: [], 1: ["s"], 2: ["z"], 3: ["sdg"]}


# ------------------------------------------------------------------------------------------ Z[omega] / Z[sqrt2]
def _zmul(x, y):
    a, b, c, d = x
    e, f, g, h = y
    return (a * e - b * h - c * g - d * f,
            a * f + b * e - c * h - d * g,
            a * g + b * f + c * e - d * h,
            a * h + b * g + c * f + d * e)


def _zadd(x, y):
    return (x[0] + y[0], x[1] + y[1], x[2] + y[2], x[3] + y[3])


def _zsub(x, y):
    return (x[0] - y[0], x[1] - y[1], x[2] - y[2], x[3] - y[3])


def _zconj(x):
    return (x[0], -x[3], -x[2], -x[1])


def _zsig(x):
    return (x[0], x[3], -x[2], x[1])


def _zmulw(x, j):
    j %= 8
    if j >= 4:
        x = (-x[0], -x[1], -x[2], -x[3])
        j -= 4
    for _ in range(j):
        x = (-x[3], x[0], x[1], x[2])
    return x


def _zdiv2(x):
    """x / sqrt2 if it lies in Z[omega], else None."""
    y = _zmul(x, (0, 1, 0, -1))
    if (y[0] | y[1] | y[2] | y[3]) & 1:
        return None
    return (y[0] // 2, y[1] // 2, y[2] // 2, y[3] // 2)


_DELTA = (1, 1, 0, 0)
_DELTA_C = _zconj(_DELTA)
_ONE = (1, 0, 0, 0)
_OMEGA_POW = {}
for _j in range(8):
    _OMEGA_POW[_zmulw(_ONE, _j)] = _j


def _zpow(x, e):
    r = _ONE
    for _ in range(e):
        r = _zmul(r, x)
    return r


def _emb(p, q):
    return (p, q, 0, -q)


def _zs_mul(x, y):
    return (x[0] * y[0] + 2 * x[1] * y[1], x[0] * y[1] + x[1] * y[0])


def _zs_divexact(x, y):
    n = y[0] * y[0] - 2 * y[1] * y[1]
    if n == 0:
        return None
    a = x[0] * y[0] - 2 * x[1] * y[1]
    b = x[1] * y[0] - x[0] * y[1]
    if a % n or b % n:
        return None
    return (a // n, b // n)


def _zs_pow(x, e):
    r = (1, 0)
    for _ in range(e):
        r = _zs_mul(r, x)
    return r


def _rdiv(a, n):
    """nearest integer to a / n (n != 0)."""
    if n < 0:
        a, n = -a, -n
    return (2 * a + n) // (2 * n)


def _zs_gcd(x, y):
    while y != (0, 0):
        n = y[0] * y[0] - 2 * y[1] * y[1]
        a = x[0] * y[0] - 2 * x[1] * y[1]
        b = x[1] * y[0] - x[0] * y[1]
        q = (_rdiv(a, n), _rdiv(b, n))
        qy = _zs_mul(q, y)
        x, y = y, (x[0] - qy[0], x[1] - qy[1])
    return x


def _znorm(x):
    p = _zmul(x, _zconj(x))
    return p[0] * p[0] - 2 * p[1] * p[1]


def _zdivmod(x, y):
    ycc = _zmul(_zmul(_zconj(y), _zsig(y)), _zsig(_zconj(y)))
    n = _znorm(y)
    xn = _zmul(x, ycc)
    base = [v // n for v in xn]
    best = None
    for span in ((0, 1), (-1, 0, 1, 2)):
        for combo in itertools.product(span, repeat=4):
            q = tuple(base[i] + combo[i] for i in range(4))
            r = _zsub(x, _zmul(q, y))
            nr = _znorm(r)
            if best is None or nr < best[0]:
                best = (nr, q, r)
        if best[0] < n:
            break
    return best[1], best[2]


def _zgcd(x, y):
    zero = (0, 0, 0, 0)
    while y != zero:
        _, r = _zdivmod(x, y)
        x, y = y, r
    return x


def _two_squares(D, m):
    """(x, y) with x^2 + D y^2 = m for a prime m (Cornacchia), else None."""
    t = sqrt_mod((-D) % m, m)
    if t is None:
        return None
    t = int(t)
    if t > m // 2:
        t = m - t
    a, b = m, t
    while b * b > m:
        a, b = b, a % b
    rest = m - b * b
    if rest % D:
        return None
    s = math.isqrt(rest // D)
    if s * s * D != rest:
        return None
    return (b, s)


def _inert_prime_factor(r):
    """rho in Z[omega] with rho * rho^dagger = r for a prime r = 3, 5 mod 8."""
    if r % 8 == 5:
        ab = _two_squares(1, r)
        return None if ab is None else (ab[0], 0, ab[1], 0)
    ab = _two_squares(2, r)
    return None if ab is None else (ab[0], ab[1], 0, ab[1])


def _solve_norm(p, q):
    """T in Z[omega] with T T^dagger = p + q sqrt2 (totally positive), or None."""
    if p == 0 and q == 0:
        return (0, 0, 0, 0)
    n = p * p - 2 * q * q
    if n <= 0:
        return None
    t = _ONE
    for r, e in factorint(n).items():
        r, e = int(r), int(e)
        if r == 2:
            t = _zmul(t, _zpow(_DELTA, e))
        elif r % 8 in (3, 5):
            if e % 2:
                return None
            rho = _inert_prime_factor(r)
            if rho is None:
                return None
            t = _zmul(t, _zpow(rho, e // 2))
        else:
            x = sqrt_mod(2, r)
            if x is None:
                return None
            pi = _zs_gcd((r, 0), (int(x), -1))
            if abs(pi[0] * pi[0] - 2 * pi[1] * pi[1]) != r:
                return None
            spi = (pi[0], -pi[1])
            xi = (p, q)
            v1 = v2 = 0
            while True:
                nx = _zs_divexact(xi, pi)
                if nx is None:
                    break
                xi, v1 = nx, v1 + 1
            while True:
                nx = _zs_divexact(xi, spi)
                if nx is None:
                    break
                xi, v2 = nx, v2 + 1
            if v1 + v2 != e:
                return None
            if r % 8 == 7:
                if v1 % 2 or v2 % 2:
                    return None
                t = _zmul(t, _zpow(_emb(*pi), v1 // 2))
                t = _zmul(t, _zpow(_emb(*spi), v2 // 2))
            else:
                s = sqrt_mod(r - 1, r)
                if s is None:
                    return None
                rho = _zgcd(_emb(*pi), (int(s), 0, 1, 0))
                t = _zmul(t, _zpow(rho, v1))
                t = _zmul(t, _zpow(_zsig(rho), v2))
    pp = _zmul(t, _zconj(t))
    v = _zs_divexact((p, q), (pp[0], pp[1]))
    if v is None:
        return None
    vf = v[0] + v[1] * math.sqrt(2.0)
    if vf <= 0:
        return None
    j = int(round(math.log(vf) / (2.0 * math.log(1.0 + math.sqrt(2.0)))))
    lam = (1, 1) if j >= 0 else (-1, 1)
    if _zs_pow(lam, 2 * abs(j)) != v:
        return None
    lj = _zs_pow(lam, abs(j))
    t = _zmul(t, _emb(*lj))
    pp = _zmul(t, _zconj(t))
    if (pp[0], pp[1]) != (p, q):
        return None
    return t


# ------------------------------------------------------------------------------------------ exact synthesis
def _reduce(u, t, k):
    while k > 0:
        a, b = _zdiv2(u), _zdiv2(t)
        if a is None or b is None:
            break
        u, t, k = a, b, k - 1
    return u, t, k


def _psi(u, t, k):
    if k == 0:
        return 0
    m = 1 if (_zdiv2(_zmul(u, _DELTA_C)) is not None and _zdiv2(_zmul(t, _DELTA_C)) is not None) else 0
    return 2 * k - m


def _synth(u, t, k):
    """Time-ordered gate names of the SU(2) matrix [[u, -t^dag], [t, u^dag]] / sqrt2^k (up to global phase)."""
    u, t, k = _reduce(u, t, k)
    steps = []
    guard = 0
    while k > 0:
        guard += 1
        if guard > 600:
            return None
        cur = _psi(u, t, k)
        best = None
        for j in range(8):
            w = _zmulw(t, j)
            a, b, k2 = _reduce(_zadd(u, w), _zsub(u, w), k + 1)
            key = (_psi(a, b, k2), j & 1, j)
            if best is None or key < best[0]:
                best = (key, j, a, b, k2)
        if best[0][0] >= cur:
            return None
        _, j, u, t, k = best
        steps.append(j)
    zero = (0, 0, 0, 0)
    m = len(steps)
    sj = sum(steps)
    if t == zero:
        if u not in _OMEGA_POW:
            return None
        a = _OMEGA_POW[u]
        c = (4 * m + sj - a) % 8
        front = list(_TPOW[(c - a) % 8])
    else:
        if u != zero or t not in _OMEGA_POW:
            return None
        a = _OMEGA_POW[t]
        c = (4 * m + sj - 4 - a) % 8
        front = list(_TPOW[(c - a) % 8]) + ["x"]
    gates = front
    for j in reversed(steps):
        gates.append("h")
        gates.extend(_TPOW[(-j) % 8])
    return gates


def _tcount(gates):
    return sum(1 for g in gates if g in ("t", "tdg"))


def _matrix(gates):
    m = np.eye(2, dtype=complex)
    for g in gates:
        m = _G[g] @ m
    return m


def _rz(theta):
    return np.diag([np.exp(-0.5j * theta), np.exp(0.5j * theta)])


def _aligned(w, r):
    tr = np.trace(r.conj().T @ w)
    ph = tr / abs(tr) if abs(tr) > 1e-300 else 1.0
    return float(np.linalg.norm(w - ph * r, 2))


# ------------------------------------------------------------------------------------------ lattice enumeration
def _gs(b):
    n = b.shape[0]
    bs = np.zeros_like(b)
    mu = np.zeros((n, n))
    nn = np.zeros(n)
    for i in range(n):
        v = b[i].copy()
        for j in range(i):
            mu[i, j] = float(b[i] @ bs[j]) / nn[j]
            v -= mu[i, j] * bs[j]
        bs[i] = v
        nn[i] = float(v @ v)
    return mu, nn


def _lll(m):
    b = m.T.copy()
    n = 4
    tr = np.eye(n, dtype=np.int64)
    k, it = 1, 0
    while k < n and it < 4000:
        it += 1
        mu, nn = _gs(b)
        for j in range(k - 1, -1, -1):
            q = int(round(mu[k, j]))
            if q:
                b[k] -= q * b[j]
                tr[k] -= q * tr[j]
                mu, nn = _gs(b)
        if nn[k] >= (0.99 - mu[k, k - 1] ** 2) * nn[k - 1]:
            k += 1
        else:
            b[[k, k - 1]] = b[[k - 1, k]]
            tr[[k, k - 1]] = tr[[k - 1, k]]
            k = max(k - 1, 1)
    return b.T, tr.T


def _enumerate(r, y, rad2, maxn=30000):
    rr = [[float(r[i, j]) for j in range(4)] for i in range(4)]
    out, w, cnt = [], [0] * 4, [0]

    def rec(i, rem):
        s = 0.0
        for j in range(i + 1, 4):
            s += rr[i][j] * w[j]
        c = (float(y[i]) - s) / rr[i][i]
        rad = math.sqrt(max(rem, 0.0)) / abs(rr[i][i])
        lo, hi = math.ceil(c - rad), math.floor(c + rad)
        if hi - lo > 200000:
            cnt[0] = 10 ** 9
            return
        for x in range(lo, hi + 1):
            cnt[0] += 1
            if cnt[0] > maxn:
                return
            nr = rem - (rr[i][i] * (x - c)) ** 2
            if nr < -1e-9:
                continue
            w[i] = x
            if i == 0:
                out.append(tuple(w))
            else:
                rec(i - 1, max(nr, 0.0))

    rec(3, rad2)
    return out


def _candidates(theta, eps, k):
    s = 2.0 ** (k / 2.0)
    e_i = np.exp(0.5j * theta)
    rows = np.zeros((4, 4))
    for j in range(4):
        u1 = np.exp(1j * math.pi * j / 4.0)
        u2 = np.exp(1j * 3.0 * math.pi * j / 4.0)
        w = u1 * e_i / s
        rows[0, j] = w.imag / (math.sqrt(2.0) * eps)
        rows[1, j] = w.real / (math.sqrt(2.0) * eps * eps / 4.0)
        rows[2, j] = u2.real / s
        rows[3, j] = u2.imag / s
    det = abs(np.linalg.det(rows))
    if det == 0 or 2.0 * math.pi ** 2 / det < 0.01:
        return []
    c0 = np.array([0.0, (1.0 - eps * eps / 4.0) / (math.sqrt(2.0) * eps * eps / 4.0), 0.0, 0.0])
    mp, tm = _lll(rows)
    q, r = np.linalg.qr(mp)
    y = q.T @ c0
    out = []
    for w in _enumerate(r, y, 2.0):
        v = [int(sum(int(tm[i, j]) * w[j] for j in range(4))) for i in range(4)]
        out.append(tuple(v))
    return out


_WORDS = {}


def _best_word(ra, lev):
    """(tcount, dist, gates) of the cheapest exact word within eps = 2^(-lev/2) of rz(ra), 0 < ra <= pi/4; or None."""
    key = (ra, lev)
    if key in _WORDS:
        return _WORDS[key]
    eps = 2.0 ** (-lev / 2.0)
    res = None
    triv = 2.0 * math.sin(ra / 4.0)
    if triv <= eps:
        res = (0, triv, [])
    elif eps < 0.3:
        target = _rz(ra)
        z_ok = ra
        k0 = max(1, int(1.5 * math.log2(1.0 / eps)) - 4)
        for k in range(k0, k0 + 18):
            found = None
            seen = set()
            for u in _candidates(z_ok, eps, k):
                if u in seen or u == (0, 0, 0, 0):
                    continue
                seen.add(u)
                uu = _zmul(u, _zconj(u))
                xi = ((1 << k) - uu[0], -uu[1])
                if xi[0] + xi[1] * math.sqrt(2.0) < -1e-6 or xi[0] - xi[1] * math.sqrt(2.0) < -1e-6:
                    continue
                t0 = _solve_norm(*xi)
                if t0 is None:
                    continue
                for m in range(8):
                    gates = _synth(u, _zmulw(t0, m), k)
                    if gates is None:
                        continue
                    d = _aligned(_matrix(gates), target)
                    if d > eps * (1 + 1e-6) + 1e-12:
                        continue
                    cand = (_tcount(gates), d, gates)
                    if found is None or cand[:2] < found[:2]:
                        found = cand
            if found is not None:
                res = found
                break
    _WORDS[key] = res
    return res


# ------------------------------------------------------------------------------------------ circuit side
def _rz_info(c):
    out = []
    for pos, op in enumerate(c.ops):
        if op[0] != "rz":
            continue
        a = float(op[2])
        jq = int(round(a / (math.pi / 2.0)))
        r = a - jq * math.pi / 2.0
        if abs(r) < 1e-12:
            continue
        out.append(dict(pos=pos, q=op[1][0], sign=1 if r >= 0 else -1, ra=abs(r), jq=jq % 4, ang=a))
    return out


def _find(c):
    if not dv.is_angle_circuit(c):
        return []
    info = _rz_info(c)
    if len(info) < MIN_RZ or len({i["ra"] for i in info}) > MAX_DISTINCT:
        return []
    return [("global", len(info))]


def _unitary(n, prog):
    dim = 1 << n
    m = np.eye(dim, dtype=complex)
    idx = np.arange(dim)
    perms = {}
    for op in prog:
        if op[0] == "g":
            q = op[1]
            m = np.einsum("ij,ajbc->aibc", op[2], m.reshape(1 << q, 2, dim >> (q + 1), dim)).reshape(dim, dim)
        elif op[0] == "cx":
            key = (op[1], op[2])
            if key not in perms:
                perms[key] = idx ^ (((idx >> (n - 1 - op[1])) & 1) << (n - 1 - op[2]))
            m = m[perms[key]]
        else:
            key = ("z", op[1], op[2])
            if key not in perms:
                perms[key] = 1 - 2 * (((idx >> (n - 1 - op[1])) & (idx >> (n - 1 - op[2]))) & 1)
            m = m * perms[key][:, None]
    return m


def _dist(uo, uc):
    tr = np.trace(uo.conj().T @ uc)
    ph = tr / abs(tr) if abs(tr) > 1e-300 else 1.0
    return float(np.linalg.norm(uc - ph * uo, 2))


def _occ_gates(sign, jq, word):
    g = (["x"] + list(word) + ["x"]) if sign < 0 else list(word)
    return g + _SPOW[jq]


_APPLIED = {}


def _apply(c, match):
    n = c.n
    key = (n, tuple(c.ops))
    if key in _APPLIED:
        return dv.with_ops(c, _APPLIED[key])
    info = _rz_info(c)
    nrz = len(info)
    if not dv.is_angle_circuit(c) or nrz < MIN_RZ:
        return c
    measured = n <= MAX_MEASURED_QUBITS
    target = SAFETY * EPS_APPROX
    d0 = target / nrz
    lev0 = int(math.ceil(2.0 * math.log2(1.0 / d0)))
    n_lev = (int(math.ceil(math.log2(nrz))) + 3) if measured else 5
    t_cap = 3.0 * math.log2(nrz / EPS_APPROX) + 3.0

    # staircases: per distinct reduced angle, the Pareto frontier [(dist, T, gates)] with T strictly falling
    fronts = {}
    for ra in sorted({i["ra"] for i in info}):
        ent = []
        for lev in range(lev0, lev0 - n_lev - 1, -1):
            w = _best_word(ra, lev)
            if w is not None:
                ent.append((w[1], w[0], tuple(w[2])))
        ent.sort(key=lambda e: (e[0], e[1]))
        fr = []
        for e in ent:
            if not fr or e[1] < fr[-1][1]:
                fr.append(e)
        fronts[ra] = fr
    for i in info:
        i["front"] = fronts[i["ra"]]
        ok = [j for j, e in enumerate(i["front"]) if e[0] <= d0 * (1 + 1e-12)]
        i["start"] = ok[-1] if ok else -1
    if any(i["start"] < 0 for i in info):
        return c

    # greedy order of staircase steps (first-order quadrature surrogate: cost = increase of d^2 per T saved)
    heap = []
    for k, i in enumerate(info):
        f, s = i["front"], i["start"]
        if s + 1 < len(f):
            heapq.heappush(heap, ((f[s + 1][0] ** 2 - f[s][0] ** 2) / (f[s][1] - f[s + 1][1]), k, s))
    moves = []
    while heap:
        _, k, s = heapq.heappop(heap)
        moves.append(k)
        f = info[k]["front"]
        if s + 2 < len(f):
            heapq.heappush(heap, ((f[s + 2][0] ** 2 - f[s + 1][0] ** 2) / (f[s + 1][1] - f[s + 2][1]), k, s + 1))

    mat_cache = {}

    def occ_mat(i, idx):
        key2 = (i["ra"], idx, i["sign"], i["jq"])
        if key2 not in mat_cache:
            mat_cache[key2] = _matrix(_occ_gates(i["sign"], i["jq"], i["front"][idx][2]))
        return mat_cache[key2]

    def states(m):
        st = [i["start"] for i in info]
        for k in moves[:m]:
            st[k] += 1
        return st

    def used(i, idx):
        return i["front"][idx][1] < t_cap

    uo = None
    prog_base = []
    if measured:
        for op in c.ops:
            if op[0] == "rz":
                prog_base.append(("rz", op[1][0], _rz(float(op[2]))))
            elif op[0] in ("cx", "cz"):
                prog_base.append((op[0], op[1][0], op[1][1]))
            else:
                prog_base.append(("g", op[1][0], _G[op[0]]))
        uo = _unitary(n, [("g", p[1], p[2]) if p[0] == "rz" else p for p in prog_base])
    builds = [0]

    def err(m):
        st = states(m)
        if not measured:
            return sum(i["front"][s][0] for i, s in zip(info, st) if used(i, s))
        builds[0] += 1
        sub = {i["pos"]: (occ_mat(i, s) if used(i, s) else None) for i, s in zip(info, st)}
        prog = []
        for pos, p in enumerate(prog_base):
            if p[0] == "rz":
                mat = sub.get(pos)
                prog.append(("g", p[1], p[2] if mat is None else mat))
            else:
                prog.append(p)
        return _dist(uo, _unitary(n, prog))

    if err(0) > target:
        return c
    lo, hi = 0, len(moves)
    while lo < hi and builds[0] < MAX_BUILDS - 2:
        mid = (lo + hi + 1) // 2
        if err(mid) <= target:
            lo = mid
        else:
            hi = mid - 1
    st = states(lo)
    ops = list(c.ops)
    for i, s in zip(info, st):
        if used(i, s):
            ops[i["pos"]] = None
    out, repl = [], {i["pos"]: (i, s) for i, s in zip(info, st) if used(i, s)}
    for pos, op in enumerate(c.ops):
        if pos in repl:
            i, s = repl[pos]
            for g in _occ_gates(i["sign"], i["jq"], i["front"][s][2]):
                out.append((g, (i["q"],), None))
        else:
            out.append(op)
    _APPLIED[key] = out
    return dv.with_ops(c, out)


RULE = Rule(
    name="staircase_knapsack_exact_angle_assignment",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="Ross-Selinger QIC 16 (2016) arXiv:1403.2975 (ancilla-free z-rotation approximation: lattice search for "
           "u in Z[omega]/sqrt2^k + norm equation); Kliuchnikov-Maslov-Mosca arXiv:1206.5236 (exact synthesis); "
           "Campbell-Hastings arXiv:1811.08017 / Kivlichan et al. 2020 (non-uniform rotation error budgeting)",
    idea="Replace every non-grid rz by an exact Clifford+T word with a per-rotation accuracy chosen by a knapsack "
         "over each angle's T-count-versus-accuracy staircase. The rotation residuals act about distinct Walsh "
         "characters, so the whole-circuit distance grows like the root of the summed squares rather than the sum; "
         "the greedy ranks steps by that surrogate and the largest prefix whose measured phase-aligned operator "
         "distance stays within 0.9 * 5e-4 is kept, so the allowance is spent instead of split uniformly.",
    trigger=_find,
    apply=_apply,
)
