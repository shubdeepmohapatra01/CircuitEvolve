"""Merge two same-axis Pauli rotations across anticommuting blockers; error is second order (product of sines)."""
import math

from v3.api import Rule
from v3.api import dv, pauli

BUDGET = 5e-4
_INV = {"h": "h", "s": "sdg", "sdg": "s", "x": "x", "z": "z", "cx": "cx", "cz": "cz"}
_QUARTER = math.pi / 4


def _pc(v):
    return bin(v).count("1")


def _mul(a, b):
    return (a[0] ^ b[0], a[1] ^ b[1], (a[2] + b[2] + 2 * _pc(a[1] & b[0])) % 4)


def _norm(a):
    a = math.fmod(a, 2 * math.pi)
    if a > math.pi:
        a -= 2 * math.pi
    elif a <= -math.pi:
        a += 2 * math.pi
    return a


def _is_quarter(a):
    r = a / _QUARTER
    return abs(r - round(r)) < 1e-9


def _frames(c):
    """[(op index, x, z, sign, normalized angle)] with P_k = U^dag Z_q U (U = Cliffords before the rotation)."""
    tx = {q: (1 << q, 0, 0) for q in range(c.n)}
    tz = {q: (0, 1 << q, 0) for q in range(c.n)}
    out = []
    for idx, op in enumerate(c.ops):
        g, qs, _ = op
        th = dv.rotation(op)
        if th is not None:
            x, z, e = tz[qs[0]]
            sg = 1 if (e - _pc(x & z)) % 4 == 0 else -1
            out.append((idx, x, z, sg, _norm(th)))
            continue
        if g not in _INV:
            return None
        new = {}
        for q in qs:
            for kind, base in (("x", (1 << q, 0, 1)), ("z", (0, 1 << q, 1))):
                x, z, s = base
                for gate_q in (q,):
                    pass
                x2, z2, s2 = pauli.conjugate(base, _INV[g], qs)
                res = (0, 0, (_pc(x2 & z2) + (2 if s2 < 0 else 0)) % 4)
                for q2 in qs:
                    if (x2 >> q2) & 1:
                        res = _mul(res, tx[q2])
                    if (z2 >> q2) & 1:
                        res = _mul(res, tz[q2])
                new[(kind, q)] = res
        for (kind, q), v in new.items():
            (tx if kind == "x" else tz)[q] = v
    return out


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    fr = _frames(c)
    if not fr:
        return []
    groups = {}
    for k, f in enumerate(fr):
        groups.setdefault((f[1], f[2]), []).append(k)
    import sys
    dbg = dict(ops=len(c.ops), rot=len(fr), groups=len(groups), pairs=0, cand=0, blk=0, mind=9.0)
    out = []
    for (px, pz), ks in groups.items():
        for a, b in zip(ks, ks[1:]):
            fa, fb = fr[a], fr[b]
            dbg["pairs"] += 1
            if _is_quarter(fa[4]) or _is_quarter(fb[4]):
                continue
            dbg["cand"] += 1
            sa, sb = abs(math.sin(fa[4] / 2)), abs(math.sin(fb[4] / 2))
            small = 2 * min(sa, sb)
            tot, n_block, ok = 0.0, 0, True
            for m in range(a + 1, b):
                _, x, z, _, ang = fr[m]
                if _pc((px & z) ^ (pz & x)) & 1:
                    tot += abs(math.sin(ang / 2))
                    n_block += 1
                    if small * tot > BUDGET:
                        ok = False
                        break
            if not ok or n_block == 0:
                continue
            d = small * tot
            dbg["blk"] += 1
            dbg["mind"] = min(dbg["mind"], d)
            s = fa[3] * fb[3]
            total = _norm(fa[4] + s * fb[4])
            if _is_quarter(total):
                total = round(total / _QUARTER) * _QUARTER
                saving = 100.0
            else:
                saving = 50.0
            kept, moved = (fa, fb) if sa >= sb else (fb, fa)
            new_angle = _norm(kept[4] + s * moved[4])
            if _is_quarter(new_angle):
                new_angle = round(new_angle / _QUARTER) * _QUARTER
            out.append((saving / max(d, 1e-18), d, kept[0], moved[0], new_angle))
    print("DBG", dbg, file=sys.stderr)
    out.sort(key=lambda m: (-m[0], m[2], m[3]))
    return [(k, mv, ang) for _, _, k, mv, ang in out]


def apply_match(c, m):
    kept, moved, ang = m
    ops = list(c.ops)
    ops[kept] = ("rz", ops[kept][1], ang)
    del ops[moved]
    return dv.with_ops(c, ops)


RULE = Rule(
    name="second_order_small_angle_rotation_commutation_merge",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="Childs-Su-Tran-Wiebe-Zhu PRX 11, 011020 (commutator bound); Nam et al. npj QI 4, 23 (rotation merging)",
    idea="Two rotations about the same Pauli axis separated only by anticommuting rotations are merged anyway: "
         "moving the smaller one across the blockers costs at most 2|sin(t/2)| * sum|sin(phi_b/2)| (second order), "
         "and the pair then composes exactly into one rotation (often zero when the angles cancel).",
    trigger=find_matches,
    apply=apply_match,
)
