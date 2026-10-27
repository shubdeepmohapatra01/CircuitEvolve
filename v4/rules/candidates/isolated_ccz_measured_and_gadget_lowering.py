"""Lower each ccz / ccx on its own through a temporary-AND gadget (4 T), one shared clean ancilla."""
from v4.api import Precondition, Rule
from v4.api import dv

TOFF = ("ccx", "ccz")


def _isolated_ancilla(c):
    """Highest qubit if every gate touching it sits in an adjacent and_compute / cz / and_uncompute triple."""
    a = c.n_qubits - 1
    if a < 0:
        return None
    gs = c.gates
    i, seen = 0, False
    while i < len(gs):
        g = gs[i]
        if a not in g.qubits:
            i += 1
            continue
        if not (g.name == "and_compute" and g.qubits[2] == a and i + 2 < len(gs)
                and gs[i + 1].name == "cz" and gs[i + 1].qubits[0] == a
                and gs[i + 2].name == "and_uncompute" and gs[i + 2].qubits[2] == a):
            return None
        seen = True
        i += 3
    return a if seen else None


def find_matches(c):
    if not dv.is_ir_circuit(c) or c.n_qubits > 24:
        return []
    ms = tuple(i for i, g in enumerate(c.gates)
               if g.name in TOFF and g.cond is None and len(set(g.qubits)) == 3)
    return [ms] if ms else []


def apply_match(c, m):
    if any(g.name in dv.IR_GADGETS for g in c.gates):
        return c
    anc = c.n_qubits
    chosen = set(m)
    out = []
    for k, g in enumerate(c.gates):
        if k not in chosen:
            out.append(g)
            continue
        x, y, z = g.qubits
        seq = [dv.IRGate("and_compute", (x, y, anc)), dv.IRGate("cz", (anc, z)),
               dv.IRGate("and_uncompute", (x, y, anc))]
        if g.name == "ccx":
            seq = [dv.IRGate("h", (z,))] + seq + [dv.IRGate("h", (z,))]
        out.extend(seq)
    return dv.ir_with_gates(c, out, n_qubits=anc + 1)


RULE = Rule(
    name="isolated_ccz_measured_and_gadget_lowering",
    domain="dv",
    kind="reconstruction",
    error_class="exact",
    resource_class="measured",
    source="Jones 2013 (Toffoli, 4 T, one ancilla); Gidney 2018 (temporary AND, measured uncompute)",
    idea="Lower one ccz/ccx at a time: and_compute(x,y->a) [4 T], cz(a,z), measured and_uncompute [0 T]; "
         "ccx adds h(z) on both sides. The gadget's ancilla lifetime is three adjacent ops, so one ancilla is "
         "reused by every lowered Toffoli.",
    precondition=Precondition(families=("dv_recon",), needs=("toffoli", "ancilla_room"), max_qubits=24,
                              note="needs a ccz or ccx"),
    trigger=find_matches,
    apply=apply_match,
)
