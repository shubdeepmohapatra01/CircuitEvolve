"""Joint-budget direct rotation synthesis: replace every surviving rz by a Ross-Selinger Clifford+T word, all at ONE
common accuracy delta chosen by bisection on the MEASURED whole-circuit phase-aligned operator distance."""
import math
from fractions import Fraction

import numpy as np
from sympy import factorint, isprime
from sympy.ntheory import sqrt_mod

from v3.api import Rule
from v3.api import dv

APPROX_BUDGET = 5e-4          # eps/2 of the ledger at eps = 1e-3
SAFETY = 0.9
MAX_QUBITS = 10
MIN_RZ = 8
SQ2 = math.sqrt(2.0)
LAMF = 1.0 + SQ2
OMEGA = complex(math.cos(math.pi / 4), math.sin(math.pi / 4))


# ----------------------------------------------------------------------------------------- Z[omega] (a,b,c,d)
def zadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2], a[3] + b[3])


def zsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2], a[3] - b[3])


def zmul(a, b):
    r = [0, 0, 0, 0]
    for i in range(4):
        ai = a[i]
        if ai == 0:
            continue
        for j in range(4):
            v = ai * b[j]
            k = i + j
            if k >= 4:
                r[k - 4] -= v
            else:
                r[k] += v
    return tuple(r)


def zdag(a):
    return (a[0], -a[3], -a[2], -a[1])


def zgal(a, k):
    r = [0, 0, 0, 0]
    for i in range(4):
        m = (i * k) % 8
        r[m % 4] += -a[i] if m >= 4 else a[i]
    return tuple(r)


def zmul_omega(a, m):
    for _ in range(m % 8):
        a = (-a[3], a[0], a[1], a[2])
    return a


def znorm(a):
    p = zmul(a, zmul(zgal(a, 3), zmul(zgal(a, 5), zgal(a, 7))))
    return p[0]


def zcomplex(a):
    return a[0] + a[1] * OMEGA + a[2] * 1j + a[3] * OMEGA ** 3


ZERO = (0, 0, 0, 0)
ONE = (1, 0, 0, 0)
SQ2_Z = (0, 1, 0, -1)
DELTA_Z = (1, 1, 0, 0)         # 1 + omega, delta delta^dag = sqrt2 * lambda


def zdiv_sqrt2(x):
    y = zmul(x, SQ2_Z)
    if all(c % 2 == 0 for c in y):
        return tuple(c // 2 for c in y)
    return None


def zpow(a, e):
    r = ONE
    for _ in range(e):
        r = zmul(r, a)
    return r


def zdivmod(a, b):
    cb = zmul(zgal(b, 3), zmul(zgal(b, 5), zgal(b, 7)))
    num = zmul(a, cb)
    nb = znorm(b)
    fl = [c // nb for c in num]
    best = None
    for m in range(16):
        q = tuple(fl[i] + ((m >> i) & 1) for i in range(4))
        r = zsub(a, zmul(q, b))
        nr = znorm(r)
        if best is None or nr < best[0]:
            best = (nr, q, r)
    return best[1], best[2], best[0], nb


def zgcd(a, b):
    for _ in range(2000):
        if b == ZERO:
            return a
        q, r, nr, nb = zdivmod(a, b)
        if nr >= nb:
            raise ValueError("Euclid step did not decrease the norm")
        a, b = b, r
    raise ValueError("gcd did not terminate")


# ----------------------------------------------------------------------------------------- Z[sqrt2] (a,b)
def smul(x, y):
    return (x[0] * y[0] + 2 * x[1] * y[1], x[0] * y[1] + x[1] * y[0])


def sconj(x):
    return (x[0], -x[1])


def snorm(x):
    return x[0] * x[0] - 2 * x[1] * x[1]


def sdiv(x, y):
    ny = snorm(y)
    if ny == 0:
        return None
    n = smul(x, sconj(y))
    if n[0] % ny or n[1] % ny:
        return None
    return (n[0] // ny, n[1] // ny)


def sgcd(x, y):
    for _ in range(2000):
        if y == (0, 0):
            return x
        ny = snorm(y)
        n = smul(x, sconj(y))
        q = (round(Fraction(n[0], ny)), round(Fraction(n[1], ny)))
        qy = smul(q, y)
        x, y = y, (x[0] - qy[0], x[1] - qy[1])
    raise ValueError("sgcd did not terminate")


def spow(x, e):
    r = (1, 0)
    for _ in range(e):
        r = smul(r, x)
    return r


def ssign(x):
    a, b = x
    if a >= 0 and b >= 0:
        return 0 if (a == 0 and b == 0) else 1
    if a <= 0 and b <= 0:
        return -1
    if a > 0:
        return 1 if a * a > 2 * b * b else -1
    return 1 if 2 * b * b > a * a else -1


def zw_to_zs(a):
    if a[2] != 0 or a[1] != -a[3]:
        return None
    return (a[0], a[1])


def zs_to_zw(s):
    return (s[0], s[1], 0, -s[1])


_PRIMES = tuple(p for p in range(2, 3000) if all(p % q for q in range(2, int(p ** 0.5) + 1)))


def fast_factor(n):
    """Factorization of n as {prime: exponent}, or None when n is certainly not the norm of a totally positive
    Z[sqrt2] element that is a norm from Z[omega] (or is too expensive to factor)."""
    fac = {}
    for p in _PRIMES:
        if p * p > n:
            break
        if n % p == 0:
            e = 0
            while n % p == 0:
                n //= p
                e += 1
            fac[p] = e
    if n > 1:
        if n < _PRIMES[-1] ** 2 or isprime(n):
            if n % 8 != 1:
                return None
            fac[n] = fac.get(n, 0) + 1
        elif n.bit_length() <= 44:
            for p, e in factorint(n).items():
                fac[p] = fac.get(p, 0) + e
        else:
            return None
    return fac


def solve_t(xi):
    """t in Z[omega] with t t^dag = xi (xi in Z[sqrt2], totally nonnegative) or None."""
    if xi == (0, 0):
        return ZERO
    n = snorm(xi)
    if n <= 0:
        return None
    fac = fast_factor(n)
    if fac is None:
        return None
    t = ONE
    for p, e in sorted(fac.items()):
        if p == 2:
            for _ in range(e):
                t = zmul(t, DELTA_Z)
        elif p % 8 in (3, 5):
            m, w = 0, xi
            while True:
                q = sdiv(w, (p, 0))
                if q is None:
                    break
                w, m = q, m + 1
            if p % 8 == 5:
                s = sqrt_mod(-1, p)
                gen = (int(s), 0, 1, 0) if s is not None else None
            else:
                s = sqrt_mod(-2, p)
                gen = (int(s), 1, 0, 1) if s is not None else None
            if gen is None:
                return None
            if m:
                t = zmul(t, zpow(zgcd((p, 0, 0, 0), gen), m))
        else:
            r = sqrt_mod(2, p)
            if r is None:
                return None
            pi = sgcd((p, 0), (int(r), -1))
            if abs(snorm(pi)) != p:
                return None
            pis = (pi, sconj(pi))
            ex = []
            for pp in pis:
                m, w = 0, xi
                while True:
                    q = sdiv(w, pp)
                    if q is None:
                        break
                    w, m = q, m + 1
                ex.append(m)
            if p % 8 == 7:
                for pp, m in zip(pis, ex):
                    if m % 2:
                        return None
                    t = zmul(t, zs_to_zw(spow(pp, m // 2)))
            else:
                s = sqrt_mod(-1, p)
                if s is None:
                    return None
                for pp, m in zip(pis, ex):
                    if m:
                        g = zgcd(zs_to_zw(pp), (int(s), 0, 1, 0))
                        t = zmul(t, zpow(g, m))
    tts = zw_to_zs(zmul(t, zdag(t)))
    if tts is None:
        return None
    rho = sdiv(xi, tts)
    if rho is None:
        return None
    val = rho[0] + rho[1] * SQ2
    if not val > 0:
        return None
    m = round(math.log(val) / (2 * math.log(LAMF)))
    lam = (1, 1) if m >= 0 else (-1, 1)
    if spow(lam, 2 * abs(m)) != rho:
        return None
    t = zmul(t, zs_to_zw(spow(lam, abs(m))))
    if zmul(t, zdag(t)) != zs_to_zw(xi):
        return None
    return t


# ----------------------------------------------------------------------------------------- 1-D grid problem
def grid1d(x0, x1, y0, y1):
    """All m + n sqrt2 with value in [x0, x1] and conjugate m - n sqrt2 in [y0, y1], as exact (m, n) pairs."""
    if x1 < x0 or y1 < y0:
        return []
    wx, wy = max(x1 - x0, 1e-12), max(y1 - y0, 1e-12)
    j = int(round(math.log(wy / wx) / (2 * math.log(LAMF))))
    j = max(-60, min(60, j))
    sx, sy = LAMF ** j, LAMF ** (-j)
    X0, X1 = x0 * sx, x1 * sx
    if j % 2 == 0:
        Y0, Y1 = y0 * sy, y1 * sy
    else:
        Y0, Y1 = -y1 * sy, -y0 * sy
    nlo = math.ceil((X0 - Y1) / (2 * SQ2) - 1e-9)
    nhi = math.floor((X1 - Y0) / (2 * SQ2) + 1e-9)
    inv = (-1, 1) if j >= 0 else (1, 1)
    out = []
    for n in range(nlo, nhi + 1):
        lo = max(X0 - n * SQ2, Y0 + n * SQ2)
        hi = min(X1 - n * SQ2, Y1 + n * SQ2)
        for m in range(math.ceil(lo - 1e-9), math.floor(hi + 1e-9) + 1):
            z = smul((m, n), spow(inv, abs(j)))
            out.append(z)
    return out


def candidates(theta, eps, k):
    """u in Z[omega] (as (a,b,c,d)) with u / sqrt2^k in the Ross-Selinger cap around exp(-i theta/2)."""
    K = 2.0 ** (k / 2.0)
    tx, ty = math.cos(theta / 2), -math.sin(theta / 2)
    phi = math.atan2(ty, tx)
    c0 = 1 - eps * eps / 2
    s0 = math.acos(c0)
    pts = [(math.cos(phi + a), math.sin(phi + a)) for a in (-s0, 0.0, s0)] + [(c0 * tx, c0 * ty)]
    for ang in (0.0, math.pi / 2, math.pi, 1.5 * math.pi):
        d = ((ang - phi + math.pi) % (2 * math.pi)) - math.pi
        if abs(d) <= s0:
            pts.append((math.cos(ang), math.sin(ang)))
    xmin, xmax = min(p[0] for p in pts) - 1e-12, max(p[0] for p in pts) + 1e-12
    for (m1, n1) in grid1d(SQ2 * K * xmin, SQ2 * K * xmax, -SQ2 * K - 1e-9, SQ2 * K + 1e-9):
        xv, xc = m1 + n1 * SQ2, m1 - n1 * SQ2
        x = xv / (SQ2 * K)
        if abs(x) > 1 + 1e-12:
            continue
        sy = math.sqrt(max(0.0, 1 - x * x))
        ylo, yhi = -sy, sy
        if abs(ty) > 1e-12:
            bnd = (c0 - x * tx) / ty
            if ty > 0:
                ylo = max(ylo, bnd)
            else:
                yhi = min(yhi, bnd)
        elif x * tx < c0:
            continue
        if ylo > yhi:
            continue
        r2 = 2.0 * 2.0 ** k - xc * xc
        if r2 < 0:
            continue
        rb = math.sqrt(r2)
        for (m2, n2) in grid1d(SQ2 * K * ylo - 1e-9, SQ2 * K * yhi + 1e-9, -rb - 1e-9, rb + 1e-9):
            if (m1 - m2) % 2:
                continue
            yield (n1, (m1 + m2) // 2, n2, (m2 - m1) // 2)


# ----------------------------------------------------------------------------------------- exact synthesis
_G = {"h": np.array([[1, 1], [1, -1]], complex) / SQ2, "s": np.diag([1, 1j]).astype(complex),
      "sdg": np.diag([1, -1j]).astype(complex), "x": np.array([[0, 1], [1, 0]], complex),
      "z": np.diag([1, -1]).astype(complex), "t": np.diag([1, OMEGA]), "tdg": np.diag([1, OMEGA.conjugate()])}
_TGATES = {1: ["t"], 2: ["s"], 3: ["s", "t"], 4: ["z"], 5: ["z", "t"], 6: ["sdg"], 7: ["tdg"]}


def rz_matrix(theta):
    return np.diag([np.exp(-0.5j * theta), np.exp(0.5j * theta)])


def gates_matrix(gates):
    M = np.eye(2, dtype=complex)
    for g in gates:
        M = _G[g] @ M
    return M


def dist_phase(A, B):
    """phase-aligned spectral distance min_phi ||A - e^{i phi} B|| for unitaries A, B."""
    ev = np.linalg.eigvals(B.conj().T @ A)
    ang = np.sort(np.angle(ev))
    if len(ang) == 1:
        return 0.0
    gaps = np.diff(np.concatenate([ang, [ang[0] + 2 * math.pi]]))
    arc = 2 * math.pi - float(np.max(gaps))
    return 2.0 * math.sin(min(arc, 2 * math.pi) / 4.0)


def _strip(u, t, k):
    """Divide out common factors of sqrt2 from the column (u, t) / sqrt2^k."""
    while k > 0:
        du, dt = zdiv_sqrt2(u), zdiv_sqrt2(t)
        if du is None or dt is None:
            break
        u, t, k = du, dt, k - 1
    return u, t, k


def _potential(u, k):
    """2k - v_sqrt2(|u|^2): the sqrt2-denominator exponent of |u/sqrt2^k|^2 (strictly decreases along synthesis)."""
    uu = zw_to_zs(zmul(u, zdag(u)))
    a, b = uu
    if a == 0 and b == 0:
        return 0
    v = 0
    while a % 2 == 0 and v < 2 * k:
        a, b = b, a // 2
        v += 1
    return max(0, 2 * k - v)


def exact_tokens(u, t, k):
    """Operator-order tokens whose product maps e1 to (u, t)/sqrt2^k up to a phase (Kliuchnikov-Maslov-Mosca)."""
    toks = []
    u, t, k = _strip(u, t, k)
    pot = _potential(u, k)
    for _ in range(4 * k + 16):
        if k == 0:
            break
        best = None
        for swap in (0, 1):
            a, b = (t, u) if swap else (u, t)
            for j in range(4):
                bp = zmul_omega(b, (8 - j) % 8)
                n1, n2, kk = _strip(zadd(a, bp), zsub(a, bp), k + 1)
                key = (_potential(n1, kk), kk)
                if best is None or key < best[0]:
                    best = (key, swap, j, n1, n2, kk)
        if best is None or best[0][0] >= pot:
            return None
        _, swap, j, u, t, k = best
        pot = best[0][0]
        toks += ([("X",)] if swap else []) + [("T", j), ("H",)]
    if k > 0:
        return None
    if u != ZERO:
        x, tail = u, [("T", None)]
    else:
        x, tail = t, [("X",), ("T", None)]
    a = next((m for m in range(8) if zmul_omega(ONE, m) == x), None)
    if a is None:
        return None
    tail[-1] = ("T", (-a) % 8)
    return toks + tail


def tokens_to_gates(toks):
    merged = []
    for tk in toks:
        if tk[0] == "T" and merged and merged[-1][0] == "T":
            merged[-1] = ("T", (merged[-1][1] + tk[1]) % 8)
        else:
            merged.append(tk)
    gates = []
    for tk in reversed(merged):                      # operator order -> time order
        if tk[0] == "H":
            gates.append("h")
        elif tk[0] == "X":
            gates.append("x")
        elif tk[1] % 8:
            gates += _TGATES[tk[1] % 8]
    return gates


def build_word(u, t, k, theta):
    toks = exact_tokens(u, t, k)
    if toks is None:
        return None
    target = rz_matrix(theta)
    best = None
    for s in range(8):
        gates = tokens_to_gates(toks + [("T", s)])
        d = dist_phase(gates_matrix(gates), target)
        if best is None or d < best[0]:
            best = (d, gates)
    return best


_SYN_CACHE = {}


def synth(theta, delta):
    """Up to 2 Clifford+T words (time-order gate lists) within ~delta of rz(theta), cheapest first, or []."""
    key = (round(theta, 13), round(delta, 13))
    if key in _SYN_CACHE:
        return _SYN_CACHE[key]
    eps = delta / 1.5
    k0 = max(1, int(1.5 * math.log2(1.0 / eps)) - 1)
    found = []
    for k in range(k0, k0 + 16):
        tries = 0
        for u in candidates(theta, eps, k):
            uu = zw_to_zs(zmul(u, zdag(u)))
            if uu is None:
                continue
            xi = (2 ** k - uu[0], -uu[1])
            if ssign(xi) < 0 or ssign(sconj(xi)) < 0:
                continue
            tries += 1
            if tries > 300:
                break
            try:
                t = solve_t(xi)
            except ValueError:
                continue
            if t is None:
                continue
            w = build_word(u, t, k, theta)
            if w is not None and w[0] <= 3.0 * eps:
                found.append(w[1])
                break
        if found:
            break
    found.sort(key=lambda g: (sum(x in ("t", "tdg") for x in g), len(g)))
    _SYN_CACHE[key] = found
    return found


# ----------------------------------------------------------------------------------------- circuit-level measurement
def _apply_gate(T, M, qs, n):
    if len(qs) == 1:
        return np.moveaxis(np.tensordot(M, T, axes=([1], [qs[0]])), 0, qs[0])
    G = M.reshape(2, 2, 2, 2)
    out = np.tensordot(G, T, axes=([2, 3], [qs[0], qs[1]]))
    return np.moveaxis(out, [0, 1], [qs[0], qs[1]])


_CL = {"h": _G["h"], "s": _G["s"], "sdg": _G["sdg"], "x": _G["x"], "z": _G["z"], "t": _G["t"], "tdg": _G["tdg"],
       "cx": np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], complex),
       "cz": np.diag([1, 1, 1, -1]).astype(complex)}


def evaluate(items, n):
    """Unitary of a list of (matrix, qubits) applied in order; gate by gate, no dense matrix products."""
    dim = 1 << n
    T = np.eye(dim, dtype=complex).reshape((2,) * n + (dim,))
    for M, qs in items:
        T = _apply_gate(T, M, qs, n)
    return T.reshape(dim, dim)


def fuse(items):
    """Merge adjacent single-qubit matrices on the same qubit (exact; fewer tensor contractions)."""
    out = []
    for M, qs in items:
        if out and len(qs) == 1 and out[-1][1] == qs:
            out[-1] = (M @ out[-1][0], qs)
        else:
            out.append((M, qs))
    return out


# ----------------------------------------------------------------------------------------- the rule
def _eligible(c):
    if not dv.is_angle_circuit(c) or c.n > MAX_QUBITS:
        return False
    rz = [float(a) for g, _, a in c.ops if g == "rz"]
    if len(rz) < MIN_RZ:
        return False
    for a in rz:
        r = a / (math.pi / 4)
        if abs(r - round(r)) < 1e-6:
            return False
    return True


def find_matches(c):
    return [("joint_budget",)] if _eligible(c) else []


_APPLY_CACHE = {}


def apply_match(c, m):
    key = (c.n, tuple(c.ops))
    if key not in _APPLY_CACHE:
        _APPLY_CACHE[key] = _run(c)
    ops = _APPLY_CACHE[key]
    return c if ops is None else dv.with_ops(c, ops)


def _run(c):
    n = c.n
    thetas = []
    for g, qs, a in c.ops:
        if g == "rz":
            thetas.append(((float(a) + math.pi) % (2 * math.pi)) - math.pi)   # 2pi shift = global phase only
        elif g not in _CL:
            return None
    N = len(thetas)
    exact = evaluate(fuse([(rz_matrix(float(a)), tuple(qs)) if g == "rz" else (_CL[g], tuple(qs))
                           for g, qs, a in c.ops]), n)
    budget = SAFETY * APPROX_BUDGET

    def attempt(delta):
        words = []
        for th in thetas:
            w = synth(th, delta)
            if not w:
                return None
            words.append(w[0])
        items, i = [], 0
        for g, qs, a in c.ops:
            if g == "rz":
                items.append((gates_matrix(words[i]), tuple(qs)))
                i += 1
            else:
                items.append((_CL[g], tuple(qs)))
        return dist_phase(evaluate(fuse(items), n), exact), words

    def tcost(words):
        return sum(g in ("t", "tdg") for w in words for g in w)

    lo, hi = budget / (2.5 * math.sqrt(N)), budget / (0.6 * math.sqrt(N))
    best = None
    for _ in range(4):
        r = attempt(lo)
        if r is not None and r[0] <= budget:
            best = (tcost(r[1]), r[1])
            break
        lo /= 2.0
    if best is None:
        return None
    for _ in range(2):
        mid = math.sqrt(lo * hi)
        r = attempt(mid)
        if r is not None and r[0] <= budget:
            lo = mid
            cost = tcost(r[1])
            if cost < best[0]:
                best = (cost, r[1])
        else:
            hi = mid
    words, out, i = best[1], [], 0
    for g, qs, a in c.ops:
        if g == "rz":
            out += [(x, (qs[0],), None) for x in words[i]]
            i += 1
        else:
            out.append((g, qs, a))
    return out


RULE = Rule(
    name="joint_budget_direct_rotation_synthesis",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="Ross-Selinger 2016 (arXiv:1403.2975) grid synthesis; Kliuchnikov-Maslov-Mosca 2013 exact synthesis",
    idea="Synthesize all surviving rz rotations inside the rule at one common accuracy delta, chosen by bisection on "
         "the measured whole-circuit phase-aligned distance (residuals of distinct rotations add like orthogonal "
         "errors, ~sqrt(N) delta, not N delta), instead of the per-rotation budget eps_synth / N_Rz.",
    trigger=find_matches,
    apply=apply_match,
)
