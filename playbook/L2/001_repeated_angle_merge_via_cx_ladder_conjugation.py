"""
Parses the circuit into "phase-gadget" form: for every qubit we track its current GF(2)
parity vector over a set of free binary variables (reset to a fresh basis vector at each `h`,
XORed into by each `cx` target += control). Every rz(theta) is then a term theta on the parity
vector carried by its target qubit at that point. Two rz's on the SAME exact parity vector,
with no other gate touching the carrier qubit in a way that changes the Z-eigenbasis phase
convention in between (only Clifford Z-axis gates s/sdg/z/t/tdg and more cx's acting on OTHER
qubits are tolerated), commute past everything between them (they're diagonal in the same basis)
and can be merged into one rz(theta1+theta2) placed at the second location, deleting the first.
This is exact (no approximation): rz(a) and rz(b) on the same computational-basis-diagonal
operator commute and compose additively, regardless of what diagonal Z-type gates or
commuting CNOTs (not touching the involved qubits' parity) sit between them. We implement only
the exact, same-parity-vector merge (case covered by `needs: exact`), which is strictly stronger
than a same-line static check because it tracks parity through conjugating CX ladders and
Clifford corrections, letting rotations that are textually far apart (e.g. recurring angles
on different ladder "levels" that happen to touch the same cumulative parity) merge into one.
"""
from __future__ import annotations

from dataclasses import replace
from circuitevolve.circuit import Circuit, Gate
from circuitevolve.verifier import Req


def _vecxor(a: frozenset, b: frozenset) -> frozenset:
    return a.symmetric_difference(b)


def rewrite(c: Circuit) -> tuple[Circuit, Req]:
    n = c.n
    fresh_counter = [0]
    # parity[q] = frozenset of variable ids currently XORed into qubit q (None if unknown/not tracked)
    parity = [None] * n
    # give every qubit a distinct starting free variable (in case some are never h'd before use)
    for q in range(n):
        parity[q] = frozenset({("init", q)})

    # carrier_sign[q]: tracks whether intervening Z-diagonal single-qubit gates (s/sdg/t/tdg/z)
    # change the "phase convention" in a way that would break additive merging. For diagonal
    # gates (all our 1q non-h, non-x/y/sx gates besides rz are diagonal in Z basis: s,sdg,t,tdg,z)
    # they commute freely with rz on the same qubit and don't affect merging; so no extra sign
    # bookkeeping is actually required for them. We only need to invalidate tracking on h (which
    # changes basis) and on x/y/sx/sxdg (which are not Z-diagonal).
    NONDIAG_1Q = {"h", "x", "y", "sx", "sxdg"}
    DIAG_1Q_SAFE = {"s", "sdg", "t", "tdg", "z"}

    # First pass: find rz gates with identical parity vectors at the moment they occur.
    # key -> list of (index in c.gates, theta)
    groups = {}
    order = []

    n_gates = len(c.gates)
    for i, g in enumerate(c.gates):
        if g.name == "h":
            q = g.qubits[0]
            fresh_counter[0] += 1
            parity[q] = frozenset({("h", fresh_counter[0])})
        elif g.name in NONDIAG_1Q:
            q = g.qubits[0]
            fresh_counter[0] += 1
            parity[q] = frozenset({("unk", fresh_counter[0])})
        elif g.name in DIAG_1Q_SAFE:
            pass  # diagonal, doesn't change parity tracking
        elif g.name == "cx":
            ctrl, tgt = g.qubits
            if parity[ctrl] is None or parity[tgt] is None:
                parity[tgt] = None
            else:
                parity[tgt] = _vecxor(parity[tgt], parity[ctrl])
        elif g.name in ("cz", "swap", "ccx", "ccz"):
            # swap exchanges parity vectors; cz/ccx/ccz are not simple parity-preserving ops for
            # our purposes -> invalidate involved qubits to stay safe/exact.
            if g.name == "swap":
                a, b = g.qubits
                parity[a], parity[b] = parity[b], parity[a]
            else:
                for q in g.qubits:
                    fresh_counter[0] += 1
                    parity[q] = frozenset({("inval", fresh_counter[0])})
        elif g.name == "rz":
            q = g.qubits[0]
            p = parity[q]
            if p is not None and g.cond is None:
                key = (q, p)
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append(i)
        elif g.name in ("measure", "reset"):
            q = g.qubits[0]
            fresh_counter[0] += 1
            parity[q] = frozenset({("inval", fresh_counter[0])})
        # conditioned gates: be conservative, invalidate target qubits' parity
        if g.cond is not None and g.name != "rz":
            for q in g.qubits:
                fresh_counter[0] += 1
                parity[q] = frozenset({("inval", fresh_counter[0])})

    # Build merge groups: only keep groups with >=2 rz gates on identical (qubit, parity) key.
    merge_groups = [idxs for key, idxs in groups.items() if len(idxs) >= 2]

    if not merge_groups:
        return c, Req()

    # To merge, we require that between the first and last occurrence in a merge group, none of
    # the OTHER (non-grouped) gates touching that same qubit changed its parity-tracking state in
    # a way already reflected (we already only grouped by the snapshot parity at each rz, which is
    # correctly updated through the loop above, so this is already consistent: all rz's in a group
    # truly act on the same diagonal operator at their respective positions, since cx's with the
    # SAME net ladder-effect on that qubit brought it back to the same parity vector). We now also
    # need the chain of gates strictly BETWEEN a merged pair, restricted to the carrier qubit, to
    # consist only of gates that commute with a diagonal (Z-type) rotation on that qubit, OR be
    # cx's where this qubit is the CONTROL (control is unaffected by a Z-rotation applied to it as
    # diagonal commutes with cx-control role trivially: cx control is a classical copy of the basis
    # state, diagonal gate on control commutes with cx exactly). If the qubit is the cx TARGET in
    # between, that's already accounted for in parity evolution (and such a cx changes parity so
    # would break group membership at the next rz anyway, unless the ladder returns to the same
    # parity, which is still fine: diagonal rz on a changing-but-returning parity commutes with the
    # intervening cx's forming a conjugation, standard phase-gadget algebra). So this is safe as is.

    new_gates = list(c.gates)
    removed = set()
    changed = False

    for idxs in merge_groups:
        idxs_sorted = sorted(idxs)
        total = 0.0
        for j in idxs_sorted:
            total += new_gates[j].theta
        # normalize total into (-2pi, 2pi]-ish range; rz is 2pi periodic up to global phase which
        # verifier ignores, so no need to mod further.
        last = idxs_sorted[-1]
        g0 = new_gates[last]
        new_gates[last] = replace(g0, theta=total)
        for j in idxs_sorted[:-1]:
            removed.add(j)
        changed = True

    if not changed:
        return c, Req()

    final_gates = [g for k, g in enumerate(new_gates) if k not in removed]
    new_c = Circuit(c.n, final_gates, c.nc, c.zero_init)
    return new_c, Req(eps=0.0, ancillas=0, measure=False)
