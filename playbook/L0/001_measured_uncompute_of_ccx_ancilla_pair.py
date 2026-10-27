"""
Replaces the uncompute Toffoli of a compute/intermediate/uncompute ancilla pattern with
measurement-based uncomputation (Jones/Gidney trick). Pattern: clean ancilla a=|0> is set by
an H-conjugated ccz on (c0,c1,a) [= Toffoli a ^= c0&c1], then used only as a CONTROL of
diagonal gate(s) (so it stays classical), then unset by an identical H-ccz-H on (c0,c1,a).
Since a = c0&c1 at that point, uncomputing is equivalent to: H a; measure a -> m; if m==1
apply CZ(c0,c1) classically-controlled and reset a back to |0> (a CCZ(c0,c1,a) followed by H a,
measuring |1> means we must fix up the phase that CCZ would have applied, which is exactly a CZ
on c0,c1, and then a is forced back to |0> so it is a proper clean ancilla again). This removes
one Toffoli (7 T) at the cost of one measurement + classically controlled CZ + reset (0 T), and is
sound because c0,c1 are untouched between compute and uncompute so x0&x1 is preserved throughout.
"""
from circuitevolve.circuit import Circuit, Gate
from circuitevolve.verifier import Req


def _is_h(g, q):
    return g.name == "h" and g.qubits == (q,) and g.cond is None


def _ccz_on(g, a):
    return g.name == "ccz" and g.cond is None and a in g.qubits


def _other_two(qubits, a):
    return tuple(q for q in qubits if q != a)


def rewrite(c: Circuit) -> tuple[Circuit, Req]:
    gates = c.gates
    N = len(gates)

    for a in c.zero_init:
        # find first use of a
        first_idx = None
        for i, g in enumerate(gates):
            if a in g.qubits:
                first_idx = i
                break
        if first_idx is None:
            continue

        # expect: h a ; ccz (c0,c1,a) ; h a   as the compute block
        if first_idx + 2 >= N:
            continue
        g0, g1, g2 = gates[first_idx], gates[first_idx + 1], gates[first_idx + 2]
        if not (_is_h(g0, a) and _ccz_on(g1, a) and _is_h(g2, a)):
            continue
        controls = _other_two(g1.qubits, a)
        if len(controls) != 2:
            continue
        c0, c1 = controls

        # scan forward from after the compute block for the matching uncompute block
        uncompute_start = None
        j = first_idx + 3
        valid = True
        while j < N:
            g = gates[j]
            if a in g.qubits:
                # candidate start of uncompute: h a ; ccz(c0,c1,a) ; h a  (identical pattern)
                if (j + 2 < N and _is_h(g, a) and _ccz_on(gates[j + 1], a) and _is_h(gates[j + 2], a)
                        and _other_two(gates[j + 1].qubits, a) == controls):
                    uncompute_start = j
                    break
                else:
                    # a must appear only as control of a diagonal gate that doesn't move it out of computational basis
                    if g.name in ("ccz", "cz") and a in g.qubits and g.cond is None:
                        j += 1
                        continue
                    else:
                        valid = False
                        break
            else:
                j += 1
        if not valid or uncompute_start is None:
            continue

        # ensure c0, c1 are untouched between first_idx and uncompute_start+2 (inclusive range of block)
        block_end = uncompute_start + 2
        touched_controls = False
        for k in range(first_idx, block_end + 1):
            if k in (first_idx, first_idx + 1, first_idx + 2, uncompute_start, uncompute_start + 1, uncompute_start + 2):
                continue
            g = gates[k]
            if c0 in g.qubits or c1 in g.qubits:
                touched_controls = True
                break
        if touched_controls:
            continue

        # Build the new circuit: remove uncompute block (h a; ccz; h a) at [uncompute_start, uncompute_start+2]
        # Replace with: h a ; measure a -> new_cbit ; cond CZ(c0,c1) on new_cbit ; cond X(a) on new_cbit (reset)
        new_cbit = c.nc
        new_gates = []
        new_gates.extend(gates[:uncompute_start])
        new_gates.append(Gate(name="h", qubits=(a,)))
        new_gates.append(Gate(name="measure", qubits=(a,), cbit=new_cbit))
        new_gates.append(Gate(name="cz", qubits=(c0, c1), cond=new_cbit))
        new_gates.append(Gate(name="x", qubits=(a,), cond=new_cbit))
        new_gates.extend(gates[uncompute_start + 3:])

        new_c = Circuit(n=c.n, gates=new_gates, nc=c.nc + 1, zero_init=c.zero_init)
        return new_c, Req(eps=0.0, ancillas=0, measure=True)

    return c, Req()
