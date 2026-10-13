"""CV-DV rulebook (self-evolving).

Section 1: Genesis-derived base rules (hand-written analogues of Genesis Table 3, conventions fixed).
Section 2+: rules added by the evolution loop; each carries a `# @provenance` line and a ledger.jsonl record.
Rules are only ever appended; the compiler certifies every use.

Conventions (Genesis Table 2): R(θ)=e^{-iθn}, D(α)=e^{αa†-α*a}, BS(θ,φ)=e^{-iθ/2(e^{iφ}a†b+h.c.)},
CR(θ)=e^{-iθ/2 σz n}, CP=CR(π), CD(α)=e^{σz(αa†-α*a)}.  A rule implements exp(-iH) for its kind.
Time order = call order.
"""


def rule_n__R(t, g, r):
    # H = θ n
    g.R(t.theta, t.m[0])


def rule_hop__BS(t, g, r):
    # H = θ (e^{iφ} a†b + h.c.)
    g.BS(2 * t.theta, t.phi, t.m[0], t.m[1])


def rule_z_n__CR(t, g, r):
    # H = θ Z n
    g.CR(2 * t.theta, t.q[0], t.m[0])


def rule_z_hop__cp_conj(t, g, r):
    # H = θ Z (e^{iφ} a†b + h.c.):  CP† BS(2θ, φ+π/2) CP, CP on mode b
    g.CP(t.q[0], t.m[1])
    g.BS(2 * t.theta, t.phi + m.pi / 2, t.m[0], t.m[1])
    g.CR(-m.pi, t.q[0], t.m[1])


def rule_disp__D(t, g, r):
    g.D(t.alpha, t.m[0])


def rule_pauli__rot(t, g, r):
    # single-qubit H = θ P
    if len(t.q) != 1:
        raise ValueError("single-qubit rule")
    s = t.label
    if s == "Z":
        g.rz(2 * t.theta, t.q[0])
    elif s == "X":
        g.rx(2 * t.theta, t.q[0])
    else:
        g.ry(2 * t.theta, t.q[0])


def rule_pauli__qumode_commutator(t, g, r):
    # multi-qubit H = θ P via a vacuum ancilla qumode a:
    #   CD_P(c) = U D(i^w c) U†,  U = Π_j CP(q_j, a)  (U† = Π CR(-π));
    #   CD_P(b) D(ig) CD_P(-b) D(-ig) = exp(-2i b g P),  b = g = sqrt(|θ|/2)
    w = len(t.q)
    a = g.anc_mode()
    b = m.sqrt(abs(t.theta) / 2)
    gg = b if t.theta >= 0 else -b
    iw = 1j ** w
    for q, s in zip(t.q, t.label):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.sdg(q)
            g.h(q)
    # operator order D(ig)... rightmost first; time order is reversed
    g.D(-1j * gg, a)
    for q in t.q:
        g.CR(-m.pi, q, a)
    g.D(-b * iw, a)
    for q in t.q:
        g.CP(q, a)
    g.D(1j * gg, a)
    for q in t.q:
        g.CR(-m.pi, q, a)
    g.D(b * iw, a)
    for q in t.q:
        g.CP(q, a)
    for q, s in zip(t.q, t.label):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.h(q)
            g.s(q)


def rule_pauli_disp__cd(t, g, r):
    # exp(P (α a† - α* a)) on system mode: U† D(i^w α) U with U = Π CP(q_j, mode)
    w = len(t.q)
    md = t.m[0]
    for q, s in zip(t.q, t.label):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.sdg(q)
            g.h(q)
    if w == 1:
        g.CD(t.alpha, t.q[0], md)
    else:
        for q in t.q:
            g.CR(-m.pi, q, md)
        g.D(t.alpha * 1j ** w, md)
        for q in t.q:
            g.CP(q, md)
    for q, s in zip(t.q, t.label):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.h(q)
            g.s(q)


def rule_n2__group_commutator(t, g, r):
    # H = θ n²  ≈  [e^{A} e^{B} e^{-A} e^{-B}]^r,  A = -i x σx n, B = -i x σy n on ancilla |0>,
    # e^{[A,B]} = e^{-2i x² σz n²},  x = sqrt(|θ| / (2r)).  First-order (Genesis Rule 2 analogue).
    a = g.anc_qubit()
    md = t.m[0]
    x = m.sqrt(abs(t.theta) / (2 * r))
    sx = 1 if t.theta >= 0 else -1
    for _ in range(r):
        # time order: e^{-B}, e^{-A}, e^{B}, e^{A}   (θ<0: swap A and B)
        for which, sign in ((1, -1), (0, -1), (1, 1), (0, 1)):
            if sx < 0:
                which = 1 - which
            if which == 1:
                g.sdg(a)
                g.h(a)
                g.CR(2 * sign * x, a, md)
                g.h(a)
                g.s(a)
            else:
                g.h(a)
                g.CR(2 * sign * x, a, md)
                g.h(a)


# ---------------------------------------------------------------------------------------------
# @provenance: llm | session 2026-10-13 | derived in conversation by the assistant (not by the loop)
# exact on n <= 3 for every θ, and on all n when θ is a multiple of π/4 (Genesis benchmark angles)
def rule_n2__parity_exact(t, g, r):
    # n^2 = -3/2 + 3n + (3/2)(-1)^n - n(-1)^n on n <= 3;  W = exp(-i π/2 σx n) = H CP H,
    # W† Z W = (-1)^n Z on the ancilla, so diagonal phases inside W ... W† become parity-weighted.
    a = g.anc_qubit()
    md = t.m[0]
    th = t.theta
    g.R(3 * th, md)
    g.h(a)
    g.CP(a, md)
    g.h(a)
    g.rz(3 * th, a)
    g.CR(-2 * th, a, md)
    g.h(a)
    g.CR(-m.pi, a, md)
    g.h(a)
