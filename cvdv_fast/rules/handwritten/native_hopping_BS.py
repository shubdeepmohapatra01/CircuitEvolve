from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

def synth(t, g, r):
    g.BS(2 * t.theta, t.phi, t.m[0], t.m[1])   # exp(-i theta (e^{i phi} a^+ b + h.c.))


RULE = Rule(name="native_hopping_BS", kind="synth", contract="exact", term_kinds=("hop",), synth=synth,
            idea="Bilinear hopping a^+b + h.c. is the beam-splitter generator: exp(-i theta(...)) = BS(2 theta, phi).",
            source="Liu et al. 2407.10381, Gaussian/beam-splitter instructions for multimode control")
