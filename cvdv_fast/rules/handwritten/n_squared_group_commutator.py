from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

def synth(t, g, r):
    # theta n^2 ~ [e^{A} e^{B} e^{-A} e^{-B}]^r with A = -i x X n, B = -i x Y n on an ancilla qubit |0>;
    # e^{[A,B]} = e^{-2 i x^2 Z n^2}, x = sqrt(|theta| / (2 r)). First order (error ~ (x n)^3).
    a = g.anc_qubit()
    md = t.m[0]
    x = math.sqrt(abs(t.theta) / (2 * r))
    sx = 1 if t.theta >= 0 else -1
    for _ in range(r):
        for which, sign in ((1, -1), (0, -1), (1, 1), (0, 1)):
            if sx < 0:
                which = 1 - which
            if which == 1:
                g.sdg(a); g.h(a); g.CR(2 * sign * x, a, md); g.h(a); g.s(a)
            else:
                g.h(a); g.CR(2 * sign * x, a, md); g.h(a)


RULE = Rule(name="n_squared_group_commutator", kind="synth", contract="approx", term_kinds=("n2",), synth=synth,
            idea="Self-Kerr n^2 from the BCH group commutator of two dispersive generators X n and Y n on an "
                 "ancilla qubit: [X n, Y n] = 2i Z n^2. First-order product formula, repeated r times.",
            source="Liu et al. 2407.10381, BCH / group-commutator synthesis of nonlinear generators; Genesis Rule 2")
