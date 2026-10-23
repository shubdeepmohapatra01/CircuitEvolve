"""Parity-split Majorana resynthesis: if the Gaussian R in O(2n) commutes with a Majorana-index reversal P,
conjugate by pi/4 plane rotations (T gates) and factor the two n x n sectors separately."""
import math

import numpy as np

from v3.api import Rule
from v3.api import dv, pauli

_CLIFF = ("h", "s", "sdg", "x", "z", "cx", "cz")
_INV = {"h": "h", "s": "sdg", "sdg": "s", "x": "x", "z": "z", "cx": "cx", "cz": "cz"}
_QUARTER = math.pi / 4
_SNAP = 1e-9


def _popcount(v):
    return bin(v).count("1")


def _majorana(i):
    """Majorana g_i = Z_{<j} X_j (i = 2j) or Z_{<j} Y_j (i = 2j+1) as (k, x, z): i^k X^x Z^z."""
    j = i // 2
    if i % 2 == 0:
        return (0, 1 << j, (1 << j) - 1)
    return (1, 1 << j, (1 << (j + 1)) - 1)


def _bilinear_tables(n):
    """{(x, z): (a, b, sigma)} with positive Hermitian Pauli P = sigma * (-i g_a g_b), a < b."""
    maj = [_majorana(i) for i in range(2 * n)]
    table = {}
    for a in range(2 * n):
        k1, x1, z1 = maj[a]
        for b in range(a + 1, 2 * n):
            k2, x2, z2 = maj[b]
            k = (k1 + k2 + 2 * _popcount(z1 & x2) - 1) % 4
            x, z = x1 ^ x2, z1 ^ z2
            d = (k - _popcount(x & z)) % 4
            if d not in (0, 2):
                continue
            table[(x, z)] = (a, b, 1 if d == 0 else -1)
    return table


def _axes(c):
    """Normal form: (list of (x, z, sign, theta) rotation axes in the initial frame, list of Clifford ops)."""
    cliffs, rots = [], []
    table = _bilinear_tables(c.n)
    viable = {0, 1}
    for op in c.ops:
        th = dv.rotation(op)
        if th is not None:
            p = pauli.z_on(op[1][0])
            for g, qs, _ in reversed(cliffs):
                p = pauli.conjugate(p, _INV[g], qs)
            viable = {v for v in viable if ((p[0], p[1]) if v == 0 else (p[1], p[0])) in table}
            if not viable:
                return None
            rots.append((p[0], p[1], p[2], th))
        elif op[0] in _CLIFF:
            cliffs.append(op)
        else:
            return None
    return rots, cliffs


def _emit_pauli_rotation(x, z, theta):
    """exp(-i theta P / 2) for the positive Hermitian Pauli P = (x, z): basis change, CX chain, rz, undo."""
    qs = [q for q in range(max(x.bit_length(), z.bit_length())) if ((x | z) >> q) & 1]
    pre = []
    for q in qs:
        xb, zb = (x >> q) & 1, (z >> q) & 1
        if xb and zb:
            pre += [("sdg", (q,), None), ("h", (q,), None)]
        elif xb:
            pre.append(("h", (q,), None))
    chain = [("cx", (qs[i], qs[i + 1]), None) for i in range(len(qs) - 1)]
    return pre + chain + [("rz", (qs[-1],), theta)] + chain[::-1] + _post_in_order(qs, x, z)


def _post_in_order(qs, x, z):
    out = []
    for q in qs:
        xb, zb = (x >> q) & 1, (z >> q) & 1
        if xb and zb:
            out += [("h", (q,), None), ("s", (q,), None)]
        elif xb:
            out.append(("h", (q,), None))
    return out


def _snap(a):
    a = math.fmod(a, 2 * math.pi)
    if a > math.pi:
        a -= 2 * math.pi
    elif a <= -math.pi:
        a += 2 * math.pi
    k = round(a / _QUARTER)
    if abs(a - k * _QUARTER) < _SNAP:
        if k % 8 == 0:
            return None
        return k * _QUARTER
    return a


def _gmat(m2, a, b, phi):
    G = np.eye(m2)
    cs, sn = math.cos(phi), math.sin(phi)
    G[a, a], G[b, a], G[a, b], G[b, b] = cs, -sn, sn, cs
    return G


def _collapse(c, conv):
    """(R, table, cliffs) for convention conv, or None."""
    nf = _axes(c)
    if nf is None:
        return None
    rots, cliffs = nf
    if not rots:
        return None
    table = _bilinear_tables(c.n)
    R = np.eye(2 * c.n)
    for x, z, s, th in rots:
        if conv == 1:
            x, z, s = z, x, s * (-1 if _popcount(x & z) % 2 else 1)
        hit = table.get((x, z))
        if hit is None:
            return None
        a, b, sigma = hit
        phi = sigma * s * th
        cs, sn = math.cos(phi), math.sin(phi)
        ra, rb = R[:, a].copy(), R[:, b].copy()
        R[:, a] = cs * ra - sn * rb
        R[:, b] = sn * ra + cs * rb
    u, _, vt = np.linalg.svd(R)
    return u @ vt, table, cliffs


def _involution(R, n):
    """The valid signed reversal (symmetric, squares to I) closest to commuting with R, if within 1e-9."""
    m2 = 2 * n
    best = None
    for k in range(4):
        sg = [1 if k == 0 else (-1) ** a if k == 1 else (-1) ** (a // 2) if k == 2 else (-1) ** a * (-1) ** (a // 2)
              for a in range(m2)]
        P = np.zeros((m2, m2))
        for a in range(m2):
            P[a, m2 - 1 - a] = sg[a]
        if not (np.allclose(P, P.T) and np.allclose(P @ P, np.eye(m2))):
            continue
        d = float(np.linalg.norm(P @ R @ P.T - R))
        if best is None or d < best[0]:
            best = (d, P)
    if best is None or best[0] > 1e-9:
        return None
    return best[1]


def _basis_change(P, n):
    """phi_a with Qt = prod G(a, 2n-1-a; phi_a), Q = Qt^T, Q P Q^T = diag(+1 x n, -1 x n)."""
    m2 = 2 * n
    phis = []
    Qt = np.eye(m2)
    for a in range(n):
        for phi in (_QUARTER, -_QUARTER):
            G = _gmat(m2, a, m2 - 1 - a, phi)
            D = G @ P @ G.T
            if abs(D[a, a] - 1) < 1e-9 and abs(D[m2 - 1 - a, m2 - 1 - a] + 1) < 1e-9:
                phis.append(phi)
                Qt = Qt @ G
                break
        else:
            return None
    Q = Qt.T
    D = Q @ P @ Q.T
    if np.max(np.abs(D - np.diag(np.r_[np.ones(n), -np.ones(n)]))) > 1e-9:
        return None
    return phis, Q


def _cascade(W):
    b = W.shape[0]
    W = W.copy()
    steps = []
    for col in range(b - 1):
        for r in range(b - 1, col, -1):
            xx, yy = W[r - 1, col], W[r, col]
            if abs(yy) < 1e-15 and xx > 0:
                continue
            psi = math.atan2(yy, xx)
            cs, sn = math.cos(psi), math.sin(psi)
            top, bot = W[r - 1].copy(), W[r].copy()
            W[r - 1] = cs * top + sn * bot
            W[r] = -sn * top + cs * bot
            steps.append((r - 1, -psi))
    if np.max(np.abs(np.abs(W) - np.eye(b))) > 1e-7:
        return None
    return steps, bool(W[b - 1, b - 1] < 0)


def _pauli_ops(x, z):
    ops = []
    for q in range(max(x.bit_length(), z.bit_length())):
        if (x >> q) & 1:
            ops.append(("x", (q,), None))
        if (z >> q) & 1:
            ops.append(("z", (q,), None))
    return ops


def _build(c, conv):
    n = c.n
    col = _collapse(c, conv)
    if col is None:
        return None
    R, table, cliffs = col
    P = _involution(R, n)
    if P is None:
        return None
    bc = _basis_change(P, n)
    if bc is None:
        return None
    phis, Q = bc
    m2 = 2 * n
    RQ = Q @ R @ Q.T
    inv = {(a, b): (x, z, sg) for (x, z), (a, b, sg) in table.items()}

    def plane(a, b, phi):
        if (a, b) not in inv:
            return None
        x, z, sg = inv[(a, b)]
        ang = _snap(sg * phi)
        return [] if ang is None else _emit_pauli_rotation(x, z, ang)

    net = []
    for a in range(n):
        e = plane(a, m2 - 1 - a, phis[a])
        if e is None:
            return None
        net += e
    flips = []
    for off in (0, n):
        u, _, vt = np.linalg.svd(RQ[off:off + n, off:off + n])
        res = _cascade(u @ vt)
        if res is None:
            return None
        steps, flip = res
        for a, phi in steps:
            e = plane(a + off, a + off + 1, phi)
            if e is None:
                return None
            net += e
        flips.append(flip)
    if flips[0] != flips[1]:
        return None
    if flips[0]:
        _, xa, za = _majorana(n - 1)
        _, xb, zb = _majorana(m2 - 1)
        net += _pauli_ops(xa ^ xb, za ^ zb)
    for a in range(n):
        e = plane(a, m2 - 1 - a, -phis[a])
        if e is None:
            return None
        net += e
    if conv == 1:
        hs = [("h", (q,), None) for q in range(n)]
        net = hs + net + hs
    return net + list(cliffs)


def _cost(ops):
    total = 0
    for op in ops:
        th = dv.rotation(op)
        if th is None:
            continue
        k = round(th / _QUARTER)
        if abs(th - k * _QUARTER) < _SNAP:
            total += k % 2
        else:
            total += 50
    return total


def find_matches(c):
    if not dv.is_angle_circuit(c) or c.n > 20 or c.n < 2:
        return []
    if _axes(c) is None:
        return []
    old = _cost(c.ops)
    for conv in (0, 1):
        new = _build(c, conv)
        if new is not None and _cost(new) < old:
            return [conv]
    return []


def apply_match(c, m):
    new = _build(c, m)
    if new is None:
        return c
    return dv.with_ops(c, new)


RULE = Rule(
    name="majorana_reversal_involution_block_resynthesis",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="Jiang et al., Phys. Rev. Applied 9, 044036 (2018); Kivlichan et al., PRL 120, 110501 (2018); "
           "Terhal & DiVincenzo, PRA 65, 032325 (2002); Lieb, Schultz, Mattis, Ann. Phys. 16, 407 (1961)",
    idea="A Gaussian unitary with R in O(2n) commuting with a signed Majorana-index reversal P (P^2 = I) is block "
         "diagonal in P's eigenbasis; the basis change is n disjoint pi/4 plane rotations (one T each). Factor the "
         "two n x n sectors separately (<= 2 n(n-1)/2 angles instead of n(2n-1)) and emit Q^T, blocks, Q, Clifford.",
    trigger=find_matches,
    apply=apply_match,
)
