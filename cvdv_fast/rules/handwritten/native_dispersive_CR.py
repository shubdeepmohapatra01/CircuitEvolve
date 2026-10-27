from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

def synth(t, g, r):
    g.CR(2 * t.theta, t.q[0], t.m[0])          # exp(-i theta Z n) = CR(2 theta)


RULE = Rule(name="native_dispersive_CR", kind="synth", contract="exact", term_kinds=("z_n",), synth=synth,
            idea="Z n is the dispersive (conditional-rotation) generator: exp(-i theta Z n) = CR(2 theta).",
            source="Liu et al. 2407.10381, hybrid instructions: dispersive conditional rotation")
