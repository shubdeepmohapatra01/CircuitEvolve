"""Merge two Z-rotations whose axes coincide in the Pauli frame of the Clifford skeleton between them."""
from v4.api import Precondition, Rule
from v4.api import dv, pauli

_INV = {"s": "sdg", "sdg": "s"}


def find_matches(c):
    """(i, j, s): rotation j transported backwards to just after i is s * Z_{q_i}."""
    if not dv.is_angle_circuit(c):
        return []
    ops = c.ops
    out, used = [], set()
    for j, op in enumerate(ops):
        if dv.rotation(op) is None:
            continue
        p = pauli.z_on(op[1][0])
        for i in range(j - 1, -1, -1):
            g, qs, _ = ops[i]
            if dv.rotation(ops[i]) is not None:
                s = pauli.is_z(p, qs[0])
                if s and i not in used:
                    out.append((i, j, s))
                    used.update((i, j))
                    break
                if not pauli.commutes_with_z(p, qs[0]):
                    break
                continue
            # R_j C = C (C^dag R_j C): conjugate by the inverse gate
            p = pauli.conjugate(p, _INV.get(g, g), qs)
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
    trigger=find_matches,
    apply=apply_match,
)
