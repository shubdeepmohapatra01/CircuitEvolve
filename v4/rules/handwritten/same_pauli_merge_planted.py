"""P1 hand-written rule 4 (no LLM), PLANTED BUG: same_pauli_merge, but about 1 match in 10 ((i + k) % 10 == 0,
decided by the match itself so it is deterministic and independent of application order) merges with the wrong
sign (b - a instead of b + a). Admission must REJECT it by verification."""
from v4.api import Rule
from v4.api import dv, pauli


def find_matches(c):
    """(i, k, sign): rotation i, pushed forward through the gates between, becomes sign * rotation on k's Pauli."""
    if not dv.is_angle_circuit(c):
        return []
    ops = c.ops
    out, used = [], set()
    for i, op in enumerate(ops):
        if dv.rotation(op) is None or i in used:
            continue
        p = pauli.z_on(op[1][0])
        for j in range(i + 1, len(ops)):
            g, qs, _ = ops[j]
            if dv.rotation(ops[j]) is not None:
                sign = pauli.is_z(p, qs[0])
                if sign and j not in used:
                    out.append((i, j, sign))
                    used.update((i, j))
                    break
                if not pauli.commutes_with_z(p, qs[0]):
                    break
                continue
            p = pauli.conjugate(p, g, qs)
    return out


def apply_match(c, m):
    i, k, sign = m
    ops = list(c.ops)
    corrupt = (i + k) % 10 == 0
    theta = dv.rotation(ops[k]) + (-sign if corrupt else sign) * dv.rotation(ops[i])
    ops[k] = ("rz", ops[k][1], theta)
    del ops[i]
    return dv.with_ops(c, ops)


RULE = Rule(
    name="same_pauli_merge_planted",
    domain="dv",
    kind="rewrite",
    contract="exact",
    source="P1 planted-bug control (hand-written). Base: textbook (phase folding / Pauli-rotation merging; e.g. Amy-Maslov-Mosca 2014, Zhang-Chen 2019)",
    idea="exp(-i a/2 P) C = C exp(-i a/2 C^dag P C) for a Clifford C, and rotations about commuting Paulis commute. "
         "So a Z-rotation can be moved forward through Cliffords (its Pauli conjugated) and past rotations whose "
         "Pauli commutes with it; if it reaches a rotation whose Pauli is +-Z_q, the two combine: "
         "rz(b) rz(+-a) = rz(b +- a) on that qubit, up to global phase. Exact.",
    trigger=find_matches,
    apply=apply_match,
)
