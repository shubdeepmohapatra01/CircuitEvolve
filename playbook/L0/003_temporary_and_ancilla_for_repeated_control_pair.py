"""
Fuses two ccz(p,q,t) Toffolis that share the same control pair (p,q) (with p,q untouched
between them) into a single compute/uncompute-AND pattern: a fresh ancilla a is set once to
p&q via a plain Toffoli ccx(p,q,a) (a starts at |0>, so a ^= p&q = p&q exactly), each original
ccz(p,q,t) becomes a cheap cz(a,t) (0T, since a==p&q at that point and p,q untouched between
uses), and a is uncomputed with the measurement trick (H a; measure; classically-controlled
cz(p,q) fixup; reset a back to |0>). This is sound because p,q are never touched between the
first and second occurrence, so a continues to equal p&q throughout, and the final measured
uncompute exactly inverts the ccx(p,q,a) compute step. Net per fused pair: 14T -> 7T (one real
Toffoli for the compute step, both uses and the uncompute are free).
"""
from circuitevolve.circuit import Circuit, Gate
from circuitevolve.verifier import Req


def _find_shared_pair_ccz(c: Circuit):
    """Find two ccz gates sharing a common control pair (p,q) with the same target t, with no
    gate touching p or q strictly between them."""
    gates = c.gates
    n = len(gates)
    for i in range(n):
        gi = gates[i]
        if gi.name != "ccz":
            continue
        qs = gi.qubits
        for pair_idx in [(0, 1), (0, 2), (1, 2)]:
            p, q = qs[pair_idx[0]], qs[pair_idx[1]]
            t = [x for x in qs if x not in (p, q)][0]
            for j in range(i + 1, n):
                gj = gates[j]
                if gj.name == "ccz" and set(gj.qubits) == {p, q, t}:
                    ok = True
                    for k in range(i + 1, j):
                        gk = gates[k]
                        if p in gk.qubits or q in gk.qubits:
                            ok = False
                            break
                    if ok:
                        return i, j, p, q, t
                    else:
                        break
                if p in gj.qubits or q in gj.qubits:
                    break
    return None


def rewrite(c: Circuit) -> tuple[Circuit, Req]:
    found = _find_shared_pair_ccz(c)
    if found is None:
        return c, Req()

    i, j, p, q, t = found
    gates = c.gates
    a = c.n          # fresh ancilla qubit, starts at |0>
    cbit = c.nc       # fresh classical bit

    new_gates = list(gates[:i])

    # Compute a ^= p & q exactly, with a starting at |0> (so a becomes p&q).
    new_gates.append(Gate("ccx", (p, q, a)))

    # First use: original ccz(p,q,t) at position i becomes cz(a,t) since a == p&q here.
    new_gates.append(Gate("cz", (a, t)))

    # Gates strictly between i and j, unchanged (they don't touch p,q by construction).
    new_gates.extend(gates[i + 1:j])

    # Second use: original ccz(p,q,t) at position j becomes cz(a,t).
    new_gates.append(Gate("cz", (a, t)))

    # Measured uncompute of a = p & q (Jones/Gidney trick): H a; measure a -> cbit;
    # if m==1, apply classically-controlled cz(p,q) fixup; reset a back to |0>.
    new_gates.append(Gate("h", (a,)))
    new_gates.append(Gate("measure", (a,), cbit=cbit))
    new_gates.append(Gate("cz", (p, q), cond=cbit))
    new_gates.append(Gate("reset", (a,)))

    # Rest of circuit after j, unchanged.
    new_gates.extend(gates[j + 1:])

    new_c = Circuit(c.n + 1, new_gates, nc=c.nc + 1, zero_init=c.zero_init)
    req = Req(eps=0.0, ancillas=1, measure=True)
    return new_c, req
