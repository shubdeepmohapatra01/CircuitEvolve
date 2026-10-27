from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

def synth(t, g, r):
    # CP on mode b maps b -> i Z b (up to the frame), so CP . BS(2 theta, phi + pi/2) . CP^+ = CBS-like
    g.CP(t.q[0], t.m[1])
    g.BS(2 * t.theta, t.phi + math.pi / 2, t.m[0], t.m[1])
    g.CR(-math.pi, t.q[0], t.m[1])


RULE = Rule(name="conditional_BS_by_parity_conjugation", kind="synth", contract="exact", term_kinds=("z_hop",),
            synth=synth,
            idea="Conjugating a beam splitter by a qubit-controlled pi rotation (CP) on one mode makes its phase "
                 "qubit-dependent: CP^+ BS(2theta, phi+pi/2) CP = exp(-i theta Z (e^{i phi} a^+ b + h.c.)). "
                 "Uses only the phase-space ISA (no CBS).",
            source="Liu et al. 2407.10381, conjugation / phase-space ISA compilation identities")
