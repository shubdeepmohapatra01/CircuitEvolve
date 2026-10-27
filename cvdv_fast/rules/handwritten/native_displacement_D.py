from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

def synth(t, g, r):
    g.D(t.alpha, t.m[0])


RULE = Rule(name="native_displacement_D", kind="synth", contract="exact", term_kinds=("disp",), synth=synth,
            idea="Linear term i(alpha a^+ - alpha* a) is the displacement generator: D(alpha).",
            source="Liu et al. 2407.10381, ISA section (displacement)")
