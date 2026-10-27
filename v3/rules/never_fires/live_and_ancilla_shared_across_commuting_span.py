"""Keep one temporary-AND ancilla live across a span of ccz/ccx gates that share a control pair."""
from v3.api import Rule
from v3.api import dv

_DIAG = {"z", "s", "sdg", "t", "tdg", "cz", "ccz"}


def _writes(g):
    n, qs = g.name, g.qubits
    if n in _DIAG:
        return frozenset()
    if n in ("h", "x", "measure"):
        return frozenset(qs)
    if n == "cx":
        return frozenset(qs[1:])
    if n == "ccx":
        return frozenset(qs[2:])
    if n == "and_compute":
        return frozenset(qs[2:])
    return frozenset(qs)


def _pairs(g):
    q = g.qubits
    if g.cond is not None:
        return []
    if g.name == "ccz":
        return [frozenset((q[0], q[1])), frozenset((q[0], q[2])), frozenset((q[1], q[2]))]
    if g.name == "ccx":
        return [frozenset((q[0], q[1]))]
    return []


def _clean_prefix(gates):
    """pre[i] = set of qubits written by gates[:i] cumulative is too big; use per-gate write sets instead."""
    return [_writes(g) for g in gates]


def _segments(positions, pair, wr):
    segs, cur = [], []
    for p in positions:
        if cur and any(wr[j] & pair for j in range(cur[-1] + 1, p)):
            segs.append(cur)
            cur = []
        cur.append(p)
    if cur:
        segs.append(cur)
    return segs


def _cancel_matches(gates, wr):
    out, used = [], set()
    ccz = [i for i, g in enumerate(gates) if g.name == "ccz" and g.cond is None]
    for ai, i in enumerate(ccz):
        if i in used:
            continue
        tri = frozenset(gates[i].qubits)
        for j in ccz[ai + 1:]:
            if j in used or frozenset(gates[j].qubits) != tri:
                continue
            if all(not (wr[k] & tri) for k in range(i + 1, j)):
                out.append(("cancel", i, j))
                used.update((i, j))
            break
    return out, used


def trigger(c):
    if not dv.is_ir_circuit(c):
        return []
    gates = c.gates
    wr = _clean_prefix(gates)
    matches, used = _cancel_matches(gates, wr)
    cands = {}
    for i, g in enumerate(gates):
        if g.name in ("ccz", "ccx") and i not in used:
            for pr in _pairs(g):
                cands.setdefault(pr, []).append(i)
    pool = {i for v in cands.values() for i in v}
    while True:
        best = None
        for pr in sorted(cands, key=lambda s: sorted(s)):
            pos = [p for p in cands[pr] if p in pool]
            for seg in _segments(pos, pr, wr):
                if len(seg) < 2:
                    continue
                key = (-len(seg), seg[-1] - seg[0], seg[0], sorted(pr))
                if best is None or key < best[0]:
                    best = (key, pr, seg)
        if best is None:
            break
        _, pr, seg = best
        matches.append(("share", tuple(sorted(pr)), tuple(seg)))
        pool -= set(seg)
    return matches


def apply(c, m):
    if not dv.is_ir_circuit(c):
        return c
    gates = list(c.gates)
    if m[0] == "cancel":
        _, i, j = m
        if not (i < j < len(gates)) or gates[i].name != "ccz" or gates[j].name != "ccz":
            return c
        return dv.ir_with_gates(c, [g for k, g in enumerate(gates) if k not in (i, j)])
    _, pair, seg = m
    a, b = pair
    t = c.n_qubits
    first, last = seg[0], seg[-1]
    members = set(seg)
    out = []
    for k, g in enumerate(gates):
        if k == first:
            out.append(dv.IRGate("and_compute", (a, b, t)))
        if k in members:
            rest = [q for q in g.qubits if q not in pair]
            if g.name == "ccz":
                out.append(dv.IRGate("cz", (t, rest[0])))
            else:
                out.append(dv.IRGate("cx", (t, g.qubits[2])))
        else:
            out.append(g)
        if k == last:
            out.append(dv.IRGate("and_uncompute", (a, b, t)))
    return dv.ir_with_gates(c, out, n_qubits=c.n_qubits + 1)


RULE = Rule(
    name="live_and_ancilla_shared_across_commuting_span",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney 2018 (temporary logical-AND); Jones 2013; Nam et al. 2018 (commutation-based regrouping)",
    idea="Toffolis sharing a control pair {a,b} need not be adjacent: if no op between them writes a or b, one "
         "temporary AND t=a.b (4 T) stays live across the span, each member becomes cz/cx(t,target) (0 T), and "
         "t is uncomputed by measurement (0 T). Ops inside the span are left in place.",
    trigger=trigger,
    apply=apply,
)
