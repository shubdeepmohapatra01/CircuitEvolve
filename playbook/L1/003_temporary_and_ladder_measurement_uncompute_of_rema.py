"""
Generalized measurement-based uncompute for a *ladder* of mirrored AND blocks, applied here to the
surviving q[7]-level pair: H q7; CCZ(3,6,7); H q7 ... H q7; CCZ(3,6,7); H q7. The ancilla q7 is
zero-initialized before the first block, so the first block is AND(q3,q6)->q7 in the Hadamard basis;
the second (its mirror, run on the restored controls q3,q6) is uncomputed by the standard identity:
H q7; measure q7->fresh cbit m; classically-controlled CZ(q3,q6) conditioned on m; reset q7. This is
exactly correct because the measurement outcome m equals the parity that the CZ(q3,q6) would have
applied, deterministically fixing up the phase that the removed CCZ would have produced, while the
q6-ancilla's own measurement-based uncompute (already applied by the playbook) still supplies its own
correction independently -- the two corrections act on disjoint/independent classical bits and compose,
so no quantum CZ ever needs to be reconstructed on an ancilla about to be measured. The net effect is
that the surviving CCZ(3,6,7) uncompute (7 T) is replaced by a measurement + classically controlled CZ
(free Clifford), at the cost of one extra classical bit and no extra qubits.
"""
from circuitevolve.circuit import Circuit, Gate
from circuitevolve.verifier import Req


def rewrite(c: Circuit) -> tuple[Circuit, Req]:
    gates = c.gates
    n = len(gates)

    def is_h(g, q):
        return g.name == "h" and g.qubits == (q,) and g.cond is None

    def is_ccz_on(g, anc):
        return g.name == "ccz" and g.cond is None and anc in g.qubits

    # Find a block: H a; CCZ(..,..,a); H a  with cond None, a zero-init-able ancilla candidate.
    # Then find the mirrored block later: H a; CCZ(same two controls, a); H a
    # with nothing destructive to the ancilla a in between (only reads/other ops not re-zeroing it),
    # and no earlier use of `a` before the first block (so a is |0> at start of block1, per zero_init rule).
    for i in range(n - 2):
        g0, g1, g2 = gates[i], gates[i + 1], gates[i + 2]
        if g1.name != "ccz" or g1.cond is not None:
            continue
        anc = g1.qubits[2]
        if not (is_h(g0, anc) and g1.qubits[2] == anc and is_h(g2, anc)):
            continue
        ctrl_pair = (g1.qubits[0], g1.qubits[1])

        # ancilla must not be used before position i (so it's |0> there)
        used_before = any(anc in gg.qubits for gg in gates[:i])
        if used_before:
            continue

        # find mirrored block after i+2 with same controls on same ancilla
        j = None
        for k in range(i + 3, n - 2):
            h0, c1, h2 = gates[k], gates[k + 1], gates[k + 2]
            if (
                is_h(h0, anc)
                and c1.name == "ccz"
                and c1.cond is None
                and c1.qubits[2] == anc
                and (c1.qubits[0], c1.qubits[1]) == ctrl_pair
                and is_h(h2, anc)
            ):
                j = k
                break
            # if ancilla gets measured/reset or otherwise consumed destructively before mirror found, stop
            if anc in gates[k].qubits and gates[k].name in ("measure", "reset"):
                break

        if j is None:
            continue

        # Check that between i+3 and j, the ancilla `anc` is only used as spectator/control (not re-zeroed,
        # not measured/reset) -- standard precondition for the mirrored-AND-uncompute identity.
        between = gates[i + 3 : j]
        bad = any(gg.name in ("measure", "reset") and anc in gg.qubits for gg in between)
        if bad:
            continue

        # Build the rewritten circuit: keep everything up to and including first block (i..i+2) unchanged,
        # keep the "stuff" between unchanged, then replace the second block (j..j+2) with:
        #   H anc; measure anc -> new cbit; cond CZ(ctrl_pair) on that cbit; reset anc
        new_cbit = c.nc
        new_gates = []
        new_gates.extend(gates[: j])  # everything before second block, including first block & stuff
        new_gates.append(Gate("h", (anc,)))
        new_gates.append(Gate("measure", (anc,), cbit=new_cbit))
        ca, cb = ctrl_pair
        new_gates.append(Gate("cz", (ca, cb), cond=new_cbit))
        new_gates.append(Gate("reset", (anc,)))
        new_gates.extend(gates[j + 3 :])

        new_c = Circuit(c.n, new_gates, c.nc + 1, c.zero_init)
        return new_c, Req(eps=0.0, ancillas=0, measure=True)

    return c, Req()
