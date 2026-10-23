"""Share one Gidney temporary AND across all CCZ/CCX gates whose control wires carry the same pair of ANFs."""
from v3.api import Rule
from v3.api import dv

MAX_TERMS = 4000
PASS_THROUGH = ("z", "s", "sdg", "t", "tdg", "cz")   # diagonal: ANFs unchanged


def _and(a, b):
    acc = set()
    for m in a:
        for k in b:
            acc ^= {m | k}
    return frozenset(acc)


def _parse(c):
    """-> (items, skip); items = (start, length, kind, controls, target) per ccz/ccx (h-ccz-h folded to ccx)."""
    gs = c.gates
    items, skip = [], set()
    for i, g in enumerate(gs):
        if g.name in ("ccx", "ccz"):
            qs = g.qubits
            if g.name == "ccx":
                items.append((i, 1, "cx", qs[:2], qs[2]))
            elif (i > 0 and i + 1 < len(gs) and gs[i - 1].name == "h" and gs[i + 1].name == "h"
                  and gs[i - 1].qubits == gs[i + 1].qubits and gs[i - 1].qubits[0] in qs
                  and i - 1 not in skip):
                t = gs[i - 1].qubits[0]
                items.append((i - 1, 3, "cx", tuple(q for q in qs if q != t), t))
                skip.update((i - 1, i + 1))
            else:
                items.append((i, 1, "cz", qs[:2], qs[2]))
    return items, skip


def find_matches(c):
    if not dv.is_ir_circuit(c) or c.n_cbits:
        return []
    if any(g.cond is not None for g in c.gates):
        return []
    items, skip = _parse(c)
    if len(items) < 2:
        return []
    by_start = {it[0]: it for it in items}
    inside = set()
    for it in items:
        if it[1] == 3:
            inside.update((it[0] + 1, it[0] + 2))
    anf = [frozenset([frozenset([q])]) for q in range(c.n_qubits)]
    one = frozenset([frozenset()])
    keys = {}
    for i, g in enumerate(c.gates):
        if i in inside:
            continue
        if i in by_start:
            it = by_start[i]
            c1, c2 = it[3]
            if anf[c1] == anf[c2]:
                return []
            keys[i] = frozenset([anf[c1], anf[c2]])
            if it[2] == "cx":
                anf[it[4]] = anf[it[4]] ^ _and(anf[c1], anf[c2])
                if len(anf[it[4]]) > MAX_TERMS:
                    return []
            continue
        if i in skip:
            continue
        n, qs = g.name, g.qubits
        if n == "x":
            anf[qs[0]] = anf[qs[0]] ^ one
        elif n == "cx":
            anf[qs[1]] = anf[qs[1]] ^ anf[qs[0]]
        elif n in PASS_THROUGH:
            pass
        elif n in ("and_compute", "and_uncompute"):
            anf[qs[2]] = anf[qs[2]] ^ _and(anf[qs[0]], anf[qs[1]])
        else:
            return []
    classes = {}
    for it in items:
        classes.setdefault(keys[it[0]], []).append(it[0])
    if len(classes) >= len(items):
        return []
    return sorted((tuple(v) for v in classes.values()), key=lambda v: (-len(v), v))


def _free_slot(c, lo, hi):
    """An existing gadget-only, non-register qubit untouched in gates[lo:hi] (hence clean there), else None."""
    regs = {q for reg in c.registers.values() for q in reg}
    touch = {}
    for i, g in enumerate(c.gates):
        for k, q in enumerate(g.qubits):
            ok = (g.name in ("and_compute", "and_uncompute") and k == 2) or (g.name == "cx" and k == 0)
            touch.setdefault(q, []).append((i, ok))
    for q in range(c.n_qubits):
        if q in regs or q not in touch:
            continue
        if all(ok for _, ok in touch[q]) and not any(lo <= i < hi for i, _ in touch[q]) and \
                any(c.gates[i].name == "and_compute" for i, _ in touch[q]):
            return q
    return None


def apply_match(c, m):
    items, _ = _parse(c)
    by_start = {it[0]: it for it in items}
    last_it = by_start[m[-1]]
    a = _free_slot(c, m[0], last_it[0] + last_it[1])
    n_new = c.n_qubits
    if a is None:
        a = c.n_qubits
        n_new += 1
    members = set(m)
    out = []
    i = 0
    gs = c.gates
    while i < len(gs):
        if i not in members:
            out.append(gs[i])
            i += 1
            continue
        it = by_start[i]
        c1, c2 = it[3]
        if i == m[0]:
            out.append(dv.IRGate("and_compute", (c1, c2, a)))
        out.append(dv.IRGate(it[2], (a, it[4])))
        if i == m[-1]:
            out.append(dv.IRGate("and_uncompute", (c1, c2, a)))
        i += it[1]
    return dv.ir_with_gates(c, out, n_qubits=n_new)


RULE = Rule(
    name="shared_temporary_and_across_compute_uncompute_pairs",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney, Halving the cost of quantum addition, Quantum 2, 74 (2018); ANF control matching",
    idea="In a Hadamard-free (after h-ccz-h folding) Toffoli circuit, symbolically track each wire's GF(2) "
         "polynomial. CCZ/CCX gates whose two controls carry the same pair of polynomials need the same AND value, "
         "so one 4-T temporary AND (clean ancilla, measurement-based uncompute) serves the whole class, with a "
         "cz/cx from the ancilla onto each member's target.",
    trigger=find_matches,
    apply=apply_match,
)
