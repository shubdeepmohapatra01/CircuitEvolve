"""Hamming-weight phasing: k equal-angle rotations about pairwise commuting Pauli axes -> ceil(log2(k+1)) rotations.

The axes come from `pauli.frames`; a set is usable when its members commute pairwise and with every
rotation lying between the set's first and last positions (so all of them can be moved to the last
member's position). At that position each member's Pauli is copied by CNOTs onto its own clean ancilla
(eigenvalue bit b_j), a tree of full adders (one temporary AND each) accumulates the Hamming weight w,
rz(2^i theta) is applied on bit i of w, then the adder and the parity copies are undone. Ancillas return
to |0> and are reused by later groups. Uncompute is the plain inverse (8 T per AND): the angle circuit
cannot hold measurement.
"""
import bisect
import math

from v4.api import Precondition, Rule
from v4.api import dv, pauli

TWO_PI = 2 * math.pi
MAX_Q = 20
MIN_K = 4
MAX_K = 15
ANGLE_TOL = 1e-9
ROT_T = 50            # rough gridsynth price of one off-grid rotation (pricing guard only)
AND_T = 8             # compute + inverse of a temporary AND

# Gidney temporary AND on local qubits (a, b, t) = (0, 1, 2); t starts in |0>
_AND = [("h", 2), ("t", 2), ("cx", 0, 2), ("cx", 1, 2), ("cx", 2, 0), ("cx", 2, 1),
        ("tdg", 0), ("tdg", 1), ("t", 2), ("cx", 2, 0), ("cx", 2, 1), ("h", 2), ("s", 2)]
_INV = {"s": "sdg", "sdg": "s", "t": "tdg", "tdg": "t"}


def _and_ops(a, b, t):
    w = (a, b, t)
    return [(g[0], tuple(w[i] for i in g[1:]), None) for g in _AND]


def _inverse(ops):
    out = []
    for g, qs, a in reversed(ops):
        if g in _INV:
            out.append((_INV[g], qs, None))
        elif g == "rz":
            out.append((g, qs, -a))
        else:
            out.append((g, qs, a))
    return out


def _adder(bits, free):
    """Popcount of `bits` (wires) into one wire per binary weight; carries use wires from `free` (an iterator).
    -> (ops, weight wires LSB first, number of ANDs)."""
    ops, cols, nand = [], [list(bits)], 0
    j = 0
    while j < len(cols):
        col = cols[j]
        while len(col) >= 2:
            if j + 1 >= len(cols):
                cols.append([])
            t = next(free)
            nand += 1
            if len(col) >= 3:
                a, b, c = col[0], col[1], col[2]
                del col[:3]
                ops += [("cx", (c, a), None), ("cx", (c, b), None)] + _and_ops(a, b, t) + \
                       [("cx", (c, t), None), ("cx", (a, c), None), ("cx", (b, c), None)]
                col.append(c)
            else:
                a, b = col[0], col[1]
                del col[:2]
                ops += _and_ops(a, b, t) + [("cx", (a, b), None)]
                col.append(b)
            cols[j + 1].append(t)
            if len(col) == 1:
                break
        j += 1
    return ops, [col[0] for col in cols if col], nand


def _shape(k):
    """(wires needed beyond the k parity wires, number of ANDs, number of weight bits) for k bits."""
    _, weights, nand = _adder(list(range(k)), iter(range(k, 4 * k + 8)))
    return nand, nand, len(weights)


def _need(k):
    return k + _shape(k)[0]


def _norm(theta):
    r = dv.reduce_angle(theta)
    return abs(r), (1 if r >= 0 else -1)


def _base(c):
    return int(c.meta.get("hw_base", c.n))


def _max_k(base):
    avail = MAX_Q - base
    best = 0
    for k in range(MIN_K, MAX_K + 1):
        if _need(k) <= avail:
            best = k
    return best


def _saving_ok(k, theta):
    _, nand, m = _shape(k)
    left = sum(1 for j in range(m) if not dv.on_grid(dv.reduce_angle((2 ** j) * theta)))
    return ROT_T * (k - left) > AND_T * nand


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    base = _base(c)
    kmax = _max_k(base)
    if kmax < MIN_K:
        return []
    recs = pauli.frames(c.ops)
    if recs is None:
        return []
    ops = c.ops
    ent = []                                   # (magnitude, rec, effective sign)
    for r in recs:
        if r.on_grid or ops[r.pos][1][0] >= base:
            continue
        mag, s = _norm(r.theta)
        if mag < ANGLE_TOL or dv.on_grid(mag):
            continue
        ent.append((mag, r, s))
    ent.sort(key=lambda e: (e[0], e[1].pos))
    buckets, cur = [], []
    for e in ent:
        if cur and e[0] - cur[-1][0] > ANGLE_TOL:
            buckets.append(cur)
            cur = []
        cur.append(e)
    if cur:
        buckets.append(cur)

    rec_index = {r.pos: i for i, r in enumerate(recs)}
    nrec = len(recs)

    def reach(e):
        """Gaps g (g = between record g-1 and record g) the rotation can slide to: every record it passes
        commutes with it."""
        i, p = rec_index[e[1].pos], e[1].p
        lo = i
        while lo > 0 and pauli.commutes(recs[lo - 1].p, p):
            lo -= 1
        hi = i + 1
        while hi < nrec and pauli.commutes(recs[hi].p, p):
            hi += 1
        return lo, hi                       # reachable gaps lo..hi inclusive

    out = []
    for bk in buckets:
        if len(bk) < MIN_K:
            continue
        left = [(e, reach(e)) for e in sorted(bk, key=lambda e: e[1].pos)]
        while len(left) >= MIN_K:
            best = None
            for g in sorted({iv[0] for _, iv in left}):
                cl = []
                for e, iv in left:
                    if len(cl) >= kmax:
                        break
                    if iv[0] <= g <= iv[1] and all(pauli.commutes(e[1].p, f[1].p) for f in cl):
                        cl.append(e)
                if len(cl) >= MIN_K and (best is None or len(cl) > len(best[0])):
                    best = (cl, g)
            if best is None:
                break
            cl, g = best
            taken = {e[1].pos for e in cl}
            theta = sum(e[0] for e in cl) / len(cl)
            if _saving_ok(len(cl), theta):
                at = recs[g].pos if g < nrec else len(ops)
                out.append((len(cl), tuple((e[1].pos, e[2]) for e in cl), theta, at))
            left = [t for t in left if t[0][1].pos not in taken]
    out.sort(key=lambda m: (-m[0], m[1][0][0]))
    return [m[1:] for m in out]


def apply_match(c, m):
    if not dv.is_angle_circuit(c):
        return c
    members, theta, last = m
    base = _base(c)
    ops = list(c.ops)
    k = len(members)
    idxs = [p for p, _ in members]
    anc = list(range(base, base + k))
    comp = []
    for p, s in members:
        P = pauli.z_on(ops[p][1][0])
        if p < last:                            # slide forward past the Cliffords up to the block
            for i in range(p + 1, last):
                g, qs, _ = ops[i]
                if g in pauli.CLIFFORDS:
                    P = pauli.conjugate(P, g, qs)
        else:                                   # slide backward: conjugate by the inverse gates
            for i in range(p - 1, last - 1, -1):
                g, qs, _ = ops[i]
                if g in pauli.CLIFFORDS:
                    P = pauli.conjugate(P, _INV.get(g, g), qs)
        x, z, sg = P
        w = anc[idxs.index(p)]
        supp = [q for q in range(base) if ((x | z) >> q) & 1]
        pre, post = [], []
        for q in supp:
            xb, zb = (x >> q) & 1, (z >> q) & 1
            if xb and zb:
                pre += [("sdg", (q,), None), ("h", (q,), None)]
                post = [("h", (q,), None), ("s", (q,), None)] + post
            elif xb:
                pre.append(("h", (q,), None))
                post = [("h", (q,), None)] + post
        comp += pre + [("cx", (q, w), None) for q in supp] + post
        if sg * s < 0:
            comp.append(("x", (w,), None))
    free = iter(range(base + k, base + 4 * k + 8))
    add, weights, _ = _adder(anc, free)
    top = max([base + k - 1] + [q for g, qs, _ in add for q in qs])
    phase = [("rz", (w,), float(dv.reduce_angle((2 ** j) * theta))) for j, w in enumerate(weights)]
    block = comp + add + phase + _inverse(add) + _inverse(comp)
    drop = set(idxs)
    new_ops = []
    for i, op in enumerate(ops):
        if i == last:
            new_ops += block
        elif i not in drop:
            new_ops.append(op)
    n_new = max(c.n, top + 1)
    meta = dict(c.meta)
    meta["hw_base"] = base
    return dv.Circuit(n_new, dv.normalize(new_ops), meta)


RULE = Rule(
    name="hamming_weight_phasing_equal_angle_groups",
    domain="dv",
    kind="reconstruction",
    source="Kivlichan et al., Quantum 4, 296 (2020), Hamming weight phasing; Gidney, Quantum 2, 74 (2018)",
    idea="k equal-angle rotations about pairwise commuting Pauli axes (front frame, reorderable) are replaced "
         "by a Hamming-weight register: parities are copied onto clean ancillas, a full-adder tree (one "
         "temporary AND each) computes the weight, rz(2^i theta) goes on bit i, and everything is uncomputed. "
         "k rotations become ceil(log2(k+1)) rotations plus k - m ANDs; ancillas are reused between groups.",
    error_class="exact",
    resource_class="ancilla",
    precondition=Precondition(families=("dv_angle",), needs=("nonclifford_rz", "ancilla_room"), max_qubits=20,
        note="needs >= 4 off-grid rotations of one angle; widths beyond 20 qubits lose the whole-circuit check"),
    trigger=find_matches,
    apply=apply_match,
)
