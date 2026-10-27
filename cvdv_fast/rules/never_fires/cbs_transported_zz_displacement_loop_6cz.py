from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath


def synth(t, g, r):
    # exp(-i theta P_j P_k) for neighbouring qubits j,k with co-located modes a=m_j, b=m_k.
    # Only handles two-qubit Pauli strings (ZZ, XX, YY after basis change); needs the two
    # qubits' modes to be present and distinct.
    if len(t.q) != 2:
        return None
    if len(t.m) != 2:
        return None

    j, k = t.q
    a, b = t.m
    s0, s1 = t.label[0], t.label[1]

    theta = t.theta
    gg = math.sqrt(abs(theta) / 2)
    bb = gg if theta >= 0 else -gg

    # basis change in
    for q, s in zip((j, k), (s0, s1)):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.sdg(q); g.h(q)
        elif s == "Z":
            pass
        else:
            return None

    # closed loop core:
    #  1. D_a(-i g)
    #  2. CBS_j(-pi,0)
    #  3. CD_k(-i b)
    #  4. CBS_j(pi,0)
    #  5. D_a(+i g)
    #  6. CBS_j(-pi,0)
    #  7. CD_k(+i b)
    #  8. CBS_j(pi,0)
    g.D(-1j * gg, a)
    g.CBS(-math.pi, 0.0, j, a, b)
    g.CD(-1j * bb, k, b)
    g.CBS(math.pi, 0.0, j, a, b)
    g.D(1j * gg, a)
    g.CBS(-math.pi, 0.0, j, a, b)
    g.CD(1j * bb, k, b)
    g.CBS(math.pi, 0.0, j, a, b)

    # basis change out
    for q, s in zip((j, k), (s0, s1)):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.h(q); g.s(q)


RULE = Rule(name="cbs_transported_zz_displacement_loop_6cz", kind="synth", contract="exact", term_kinds=("pauli",),
            synth=synth,
            idea="Realise exp(-i theta P_j P_k) for neighbouring qubits j,k with co-located modes a=m_j, b=m_k "
                 "(P = Z, or X/Y after single-qubit basis change) via a 6-two-op-gate core instead of the 8-gate "
                 "CD+swap gadget. Conjugating CD_k(beta) by U = CBS_j(pi,0) uses the Hadamard lemma "
                 "(U b U^+ = i Z_j a, since [a b^+, b] = -a and [a^+ b, b] = 0) to produce a Z_jZ_k-conditioned "
                 "displacement of mode a: U CD_k(beta) U^+ = exp(Z_jZ_k (c a^+ - c* a)) with c = -i beta, exactly, "
                 "with mode b restored since it only appears inside the conjugation. Closing this with a plain "
                 "displacement D_a(ig) in a Heisenberg-Weyl loop, W(b) D_a(ig) W(-b) D_a(-ig) = exp(-2i b g Z_jZ_k), "
                 "gives an exact c-number commutator so mode a also returns to its input state for every photon "
                 "number, with b,g chosen so 2bg = theta. No ancilla is needed; XX/YY wrap the same core in the "
                 "usual per-qubit basis changes.",
            source="Liu et al. 2407.10381, Hadamard-lemma conjugation of a conditional displacement by a "
                    "conditional beam-splitter plus Heisenberg-Weyl closed phase-space loop (seed identity 3 "
                    "analogue, applied after CBS transport instead of swap transport)")
