from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath


def synth(t, g, r):
    # exp(-i theta n^2) at theta = pi/2 mod pi: n^2 mod 4 depends only on parity of n, so this is exact on the
    # whole Fock space (not a truncation): exp(-i(pi/2) n^2) = e^{-i pi/4} * exp(+i(pi/4) p), p = (-1)^n.
    # General theta = pi/2 + k*pi: exp(-i theta n^2) = R(k*pi) * exp(-i(pi/2) n^2), since (-1)^{k n^2} = (-1)^{k n}.
    if len(t.m) != 1 or len(t.q) != 0:
        return None
    k = (t.theta - math.pi / 2) / math.pi
    kr = round(k)
    if abs(k - kr) > 1e-9:
        return None

    m = t.m[0]
    if kr != 0:
        g.R(kr * math.pi, m)

    a = g.anc_qubit()
    g.h(a)
    g.CR(math.pi, a, m)
    g.rx(-math.pi / 2, a)
    g.CR(-math.pi, a, m)
    g.h(a)


RULE = Rule(name="kerr_half_pi_parity_phase_kickback_5op", kind="synth", contract="exact", term_kinds=("n2",),
            synth=synth,
            idea="For every integer n, n^2 mod 4 depends only on parity, so exp(-i(pi/2) n^2) = e^{-i pi/4} "
                 "exp(+i(pi/4) p) with p=(-1)^n, exactly on the whole Fock space. A clean ancilla picks up the "
                 "parity via CR(pi) (phase kickback to |+>/|->), an rx diagonal in that basis applies the parity "
                 "phase, and CR(-pi) cancels the residual mode phase and returns the ancilla to |0>. General theta "
                 "= pi/2 + k*pi factors as R(k*pi) times this operator since (-1)^{k n^2} = (-1)^{k n}.",
            source="Number-theoretic parity identity for n^2 mod 4 + standard phase-kickback construction "
                   "(cf. Liu et al. 2407.10381 CR-based qubit-mode kickback)")
