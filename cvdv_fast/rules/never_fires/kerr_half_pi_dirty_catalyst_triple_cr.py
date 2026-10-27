"""kerr_half_pi_dirty_catalyst_triple_cr

exp(-i theta n^2) at theta = +-pi/2 (mod 2 pi) via a dirty-qubit catalyst and three
Pauli-basis CR(pi) gates, no ancilla routing required.

Mechanism (exact block-scalar identity in the qubit (x) Fock decomposition):

  CR_P(pi) := exp(-i (pi/2) P n) for a qubit Pauli P (CR_Z(pi) is the native CR(pi)
  gate; CR_X(pi) = H.CR(pi).H; CR_Y(pi) = S.H.CR(pi).H.Sdg using Y = S X Sdg).

  On the photon-number block n, CR_P(pi) acts on the qubit as (-iP)^n. The operator
  product W = CR_Z(pi).CR_X(pi).CR_Y(pi) (rightmost acts first) therefore acts on
  block n as (-iZ)^n (-iX)^n (-iY)^n = s(n) * I_qubit with s(n) = (-1)^{n(n+1)/2}
  (period-4 pattern +1,-1,-1,+1,...), exactly, for every n (no Fock cutoff needed):
  W is the identity on the qubit factor for ANY qubit state.

  Multiplying by R(-pi/2) = exp(+i pi n / 2) contributes i^n, and s(n) * i^n =
  exp(-i pi n^2 / 2) exactly (because n^2 mod 4 = n mod 2). Hence

      exp(-i (pi/2) n^2) = R(-pi/2) . W   exactly, no global phase,

  and the qubit used to build W returns to its input state untouched -- it can be
  the ordinary "site" qubit already co-located with this mode rather than a fresh
  ancilla, so no ancilla routing / qumode SWAPs are required. The mirrored case
  theta = -pi/2 (== 3pi/2 mod 2pi) is the Hermitian conjugate of the whole circuit:
  reverse the gate order, flip CR(pi) -> CR(-pi), swap s <-> sdg, and use R(+pi/2)
  instead of R(-pi/2).

  Order matters: the operator product must be Z.X.Y (Y applied first in time,
  then X, then Z) -- the reversed order Y.X.Z gives a different sign pattern.

Source: Liu et al. 2407.10381 (CR/displacement identities on bosonic modes);
block-diagonal centre-of-SU(2) argument per photon-number sector; dirty-qubit
catalyst construction (Genesis-style "catalysis" ancilla reuse).
"""

from cvdv_fast.api import Rule
import math

_TWO_PI = 2 * math.pi
_TOL = 1e-9


def synth(t, g, r):
    if t.kind != "n2":
        return None
    if len(t.m) != 1:
        return None

    m = t.m[0]
    # The term itself carries no qubit (n2 is purely bosonic); borrow the qubit
    # already co-located with this mode (same site index) as a dirty catalyst.
    # If a qubit happens to be attached to this TermView anyway, reuse that one.
    q = t.q[0] if t.q else m

    theta = t.theta % _TWO_PI

    is_plus = abs(theta - math.pi / 2) < _TOL
    is_minus = abs(theta - 3 * math.pi / 2) < _TOL
    if not (is_plus or is_minus):
        return None

    if is_plus:
        # exp(-i (pi/2) n^2) = R(-pi/2) . CR_Z(pi) . CR_X(pi) . CR_Y(pi)
        # time order (first emitted acts first): Y, then X, then Z, then R.
        g.sdg(q)
        g.h(q)
        g.CR(math.pi, q, m)
        g.h(q)
        g.s(q)
        g.h(q)
        g.CR(math.pi, q, m)
        g.h(q)
        g.CR(math.pi, q, m)
        g.R(-math.pi / 2, m)
    else:
        # Hermitian conjugate of the above: reversed order, CR(-pi), s<->sdg, R(+pi/2).
        g.R(math.pi / 2, m)
        g.CR(-math.pi, q, m)
        g.h(q)
        g.CR(-math.pi, q, m)
        g.h(q)
        g.sdg(q)
        g.h(q)
        g.CR(-math.pi, q, m)
        g.h(q)
        g.s(q)


RULE = Rule(
    name="kerr_half_pi_dirty_catalyst_triple_cr",
    kind="synth",
    contract="exact",
    term_kinds=("n2",),
    synth=synth,
    idea=(
        "Target exp(-i theta n^2) at theta == pi/2 (mod 2pi), or its mirror -pi/2. "
        "On each photon-number block n, the product W = CR_Z(pi).CR_X(pi).CR_Y(pi) "
        "of three qubit-controlled rotations acts on the qubit as (-iZ)^n(-iX)^n(-iY)^n "
        "= s(n)*I (period-4 sign pattern), exactly, for every n: W is the identity on the "
        "qubit for any qubit state, so no clean ancilla is needed -- the site qubit already "
        "co-located with the mode can be used as a dirty catalyst and returns unchanged. "
        "Multiplying by R(-pi/2) turns s(n) into exp(-i pi n^2/2) exactly, since n^2 mod 4 "
        "= n mod 2. CR_X/CR_Y are CR(pi) conjugated by H / S.H respectively. Y must be "
        "applied first in time, then X, then Z (order of the operator product matters). "
        "The mirrored theta = -pi/2 case is the Hermitian conjugate circuit: reverse the "
        "gate order, CR(pi) -> CR(-pi), swap s/sdg, and R(-pi/2) -> R(+pi/2)."
    ),
    source=(
        "Liu et al. 2407.10381 (CR / displacement identities on bosonic modes); exact "
        "block-scalar (centre of SU(2) per Fock block) argument; dirty-qubit catalyst reuse "
        "of a co-located site qubit in place of a routed clean ancilla."
    ),
    meta={
        "mechanism": "exact block-scalar identity in the qubit (x) Fock decomposition "
                     "(centre of SU(2) per photon-number block); dirty-qubit catalyst",
        "target_parts": "n2 (self-Kerr) terms at theta == +-pi/2 mod 2pi, e.g. "
                         "z2Higgs_small terms 3-6 (qm0..qm3).",
    },
)
