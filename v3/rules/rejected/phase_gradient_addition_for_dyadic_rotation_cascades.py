"""Phase-gradient addition for dyadic rotation cascades (Gidney; Babbush et al. 2018).

Rotations rz(2 pi s / 2^e) with distinct e inside one Hadamard-free segment are replaced by CNOT loading of their
parity bits into a B-bit work register and one ripple-carry addition into a shared phase-gradient catalyst.
Everything is Clifford+T except the B-3 gradient preparation / unpreparation rotations.
"""
import math

from v3.api import Rule
from v3.api import dv

E_MIN, E_MAX = 3, 14
TOL = 1e-9
MIN_GROUP = 4


# ------------------------------------------------------------------------------------------------ scan
def _dyadic(op):
    a = dv.rotation(op)
    if a is None:
        return None
    a = math.fmod(a, 2 * math.pi)
    if a > math.pi:
        a -= 2 * math.pi
    elif a <= -math.pi:
        a += 2 * math.pi
    if abs(a) < 1e-12:
        return None
    e = int(round(math.log2(2 * math.pi / abs(a))))
    if E_MIN <= e <= E_MAX and abs(abs(a) - 2 * math.pi / 2 ** e) <= TOL:
        return (1 if a > 0 else -1), e
    return None


def _scan(c):
    """Kept rotations: dict(idx, seg, s, e, mask, const, wires) where wires = labels of all wires at that op."""
    n = c.n
    lab = [(1 << q, 0) for q in range(n)]
    seg, out = 0, []
    for i, op in enumerate(c.ops):
        g, qs, _ = op
        if g == "h":
            seg += 1
            lab = [(1 << q, 0) for q in range(n)]
        elif g == "cx":
            (m1, c1), (m2, c2) = lab[qs[0]], lab[qs[1]]
            lab[qs[1]] = (m1 ^ m2, c1 ^ c2)
        elif g == "x":
            m, k = lab[qs[0]]
            lab[qs[0]] = (m, k ^ 1)
        else:
            d = _dyadic(op)
            if d is not None:
                m, k = lab[qs[0]]
                out.append(dict(idx=i, seg=seg, s=d[0], e=d[1], mask=m, const=k, wires=tuple(lab)))
    return out


def _groups(rots):
    """Greedy partition of each segment's rotations into distinct-exponent sets; groups with k >= MIN_GROUP."""
    by_seg = {}
    for r in rots:
        by_seg.setdefault(r["seg"], []).append(r)
    groups = []
    for seg in sorted(by_seg):
        gs = []
        for r in by_seg[seg]:
            for g in gs:
                if r["e"] not in g["es"]:
                    g["es"].add(r["e"])
                    g["m"].append(r)
                    break
            else:
                gs.append(dict(es={r["e"]}, m=[r]))
        groups.extend(g["m"] for g in gs if len(g["m"]) >= MIN_GROUP)
    return groups


def find_matches(c):
    if not dv.is_angle_circuit(c) or c.meta.get("phase_gradient"):
        return []
    groups = _groups(_scan(c))
    if not groups:
        return []
    B = max(r["e"] for g in groups for r in g)
    deleted = sum(1 for g in groups for r in g if r["e"] >= 4)
    if deleted < 2 * (B - 3) + 4:
        return []
    return [tuple(tuple(r["idx"] for r in g) for g in groups)]


# ------------------------------------------------------------------------------------------------ gadgets
def _and(a, b, t):
    """Gidney temporary AND (4 T) onto clean t, as a unitary."""
    return [("h", (t,), None), ("t", (t,), None), ("cx", (a, t), None), ("cx", (b, t), None),
            ("cx", (t, a), None), ("cx", (t, b), None), ("tdg", (a,), None), ("tdg", (b,), None),
            ("t", (t,), None), ("cx", (t, a), None), ("cx", (t, b), None), ("cx", (b, t), None),
            ("cx", (a, t), None), ("h", (t,), None), ("s", (t,), None)]


def _and_inv(a, b, t):
    return [("sdg", (t,), None), ("h", (t,), None), ("cx", (a, t), None), ("cx", (b, t), None),
            ("cx", (t, b), None), ("cx", (t, a), None), ("tdg", (t,), None), ("t", (b,), None),
            ("t", (a,), None), ("cx", (t, b), None), ("cx", (t, a), None), ("cx", (b, t), None),
            ("cx", (a, t), None), ("tdg", (t,), None), ("h", (t,), None)]


def _adder(g, r, cs, B):
    """g += r mod 2^B (g, r: qubit lists LSB first; cs[k] = carry qubit into bit k, k = 1..B-1)."""
    cx = lambda a, b: ("cx", (a, b), None)           # noqa: E731
    ops = _and(r[0], g[0], cs[1])
    for k in range(1, B - 1):
        ops += [cx(cs[k], r[k]), cx(cs[k], g[k])] + _and(r[k], g[k], cs[k + 1]) + [cx(cs[k], cs[k + 1])]
    ops += [cx(r[B - 1], g[B - 1]), cx(cs[B - 1], g[B - 1])]
    for k in range(B - 2, 0, -1):
        ops += [cx(cs[k], cs[k + 1])] + _and_inv(r[k], g[k], cs[k + 1]) + [cx(cs[k], r[k]), cx(r[k], g[k])]
    ops += _and_inv(r[0], g[0], cs[1]) + [cx(r[0], g[0])]
    return ops


def _solve(wires):
    """For a target mask: subset (bitmask over wires) whose label masks xor to it. Gaussian elimination."""
    basis = {}                                         # pivot bit -> (mask, combo)
    for q, (m, _) in enumerate(wires):
        combo = 1 << q
        while m:
            p = m.bit_length() - 1
            if p in basis:
                bm, bc = basis[p]
                m ^= bm
                combo ^= bc
            else:
                basis[p] = (m, combo)
                break

    def solve(t):
        combo = 0
        while t:
            p = t.bit_length() - 1
            bm, bc = basis[p]
            t ^= bm
            combo ^= bc
        return combo
    return solve


def apply_match(c, match):
    rots = {r["idx"]: r for r in _scan(c)}
    groups = [[rots[i] for i in g] for g in match]
    B = max(r["e"] for g in groups for r in g)
    n = c.n
    gq = [n + k for k in range(B)]
    wq = [n + B + k for k in range(B)]
    cs = {k: n + 2 * B + k - 1 for k in range(1, B)}
    drop = {r["idx"] for g in groups for r in g}
    block_at = {}
    for g in groups:
        last = max(g, key=lambda r: r["idx"])
        solve = _solve(last["wires"])
        load = []
        for r in g:
            combo = solve(r["mask"])
            flip = r["const"] ^ (1 if r["s"] < 0 else 0)
            for q in range(n):
                if (combo >> q) & 1:
                    flip ^= last["wires"][q][1]
                    load.append(("cx", (q, wq[B - r["e"]]), None))
            if flip:
                load.append(("x", (wq[B - r["e"]],), None))
        unload = list(reversed(load))
        block_at[last["idx"]] = load + _adder(gq, wq, cs, B) + unload
    prep = []
    for k in range(B):
        prep += [("h", (gq[k],), None), ("rz", (gq[k],), -2 * math.pi / 2 ** (B - k))]
    unprep = []
    for k in reversed(range(B)):
        unprep += [("rz", (gq[k],), 2 * math.pi / 2 ** (B - k)), ("h", (gq[k],), None)]
    body = []
    for i, op in enumerate(c.ops):
        if i in block_at:
            body += block_at[i]
        elif i not in drop:
            body.append(op)
    meta = dict(c.meta)
    meta["phase_gradient"] = B
    return dv.with_ops(dv.Circuit(n + 3 * B - 1, [], meta), prep + body + unprep)


RULE = Rule(
    name="phase_gradient_addition_for_dyadic_rotation_cascades",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney, Quantum 2, 74 (2018); Babbush et al., PRX 8, 041015 (2018) (phase-gradient rotations)",
    idea="Rotations 2 pi s/2^e with distinct e on parity labels p_i of one Hadamard-free segment multiply to "
         "exp(2 pi i v/2^B), v = sum s_i 2^(B-e_i) p_i. Load v into a clean B-bit register with CNOTs, add it into a "
         "shared phase-gradient state sum_m exp(-2 pi i m/2^B)|m> (an exact eigenvector of addition, so the state is "
         "a catalyst), unload. One 4(B-1)-T adder (8(B-1) here: the AND uncompute is unitary, no measurement in the "
         "Clifford+Rz op list) replaces all of the group's synthesized rotations; the gradient is prepared and "
         "unprepared once with B-3 synthesized rotations each.",
    trigger=find_matches,
    apply=apply_match,
)
