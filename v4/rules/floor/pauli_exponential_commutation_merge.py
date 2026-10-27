"""Pauli-exponential normal form: front-frame Paulis of all rotations, merge commuting-reachable
equal-Pauli pairs.

v4 change (V4_README section 9): the front-frame Paulis come from `v4.api.pauli.frames`, one forward
sweep over a Clifford tableau, instead of this rule's own `_records`, which conjugated each rotation's Z
back through the whole Clifford prefix - O(rotations x ops). That hand-rolled pass was the single largest
cost in the whole v3 book: 14.4 M calls to `pauli.conjugate`, 13.5 s of qpe_8's 27 s profiled run. The
API version is 2.40 ms against 174.08 ms on hhl_8 and returns the same Paulis rotation for rotation
(asserted in v4/tests/test_p3.py). The matches, and therefore every accepted rewrite, are unchanged.
"""
import math

from v4.api import Precondition, Rule
from v4.api import dv, pauli

_TOL = 1e-9


def _reduce(theta):
    return dv.reduce_angle(theta)


def _records(ops):
    """[(pos, theta, (x, z) axis, sign, needs_gridsynth)] - `pauli.frames` with this rule's field order.

    `needs_gridsynth` is what the merge test keys on: a rotation already on the pi/4 grid is a Clifford
    or T gate and merging it only pays if the RESULT is still on the grid, while an off-grid rotation
    costs gridsynth and is always worth removing."""
    recs = pauli.frames(ops)
    if recs is None:
        return None
    return [(r.pos, r.theta, r.key, r.sign, not r.on_grid) for r in recs]


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    recs = _records(c.ops)
    if not recs:
        return []
    cand = []
    for k in range(len(recs)):
        pk, tk, keyk, ek, nk = recs[k]
        for j in range(k - 1, -1, -1):
            pj, tj, keyj, ej, nj = recs[j]
            if keyj == keyk:
                s = ej * ek
                if nj or nk:
                    eff = tj + s * tk
                    ok = True
                    if not (nj and nk):
                        ok = dv.on_grid(eff, _TOL)
                    if ok:
                        cand.append((-(abs(tj) + abs(tk)), pj, pk, s))
            elif not pauli.commutes((keyj[0], keyj[1], 1), (keyk[0], keyk[1], 1)):
                break
    cand.sort()
    out, used = [], set()
    # report one at a time, but return a consistent list: disjoint pairs only
    for _, pj, pk, s in cand:
        if pj in used or pk in used:
            continue
        used.update((pj, pk))
        out.append((pj, pk, s))
    return out


def apply_match(c, m):
    pj, pk, s = m
    ops = list(c.ops)
    eff = _reduce(dv.rotation(ops[pj]) + s * dv.rotation(ops[pk]))
    qj = ops[pj][1]
    if abs(eff) < _TOL:
        del ops[pk]
        del ops[pj]
    else:
        ops[pj] = ("rz", qj, eff)
        del ops[pk]
    return dv.with_ops(c, ops)


RULE = Rule(
    name="pauli_exponential_commutation_merge",
    domain="dv",
    kind="procedure",
    contract="exact",
    source="Cowtan et al. 2019 (Pauli gadgets); Litinski 2019 (pi/8 Pauli rotations + final Clifford); Nam et al. 2018",
    idea="Move every rotation to the circuit front as a signed n-qubit Pauli exponential (X/Y/Z-type, multi-qubit), "
         "so Hadamards do not cut. Two rotations with equal Paulis merge (angles add with sign) if the later "
         "one commutes with all rotation Paulis between them; the edit is made in place in the original op list.",
    precondition=Precondition(families=("dv_angle",), needs=("rotations",),
        note="front-frames the rotations of a Clifford+Rz op list"),
    tier="floor",
    evidence=dict(
        baseline="pyzx full_reduce",
        measured={"hhl_8": "29331 -> 29205 = pyzx exactly (with the frame rule);\n                            29273 alone from the TKET input"},
        source="v3/results/p2/SUMMARY.md, attempt qpe_8 a2",
        why_floor="takes hhl_8 to pyzx exactly, the one angle circuit the frame rule does not reach;\n                   V4_README section 4.1"),
    trigger=find_matches,
    apply=apply_match,
)
