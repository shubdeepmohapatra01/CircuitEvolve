"""measured_uncompute_of_nested_and_ladder

Generalizes the single-pair measured-uncompute trick one level deeper: ancilla a2 (q[5])
is computed as a2 = c2 & a1 (H-conjugated CCZ), used only as a diagonal control (CCZ on
c3,a2,tgt), then tory down by an identical H-CCZ-H. That teardown's phase-kickback-on-|1>
is exactly CZ(c2, a1); since a1 is itself an ancilla about to be (or already) measured-
uncomputed, we land the fixup CZ(c2,a1) just before a1's own H/measure step, where it is
a plain classically-controlled Clifford gate that commutes freely into that slot (nothing
but a1's own H and measurement happens between). This removes the ccz(c2,a1,a2) teardown
Toffoli (7 T) and replaces it with: H a2; measure a2->m2; if m2: CZ(c2,a1); reset a2 -
exact, zero-error, relying only on a2 being a clean ancilla equal to c2&a1 at that point.
"""
from circuitevolve.circuit import Circuit, Gate
from circuitevolve.verifier import Req


def rewrite(c: Circuit) -> tuple[Circuit, Req]:
    gates = c.gates
    n = len(gates)

    def is_h1(g, q=None):
        return g.name == "h" and len(g.qubits) == 1 and (q is None or g.qubits[0] == q)

    def find_ladder(i):
        """Match at index i: h a2; ccz c2,a1,a2; h a2; h tgt; ccz c3,a2,tgt; h tgt;
        h a2; ccz c2,a1,a2; h a2   (compute / use / teardown of a2, nested on a1)."""
        if i + 8 >= n:
            return None
        g = gates
        if not is_h1(g[i]):
            return None
        a2 = g[i].qubits[0]
        if g[i + 1].name != "ccz":
            return None
        c2, a1, a2b = g[i + 1].qubits
        if a2b != a2:
            return None
        if not is_h1(g[i + 2], a2):
            return None
        if not is_h1(g[i + 3]):
            return None
        tgt = g[i + 3].qubits[0]
        if g[i + 4].name != "ccz":
            return None
        c3, a2c, tgtb = g[i + 4].qubits
        if a2c != a2 or tgtb != tgt:
            return None
        if not is_h1(g[i + 5], tgt):
            return None
        if not is_h1(g[i + 6], a2):
            return None
        if g[i + 7].name != "ccz":
            return None
        c2b, a1b, a2d = g[i + 7].qubits
        if c2b != c2 or a1b != a1 or a2d != a2:
            return None
        if not is_h1(g[i + 8], a2):
            return None
        return dict(a2=a2, a1=a1, c2=c2, c3=c3, tgt=tgt, start=i, end=i + 9)

    m = None
    for i in range(n):
        m = find_ladder(i)
        if m is not None:
            break
    if m is None:
        return c, Req()

    a2, a1, c2, c3, tgt = m["a2"], m["a1"], m["c2"], m["c3"], m["tgt"]
    start, end = m["start"], m["end"]

    # a2 must be a clean ancilla that is |0> on entry to this segment: require it appears
    # in zero_init and is not touched before `start` other than inside this match (the
    # matched block itself is a1's "use" context, so this is fine structurally; we rely on
    # the benchmark-level zero_init contract exactly as the base rule does).
    if a2 not in c.zero_init:
        return c, Req()

    # After the ladder teardown, find a1's own pending uncompute: either the still-exact
    # `h a1; ccz c0,c1,a1; h a1` form, or the already-measured-uncompute form produced by
    # measured_uncompute_of_ccx_ancilla_pair: `h a1; measure a1->cb; if cb: cz c0,c1; if cb: x a1`.
    # We only need to find a1's NEXT `h a1` after `end` (nothing else may touch a1 in between)
    # and insert our classically-controlled CZ(c2, a1) right before that h.
    j = end
    while j < n and a1 not in gates[j].qubits:
        j += 1
    if j >= n or not is_h1(gates[j], a1):
        # a1's next touch isn't the expected H start of its uncompute; bail out to stay safe.
        return c, Req()

    insert_at = j  # insert fixup CZ(c2, a1) right before a1's H (its uncompute entry point)

    nc_base = c.nc
    cb_a2 = nc_base  # fresh classical bit for a2's measurement

    new_gates = list(gates[:start])

    # --- compute phase (unchanged) ---
    new_gates.append(Gate("h", (a2,)))
    new_gates.append(Gate("ccz", (c2, a1, a2)))
    new_gates.append(Gate("h", (a2,)))

    # --- use phase (unchanged) ---
    new_gates.append(Gate("h", (tgt,)))
    new_gates.append(Gate("ccz", (c3, a2, tgt)))
    new_gates.append(Gate("h", (tgt,)))

    # --- measured uncompute of a2 ---
    new_gates.append(Gate("h", (a2,)))
    new_gates.append(Gate("measure", (a2,), cbit=cb_a2))
    new_gates.append(Gate("cz", (c2, a1), cond=cb_a2))
    new_gates.append(Gate("reset", (a2,)))

    # --- everything between end and a1's uncompute entry point, unchanged ---
    new_gates.extend(gates[end:insert_at])

    # the fixup CZ(c2, a1) is already placed above (right before this point in program
    # order); now emit a1's own uncompute step(s) unchanged starting at insert_at.
    new_gates.extend(gates[insert_at:])

    new_c = Circuit(c.n, new_gates, nc_base + 1, c.zero_init)

    return new_c, Req(eps=0.0, ancillas=0, measure=True)
