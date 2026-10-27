"""Symmetry-adapted Majorana block resynthesis: the Gaussian-unitary matrix R in O(2n) of a Clifford+Rz circuit is
factored as R = Q^T R_Q Q with Q a fixed momentum-basis change (Fourier / sine / cosine, optionally times the
Majorana flavour swap) and R_Q block-diagonal in momentum blocks; each piece gets its own Givens cascade."""
import math
import sys

import numpy as np

from v3.api import Rule
from v3.api import dv, pauli

_CLIFF = ("h", "s", "sdg", "x", "z", "cx", "cz")
_INV = {"h": "h", "s": "sdg", "sdg": "s", "x": "x", "z": "z", "cx": "cx", "cz": "cz"}
_QUARTER = math.pi / 4
_SNAP = 1e-9
_TOL_MASS = 1e-7
_DEBUG = False


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


def _gaussian_R(c, conv):
    """(R in O(2n), residual Clifford ops) for JW convention conv, or None if not a Gaussian unitary."""
    n = c.n
    nf = _axes(c)
    if nf is None:
        return None
    rots, cliffs = nf
    if not rots:
        return None
    table = _bilinear_tables(n)
    R = np.eye(2 * n)
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
    return u @ vt, list(cliffs)


def _rot_mat(m, a, b, phi):
    M = np.eye(m)
    cs, sn = math.cos(phi), math.sin(phi)
    M[a, a] = cs
    M[b, a] = -sn
    M[a, b] = sn
    M[b, b] = cs
    return M


def _cascade(M, idx):
    """Items ('rot', a, b, phi) / ('flip', i) in global Majorana indices idx (ascending) whose ordered matrix
    product is the orthogonal matrix M (adjacent-plane Givens cascade), or None."""
    m = len(idx)
    W = np.array(M, dtype=float)
    steps = []
    for col in range(m - 1):
        for r in range(m - 1, col, -1):
            xx, yy = W[r - 1, col], W[r, col]
            if abs(yy) < 1e-15 and xx > 0:
                continue
            psi = math.atan2(yy, xx)
            cs, sn = math.cos(psi), math.sin(psi)
            top, bot = W[r - 1].copy(), W[r].copy()
            W[r - 1] = cs * top + sn * bot
            W[r] = -sn * top + cs * bot
            steps.append((r - 1, -psi))
    if np.max(np.abs(np.abs(W) - np.eye(m))) > 1e-7:
        return None
    items = [("rot", idx[a], idx[a + 1], phi) for a, phi in steps]
    if W[m - 1, m - 1] < 0:
        items.append(("flip", idx[m - 1]))
    return items


def _inverse(seq):
    out = []
    for it in reversed(seq):
        out.append(("rot", it[1], it[2], -it[3]) if it[0] == "rot" else it)
    return out


def _is_grid(phi):
    return abs(phi - round(phi / _QUARTER) * _QUARTER) < _SNAP


def _n_arbitrary(seq):
    return sum(1 for it in seq if it[0] == "rot" and not _is_grid(it[3]))


def _library(n):
    """[(label, M (n x n, rows = modes), mode-block row lists)]; mode row k -> Majorana rows 2k + flavour."""
    j = np.arange(n)
    out = [("identity", np.eye(n), [[k] for k in range(n)])]
    rows, blocks, pos = [], [], 0
    for k in range(n // 2 + 1):
        th = 2 * math.pi * k * j / n
        if k == 0:
            rows.append(np.ones(n) / math.sqrt(n))
            blocks.append([pos])
            pos += 1
        elif 2 * k == n:
            rows.append(np.cos(th) / math.sqrt(n))
            blocks.append([pos])
            pos += 1
        else:
            rows.append(np.cos(th) * math.sqrt(2.0 / n))
            rows.append(np.sin(th) * math.sqrt(2.0 / n))
            blocks.append([pos, pos + 1])
            pos += 2
    out.append(("fourier", np.array(rows), blocks))
    kk = np.arange(n)[:, None]
    jj = np.arange(n)[None, :]
    out.append(("dst", math.sqrt(2.0 / (n + 1)) * np.sin(math.pi * (kk + 1) * (jj + 1) / (n + 1)),
                [[q] for q in range(n)]))
    dct = math.sqrt(2.0 / n) * np.cos(math.pi * kk * (2 * jj + 1) / (2 * n))
    dct[0] /= math.sqrt(2.0)
    out.append(("dct", dct, [[q] for q in range(n)]))
    return out


def _candidates(n):
    """[(label, Q matrix, forward item sequence of Q, blocks as Majorana index lists)]."""
    m2 = 2 * n
    out = []
    swap_items = [("rot", 2 * j, 2 * j + 1, math.pi / 2) for j in range(n)]
    swap_mat = np.eye(m2)
    for it in swap_items:
        swap_mat = swap_mat @ _rot_mat(m2, it[1], it[2], it[3])
    for label, M, mblocks in _library(n):
        seq, ok = [], True
        if label != "identity":
            for f in (0, 1):
                items = _cascade(M, [2 * j + f for j in range(n)])
                if items is None:
                    ok = False
                    break
                seq += items
        if not ok:
            continue
        Q = np.kron(M, np.eye(2))
        blocks = [sorted(2 * k + f for k in mb for f in (0, 1)) for mb in mblocks]
        out.append((label, Q, seq, blocks))
        out.append((label + "+swap", swap_mat @ Q, swap_items + seq, blocks))
    return out


def _plan(R):
    """Item sequence (Q^T ; blocks ; Q) for the best admissible basis, or None."""
    n = R.shape[0] // 2
    best = None
    for label, Q, seq, blocks in _candidates(n):
        RQ = Q @ R @ Q.T
        bd = np.zeros_like(RQ)
        for b in blocks:
            bd[np.ix_(b, b)] = RQ[np.ix_(b, b)]
        mass = float(np.linalg.norm(RQ - bd))
        cost = 2 * _n_arbitrary(seq) + sum(len(b) * (len(b) - 1) // 2 for b in blocks)
        if _DEBUG:
            print(f"[sym] {label}: mass={mass:.3e} cost={cost}", file=sys.stderr)
        if mass > _TOL_MASS:
            continue
        if best is None or cost < best[0]:
            best = (cost, seq, blocks, RQ)
    if best is None or best[0] >= n * (2 * n - 1):
        return None
    _, seq, blocks, RQ = best
    full = list(_inverse(seq))
    for b in blocks:
        u, _, vt = np.linalg.svd(RQ[np.ix_(b, b)])
        items = _cascade(u @ vt, b)
        if items is None:
            return None
        full += items
    return full + list(seq)


def _flip_ops(n, i):
    """Pauli whose conjugation negates exactly Majorana g_i: Z^n . g_i."""
    _, x, z = _majorana(i)
    z ^= (1 << n) - 1
    return [("x", (q,), None) for q in range(n) if (x >> q) & 1] + \
           [("z", (q,), None) for q in range(n) if (z >> q) & 1]


def _build(c, conv):
    got = _gaussian_R(c, conv)
    if got is None:
        return None
    R, cliffs = got
    n = c.n
    plan = _plan(R)
    if plan is None:
        return None
    inv = {(a, b): (x, z, sg) for (x, z), (a, b, sg) in _bilinear_tables(n).items()}
    net = []
    for it in plan:
        if it[0] == "flip":
            net += _flip_ops(n, it[1])
            continue
        x, z, sg = inv[(it[1], it[2])]
        ang = _snap(sg * it[3])
        if ang is None:
            continue
        net += _emit_pauli_rotation(x, z, ang)
    if conv == 1:
        hs = [("h", (q,), None) for q in range(n)]
        net = hs + net + hs
    return net + cliffs


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
    name="symmetry_adapted_majorana_block_resynthesis",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="Jiang et al., Phys. Rev. Applied 9, 044036 (2018); Kivlichan et al., PRL 120, 110501 (2018); "
           "Ferris, PRL 113, 010401 (2014); Verstraete, Cirac, Latorre, PRA 79, 032316 (2009); "
           "Lieb, Schultz, Mattis, Ann. Phys. 16, 407 (1961); Terhal & DiVincenzo, PRA 65, 032325 (2002)",
    idea="Gaussian unitary with Majorana-rotation matrix R in O(2n). If R commutes with a chain symmetry it is "
         "block-diagonal in a fixed real momentum basis Q (Fourier / sine / cosine, optionally with flavour swap): "
         "R = Q^T R_Q Q. Measure the off-block mass of Q R Q^T, bail unless it is below 1e-7 and the cost model "
         "beats the n(2n-1) generic cascade, then emit Q^T, the block Givens cascades, Q and the residual Clifford. "
         "Exact up to the dropped mass and floating point.",
    trigger=find_matches,
    apply=apply_match,
)
