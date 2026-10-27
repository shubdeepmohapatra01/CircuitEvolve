from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

def synth(t, g, r):
    g.R(t.theta, t.m[0])          # exp(-i theta n) = R(theta)


RULE = Rule(name="native_number_R", kind="synth", contract="exact", term_kinds=("n",), synth=synth,
            idea="theta n is the generator of the native phase-space rotation R(theta) = exp(-i theta n).",
            source="Liu et al. 2407.10381, ISA section (oscillator rotation is native in every CV ISA)")
