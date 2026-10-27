"""Merge two Z-rotations whose axes coincide in the Pauli frame of the Clifford skeleton between them.

v4 change (V4_README section 9): the axes come from `v4.api.pauli.frames`, one forward sweep over a
Clifford tableau, instead of transporting each rotation's Z backwards through the Cliffords between it
and every earlier rotation - O(rotations x ops) per trigger call.

The two formulations are the SAME test. Transporting rotation j back to just after rotation i gives
Q = C_between^dag Z_qj C_between, and the front-frame Paulis are P_i = Phi_i(Z_qi), P_j = Phi_j(Z_qj)
= Phi_i(Q). So "Q = s Z_qi" is exactly "P_j = s P_i", i.e. the two axes are equal up to sign. Commutation
is frame-independent in the same way, so the walk's stopping condition - the intervening rotation's Z
must commute with the transported Pauli - becomes "P_i must commute with P_j". The matches are
identical on all five angle circuits (v4/tests/test_p3.py).
"""
from v4.api import Precondition, Rule
from v4.api import dv, pauli


def find_matches(c):
    """(i, j, s): rotation j's front-frame axis equals s times rotation i's, with every rotation between
    them commuting with it - so the two angles add (a_i + s a_j) and the later op is deleted."""
    if not dv.is_angle_circuit(c):
        return []
    recs = pauli.frames(c.ops)
    if recs is None:
        return []
    out, used = [], set()
    for k in range(len(recs)):
        rk = recs[k]
        for m in range(k - 1, -1, -1):
            rm = recs[m]
            s = pauli.axis_eq(rm.p, rk.p)
            if s and rm.pos not in used and rk.pos not in used:
                out.append((rm.pos, rk.pos, s))
                used.update((rm.pos, rk.pos))
                break
            if not pauli.commutes(rm.p, rk.p):
                break
    return out


def apply_match(c, m):
    i, j, s = m
    ops = list(c.ops)
    theta = dv.rotation(ops[i]) + s * dv.rotation(ops[j])
    ops[i] = ("rz", ops[i][1], theta)
    del ops[j]
    return dv.with_ops(c, ops)


RULE = Rule(
    name="pauli_frame_rotation_merge",
    domain="dv",
    kind="procedure",
    contract="exact",
    source="Litinski 1808.02892; Kissinger & van de Wetering 1903.10477 (phase teleportation)",
    idea="Move a later Z-rotation backwards through the Clifford ops between (its axis becomes C^dag P C per op) "
         "and past rotations whose Z commutes with that axis; if it lands as +-Z on an earlier rotation's qubit, "
         "the two angles add (a_i + s a_j) and the later op is deleted. Exact up to global phase.",
    precondition=Precondition(families=("dv_angle",), needs=("rotations",),
        note="merges two Z-rotations; nothing to merge without rotations, and the op-list form is dv_angle"),
    tier="floor",
    evidence=dict(
        baseline="pyzx full_reduce",
        measured_alone={"qft_8": "2391 -> 1583", "qpe_8": "14761 -> 11485 = pyzx exactly",
                        "hhl_8": "35450 -> 29331", "qae_13": "7821 -> 4527 = pyzx exactly"},
        measured_in_floor={"qpe_8": "11485 = pyzx exactly", "qae_13": "4526, 1 T BELOW pyzx's 4527"},
        source="v3/results/p2/SUMMARY.md attempt hhl_8 a1; re-measured in v4 (v4/results/floor_gate_p2.json)",
        why_floor="phase-gadget fusion is pyzx's T win on these inputs, and this rule reproduces pyzx\n                   exactly on qpe_8 and qae_13. V4_README 4.1 also credits it with qft_8 = 1577; that\n                   number came from a two-rule book in the P2 log. Alone and inside the v4 floor it\n                   gives 1583 - see v4/BUILD_LOG.md P2."),
    trigger=find_matches,
    apply=apply_match,
)
