"""Collapse two Toffoli-level gates on the same qubit triple separated only by X gates on that triple."""
from v3.api import Rule
from v3.api import dv


def _normalized(gates):
    """[(kind, ccz_index, qubits, deleted_indices)] for ccz / ccx (h-ccz-h fused to ccx)."""
    n = len(gates)
    out = []
    for i, g in enumerate(gates):
        if g.name not in ("ccz", "ccx") or g.cond is not None:
            continue
        kind, qs, dele = g.name, tuple(g.qubits), (i,)
        if g.name == "ccz":
            for w in qs:
                before = after = None
                for j in range(i - 1, -1, -1):
                    if w in gates[j].qubits:
                        before = j
                        break
                for j in range(i + 1, n):
                    if w in gates[j].qubits:
                        after = j
                        break
                if (before is not None and after is not None and before != after
                        and gates[before].name == "h" and gates[after].name == "h"
                        and gates[before].cond is None and gates[after].cond is None
                        and gates[before].qubits == (w,) and gates[after].qubits == (w,)):
                    kind, qs, dele = "ccx", tuple(q for q in qs if q != w) + (w,), (before, i, after)
                    break
        out.append((kind, i, qs, dele))
    return out


def _key(t):
    kind, _, qs, _ = t
    if kind == "ccz":
        return ("ccz", frozenset(qs))
    return ("ccx", frozenset(qs[:2]), qs[2])


def _residue(kind, qs, par):
    a, b, c = qs
    al, be, ga = par[a], par[b], par[c]
    res = []
    if kind == "ccz":
        if al:
            res.append(("cz", (b, c)))
        if be:
            res.append(("cz", (a, c)))
        if ga:
            res.append(("cz", (a, b)))
        if be and ga:
            res.append(("z", (a,)))
        if al and ga:
            res.append(("z", (b,)))
        if al and be:
            res.append(("z", (c,)))
    else:
        al, be = par[a], par[b]
        if al:
            res.append(("cx", (b, c)))
        if be:
            res.append(("cx", (a, c)))
        if al and be:
            res.append(("x", (c,)))
    return tuple(res)


def find_matches(c):
    if not dv.is_ir_circuit(c):
        return []
    gates = c.gates
    norm = _normalized(gates)
    groups = {}
    for t in norm:
        groups.setdefault(_key(t), []).append(t)
    cands = []
    for lst in groups.values():
        for x in range(len(lst)):
            for y in range(x + 1, len(lst)):
                tp, tq = lst[x], lst[y]
                triple = set(tq[2])
                skip = set(tp[3]) | set(tq[3])
                par = {w: 0 for w in triple}
                ok = True
                for k in range(tp[1] + 1, tq[1]):
                    if k in skip:
                        continue
                    g = gates[k]
                    hit = triple.intersection(g.qubits)
                    if not hit:
                        continue
                    if g.name == "x" and g.cond is None and len(g.qubits) == 1:
                        par[g.qubits[0]] ^= 1
                    else:
                        ok = False
                        break
                if not ok:
                    continue
                zero = not any(par.values()) if tq[0] == "ccz" else not (par[tq[2][0]] or par[tq[2][1]])
                cands.append((0 if zero else 1, tq[1] - tp[1], tp[1], tp, tq, dict(par)))
    cands.sort(key=lambda t: t[:3])
    used, out = set(), []
    for _, _, _, tp, tq, par in cands:
        if tp[1] in used or tq[1] in used:
            continue
        used.add(tp[1])
        used.add(tq[1])
        delete = tuple(sorted(set(tp[3]) | set(tq[3])))
        out.append((delete, tq[1], _residue(tq[0], tq[2], par)))
    return out


def apply_match(c, m):
    if not dv.is_ir_circuit(c):
        return c
    delete, pos, residue = m
    dset = set(delete)
    new = []
    for i, g in enumerate(c.gates):
        if i == pos:
            new.extend(dv.IRGate(name, tuple(qs)) for name, qs in residue)
        if i in dset:
            continue
        new.append(g)
    return dv.ir_with_gates(c, new)


RULE = Rule(
    name="complementary_control_toffoli_pair_collapse",
    domain="dv",
    kind="rewrite",
    contract="exact",
    source="Maslov-Dueck-Miller 2005 Toffoli templates; Iwama-Kambayashi-Yamashita 2002; Amy-Maslov-Mosca 2014",
    idea="Two CCZ (or CCX with same target) on the same triple, separated only by X gates on the triple, compose "
         "to a phase (-1)^{(A^al)(B^be)(C^ga) + ABC} whose cubic term cancels: a Clifford (CZ/Z) residue. For "
         "CCX the composite flip of the target is al*B + be*A + al*be: CX/X. h-ccz-h on adjacent wire is fused "
         "to ccx first. 8 T -> 0 T per pair, exact, no ancilla.",
    trigger=find_matches,
    apply=apply_match,
)
