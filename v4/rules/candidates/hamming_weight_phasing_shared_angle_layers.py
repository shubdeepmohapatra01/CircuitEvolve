"""Hamming weight phasing of equal-angle rotation layers (Gidney-Fowler 2019 / Kivlichan et al. 2020), Clifford+Rz.

Rotations with the same |residue| angle whose Z-parity strings can be pushed forward to one common time (cx / x /
diagonal gates only; an h on a wire of the string ends its life) commute and act as exp(i b W), W = Hamming weight of
the parity bits. The bits are copied to clean ancillas, summed with a tree of AND-based adders (4 T per AND), W's
binary digits get rz(2^j b), and everything is uncomputed.
"""
import math

from v4.api import Rule
from v4.api import dv

TWO_PI = 2 * math.pi
QUARTER = math.pi / 4
MIN_K = 3
MAX_K = 32


def _is_generic(a):
    r = a / QUARTER
    return abs(r - round(r)) > 1e-7


def _key(a):
    """(key in (0, pi], flip): rz(a) ~ exp(i key p) (flip=0) or exp(i key (1-p)) up to phase (flip=1)."""
    m = a % TWO_PI
    if m <= TWO_PI - m:
        return round(m, 9), 0
    return round(TWO_PI - m, 9), 1


def _push(op, S, const):
    g, qs, _ = op
    if g == "h":
        return None if (S >> qs[0]) & 1 else (S, const)
    if g == "cx":
        ctl, tgt = qs
        if (S >> tgt) & 1:
            S ^= 1 << ctl
        return S, const
    if g == "x":
        return S, const ^ ((S >> qs[0]) & 1)
    return S, const


def _death(ops, i):
    S, const = 1 << ops[i][1][0], 0
    for j in range(i + 1, len(ops)):
        r = _push(ops[j], S, const)
        if r is None:
            return j
        S, const = r
    return len(ops)


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    ops = c.ops
    buckets = {}
    for i, op in enumerate(ops):
        if op[0] == "rz" and _is_generic(op[2]):
            key, flip = _key(op[2])
            buckets.setdefault(key, []).append((i, flip, _death(ops, i)))
    out = []
    for key, mem in sorted(buckets.items()):
        mem = list(mem)
        while len(mem) >= MIN_K:
            best = None
            for t, _, _ in mem:
                alive = [m for m in mem if m[0] <= t < m[2]]
                if best is None or len(alive) > len(best):
                    best = alive
            if best is None or len(best) < MIN_K:
                break
            best = best[-MAX_K:]
            k = len(best)
            if k.bit_length() < k:                      # m = ceil(log2(k+1)) = bit_length(k) must be < k
                out.append((k, tuple(m[0] for m in best), key, tuple(m[1] for m in best)))
            used = {m[0] for m in best}
            mem = [m for m in mem if m[0] not in used]
    out.sort(key=lambda m: (-m[0], m[1]))
    return [(idxs, key, flips) for _, idxs, key, flips in out]


def _and_compute(a, b, t):
    return [("h", (t,), None), ("t", (t,), None), ("cx", (a, t), None), ("cx", (b, t), None),
            ("cx", (t, a), None), ("cx", (t, b), None), ("tdg", (a,), None), ("tdg", (b,), None),
            ("t", (t,), None), ("cx", (t, a), None), ("cx", (t, b), None), ("h", (t,), None), ("s", (t,), None)]


_INV = {"h": "h", "x": "x", "cx": "cx", "s": "sdg", "sdg": "s", "t": "tdg", "tdg": "t"}


def _adjoint(ops):
    return [(_INV[g], qs, None) for g, qs, _ in reversed(ops)]


def _network(copies, start):
    """Adder tree: full adder = 2 CNOT + 1 AND, half adder = 1 AND. Returns (ops, [(qubit, level)], next qubit)."""
    nxt = start
    net = []
    levels = [list(copies)]
    wbits = []
    j = 0
    while j < len(levels):
        lv = levels[j]
        while len(lv) >= 3:
            a, b, cc = lv.pop(0), lv.pop(0), lv.pop(0)
            r, nxt = nxt, nxt + 1
            net += [("cx", (cc, a), None), ("cx", (cc, b), None)] + _and_compute(a, b, r)
            net += [("cx", (cc, r), None), ("cx", (a, cc), None), ("cx", (b, cc), None)]
            lv.append(cc)
            if j + 1 == len(levels):
                levels.append([])
            levels[j + 1].append(r)
        if len(lv) == 2:
            a, b = lv
            r, nxt = nxt, nxt + 1
            net += _and_compute(a, b, r) + [("cx", (a, b), None)]
            lv = [b]
            if j + 1 == len(levels):
                levels.append([])
            levels[j + 1].append(r)
        if lv:
            wbits.append((lv[0], j))
        j += 1
    return net, wbits, nxt


def apply_match(c, m):
    if not dv.is_angle_circuit(c):
        return c
    idxs, key, flips = m
    last = max(idxs)
    n = c.n
    copy_ops, copies = [], []
    for j, (i, flip) in enumerate(zip(idxs, flips)):
        S, const = 1 << c.ops[i][1][0], 0
        for k in range(i + 1, last + 1):
            r = _push(c.ops[k], S, const)
            if r is None:
                return c
            S, const = r
        anc = n + j
        for w in range(n):
            if (S >> w) & 1:
                copy_ops.append(("cx", (w, anc), None))
        if const ^ flip:
            copy_ops.append(("x", (anc,), None))
        copies.append(anc)
    net, wbits, total = _network(copies, n + len(copies))
    rots = [("rz", (q,), math.fmod(key * (1 << j), TWO_PI)) for q, j in wbits]
    repl = copy_ops + net + rots + _adjoint(net) + list(reversed(copy_ops))
    skip = set(idxs)
    ops = []
    for i, op in enumerate(c.ops):
        if i == last:
            ops += repl
        elif i not in skip:
            ops.append(op)
    return dv.Circuit(total, dv.normalize(ops), dict(c.meta))


RULE = Rule(
    name="hamming_weight_phasing_shared_angle_layers",
    domain="dv",
    kind="resource",
    contract="relaxed",
    source="Gidney & Fowler, Quantum 3, 135 (2019); Kivlichan et al., Quantum 4, 296 (2020); Gidney, Quantum 2, 74 (2018)",
    idea="k >= 3 equal-|angle| rotations on commuting Z-parity axes multiply to exp(i b W), W = Hamming weight of "
         "their parity bits. Copy the bits to clean ancillas, sum with a tree of AND-based adders, apply "
         "rz(2^j b) to the ceil(log2(k+1)) weight bits, uncompute: k rotations -> m rotations + (k - m) ANDs.",
    trigger=find_matches,
    apply=apply_match,
)
