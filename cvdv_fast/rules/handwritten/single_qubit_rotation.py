from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

def synth(t, g, r):
    if len(t.q) != 1:
        return None
    s = t.label
    {"Z": g.rz, "X": g.rx, "Y": g.ry}[s](2 * t.theta, t.q[0])


RULE = Rule(name="single_qubit_rotation", kind="synth", contract="exact", term_kinds=("pauli",), synth=synth,
            idea="Single-qubit Pauli exponential exp(-i theta P) = r_P(2 theta).",
            source="Liu et al. 2407.10381, qubit rotations are part of every hybrid ISA")
