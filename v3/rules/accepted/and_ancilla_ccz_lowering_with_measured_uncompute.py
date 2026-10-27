"""Lower ccz/ccx through a temporary logical-AND ancilla (4 T), shared across runs with the same control pair."""
from v3.api import Rule
from v3.api import dv

DIAGONAL = {"z", "s", "sdg", "t", "tdg", "cz"}
TOFF = ("ccx", "ccz")


def _writes(g, q):
    """True if gate g may change the computational value of wire q."""
    if q not in g.qubits:
        return False
    if g.name in DIAGONAL or g.name == "ccz":
        return False
    if g.name == "cx":
        return g.qubits[1] == q
    if g.name == "ccx":
        return g.qubits[2] == q
    return True  # x, h, measure, gadgets, anything unknown


def _runs(c):
    gates = c.gates
    out, i, n = [], 0, len(gates)
    while i < n:
        g = gates[i]
        if g.name not in TOFF or g.cond is not None:
            i += 1
            continue
        x, y = g.qubits[0], g.qubits[1]
        pair = {x, y}
        members, j = [i], i + 1
        while j < n:
            h = gates[j]
            if h.name in TOFF:
                if (h.cond is None and h.name == "ccz" or h.cond is None and h.name == "ccx") and \
                        {h.qubits[0], h.qubits[1]} == pair and h.qubits[2] not in pair:
                    members.append(j)
                    j += 1
                    continue
                break
            if _writes(h, x) or _writes(h, y):
                break
            j += 1
        out.append((x, y, tuple(members)))
        i = members[-1] + 1
    return out


def find_matches(c):
    if not dv.is_ir_circuit(c):
        return []
    if any(g.name in dv.IR_GADGETS for g in c.gates):
        return []
    runs = [r for r in _runs(c) if c.gates[r[2][0]].qubits[2] not in r[:2]]
    return [tuple(runs)] if runs else []


def apply_match(c, m):
    anc = c.n_qubits
    first = {r[2][0]: r for r in m}
    last = {r[2][-1] for r in m}
    member = {k: r for r in m for k in r[2]}
    out = []
    for k, g in enumerate(c.gates):
        if k in first:
            x, y, _ = first[k]
            out.append(dv.IRGate("and_compute", (x, y, anc)))
        if k in member:
            z = g.qubits[2]
            out.append(dv.IRGate("cz" if g.name == "ccz" else "cx", (anc, z)))
            if k in last:
                x, y, _ = member[k]
                out.append(dv.IRGate("and_uncompute", (x, y, anc)))
        else:
            out.append(g)
    return dv.ir_with_gates(c, out, n_qubits=anc + 1)


RULE = Rule(
    name="and_ancilla_ccz_lowering_with_measured_uncompute",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney 2018 (temporary logical-AND, measurement-based uncompute); Jones 2013",
    idea="ccz/ccx(x,y,z) = AND-compute(x,y->a) [4 T]; cz/cx(a,z); measured uncompute [0 T]. A run of ccz/ccx with the "
         "same control pair whose controls are not written in between shares one AND, so a run costs 4 T total "
         "instead of 7 T per gate. Runs are disjoint, so a single clean ancilla is reused.",
    trigger=find_matches,
    apply=apply_match,
)
