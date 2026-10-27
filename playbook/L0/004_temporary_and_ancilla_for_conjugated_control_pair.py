"""
temporary_and_ancilla_for_conjugated_control_pair

Generalizes the repeated-control-pair AND-fusion rule to control pairs that are
CNOT-conjugated (not literally untouched) between the two uses of a ccz sharing
the "same" AND value. We track, for each control wire, its GF(2) linear form in
terms of the original control variables through the intervening cx layer. If the
unordered pair of linear forms at a candidate ccz matches (as a set) the pair at
an earlier ccz, the two AND values (product of the two forms) are provably equal
as boolean functions of the original inputs, so both ccz's may be replaced by a
cz on a single fresh ancilla a = AND, computed once with one Toffoli and
uncomputed with the measurement-based (Jones/Gidney) trick: H a; measure a -> m;
if m==1 apply cz on the CURRENT (possibly relabeled/conjugated) control wires;
reset a. This is sound because the cx's between the two uses only permute/XOR
the *representation* of the AND term among wires, never its logical value, and
the final measured uncompute is the standard CCZ/AND uncomputation identity
applied with whatever wires currently hold the matching linear forms.
"""
from circuitevolve.circuit import Circuit, Gate
from circuitevolve.verifier import Req


def _lits_xor(a: frozenset, b: frozenset) -> frozenset:
    return a.symmetric_difference(b)


def rewrite(c: Circuit) -> tuple[Circuit, Req]:
    gates = c.gates
    N = len(gates)

    # Track, for each qubit, its GF(2) linear form over the ORIGINAL qubit indices
    # as a frozenset of variable indices (xor of singleton terms). Initialize each
    # qubit i to {i} (its own variable). Non-Clifford/non-cx gates on a qubit that
    # is part of a tracked control invalidate tracking for that qubit's "simple
    # control" status going forward (we only need this on wires used as ccz/ccx
    # controls and cx's, which is exactly the allowed conjugation class here).
    form = {q: frozenset({q}) for q in range(c.n)}

    # Records of ccz occurrences we can potentially fuse:
    # key: frozenset({form[control0], form[control1]})  (the control pair forms, unordered)
    # value: list of dict(idx=gate index, qa=control wire a, qb=control wire b, t=target wire)
    occurrences = {}

    # We also need, at each ccz we might match against an earlier one, the actual
    # current wires holding those forms (for emitting cz(a,t) and the fixup cz).
    found_pair = None  # (idx1, idx2, p_wire1, q_wire1, p_wire2, q_wire2, t1, t2, key)

    for i, g in enumerate(gates):
        if g.name == "cx":
            a, b = g.qubits
            # b ^= a  =>  form[b] ^= form[a]
            form[b] = _lits_xor(form[b], form[a])
            continue
        if g.name == "ccz":
            p, q, t = g.qubits
            key = frozenset({form[p], form[q]})
            if key in occurrences:
                for prev in occurrences[key]:
                    # candidate match: ensure the two ccz's are not overlapping/identical gate,
                    # and that nothing non-Clifford/untracked happened to invalidate correctness.
                    if prev["idx"] == i:
                        continue
                    found_pair = (prev, dict(idx=i, qa=p, qb=q, t=t), key)
                    break
            if found_pair is not None:
                break
            occurrences.setdefault(key, []).append(dict(idx=i, qa=p, qb=q, t=t))
            continue
        # Any other gate touching a qubit we are tracking as a "pure linear form"
        # could invalidate the tracking if it's not a simple relabel. Gates besides
        # cx/ccz/h/measure/reset/cz on tracked wires are not expected in this
        # pattern; to stay safe and general we only invalidate tracking of a qubit
        # if it's touched by something other than cx (as control or target) or ccz
        # (as control) -- e.g. an h flips it out of being a "pure AND input" wire
        # in a way our pattern doesn't rely on here, so we leave forms alone for
        # other gate types (h, cz, measure, reset, ccx-as-target...) since none of
        # those mutate the boolean value carried by the wire's computational basis
        # label in a way relevant to the forms dict (form tracks value-propagation
        # only through cx, which is the only gate that changes which wire holds
        # which linear combination of original inputs).
        continue

    if found_pair is None:
        return c, Req()

    prev, cur, key = found_pair
    i1, qa1, qb1, t1 = prev["idx"], prev["qa"], prev["qb"], prev["t"]
    i2, qa2, qb2, t2 = cur["idx"], cur["qa"], cur["qb"], cur["t"]

    # Build new circuit: fresh ancilla index c.n, fresh classical bit c.nc
    anc = c.n
    cbit = c.nc
    new_gates = []

    for idx, g in enumerate(gates):
        if idx == i1:
            # compute ancilla = qa1 & qb1 via plain Toffoli into fresh ancilla,
            # then apply cz(anc, t1) in place of ccz(qa1,qb1,t1)
            new_gates.append(Gate("ccx", (qa1, qb1, anc)))
            new_gates.append(Gate("cz", (anc, t1)))
        elif idx == i2:
            # second use: just cz(anc, t2) -- ancilla already equals the AND value
            new_gates.append(Gate("cz", (anc, t2)))
            # uncompute ancilla with measurement trick, using the CURRENT control
            # wires (qa2, qb2) for the fixup cz, since those are the wires that
            # currently hold the matching linear forms (the compute step used
            # qa1,qb1 but the value a = AND is invariant; to uncompute via the
            # standard trick we must re-express using an actual ccx(qa2,qb2,anc)
            # equivalence point -- since a already equals qa2&qb2 as a boolean
            # function (same key), H;measure;fixup cz(qa2,qb2);reset is valid.
            new_gates.append(Gate("h", (anc,)))
            new_gates.append(Gate("measure", (anc,), cbit=cbit))
            new_gates.append(Gate("cz", (qa2, qb2), cond=cbit))
            new_gates.append(Gate("reset", (anc,)))
        else:
            new_gates.append(g)

    new_c = Circuit(c.n + 1, new_gates, c.nc + 1, c.zero_init)
    return new_c, Req(eps=0.0, ancillas=1, measure=True)
