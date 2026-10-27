"""Hadamard-free phase blocks re-expressed in the monomial (Reed-Muller) basis; each monomial of degree >= 2 is
paid for with one rotation on an AND-ancilla instead of 2^d - 1 parity rotations."""
import math

from v4.api import Rule
from v4.api import dv

C_RZ = 45.0              # gridsynth cost of one non-grid rotation at the current operating point
AND_T = 8                # AND gadget compute (4 T) + exact inverse uncompute (4 T): angle circuits hold no measurement
MAX_SUPP = 9             # parity support size above which a block is skipped (2^supp subsets per rotation)
PI = math.pi
TWO_PI = 2 * PI
PHASE = ("cx", "x", "z", "s", "sdg", "t", "tdg", "rz")
ROT = {"z": PI, "s": PI / 2, "sdg": -PI / 2, "t": PI / 4, "tdg": -PI / 4}

# Gidney temporary AND (local qubits a=0, b=1, target=2); inverse = reversed with t<->tdg, s<->sdg
_AND = [("h", 2), ("t", 2), ("cx", 0, 2), ("cx", 1, 2), ("cx", 2, 0), ("cx", 2, 1), ("tdg", 0), ("tdg", 1),
        ("t", 2), ("cx", 2, 0), ("cx", 2, 1), ("h", 2), ("s", 2)]
_DAG = {"t": "tdg", "tdg": "t", "s": "sdg", "sdg": "s"}


def _gate(g, qs):
    return (g[0], tuple(qs[i] for i in g[1:]), None)


def _and_compute(a, b, t):
    return [_gate(g, (a, b, t)) for g in _AND]


def _and_uncompute(a, b, t):
    return [_gate((_DAG.get(g[0], g[0]),) + g[1:], (a, b, t)) for g in reversed(_AND)]


def _theta(op):
    g, _, a = op
    return float(a) if g == "rz" else ROT.get(g)


def _cost(theta):
    r = theta / (PI / 4)
    if abs(r - round(r)) < 1e-7:
        return 1.0 if int(round(r)) % 2 else 0.0
    return C_RZ


def _reduce(a):
    a = math.fmod(a, TWO_PI)
    if a > PI:
        a -= TWO_PI
    elif a <= -PI:
        a += TWO_PI
    return a


def _reorder(ops):
    """Stable topological reorder that delays h / cz / unknown gates, so Hadamard-free runs get longer."""
    n = len(ops)
    queues = {}
    for i, (_, qs, _) in enumerate(ops):
        for q in qs:
            queues.setdefault(q, []).append(i)
    ptr = {q: 0 for q in queues}
    done = [False] * n
    out = []

    def ready(i):
        return all(queues[q][ptr[q]] == i for q in ops[i][1])

    first = 0
    while len(out) < n:
        while done[first]:
            first += 1
        pick = None
        fallback = None
        for i in range(first, n):
            if done[i] or not ready(i):
                continue
            if ops[i][0] in PHASE:
                pick = i
                break
            if fallback is None:
                fallback = i
        if pick is None:
            pick = fallback
        done[pick] = True
        out.append(ops[pick])
        for q in ops[pick][1]:
            ptr[q] += 1
    return out


def _runs(ops):
    out, i, n = [], 0, len(ops)
    while i < n:
        if ops[i][0] not in PHASE:
            i += 1
            continue
        j = i
        while j < n and ops[j][0] in PHASE:
            j += 1
        out.append((i, j))
        i = j
    return out


def _block_info(block):
    """-> (wires, coeffs {monomial var-tuple: angle}, AND prefixes, cost before, cost after) or None."""
    wires = sorted({q for op in block for q in op[1]})
    var = {q: k for k, q in enumerate(wires)}
    p = {q: 1 << var[q] for q in wires}
    c = {q: 0 for q in wires}
    acc = {}
    before = 0.0
    nrot = 0
    for op in block:
        g, qs, _ = op
        if g == "cx":
            a, b = qs
            p[b] ^= p[a]
            c[b] ^= c[a]
        elif g == "x":
            c[qs[0]] ^= 1
        else:
            th = _theta(op)
            before += _cost(th)
            nrot += 1
            supp = p[qs[0]]
            if supp.bit_count() > MAX_SUPP:
                return None
            w = -th if c[qs[0]] else th
            sub = supp
            while sub:
                acc[sub] = acc.get(sub, 0.0) + w
                sub = (sub - 1) & supp
    if nrot < 2:
        return None
    coeffs = {}
    for m, w in acc.items():
        d = m.bit_count()
        v = _reduce(w * (-2.0) ** (d - 1))
        if abs(v) > 1e-9:
            coeffs[tuple(i for i in range(len(wires)) if (m >> i) & 1)] = v
    prefixes = set()
    for t in coeffs:
        for L in range(2, len(t) + 1):
            prefixes.add(t[:L])
    after = sum(_cost(v) for v in coeffs.values()) + AND_T * len(prefixes)
    return wires, coeffs, prefixes, before, after


def _emit(wires, coeffs, prefixes, base):
    ops = []
    for t, v in sorted(coeffs.items()):
        if len(t) == 1:
            ops.append(("rz", (wires[t[0]],), v))
    kids = {}
    for pre in prefixes:
        kids.setdefault(pre[:-1], []).append(pre)
    for lst in kids.values():
        lst.sort()
    depth = [0]

    def visit(pre, qubit):
        for ch in kids.get(pre, []):
            lvl = len(ch) - 2
            anc = base + lvl
            depth[0] = max(depth[0], lvl + 1)
            ops.extend(_and_compute(qubit, wires[ch[-1]], anc))
            if ch in coeffs:
                ops.append(("rz", (anc,), coeffs[ch]))
            visit(ch, anc)
            ops.extend(_and_uncompute(qubit, wires[ch[-1]], anc))

    for i in range(len(wires)):
        visit((i,), wires[i])
    return ops, depth[0]


def trigger(c):
    if not dv.is_angle_circuit(c):
        return []
    ops = _reorder(list(c.ops))
    found = []
    for s, e in _runs(ops):
        block = ops[s:e]
        info = _block_info(block)
        if info is None:
            continue
        gain = info[3] - info[4]
        if gain > 1e-9:
            found.append((gain, s, tuple(block)))
    found.sort(key=lambda x: (-x[0], x[1]))
    return [(s, blk) for _, s, blk in found]


def apply(c, m):
    if not dv.is_angle_circuit(c):
        return c
    s, block = m
    ops = _reorder(list(c.ops))
    e = s + len(block)
    if tuple(ops[s:e]) != tuple(block):
        return c
    info = _block_info(list(block))
    if info is None:
        return c
    wires, coeffs, prefixes, _, _ = info
    base = c.meta.get("and_base", c.n)
    new_ops, k = _emit(wires, coeffs, prefixes, base)
    lin = [op for op in block if op[0] in ("cx", "x")]
    out_ops = ops[:s] + new_ops + lin + ops[e:]
    n_new = max(c.n, base + k)
    meta = dict(c.meta)
    meta["and_base"] = base
    return dv.with_ops(dv.Circuit(n_new, [], meta), out_ops)


RULE = Rule(
    name="and_monomial_phase_polynomial_resynthesis",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Amy-Mosca 2019 (Reed-Muller phase polynomials); Gidney 2018 (temporary AND); Gidney-Ekera 2021",
    idea="A Hadamard-free block is diag(e^{i f(x)}) . L. Writing f in the monomial basis, xor_{i in S} x_i = "
         "sum_{T subset S} (-2)^{|T|-1} prod_{i in T} x_i, gives one coefficient per monomial; each monomial of "
         "degree >= 2 is computed onto a clean AND-ancilla (shared prefix ladder), rotated once, and uncomputed. "
         "Fires only when monomials plus AND cost is below the rotations replaced.",
    trigger=trigger,
    apply=apply,
)
