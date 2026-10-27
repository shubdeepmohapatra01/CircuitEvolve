from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

def synth(t, g, r):
    # multi-qubit exp(-i theta P) via a vacuum bus qumode a (Molmer-Sorensen-type closed phase-space loop):
    #   CD_P(c) = U D(i^w c) U^+, U = prod_j CP(q_j, a);  CD_P(b) D(i g) CD_P(-b) D(-i g) = exp(-2 i b g P)
    #   (displacement commutator is a c-number times P, so BCH terminates: exact; the bus returns to its state)
    if len(t.q) < 2:
        return None
    w = len(t.q)
    a = g.anc_mode()
    b = math.sqrt(abs(t.theta) / 2)
    gg = b if t.theta >= 0 else -b
    iw = 1j ** w
    for q, s in zip(t.q, t.label):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.sdg(q); g.h(q)
    g.D(-1j * gg, a)
    for q in t.q:
        g.CR(-math.pi, q, a)
    g.D(-b * iw, a)
    for q in t.q:
        g.CP(q, a)
    g.D(1j * gg, a)
    for q in t.q:
        g.CR(-math.pi, q, a)
    g.D(b * iw, a)
    for q in t.q:
        g.CP(q, a)
    for q, s in zip(t.q, t.label):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.h(q); g.s(q)


RULE = Rule(name="pauli_string_bus_mode_geometric_phase", kind="synth", contract="exact", term_kinds=("pauli",),
            synth=synth,
            idea="Multi-qubit Pauli exponential through a shared bus oscillator: a P-conditioned displacement and an "
                 "ordinary displacement enclose a phase-space loop; their commutator is a c-number times P, so "
                 "CD_P(b) D(ig) CD_P(-b) D(-ig) = exp(-2i b g P) exactly and the bus returns to its input state. "
                 "CD_P is built from D conjugated by CP on every qubit; X/Y by single-qubit basis change.",
            source="Liu et al. 2407.10381, BCH / displacement-commutator (geometric phase) qubit-qubit entangling via "
                   "a shared mode; also Genesis Rule 15 analogue")
