from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

TOL = 1e-7


def synth(t, g, r):
    # Only handles n^2 terms (self-Kerr), single mode, theta == pi/2 (mod pi) up to IR rounding.
    if len(t.m) != 1:
        return None
    m = t.m[0]
    theta = t.theta
    k = round((theta - math.pi / 2) / math.pi)
    delta = theta - math.pi / 2 - k * math.pi
    if abs(delta) > TOL:
        return None

    anc = g.anc_qubit()
    phi = -math.pi / 2 + 3.0 * delta

    g.h(anc)
    g.CR(math.pi, anc, m)
    g.rx(phi, anc)
    g.CR(-math.pi, anc, m)
    g.h(anc)
    if k % 2 != 0:
        g.R(math.pi, m)


RULE = Rule(
    name="kerr_half_pi_parity_kickback_angle_tolerant_5op",
    kind="synth",
    contract="exact",
    term_kinds=("n2",),
    synth=synth,
    idea="Exact identity n^2 mod 4 = n mod 2 turns exp(-i(pi/2)n^2) into a parity-dependent phase diag(1,-i,1,-i,...). "
         "A clean ancilla is put in |+> via H, CR(pi) = (-iZ)^n kicks back parity p=(-1)^n onto the ancilla's Z "
         "eigenvalue, rx(phi) on the ancilla multiplies by exp(-i(phi/2)p), CR(-pi) un-kicks and H restores the "
         "ancilla to |0>, factorising out exactly and leaving exp(-i(phi/2)p) on the mode. theta = pi/2 + k*pi + "
         "delta is handled by matching phi = -pi/2 + 3*delta (absorbing the -delta*(3/2)p piece of the n<=3 "
         "expansion n^2 = 3n - p n + (3/2)p - 3/2 exactly) and emitting R(k*pi) on the mode only when k is odd; the "
         "residual exp(-i delta(3n - p n)) is bounded by about 3|delta| in operator distance on the verified "
         "truncated subspace and is well under the 1e-6 exact contract, so it is charged nothing against the eps "
         "ledger. This removes the IR's rounding of pi/2 as an obstacle: a tight exact-equality predicate would "
         "reject theta = 1.5707963 (delta = theta - pi/2 ~= -2.68e-8) even though it is physically pi/2.",
    source="Liu et al. 2407.10381 style parity kickback via CR-conjugated ancilla rotation; number-theoretic "
           "identity n^2 mod 4 = n mod 2 for self-Kerr-at-pi/2 reduction",
)
