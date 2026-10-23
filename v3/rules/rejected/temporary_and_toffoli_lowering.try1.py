"""Lower ccz/ccx to Gidney's temporary-AND gadget (4 T), sharing one live ancilla between Toffolis on the same
control pair when neither control is written in between."""
from v3.api import Rule
from v3.api import dv

_TOFF = ("ccz", "ccx")
_WRITE_1Q = ("x", "h")


def _writes(g, q):
    """Does gate g change the computational-basis value of qubit q?"""
    if q not in g.qubits:
        return False
    if g.name == "measure":
        return True
    if g.name in _WRITE_1Q:
        return True
    if g.name == "cx":
        return g.qubits[1] == q
    if g.name in ("ccx", "and_compute", "and_uncompute"):
        return g.qubits[2] == q
    if g.name in ("ccz", "cz", "z", "s", "sdg", "t", "tdg"):
        return False
    return True  # unknown gate: be conservative


def _groups(c):
    gates = c.gates
    used, groups = set(), []
    for i, g in enumerate(gates):
        if i in used or g.name not in _TOFF or g.cond is not None:
            continue
        a, b = g.qubits[0], g.qubits[1]
        pair = {a, b}
        grp = [i]
        used.add(i)
        for j in range(i + 1, len(gates)):
            h = gates[j]
            if h.name in _TOFF and h.cond is None and j not in used and {h.qubits[0], h.qubits[1]} == pair:
                grp.append(j)
                used.add(j)
                continue
            if _writes(h, a) or _writes(h, b):
                break
        groups.append((a, b, tuple(grp)))
    return groups


def find_matches(c):
    if not dv.is_ir_circuit(c):
        return []
    groups = _groups(c)
    if not groups:
        return []
    return [tuple(groups)]  # one global match: needs a shared ancilla pool


def apply_match(c, m):
    gates = c.gates
    starts, ends, site_of = {}, {}, {}
    for gi, (a, b, idxs) in enumerate(m):
        starts.setdefault(idxs[0], []).append(gi)
        ends.setdefault(idxs[-1], []).append(gi)
        for j in idxs:
            site_of[j] = gi
    n0 = c.n_qubits
    free, n_anc, anc = [], 0, {}
    out = []
    for i, g in enumerate(gates):
        if i not in site_of:
            out.append(g)
            continue
        gi = site_of[i]
        a, b, _ = m[gi]
        if gi in starts.get(i, ()):
            if free:
                t = free.pop(0)
            else:
                t = n0 + n_anc
                n_anc += 1
            anc[gi] = t
            out.append(dv.IRGate("and_compute", (a, b, t)))
        t = anc[gi]
        out.append(dv.IRGate("cz" if g.name == "ccz" else "cx", (t, g.qubits[2])))
        if gi in ends.get(i, ()):
            out.append(dv.IRGate("and_uncompute", (a, b, t)))
            free.append(t)
            free.sort()
    return dv.ir_with_gates(c, out, n_qubits=n0 + n_anc)


RULE = Rule(
    name="temporary_and_toffoli_lowering",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney, Halving the cost of quantum addition, Quantum 2, 74 (2018); Jones, PRA 87, 022328 (2013)",
    idea="CCZ(a,b,c) = and_compute(a,b->t); cz(t,c); and_uncompute(t). The AND gadget costs 4 T and the measurement-"
         "based uncompute is free, so each Toffoli drops from 7 T to 4 T; Toffolis on the same control pair with no "
         "write to the controls in between share one ancilla, so a compute/uncompute pair costs 4 T in total.",
    trigger=find_matches,
    apply=apply_match,
)
