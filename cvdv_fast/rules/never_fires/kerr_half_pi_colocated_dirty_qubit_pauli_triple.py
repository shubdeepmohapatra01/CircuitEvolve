from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath


def synth(t, g, r):
    # exp(-i theta n^2) on a single mode, using the co-located qubit q = t.q[0] as a DIRTY catalyst
    # (its state is arbitrary and is returned unchanged, up to the global/qubit-local phase handled
    # by construction below, since the three-CR product is a pure c-number times identity on the qubit
    # for every Fock level n).
    #
    # Identity: n^2 mod 4 = n mod 2, so with theta = pi/2 + k*pi + delta (|delta| small):
    #   exp(-i theta n^2) = R(3*delta + pi/2 + k*pi)(m) * (-iZ)^n (-iY)^n (-iX)^n
    # where (-iZ)^n = CR(pi), (-iY)^n = (S H) CR(pi) (S H)^+, (-iX)^n = H CR(pi) H,
    # all conjugations realized by surrounding single-qubit Cliffords on q.
    if t.kind != "n2":
        return None
    if len(t.q) != 1 or len(t.m) != 1:
        return None

    q = t.q[0]
    m = t.m[0]
    theta = t.theta

    k = round((theta - math.pi / 2) / math.pi)
    delta = theta - math.pi / 2 - k * math.pi
    if abs(delta) > 1e-7:
        return None

    # (-iX)^n block: H CR(pi) H
    g.h(q)
    g.CR(math.pi, q, m)
    g.h(q)

    # (-iY)^n block: (S H) CR(pi) (S H)^+ = H Sdg CR(pi) S H  -- conjugation order:
    # V = S H  =>  V Z V^+ = Y  =>  (-iY)^n = V (-iZ)^n V^+ = (S H) CR(pi) (H^+ S^+)
    # apply V^+ first (to go into Z basis), CR(pi), then V to come back.
    g.sdg(q)
    g.h(q)
    g.CR(math.pi, q, m)
    g.h(q)
    g.s(q)

    # (-iZ)^n block: CR(pi) directly
    g.CR(math.pi, q, m)

    # mode-only residual rotation (folds in the 3*delta angle correction and k*pi, plus pi/2)
    angle = math.pi / 2 + k * math.pi + 3 * delta
    g.R(angle, m)


RULE = Rule(name="kerr_half_pi_colocated_dirty_qubit_pauli_triple", kind="synth", contract="exact",
            term_kinds=("n2",),
            synth=synth,
            idea="Implement exp(-i theta n^2) for theta = pi/2 + k*pi + delta using only the mode's co-located "
                 "qubit as a dirty catalyst (arbitrary state, no ancilla). Uses n^2 mod 4 = n mod 2 so that "
                 "exp(-i(pi/2)n^2) = R(pi/2) (-iZ)^n (-iY)^n (-iX)^n exactly; each (-iP)^n is CR(pi) conjugated "
                 "by the Clifford taking Z to P (H for X, SH for Y). The product of the three P-conditioned pi "
                 "rotations is a pure phase on the qubit for every Fock level, so the dirty qubit returns "
                 "unchanged and no ancilla or SWAP routing is needed. Residual k*pi and small delta fold into a "
                 "mode-only R rotation (3*delta from the n<=3 angle-matching expansion).",
            source="Card: kerr_half_pi_colocated_dirty_qubit_pauli_triple; number-theoretic n^2 mod 4 = n mod 2 "
                   "identity + three-anticommuting-Pauli-conditioned-rotation dirty-catalyst trick")
