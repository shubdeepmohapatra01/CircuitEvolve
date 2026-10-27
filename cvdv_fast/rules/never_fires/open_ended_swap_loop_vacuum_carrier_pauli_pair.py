from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath


def synth(t, g, r):
    # Weight-2 Pauli term exp(-i theta P_j P_k) on neighbouring qubits j,k using their co-located
    # ancilla qumodes m_j, m_k as a vacuum carrier. Gadget: drop the trailing BS of the accepted
    # 8-gate loop since the final BS acts on vacuum and a passive linear-optics unitary fixes vacuum.
    if len(t.q) != 2:
        return None
    if len(t.m) < 2:
        return None

    qj, qk = t.q[0], t.q[1]
    mj, mk = t.m[0], t.m[1]
    sj, sk = t.label[0], t.label[1]

    # basis change to Z for X/Y
    for q, s in ((qj, sj), (qk, sk)):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.rx(math.pi / 2, q)
        elif s != "Z":
            return None

    # Same alpha, beta magnitude/relation as the accepted colocated_mode_swap_loop_pauli_zz rule:
    # four CD-with-interleaved-swap gadget accumulates phase c*|alpha||beta|*Z_j*Z_k = theta (up to sign),
    # with |alpha| = |beta| = sqrt(|theta|/2) and sign of theta folded into beta's sign.
    b = math.sqrt(abs(t.theta) / 2)
    alpha = b
    beta = b if t.theta >= 0 else -b

    g.CD(alpha, qj, mj)
    g.BS(math.pi, 0.0, mj, mk)
    g.CD(beta, qk, mk)
    g.BS(math.pi, 0.0, mj, mk)
    g.CD(alpha, qj, mj)
    g.BS(math.pi, 0.0, mj, mk)
    g.CD(beta, qk, mk)

    # undo basis change
    for q, s in ((qj, sj), (qk, sk)):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.rx(-math.pi / 2, q)


RULE = Rule(
    name="open_ended_swap_loop_vacuum_carrier_pauli_pair",
    kind="synth",
    contract="exact",
    term_kinds=("pauli",),
    synth=synth,
    idea="Weight-2 Pauli ZZ/XX/YY gadget on neighbouring qubits whose co-located qumodes are vacuum ancillas: "
         "drop the trailing BS of the accepted 8-gate closed Heisenberg-Weyl loop (CD_j, BS, CD_k, BS, CD_j, BS, "
         "CD_k, BS) since carrier tracking shows both modes are already in vacuum after 7 gates, and a passive "
         "linear-optics unitary (BS) acting on vacuum is the identity with no phase. Saves one 2-op gate per "
         "pair term with an unchanged alpha/beta relation and identical accuracy to the 8-gate version.",
    source="Liu et al. 2407.10381, Heisenberg-Weyl closed-loop qubit-qubit entangling via a shared mode pair; "
           "optimization of colocated_mode_swap_loop_pauli_zz by exact BS action on two-mode vacuum",
)
