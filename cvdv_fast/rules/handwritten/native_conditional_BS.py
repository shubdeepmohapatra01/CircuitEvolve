from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

def synth(t, g, r):
    g.CBS(2 * t.theta, t.phi, t.q[0], t.m[0], t.m[1])


RULE = Rule(name="native_conditional_BS", kind="synth", contract="exact", term_kinds=("z_hop",), synth=synth,
            idea="Z (a^+b + h.c.) is the conditional beam-splitter generator: exp(-i theta Z(...)) = CBS(2 theta, phi).",
            source="Liu et al. 2407.10381, hybrid instructions: conditional beam splitter")
