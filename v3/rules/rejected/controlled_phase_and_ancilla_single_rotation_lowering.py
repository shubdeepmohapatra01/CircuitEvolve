"""Controlled-phase pairs rz_M(a) rz_{M^L1}(-a) -> one rotation on an AND ancilla + a shared hub rotation."""
import math

from v3.api import Rule
from v3.api import dv

DIAG = ("z", "s", "sdg", "cz")
SEG_OPS = ("cx", "x", "t", "tdg", "rz") + DIAG
TWO_PI = 2 * math.pi
TOL = 1e-9


def _norm(a):
    a = math.fmod(a, TWO_PI)
    if a <= -math.pi:
        a += TWO_PI
    if a > math.pi:
        a -= TWO_PI
    return a


def _is_clifford_angle(a):
    k = a / (math.pi / 4)
    return abs(k - round(k)) < 1e-9


def _segments(ops):
    """Maximal runs of ops in SEG_OPS as (start, end) half-open."""
    out, s = [], None
    for i, (g, _, _) in enumerate(ops):
        if g in SEG_OPS:
            if s is None:
                s = i
        elif s is not None:
            out.append((s, i))
            s = None
    if s is not None:
        out.append((s, len(ops)))
    return out


def _walk(ops, n, s, e):
    """Yield (index, labels_before_op); labels = per-wire (linear mask, const) as a list of ints with const in bit n."""
    lab = [1 << q for q in range(n)]
    for i in range(s, e):
        g, qs, _ = ops[i]
        yield i, lab
        if g == "cx":
            lab[qs[1]] ^= lab[qs[0]]
        elif g == "x":
            lab[qs[0]] ^= 1 << n


def _rotations(ops, n, s, e):
    """[(index, linear mask, signed normalized angle)] of the non-Clifford rotations in the segment."""
    out = []
    for i, lab in _walk(ops, n, s, e):
        a = dv.rotation(ops[i])
        if a is None:
            continue
        a = _norm(a)
        if _is_clifford_angle(a):
            continue
        L = lab[ops[i][1][0]]
        if (L >> n) & 1:
            a = _norm(-a)
        out.append((i, L & ((1 << n) - 1), a))
    return out


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    ops, n = list(c.ops), c.n
    matches = []
    for s, e in _segments(ops):
        rots = _rotations(ops, n, s, e)
        cand = {}
        for x in range(len(rots)):
            for y in range(x + 1, len(rots)):
                ix, mx, ax = rots[x]
                iy, my, ay = rots[y]
                if abs(_norm(ax + ay)) > TOL:
                    continue
                hub = mx ^ my
                if hub == 0 or mx == 0 or my == 0:
                    continue
                cand.setdefault(hub, []).append((ix, iy, mx, ax))
        groups = []
        for hub, prs in cand.items():
            used, chosen = set(), []
            for ix, iy, mx, ax in prs:
                if ix in used or iy in used:
                    continue
                used.update((ix, iy))
                chosen.append((ix, iy, mx, ax))
            if len(chosen) >= 2:
                groups.append((-len(chosen), hub, chosen))
        groups.sort(key=lambda t: (t[0], t[1]))
        taken = set()
        for negk, hub, chosen in groups:
            ch = [p for p in chosen if p[0] not in taken and p[1] not in taken]
            if len(ch) >= 2:
                for p in ch:
                    taken.update((p[0], p[1]))
                matches.append((s, e, hub, tuple(ch)))
    return matches


def _solve(lab, n, target):
    """Wires whose linear labels XOR to `target` (Gaussian elimination), or None."""
    mask = (1 << n) - 1
    basis = []   # (vector, wire-set bitmask)
    for q in range(n):
        v, w = lab[q] & mask, 1 << q
        for bv, bw in basis:
            if v ^ bv < v:
                v, w = v ^ bv, w ^ bw
        if v:
            basis.append((v, w))
            basis.sort(key=lambda t: -t[0])
    v, w = target, 0
    for bv, bw in basis:
        if v ^ bv < v:
            v, w = v ^ bv, w ^ bw
    return None if v else [q for q in range(n) if (w >> q) & 1]


def _ccx(a, b, t):
    return [("h", (t,), None), ("cx", (b, t), None), ("tdg", (t,), None), ("cx", (a, t), None),
            ("t", (t,), None), ("cx", (b, t), None), ("tdg", (t,), None), ("cx", (a, t), None),
            ("t", (b,), None), ("t", (t,), None), ("h", (t,), None), ("cx", (a, b), None),
            ("t", (a,), None), ("tdg", (b,), None), ("cx", (a, b), None)]


def apply_match(c, m):
    if not dv.is_angle_circuit(c):
        return c
    s, e, hub, pairs = m
    ops, n = list(c.ops), c.n
    meta = dict(c.meta)
    if "cpl_anc" in meta:
        b1, b2, an = meta["cpl_anc"]
        n_new = n
    else:
        b1, b2, an = n, n + 1, n + 2
        meta["cpl_anc"] = (b1, b2, an)
        n_new = n + 3
    order = sorted(pairs, key=lambda p: max(p[0], p[1]))
    last = max(order[-1][0], order[-1][1])
    first = max(order[0][0], order[0][1])
    drop = {p[0] for p in pairs} | {p[1] for p in pairs}
    pos = {max(p[0], p[1]): p for p in pairs}
    total = sum(p[3] for p in pairs)
    snaps = {}
    for i, lab in _walk(ops, n, s, e):
        if i in pos or i == first or i == last:
            snaps[i] = list(lab)

    def copy(target, anc, i):
        ws = _solve(snaps[i], n, target)
        if ws is None:
            raise ValueError("label not expressible")
        return [("cx", (q, anc), None) for q in ws]

    new = list(ops[:s])
    for i in range(s, e):
        if i not in drop:
            new.append(ops[i])
            continue
        if i not in pos:
            continue
        ix, iy, mx, ax = pos[i]
        if i == first:
            new += copy(hub, b1, i)
        cp = copy(mx, b2, i)
        new += cp + _ccx(b1, b2, an) + [("rz", (an,), _norm(2 * ax))] + _ccx(b1, b2, an) + cp
        if i == last:
            new.append(("rz", (b1,), _norm(-total)))
            new += copy(hub, b1, i)
    new += ops[e:]
    base = dv.Circuit(n_new, [], meta)
    return dv.with_ops(base, new)


RULE = Rule(
    name="controlled_phase_and_ancilla_single_rotation_lowering",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney 2018 (AND gadget); Barenco 1995 (CP = three Z rotations); Nam et al. 2018 (parity labels)",
    idea="In a Hadamard-free segment, rz_M(a) rz_{M^L1}(-a) = rz_{L1}(-a) CP_{2a}(L1, M) because x^y = x+y-2xy. "
         "With >= 2 such pairs sharing the hub L1, compute L1 once into an ancilla, compute each AND L1*M into a "
         "clean ancilla, apply one rz(2a) on it, uncompute, and apply one merged rz(-sum a) on L1: 2k rotations "
         "become k+1. (Here the AND is the unitary 7T Toffoli on a clean target, because angle circuits cannot "
         "express the measured 4T gadget.)",
    trigger=find_matches,
    apply=apply_match,
)
