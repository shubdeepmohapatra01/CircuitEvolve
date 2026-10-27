from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

def synth(t, g, r):
    # exp(P (alpha a^+ - alpha* a)) on system mode: single qubit -> CD; multi-qubit -> U^+ D(i^w alpha) U
    w = len(t.q)
    md = t.m[0]
    for q, s in zip(t.q, t.label):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.sdg(q); g.h(q)
    if w == 1:
        g.CD(t.alpha, t.q[0], md)
    else:
        for q in t.q:
            g.CR(-math.pi, q, md)
        g.D(t.alpha * 1j ** w, md)
        for q in t.q:
            g.CP(q, md)
    for q, s in zip(t.q, t.label):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.h(q); g.s(q)


RULE = Rule(name="pauli_conditional_displacement", kind="synth", contract="exact", term_kinds=("pauli_disp",),
            synth=synth,
            idea="Qubit-conditioned displacement: Z (alpha a^+ - alpha* a) is the native CD generator. For a Pauli "
                 "string, conjugate an ordinary D by CP on every qubit (each CP rotates the mode by +-pi/2 "
                 "conditionally), giving D's direction a factor prod Z_j; X/Y via single-qubit basis change.",
            source="Liu et al. 2407.10381, phase-space ISA: conditional displacement + conjugation by CP")
