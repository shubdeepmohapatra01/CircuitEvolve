from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

def synth(t, g, r):
    if len(t.q) != 1 or t.label != "X":
        return None
    g.RB(1j * t.alpha, t.q[0], t.m[0])


RULE = Rule(name="native_rabi_RB", kind="synth", contract="exact", term_kinds=("pauli_disp",), synth=synth,
            idea="X (alpha a^+ - alpha* a) is the Rabi-interaction generator: RB(i alpha).",
            source="Liu et al. 2407.10381, hybrid instructions: Rabi interaction")
