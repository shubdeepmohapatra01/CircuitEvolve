"""Clock-controlled free-fermion (Gaussian) resynthesis by an analytic Givens cascade (no numerical optimiser)."""
import itertools
import math
import sys

import numpy as np

from v3.api import Rule
from v3.api import dv, pauli

PI4 = math.pi / 4
CLIFF = ("h", "s", "sdg", "x", "z", "cx", "cz")
GENERIC_COST = 55
MAX_WIRES = 9
MAX_TRIES = 25
DBG = [0, None]
TOL = 1e-9


# ---------------------------------------------------------------- Pauli algebra: matrix = i^ph X^x Z^z
def _pc(v):
    return bin(v).count("1")


def _to_ph(p):
    x, z, s = p
    return (x, z, (_pc(x & z) + (2 if s < 0 else 0)) % 4)


def _from_ph(t):
    x, z, ph = t
    r = (ph - _pc(x & z)) % 4
    if r not in (0, 2):
        raise ValueError("non-Hermitian Pauli")
    return (x, z, 1 if r == 0 else -1)


def _mul(a, b):
    return (a[0] ^ b[0], a[1] ^ b[1], (a[2] + b[2] + 2 * _pc(a[1] & b[0])) % 4)


def _map(p, IX, IZ, nq):
    """Image of the signed Hermitian Pauli p under the linear Clifford map given by generator images (ph form)."""
    x, z, s = p
    acc = (0, 0, 2 if s < 0 else 0)
    for q in range(nq):
        xb, zb = (x >> q) & 1, (z >> q) & 1
        if xb and zb:
            t = _mul(IX[q], IZ[q])
            t = (t[0], t[1], (t[2] + 1) % 4)
        elif xb:
            t = IX[q]
        elif zb:
            t = IZ[q]
        else:
            continue
        acc = _mul(acc, t)
    return acc


def _inv(g):
    return {"s": "sdg", "sdg": "s"}.get(g, g)


def _frame(ops, n):
    """[(op index, signed axis K^dag Z_q K, angle)] with K the product of the Cliffords before the op."""
    AX = [_to_ph((1 << q, 0, 1)) for q in range(n)]
    AZ = [_to_ph((0, 1 << q, 1)) for q in range(n)]
    rots = []
    for i, op in enumerate(ops):
        g, qs, _ = op
        th = dv.rotation(op)
        if th is not None:
            rots.append((i, _from_ph(AZ[qs[0]]), th))
        elif g in CLIFF:
            ig = _inv(g)
            upd = []
            for q in qs:
                zq = pauli.conjugate((0, 1 << q, 1), ig, qs)
                xq = pauli.conjugate((1 << q, 0, 1), ig, qs)
                upd.append((q, _map(xq, AX, AZ, n), _map(zq, AX, AZ, n)))
            for q, ax, az in upd:
                AX[q], AZ[q] = ax, az
        else:
            return None
    return rots


def _forward(ops, a, n):
    FX = [(1 << q, 0, 1) for q in range(n)]
    FZ = [(0, 1 << q, 1) for q in range(n)]
    for op in ops[:a]:
        g, qs, _ = op
        if dv.rotation(op) is not None:
            continue
        for q in range(n):
            FX[q] = pauli.conjugate(FX[q], g, qs)
            FZ[q] = pauli.conjugate(FZ[q], g, qs)
    return [_to_ph(f) for f in FX], [_to_ph(f) for f in FZ]


# ---------------------------------------------------------------- Majorana tables (dense, k <= 4)
_I = np.eye(2, dtype=complex)
_X = np.array([[0, 1], [1, 0]], dtype=complex)
_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
_Zm = np.diag([1, -1]).astype(complex)
_LET = {(0, 0): _I, (1, 0): _X, (1, 1): _Y, (0, 1): _Zm}
_TAB = {}


def _kron(ms):
    out = np.eye(1, dtype=complex)
    for m in ms:
        out = np.kron(out, m)
    return out


def _tab(k):
    if k in _TAB:
        return _TAB[k]
    cs = []
    for a in range(k):
        for L in (_X, _Y):
            cs.append(_kron([_Zm] * a + [L] + [_I] * (k - a - 1)))
    D = 2 ** k
    pstr = {lt: _kron([_LET[l] for l in lt])
            for lt in itertools.product(((0, 0), (1, 0), (1, 1), (0, 1)), repeat=k)}
    fwd, rev, B = {}, {}, {}
    m = 2 * k
    for mu in range(m):
        for nu in range(mu + 1, m):
            b = 1j * cs[mu] @ cs[nu]
            B[(mu, nu)] = b
            for lt, P in pstr.items():
                ip = float(np.real(np.sum(P * b.T))) / D
                if abs(abs(ip) - 1) < 1e-9:
                    e = 1 if ip > 0 else -1
                    fwd[lt] = (mu, nu, e)
                    rev[(mu, nu)] = (lt, e)
                    break
    tab = {"c": cs, "B": B, "fwd": fwd, "rev": rev, "D": D}
    # sign convention of the plane rotation in the representation R(G): G c_s G^dag = sum_r c_r R_rs
    G = _gen(tab, 0, 1, math.pi / 2)
    tab["sg0"] = 1 if _rep(tab, G)[0, 1] > 0 else -1
    _TAB[k] = tab
    return tab


def _gen(tab, mu, nu, th):
    D = tab["D"]
    return math.cos(th / 2) * np.eye(D, dtype=complex) - 1j * math.sin(th / 2) * tab["B"][(mu, nu)]


def _rep(tab, G):
    cs, D = tab["c"], tab["D"]
    m = len(cs)
    Gd = G.conj().T
    cg = [G @ c @ Gd for c in cs]
    R = np.zeros((m, m))
    for r in range(m):
        for s in range(m):
            R[r, s] = float(np.real(np.sum(cs[r] * cg[s].T))) / D
    return R


def _cascade(R, sg):
    """R in SO(m) -> plane rotations [(mu, nu, theta)] in TIME order whose operator product has representation R."""
    m = R.shape[0]
    M = R.copy()
    facs = []
    for col in range(m - 1):
        for row in range(m - 1, col, -1):
            a, b = M[row - 1, col], M[row, col]
            if abs(b) < 1e-14:
                continue
            r = math.hypot(a, b)
            c, sp = a / r, -b / r
            ra, rb = M[row - 1].copy(), M[row].copy()
            M[row - 1] = c * ra - sp * rb
            M[row] = sp * ra + c * rb
            facs.append((row - 1, row, math.atan2(sg * sp, c)))
    d = np.diag(M)
    if np.abs(M - np.diag(d)).max() > 1e-8 or np.abs(np.abs(d) - 1).max() > 1e-8:
        return None
    neg = [i for i in range(m) if d[i] < 0]
    if len(neg) % 2:
        return None
    dfac = [(neg[i], neg[i + 1], math.pi) for i in range(0, len(neg), 2)]
    return dfac + facs[::-1]


# ---------------------------------------------------------------- emission
def _rz(t, ang):
    k = round(ang / PI4)
    if abs(ang - k * PI4) < 1e-10:
        ang = k * PI4
        if k % 8 == 0:
            return []
    return [("rz", (t,), float(ang))]


def _gadget(p, ang):
    x, z, s = p
    supp = [q for q in range(max(x | z, 1).bit_length()) if ((x | z) >> q) & 1]
    pre = []
    for q in supp:
        xb, zb = (x >> q) & 1, (z >> q) & 1
        if xb and zb:
            pre += [("sdg", (q,), None), ("h", (q,), None)]
        elif xb:
            pre.append(("h", (q,), None))
    cur = p
    for g, qs, _ in pre:
        cur = pauli.conjugate(cur, g, qs)
    t = supp[-1]
    lad = [("cx", (q, t), None) for q in supp if q != t]
    for g, qs, _ in lad:
        cur = pauli.conjugate(cur, g, qs)
    if cur[0] != 0 or cur[1] != (1 << t):
        raise ValueError("gadget frame error")
    post = [({"sdg": "s", "h": "h"}[g], qs, None) for g, qs, _ in pre[::-1]]
    return pre + lad + _rz(t, ang * cur[2]) + lad[::-1] + post


# ---------------------------------------------------------------- dense check
_PH = {"s": (1, 1j), "sdg": (1, -1j), "z": (1, -1), "t": (1, np.exp(1j * PI4)), "tdg": (1, np.exp(-1j * PI4))}


def _unitary(ops, wires):
    pos = {q: i for i, q in enumerate(wires)}
    m = len(wires)
    D = 2 ** m
    U = np.eye(D, dtype=complex).reshape((2,) * m + (D,))
    r2 = 1 / math.sqrt(2)
    for g, qs, a in ops:
        q = pos[qs[0]]
        if g == "h":
            a0, a1 = np.take(U, 0, axis=q), np.take(U, 1, axis=q)
            U = np.stack([(a0 + a1) * r2, (a0 - a1) * r2], axis=q)
        elif g == "x":
            U = np.ascontiguousarray(np.flip(U, axis=q))
        elif g in _PH or g == "rz":
            p0, p1 = _PH[g] if g != "rz" else (np.exp(-0.5j * a), np.exp(0.5j * a))
            i0 = [slice(None)] * (m + 1)
            i1 = list(i0)
            i0[q], i1[q] = 0, 1
            U[tuple(i0)] *= p0
            U[tuple(i1)] *= p1
        elif g == "cx":
            t = pos[qs[1]]
            idx = [slice(None)] * (m + 1)
            idx[q] = 1
            sub = U[tuple(idx)]
            U[tuple(idx)] = np.flip(sub, axis=t if t < q else t - 1).copy()
        elif g == "cz":
            t = pos[qs[1]]
            idx = [slice(None)] * (m + 1)
            idx[q], idx[t] = 1, 1
            U[tuple(idx)] *= -1
        else:
            raise ValueError(g)
    return U.reshape(D, D)


def _distance(ops1, ops2):
    wires = sorted({q for op in list(ops1) + list(ops2) for q in op[1]})
    if len(wires) > MAX_WIRES:
        return None
    U1, U2 = _unitary(ops1, wires), _unitary(ops2, wires)
    D = U1.shape[0]
    M = U1.conj().T @ U2
    tr = np.trace(M)
    if abs(tr) / D < 0.99:
        return 1.0
    return float(np.linalg.norm(M - np.exp(1j * np.angle(tr)) * np.eye(D), 2))


def _cost(ops):
    c = 0
    for g, _, a in ops:
        if g in ("t", "tdg"):
            c += 1
        elif g == "rz":
            k = a / PI4
            kr = round(k)
            c += (kr % 2) if abs(k - kr) < 1e-6 else GENERIC_COST
    return c


def _generic(a):
    k = a / PI4
    return abs(k - round(k)) >= 1e-6


# ---------------------------------------------------------------- run discovery
def _runs(cls, N):
    out, cur, u = [], [], 0
    for i in range(N):
        e = cls.get(i)
        if e is None:
            if cur:
                out.append((cur, u))
            cur, u = [], 0
            continue
        uc = e[0]
        if uc and u and uc != u:
            out.append((cur, u))
            cur, u = [], 0
        cur.append((i,) + e)
        if uc:
            u = uc
    if cur:
        out.append((cur, u))
    return out


def _pauli_of(lt, order):
    x = z = 0
    for j, (xb, zb) in enumerate(lt):
        if xb:
            x |= 1 << order[j]
        if zb:
            z |= 1 << order[j]
    return (x, z, 1)


def _build(ops, n, rots, ent, u, order, a, b):
    k = len(order)
    tab = _tab(k)
    D = tab["D"]
    Gp = np.eye(D, dtype=complex)
    Gm = np.eye(D, dtype=complex)
    for ri, uc, mu, nu, eps in ent:
        ang = rots[ri][2]
        if mu is None:
            Gp = Gp * np.exp(-0.5j * ang * eps)
            Gm = Gm * np.exp(0.5j * ang * eps)
        else:
            Gp = _gen(tab, mu, nu, ang * eps) @ Gp
            Gm = _gen(tab, mu, nu, (-ang if uc else ang) * eps) @ Gm
    Rp, Rm = _rep(tab, Gp), _rep(tab, Gm)
    RH = Rp.T @ Rm
    Hd = Gp.conj().T @ Gm
    span = ops[a:b + 1]
    cliffs = [op for op in span if dv.rotation(op) is None]
    old = _cost(span)
    FX, FZ = _forward(ops, a, n)
    for sg in (tab["sg0"], -tab["sg0"]):
        fp = _cascade(Rp, sg)
        fh = _cascade(RH, sg) if u else []
        if fp is None or fh is None:
            continue
        gl = []
        psi = 0.0
        if u:
            Hc = np.eye(D, dtype=complex)
            for mu, nu, th in fh:
                Hc = _gen(tab, mu, nu, th) @ Hc
            tr = np.trace(Hc.conj().T @ Hd) / D
            if abs(tr) < 1 - 1e-6:
                print("DBG psi fail", abs(tr), file=sys.stderr)
                continue
            psi = float(np.angle(tr))
            for mu, nu, th in fh:
                lt, e0 = tab["rev"][(mu, nu)]
                P = _pauli_of(lt, order)
                gl.append((P, th * e0 / 2))
                gl.append(((P[0], P[1] | u, 1), -th * e0 / 2))
            gl.append(((0, u, 1), psi))
        for mu, nu, th in fp:
            lt, e0 = tab["rev"][(mu, nu)]
            gl.append((_pauli_of(lt, order), th * e0))
        repl = []
        for P, ang in gl:
            if abs(ang) < 1e-12:
                continue
            loc = _from_ph(_map(P, FX, FZ, n))
            repl += _gadget(loc, ang)
        repl += cliffs
        print("DBG build sg", sg, "old", old, "new", _cost(repl), "k", k, "u", u, "nent", len(ent), file=sys.stderr)
        if _cost(repl) >= old:
            continue
        d = _distance(span, repl)
        print("DBG dist", d, file=sys.stderr)
        if d is None or d > TOL:
            continue
        return (a, b, tuple(span), tuple(repl))
    return None


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    ops = list(c.ops)
    n = c.n
    if n < 2 or n > 9:
        return []
    rots = _frame(ops, n)
    if rots is None or len(rots) < 12:
        return []
    N = len(rots)
    xs = [r[1][0] for r in rots]
    cands, seen = [], set()
    for k in (4, 3, 2):
        if k > n:
            continue
        thr = k * (2 * k - 1)
        tab = _tab(k)
        for sub in itertools.combinations(range(n), k):
            sm = sum(1 << q for q in sub)
            adm = [i for i in range(N) if not (xs[i] & ~sm)]
            if len(adm) <= thr:
                continue
            for order in itertools.permutations(sub):
                if order[0] > order[-1]:
                    continue
                cls = {}
                for i in adm:
                    x, z, s = rots[i][1]
                    lt = tuple(((x >> q) & 1, (z >> q) & 1) for q in order)
                    uc = z & ~sm
                    e = tab["fwd"].get(lt)
                    if e is not None:
                        cls[i] = (uc, e[0], e[1], s * e[2])
                    elif uc and not any(l[0] or l[1] for l in lt):
                        cls[i] = (uc, None, None, s)
                rr = _runs(cls, N)
                if len(cls) > DBG[0]:
                    DBG[0] = len(cls)
                    DBG[1] = (order, len(cls), max([len(r[0]) for r in rr] or [0]))
                for run, u in rr:
                    g =sum(1 for e in run if _generic(rots[e[0]][2]))
                    if g <= (3 * thr + 1 if u else thr):
                        continue
                    key = (run[0][0], run[-1][0])
                    if key in seen:
                        continue
                    seen.add(key)
                    cands.append((-g, key[0], key[1], order, run, u))
    cands.sort(key=lambda t: t[:4])
    wh = {}
    for r in rots:
        key = (_pc(r[1][0]), _pc(r[1][1] & ~r[1][0]), _pc(r[1][0] & r[1][1]))
        wh[key] = wh.get(key, 0) + 1
    print("DBG best", DBG[1], "hist(nX,nZ,nY)", sorted(wh.items(), key=lambda t: -t[1])[:14], file=sys.stderr)
    print("DBG n", n, "rots", N, "cands", len(cands), [(-t[0], t[1], t[2], t[3], t[5]) for t in cands[:8]],
          file=sys.stderr)
    out, taken, tries = [], [], 0
    for _, i0, i1, order, run, u in cands:
        if tries >= MAX_TRIES:
            break
        a, b = rots[i0][0], rots[i1][0]
        if any(not (b < ta or a > tb) for ta, tb in taken):
            continue
        tries += 1
        m = _build(ops, n, rots, run, u, order, a, b)
        if m is not None:
            out.append(m)
            taken.append((a, b))
    out.sort(key=lambda m: m[0])
    return out


def apply_match(c, m):
    a, b, span, repl = m
    ops = list(c.ops)
    if tuple(ops[a:b + 1]) != tuple(span):
        a = None
        L = len(span)
        for i in range(len(ops) - L + 1):
            if tuple(ops[i:i + L]) == tuple(span):
                a = i
                break
        if a is None:
            return c
        b = a + L - 1
    ops[a:b + 1] = list(repl)
    return dv.with_ops(c, ops)


RULE = Rule(
    name="controlled_gaussian_givens_resynthesis",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="Jozsa-Miyake 2008 / Terhal-DiVincenzo (Spin(2k)->SO(2k)); Kivlichan et al. PRL 120, 110501 (Givens "
           "cascades); Litinski 2018 (Pauli-rotation normal form)",
    idea="Push Cliffords out so the circuit is an ordered product of Pauli exponentials. A maximal run whose axes are "
         "(Z-string on clock wires) x (Jordan-Wigner Majorana bilinear on system wires), with one clock string u, is "
         "block diagonal in the clock parity: Gaussian G_+ on one branch, G_- on the other. Their SO(2k) matrices "
         "factor by a Givens cascade into <= k(2k-1) plane rotations each; G_+ is emitted once, H = G_+^dag G_- is "
         "emitted u-controlled (two rotations per plane) plus one parity phase, so the run costs <= 3k(2k-1)+1 "
         "rotations whatever its length.",
    trigger=find_matches,
    apply=apply_match,
)
