"""Hamming-weight phasing: k same-angle rotations about commuting, independent Pauli axes -> ceil(log2(k+1)) rotations."""
import math

from v4.api import Rule
from v4.api import dv, pauli

TWO_PI = 2 * math.pi
QUARTER = math.pi / 4
ANGLE_TOL = 1e-12
RZ_COST = 58          # rough gridsynth cost of one generic rotation
TOFFOLI_T = 7
MAX_GROUP = 7         # 2^m - 1 sizes are the efficient ones (3 -> 2 rotations, 7 -> 3 rotations)
MIN_GROUP = 3


def _generic(a):
    """True if the (normalised) angle is NOT a multiple of pi/4 (i.e. costs a synthesized rotation)."""
    r = a / QUARTER
    return abs(r - round(r)) > 1e-9


def _norm(a):
    return math.remainder(a, TWO_PI)


def _commute(p, q):
    return (bin(p[0] & q[1]).count("1") + bin(p[1] & q[0]).count("1")) % 2 == 0


def _indep(vec, basis):
    v = vec
    while v:
        h = v.bit_length() - 1
        if h in basis:
            v ^= basis[h]
        else:
            basis[h] = v
            return True
    return False


def _runs(c):
    """Maximal runs of pairwise commuting rotations: (lo, hi, [(op index, Pauli in the frame at hi)])."""
    ops = c.ops
    out, run = [], []
    for i, op in enumerate(ops):
        g, qs, _ = op
        if dv.rotation(op) is None:
            if run:
                mask = 0
                for q in qs:
                    mask |= 1 << q
                new = []
                for j, p in run:
                    if (p[0] | p[1]) & mask:
                        p = pauli.conjugate(p, g, qs)
                    new.append((j, p))
                run = new
        else:
            z = pauli.z_on(qs[0])
            if any(not _commute(p, z) for _, p in run):
                out.append((run[0][0], i - 1, run))
                run = []
            run.append((i, z))
    if run:
        out.append((run[0][0], len(ops) - 1, run))
    return out


# ---------------------------------------------------------------- adder network
def _ccx(a, b, c):
    return [("h", (c,), None), ("cx", (b, c), None), ("tdg", (c,), None), ("cx", (a, c), None),
            ("t", (c,), None), ("cx", (b, c), None), ("tdg", (c,), None), ("cx", (a, c), None),
            ("t", (b,), None), ("t", (c,), None), ("h", (c,), None), ("cx", (a, b), None),
            ("t", (a,), None), ("tdg", (b,), None), ("cx", (a, b), None)]


def _inverse(ops):
    inv = {"s": "sdg", "sdg": "s", "t": "tdg", "tdg": "t"}
    out = []
    for g, qs, a in reversed(ops):
        if g in inv:
            out.append((inv[g], qs, None))
        elif g == "rz":
            out.append((g, qs, -a))
        else:
            out.append((g, qs, a))
    return out


def _adder(bits, next_wire):
    """Popcount of `bits` into binary weight wires (LSB first). Returns (ops, weight wires, next free wire, #ccx)."""
    ops, cols, ntof = [], [list(bits)], 0
    j = 0
    while j < len(cols):
        col = cols[j]
        while len(col) >= 2:
            if j + 1 >= len(cols):
                cols.append([])
            carry = next_wire
            next_wire += 1
            if len(col) >= 3:
                a, b, c = col[0], col[1], col[2]
                del col[:3]
                ops += [("cx", (a, b), None), ("cx", (a, c), None)] + _ccx(b, c, carry) + \
                       [("cx", (a, carry), None), ("cx", (b, a), None), ("cx", (c, a), None)]
            else:
                a, b = col[0], col[1]
                del col[:2]
                ops += _ccx(a, b, carry) + [("cx", (b, a), None)]
            ntof += 1
            col.append(a)
            cols[j + 1].append(carry)
            if len(col) == 1:
                break
        j += 1
    weights = [col[0] for col in cols if col]
    return ops, weights, next_wire, ntof


def _saving(k, theta):
    """Rough cost saving (T) of grouping k rotations of angle theta; adder shape does not depend on theta."""
    _, weights, _, ntof = _adder(list(range(k)), k)
    new = TOFFOLI_T * ntof
    for j in range(len(weights)):
        phi = _norm((2 ** j) * theta)
        if _generic(phi):
            new += RZ_COST
        else:
            r = round(phi / QUARTER)
            new += 1 if r % 2 else 0
    return RZ_COST * k - new


# ---------------------------------------------------------------- trigger / apply
def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    ops = c.ops
    n = c.n
    out = []
    for lo, hi, run in _runs(c):
        if len(run) < MIN_GROUP:
            continue
        ent = []
        for idx, p in run:
            an = _norm(dv.rotation(ops[idx]))
            if _generic(an):
                ent.append((abs(an), idx, p))
        if len(ent) < MIN_GROUP:
            continue
        ent.sort(key=lambda e: (e[0], e[1]))
        clusters, cur = [], [ent[0]]
        for e in ent[1:]:
            if e[0] - cur[-1][0] <= ANGLE_TOL:
                cur.append(e)
            else:
                clusters.append(cur)
                cur = [e]
        clusters.append(cur)
        for cl in clusters:
            if len(cl) < MIN_GROUP:
                continue
            cl.sort(key=lambda e: e[1])
            basis, members = {}, []
            for mag, idx, p in cl:
                if _indep(p[0] | (p[1] << n), basis):
                    members.append((mag, idx))
            while len(members) >= MIN_GROUP:
                size = MAX_GROUP if len(members) >= MAX_GROUP else MIN_GROUP
                chunk, members = members[:size], members[size:]
                theta = sum(m[0] for m in chunk) / len(chunk)
                if _saving(len(chunk), theta) > 0:
                    out.append((lo, hi, tuple(m[1] for m in chunk)))
    return out


def apply_match(c, m):
    if not dv.is_angle_circuit(c):
        return c
    lo, hi, idxs = m
    ops = list(c.ops)
    idxset = set(idxs)
    paulis = {}
    for i in range(lo, hi + 1):
        g, qs, _ = ops[i]
        if i in idxset:
            paulis[i] = pauli.z_on(qs[0])
        elif dv.rotation(ops[i]) is None:
            for j in list(paulis):
                paulis[j] = pauli.conjugate(paulis[j], g, qs)
    n, k = c.n, len(idxs)
    angs = {i: _norm(dv.rotation(ops[i])) for i in idxs}
    theta = sum(abs(a) for a in angs.values()) / k
    anc = list(range(n, n + k))

    comp = []                                   # indicator b_i = [signed Pauli has eigenvalue -1] -> anc_i
    for i, w in zip(idxs, anc):
        x, z, sg = paulis[i]
        s = sg * (1 if angs[i] > 0 else -1)
        supp = [q for q in range(n) if ((x | z) >> q) & 1]
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
        if s < 0:
            comp.append(("x", (w,), None))

    add, weights, nxt, _ = _adder(anc, n + k)
    phase = [("rz", (w,), float((2 ** j) * theta)) for j, w in enumerate(weights)]
    block = comp + add + phase + _inverse(add) + _inverse(comp)

    span = [ops[i] for i in range(lo, hi + 1) if i not in idxset]
    new_ops = ops[:lo] + span + block + ops[hi + 1:]
    wide = dv.Circuit(nxt, [], dict(c.meta))
    return dv.with_ops(wide, new_ops)


RULE = Rule(
    name="hamming_weight_phasing_same_angle_group",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Kivlichan, Gidney et al., Quantum 4, 296 (2020), Hamming weight phasing; Gidney arXiv:1709.06648",
    idea="Rotations of equal angle theta about pairwise commuting, GF(2)-independent Pauli axes (found by pushing "
         "each Z-rotation forward through the Cliffords to the end of a run of mutually commuting rotations) are "
         "removed and replaced by one phase e^{i theta W}, W = number of -1 eigenvalues. W is computed into clean "
         "ancillas (parity of each axis onto its own ancilla, then a full-adder popcount tree with 7-T Toffolis), "
         "rz(2^j theta) is applied on weight bit j, and everything is uncomputed. Groups of 3 or 7 give 2 or 3 "
         "rotations instead of 3 or 7; theta at multiples of pi/16 makes some of them Clifford/T.",
    trigger=find_matches,
    apply=apply_match,
)
