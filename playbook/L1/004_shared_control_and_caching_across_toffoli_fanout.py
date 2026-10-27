"""
shared_control_and_caching_across_toffoli_fanout

Finds two or more Toffoli-equivalent gates (CCX, or CCZ which is CCX conjugated
by H on the target) that share the SAME unordered control pair {c1,c2}, with no
gate strictly between the first and last matched occurrence touching c1 or c2
(a spectator-safe span, so the controls -- and hence the AND of them -- are
unchanged throughout). It computes anc <- AND(c1,c2) exactly once on a fresh
|0> ancilla using the exact (non-approximate) Toffoli-based definition
anc = CCX(c1,c2,anc), replaces every matched occurrence by a single CX(anc,t)
(CCX form) or CZ(anc,t) (CCZ form via H-sandwich), and uncomputes the ancilla
once at the end with the standard measurement-based AND-uncompute: H anc;
measure anc -> m; classically-controlled CZ(c1,c2) conditioned on m; reset anc.
This is exact: since c1,c2 are untouched across the whole span, the ancilla
equals AND(c1,c2) at every matched gate, so substituting CX/CZ from the cached
ancilla reproduces each original Toffoli's action; the final H+measure+CZ is
the textbook identity that deterministically restores |0> and fixes up the
phase the removed final CCZ(c1,c2,anc) would have applied. Because computing
AND(c1,c2) onto a fresh ancilla via an actual CCX gate costs only whatever the
downstream T-synthesis of that CCX costs once (7 T, vs 7 T times the number of
shared occurrences), repeated occurrences become free CX/CZ gates.
"""
from __future__ import annotations

from circuitevolve.circuit import Circuit, Gate
from circuitevolve.verifier import Req


def _tof_info(g: Gate):
    """Return (control_pair, target, kind) for CCX/CCZ gates, else None."""
    if g.name == "ccx":
        a, b, t = g.qubits
        return frozenset((a, b)), t, "cx"
    if g.name == "ccz":
        a, b, t = g.qubits
        return frozenset((a, b)), t, "cz"
    return None


def rewrite(c: Circuit) -> tuple[Circuit, Req]:
    gates = c.gates

    by_pair: dict[frozenset, list[int]] = {}
    for i, g in enumerate(gates):
        info = _tof_info(g)
        if info is not None:
            pair, _, _ = info
            by_pair.setdefault(pair, []).append(i)

    chosen_pair = None
    chosen_indices = None

    for pair, idxs in by_pair.items():
        if len(idxs) < 2:
            continue
        c1, c2 = tuple(pair)
        lo, hi = idxs[0], idxs[-1]
        matched_set = set(idxs)
        safe = True
        for j in range(lo, hi + 1):
            if j in matched_set:
                continue
            gj = gates[j]
            if c1 in gj.qubits or c2 in gj.qubits:
                safe = False
                break
        if safe and (chosen_pair is None or len(idxs) > len(chosen_indices)):
            chosen_pair = pair
            chosen_indices = idxs

    if chosen_pair is None:
        return c, Req()

    c1, c2 = tuple(sorted(chosen_pair))
    idxs = chosen_indices
    lo, hi = idxs[0], idxs[-1]
    matched_set = set(idxs)

    anc = c.n
    cbit = c.nc

    new_gates: list[Gate] = []
    new_gates.extend(gates[:lo])

    # Exact AND: anc (clean |0>) <- CCX(c1, c2, anc). A plain Toffoli on a |0>
    # target computes exactly AND(c1,c2) into the target, by CCX's definition.
    new_gates.append(Gate("ccx", (c1, c2, anc)))

    for j in range(lo, hi + 1):
        g = gates[j]
        if j in matched_set:
            _, t, kind = _tof_info(g)
            if kind == "cx":
                new_gates.append(Gate("cx", (anc, t)))
            else:
                new_gates.append(Gate("cz", (anc, t)))
        else:
            new_gates.append(g)

    # Standard measurement-based AND-uncompute.
    new_gates.append(Gate("h", (anc,)))
    new_gates.append(Gate("measure", (anc,), cbit=cbit))
    new_gates.append(Gate("cz", (c1, c2), cond=cbit))
    new_gates.append(Gate("reset", (anc,)))

    new_gates.extend(gates[hi + 1:])

    new_c = Circuit(c.n + 1, new_gates, c.nc + 1, c.zero_init)

    req = Req(eps=0.0, ancillas=1, measure=True)
    return new_c, req
