"""Globally cache AND values by symbolic (ANF) wire-value matching: one 4-T temporary AND per distinct control-value pair."""
from v3.api import Rule
from v3.api import dv

CAP = 64
DIAG = {"z", "s", "sdg", "t", "tdg", "cz", "ccz", "rz"}
ONE = frozenset([frozenset()])
ZERO = frozenset()


def _mul(p, q):
    out = set()
    for a in p:
        for b in q:
            out ^= {a | b}
    return frozenset(out)


def _add_val(p, q):
    return frozenset(set(p) ^ set(q))


def _cap(p):
    return p if p is not None and len(p) <= CAP else None


def _canon(p):
    return tuple(sorted(tuple(sorted(m)) for m in p))


def _sweep(c):
    """List of (index, name, c1, c2, target, key) for each keyable ccz/ccx."""
    n = c.n_qubits
    inputs = {q for reg in c.registers.values() for q in reg} or set(range(n))
    v = [frozenset([frozenset([q])]) if q in inputs else ZERO for q in range(n)]
    occ = []
    gs = c.gates
    skip_h, conj = set(), {}   # h(t) ccz(.,.,t) h(t) (other gates disjoint) = ccx: h's skipped, ccz -> target t
    for j, g in enumerate(gs):
        if g.name != "ccz" or g.cond is not None or j in conj:
            continue
        for t in g.qubits:
            i = j - 1
            while i >= 0 and not (set(gs[i].qubits) & set(g.qubits)):
                i -= 1
            k = j + 1
            while k < len(gs) and not (set(gs[k].qubits) & set(g.qubits)):
                k += 1
            if i < 0 or k >= len(gs) or i in skip_h or k in skip_h:
                continue
            hi, hk = gs[i], gs[k]
            if (hi.name == "h" and hk.name == "h" and hi.qubits == (t,) and hk.qubits == (t,)
                    and hi.cond is None and hk.cond is None):
                conj[j] = t
                skip_h.update((i, k))
                break
    for i, g in enumerate(gs):
        nm, qs = g.name, g.qubits
        if i in skip_h:
            continue
        if i in conj:
            t = conj[i]
            a, b = [q for q in qs if q != t]
            if v[a] is not None and v[b] is not None and v[a] and v[b]:
                occ.append((i, "ccz", a, b, t, tuple(sorted((_canon(v[a]), _canon(v[b]))))))
            if v[a] is None or v[b] is None or v[t] is None:
                v[t] = None
            else:
                v[t] = _cap(_add_val(v[t], _mul(v[a], v[b])))
            continue
        if g.cond is not None:
            if nm in DIAG:
                continue
            for q in qs:
                v[q] = None
            continue
        if nm in DIAG:
            continue
        if nm == "x":
            if v[qs[0]] is not None:
                v[qs[0]] = _add_val(v[qs[0]], ONE)
        elif nm == "cx":
            a, b = qs
            v[b] = None if v[a] is None or v[b] is None else _cap(_add_val(v[b], v[a]))
        elif nm in ("ccx", "and_compute"):
            a, b, t = qs
            if nm == "ccx" and v[a] is not None and v[b] is not None:
                pa, pb = v[a], v[b]
                if pa and pb:
                    key = tuple(sorted((_canon(pa), _canon(pb))))
                    occ.append((i, nm, a, b, t, key))
            if v[a] is None or v[b] is None or v[t] is None:
                v[t] = None
            else:
                v[t] = _cap(_add_val(v[t], _mul(v[a], v[b])))
        elif nm == "and_uncompute":
            v[qs[2]] = ZERO
        elif nm == "ccz":
            a, b, t = qs
            if v[a] is not None and v[b] is not None and v[a] and v[b]:
                key = tuple(sorted((_canon(v[a]), _canon(v[b]))))
                occ.append((i, nm, a, b, t, key))
        else:  # h, measure, unknown gates
            for q in qs:
                v[q] = None
    return occ


def _groups(c):
    groups = {}
    for o in _sweep(c):
        groups.setdefault(o[5], []).append(o)
    return groups


def find_matches(c):
    if not dv.is_ir_circuit(c):
        return []
    groups = _groups(c)
    ms = [(key, len(occs), occs[0][0]) for key, occs in groups.items()]
    ms.sort(key=lambda m: (-m[1], m[2]))
    return ms


def _free_ancilla(c, lo, hi):
    """An existing ancilla qubit certainly |0> over [lo, hi] and certainly |0> again afterwards."""
    used = {q for reg in c.registers.values() for q in reg}
    for q in range(c.n_qubits):
        if q in used:
            continue
        if any(q in c.gates[j].qubits for j in range(lo, hi + 1)):
            continue
        before = [c.gates[j] for j in range(lo) if q in c.gates[j].qubits]
        if before and not (before[-1].name == "and_uncompute" and before[-1].qubits[2] == q):
            continue
        after = [c.gates[j] for j in range(hi + 1, len(c.gates)) if q in c.gates[j].qubits]
        if after and not (after[0].name == "and_compute" and after[0].qubits[2] == q):
            continue
        return q
    return None


def apply_match(c, m):
    key = m[0]
    if not dv.is_ir_circuit(c):
        return c
    occs = _groups(c).get(key)
    if not occs:
        return c
    first, last = occs[0], occs[-1]
    lo, hi = first[0], last[0]
    a = _free_ancilla(c, lo, hi)
    n_qubits = c.n_qubits
    if a is None:
        a = n_qubits
        n_qubits += 1
    by_idx = {o[0]: o for o in occs}
    out = []
    for i, g in enumerate(c.gates):
        if i == lo:
            out.append(dv.IRGate("and_compute", (first[2], first[3], a)))
        o = by_idx.get(i)
        if o is None:
            out.append(g)
        elif o[1] == "ccz":
            out.append(dv.IRGate("cz", (a, o[4])))
        else:
            out.append(dv.IRGate("cx", (a, o[4])))
        if i == hi:
            out.append(dv.IRGate("and_uncompute", (last[2], last[3], a)))
    return dv.ir_with_gates(c, out, n_qubits=n_qubits)


RULE = Rule(
    name="shared_and_value_cache_by_anf_matching",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney 2018 (temporary AND, measured uncompute); Bennett 1973; Amy-Maslov-Mosca 2014 (GF(2) wire-value tracking); Jones 2013",
    idea="Track every wire's value as a GF(2) ANF polynomial; ccz/ccx gates whose control pair carries the same pair of "
         "logical values share one clean 4-T temporary-AND ancilla (compute before the first, cz/cx from it for each, "
         "0-T measured uncompute after the last), however far apart and however the control wires were overwritten.",
    trigger=find_matches,
    apply=apply_match,
)
