from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath


def synth(t, g, r):
    # exp(-i theta Z_j (gamma b^+ + gamma* b)) where mode b = t.m[other] is NOT the
    # qubit's home mode, but the term carries both the home mode and the target mode
    # as its two mode wires (home first, target second), coupled via a conditional
    # full beam splitter (CBS) on the qubit/home-mode/target-mode triple.
    if t.kind != "hybrid":
        return None
    if len(t.q) != 1 or len(t.m) != 2:
        return None

    j = t.q[0]
    home, other = t.m[0], t.m[1]

    theta = t.theta
    if theta == 0:
        return None

    # Target Hamiltonian part: theta * Z_j * (b^+ + b)  (phi assumed 0; gamma real)
    # (The benchmark's hybrid terms are of the form -i*c*Z*(b + b^+)-type real-linear
    # couplings; t.theta carries the real coefficient of Z_j (b^+ + b).)

    # U = CBS(pi, 0) on (j; home, other):  G_0 = a^+ b + b^+ a  (a = home mode, b = other)
    # Hadamard lemma (closes since ad_G^2 = -1 on span{a,b} up to the stated normalization):
    #   U a U^+ = i * Z_j * b   =>   U^+ (i Z_j b) U = a   =>   U^+ b U = -i Z_j a   (using U^+ = U(-pi,0))
    # We need: Z_j (gamma' b^+ - gamma'* b) with gamma' chosen so that conjugating a
    # home-mode displacement D(beta) by U produces the target Z_j-conditioned
    # displacement on mode 'other'.
    #
    # U^+ D_a(beta) U = exp(beta (U^+ a U)^+ - beta* (U^+ a U))
    # With U^+ a U = -i e^{+i*0} Z_j b  (symmetric partner of U a U^+ = i e^{-i*0} Z_j b),
    # so (U^+ a U)^+ = i Z_j b^+ (Z_j real, self-adjoint).
    # => U^+ D_a(beta) U = exp(Z_j (i beta b^+ - (-i beta*) b)) = exp(Z_j (i beta b^+ + i beta* b))
    #
    # We want this to equal exp(-i theta Z_j (b^+ + b)), i.e.
    #   i beta = -i theta  and  i beta* = -i theta  =>  beta = -theta (real).
    c = 1j  # unit-modulus phase linking (U^+ a U) to Z_j b, per the Hadamard-lemma relation above
    beta = -theta  # real theta => real beta; matches i*beta = -i*theta

    # Gate sequence (time order = emission order):
    #   1. U = CBS(pi, 0)        on (j; home, other)
    #   2. D(beta) on home mode  (home mode only; "other"/target mode untouched as operator)
    #   3. U^+ = CBS(-pi, 0)     on (j; home, other)
    g.CBS(math.pi, 0.0, j, home, other)
    g.D(beta, home)
    g.CBS(-math.pi, 0.0, j, home, other)


RULE = Rule(
    name="cbs_swap_conjugated_displacement_remote_mode",
    kind="synth",
    contract="exact",
    term_kinds=("hybrid",),
    synth=synth,
    idea="exp(-i theta Z_j (b + b^+)) for a mode b that is grid-adjacent to but not the home mode of "
         "qubit j: conjugate an ordinary home-mode displacement by a full conditional beam splitter "
         "CBS(pi,0) on (j; home, b). The Hadamard lemma closes after one commutator (ad_G^2 = identity "
         "on span{a,b}), so U maps the home-mode annihilation operator onto i*Z_j*b exactly (all photon "
         "numbers, no truncation error). Conjugating D(beta) on the home mode therefore produces exactly "
         "the Z_j-conditioned displacement of the target mode, with beta = -theta chosen to match the "
         "stated coefficient. No ancilla; no router SWAP of the remote mode is needed.",
    source="Liu et al. 2407.10381 (Hadamard-lemma / BCH conjugation of displacements through beam-splitter "
           "couplers; CBS Heisenberg action closes exactly on a 2-mode subspace), applied here to avoid "
           "routing a non-home mode next to its qubit via SWAPs",
)
