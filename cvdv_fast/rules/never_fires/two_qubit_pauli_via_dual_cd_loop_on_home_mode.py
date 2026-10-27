from cvdv_fast.api import Rule, Op
import math
import cmath


def synth(t, g, r):
    if t.kind != "pauli":
        return None
    if len(t.q) != 2 or len(t.label) != 2:
        return None
    s0, s1 = t.label[0], t.label[1]
    if s0 != s1:
        return None
    P = s0
    if P not in ("X", "Y", "Z"):
        return None

    theta = t.theta
    if theta == 0:
        return None

    j, k = t.q[0], t.q[1]

    # Mode used for the dual-CD phase-space loop. The identity below holds for
    # ANY oscillator state (not just vacuum), so this can in principle be a
    # mode already paired with qubit j ("home mode"); we request one via the
    # builder's ancilla-mode helper, which the runner is free to route onto
    # the pair it finds cheapest (e.g. a mode already adjacent to qubit j).
    m = g.anc_mode()

    rr = math.sqrt(abs(theta) / 2.0)
    beta = rr if theta >= 0 else -rr
    gamma = 1j * rr

    def basis_in(q):
        if P == "X":
            g.h(q)
        elif P == "Y":
            g.sdg(q)
            g.h(q)
        # Z: no basis change

    def basis_out(q):
        if P == "X":
            g.h(q)
        elif P == "Y":
            g.h(q)
            g.s(q)
        # Z: no basis change

    # Step 1: rotate P -> Z on both qubits (V_j, V_k)
    basis_in(j)
    basis_in(k)

    # Step 2-5: dual conditional-displacement phase-space loop on the shared
    # mode m. With A = CD(beta, j, m) = exp(Z_j (beta a^+ - beta* a)) and
    # B = CD(gamma, k, m) = exp(Z_k (gamma a^+ - gamma* a)):
    #   [A, B]'s generator commutator is (beta gamma* - beta* gamma) Z_j Z_k,
    #   a c-number times Z_j Z_k, which commutes with both A and B, so BCH
    #   terminates exactly:
    #     e^A e^B e^{-A} e^{-B} = exp(2i Im(beta gamma*) Z_j Z_k)
    # Choosing beta = +-r, gamma = i r with r = sqrt(|theta|/2) gives
    #   2 Im(beta gamma*) = -theta
    # so the product equals exp(-i theta Z_j Z_k) exactly, and the mode m
    # returns to its input state regardless of what that state was.
    g.CD(beta, j, m)
    g.CD(gamma, k, m)
    g.CD(-beta, j, m)
    g.CD(-gamma, k, m)

    # Step 6: undo the basis change
    basis_out(j)
    basis_out(k)


RULE = Rule(
    name="two_qubit_pauli_via_dual_cd_loop_on_home_mode",
    kind="synth",
    contract="exact",
    term_kinds=("pauli",),
    synth=synth,
    idea=(
        "exp(-i theta P_j P_k) for a two-qubit Pauli string with the SAME Pauli on both qubits "
        "(XX, YY or ZZ) is built from a single shared oscillator mode m via two native "
        "conditional-displacement (CD) gates per qubit, instead of a Pauli-string-conditioned "
        "CD bus built from CP conjugations. Rotate P -> Z with a one-qubit basis change "
        "(H for X; H.Sdg for Y; identity for Z), then apply A = CD(beta, j, m), "
        "B = CD(gamma, k, m), A^-1, B^-1 with beta = +-sqrt(|theta|/2), gamma = i*sqrt(|theta|/2) "
        "(sign of beta flips with the sign of theta). Since "
        "[Z_j(beta a^+ - beta* a), Z_k(gamma a^+ - gamma* a)] = (beta gamma* - beta* gamma) Z_j Z_k "
        "is a c-number times Z_j Z_k, it commutes with both generators, BCH truncates exactly, and "
        "e^A e^B e^{-A} e^{-B} = exp(2i Im(beta gamma*) Z_j Z_k) = exp(-i theta Z_j Z_k), returning "
        "the mode to whatever state it started in (vacuum ancilla or an already-populated mode). "
        "Undo the basis change to finish. Only 4 two-op CD gates (plus O(1) one-qubit gates) are "
        "needed, versus the ~8 CP + 2 D construction of the general Pauli-string bus rule."
    ),
    source=(
        "Liu et al. 2407.10381, Heisenberg-Weyl / displacement-commutator geometric-phase "
        "construction specialized to two qubits sharing one oscillator (a degenerate case of the "
        "Pauli-string bus-mode rule with w=2 and no CP-based Pauli-conditioning needed since only "
        "Z Z remains after the basis change)."
    ),
)
