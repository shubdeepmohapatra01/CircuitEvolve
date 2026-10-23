"""Free-fermion (Gaussian / matchgate) resynthesis: a Clifford+Rz circuit whose non-Clifford rotations are all
Majorana-bilinear Pauli rotations is a Gaussian unitary, determined by one real orthogonal 2n x 2n matrix R.
Collapse the rotations into R and re-emit <= n(2n-1) adjacent-plane Givens rotations."""
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
    viable = {0, 1}                                       # JW conventions still consistent with all axes so far
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


def _build(c, conv):
    """New ops for convention conv (0 direct JW, 1 all-Hadamard-conjugated), or None if not Gaussian."""
    n = c.n
    nf = _axes(c)
    if nf is None:
        return None
    rots, cliffs = nf
    if not rots:
        return None
    table = _bilinear_tables(n)
    m2 = 2 * n
    R = np.eye(m2)
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
    R = u @ vt
    W = R.copy()
    steps = []
    for col in range(m2 - 1):
        for r in range(m2 - 1, col, -1):
            xx, yy = W[r - 1, col], W[r, col]
            if abs(yy) < 1e-15 and xx > 0:
                continue
            psi = math.atan2(yy, xx)
            cs, sn = math.cos(psi), math.sin(psi)
            top, bot = W[r - 1].copy(), W[r].copy()
            W[r - 1] = cs * top + sn * bot
            W[r] = -sn * top + cs * bot
            steps.append((r - 1, -psi))
    if np.max(np.abs(np.abs(W) - np.eye(m2))) > 1e-7:
        return None
    flip = W[m2 - 1, m2 - 1] < 0
    inv = {(a, b): (x, z, sg) for (x, z), (a, b, sg) in table.items()}
    net = []
    for a, phi in steps:
        x, z, sg = inv[(a, a + 1)]
        ang = _snap(sg * phi)
        if ang is None:
            continue
        net += _emit_pauli_rotation(x, z, ang)
    if flip:
        net.append(("x", (n - 1,), None))
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
    nf = _axes(c)
    if nf is None or len(nf[0]) <= c.n * (2 * c.n - 1):
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
    name="free_fermion_gaussian_resynthesis",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="Jiang et al., Phys. Rev. Applied 9, 044036 (2018); Kivlichan et al., PRL 120, 110501 (2018); "
           "Terhal & DiVincenzo, PRA 65, 032325 (2002); Jozsa & Miyake, Proc. R. Soc. A 464, 3089 (2008)",
    idea="If every non-Clifford rotation, after pushing Cliffords to the end, is a Pauli rotation about a Majorana "
         "bilinear (Jordan-Wigner, directly or Hadamard-conjugated), the circuit is a Gaussian unitary whose action "
         "on the Majoranas is one orthogonal matrix R in O(2n). Multiply the plane rotations into R, factor it by "
         "a Givens cascade into at most n(2n-1) adjacent-plane rotations, re-emit each as a Pauli rotation and "
         "append the residual Clifford. Equal up to global phase; error is only floating point in the factorization.",
    trigger=find_matches,
    apply=apply_match,
)
