from cvdv_fast.api import Rule, Op, math

TOL = 1e-6


def _k_from_theta(theta):
    # theta = pi/2 + k*pi + delta, |delta| small; solve for integer k.
    k_float = (theta - math.pi / 2) / math.pi
    k = round(k_float)
    delta = theta - (math.pi / 2 + k * math.pi)
    return k, delta


def trigger(ops):
    out = []
    n = len(ops)
    for i in range(n):
        o0 = ops[i]
        if o0.name != "h" or len(o0.wires) != 1:
            continue
        a = o0.wires[0]
        if a[0] != "q":
            continue
        # ops[i+1] must be CR(pi) on (a, m)
        if i + 1 >= n:
            continue
        o1 = ops[i + 1]
        if o1.name != "CR" or len(o1.wires) != 2:
            continue
        if o1.wires[0] != a:
            continue
        if abs(complex(o1.params[0]) - math.pi) > 1e-9:
            continue
        m = o1.wires[1]
        if m[0] != "qm":
            continue
        # ops[i+2] must be rx(phi) on a
        if i + 2 >= n:
            continue
        o2 = ops[i + 2]
        if o2.name != "rx" or len(o2.wires) != 1 or o2.wires[0] != a:
            continue
        phi = complex(o2.params[0]).real
        # ops[i+3] must be CR(-pi) on (a, m)
        if i + 3 >= n:
            continue
        o3 = ops[i + 3]
        if o3.name != "CR" or len(o3.wires) != 2:
            continue
        if o3.wires[0] != a or o3.wires[1] != m:
            continue
        if abs(complex(o3.params[0]) + math.pi) > 1e-9:
            continue
        # ops[i+4] must be h on a
        if i + 4 >= n:
            continue
        o4 = ops[i + 4]
        if o4.name != "h" or len(o4.wires) != 1 or o4.wires[0] != a:
            continue

        j_end = i + 4  # index of last confirmed op (the closing h)
        trailing_R_idx = None

        # optional trailing R(k*pi)(m) immediately after, with nothing else touching a or m in between
        if j_end + 1 < n:
            o5 = ops[j_end + 1]
            if o5.name == "R" and len(o5.wires) == 1 and o5.wires[0] == m:
                trailing_R_idx = j_end + 1

        block_end = trailing_R_idx if trailing_R_idx is not None else j_end

        # no other gate acts on `a` or `m` strictly inside (i, block_end) besides the ones identified
        # (the pattern is contiguous i..j_end, so only need to check nothing extra sits between j_end and
        #  trailing_R_idx if any)
        if trailing_R_idx is not None:
            # nothing between j_end+1 exclusive and trailing_R_idx exclusive since they're adjacent; fine.
            pass

        # recover theta: block implements exp(-i theta n_m^2) overall (including any trailing R(k pi))
        # From the 5-op block alone, the design in the source rule encodes some base phase pi/2 plus
        # phi contributing to k via rx angle; but per the card, the combined effective theta is such
        # that theta = pi/2 + k*pi + delta. We extract k and delta directly from phi and R parameter.
        # The 5-op block's "theta" relates to phi by convention of kerr_half_pi_parity_kickback rule:
        # we don't have direct access to theta here, so reconstruct from phi (angle-tolerant family)
        # and the trailing R parameter (k*pi contribution already applied).
        # Here phi plays the role encoding theta's fractional structure; per the originating rule the
        # 5-op block alone realizes exp(-i (pi/2) n^2) up to residual delta encoded in phi's deviation
        # from pi (since rx(phi) with phi ~ pi is what realizes the pi/2*n^2 Kerr kickback).
        delta_phi = phi - math.pi
        if abs(delta_phi) > 1e-4:
            # not the angle-tolerant pi kickback we recognize; decline this match
            continue

        k = 0
        r_param = None
        if trailing_R_idx is not None:
            r_param = complex(ops[trailing_R_idx].params[0]).real
            k_float = r_param / math.pi
            k = round(k_float)
            # residual beyond k*pi folded into theta delta together with delta_phi/2 (kickback factor)
            r_delta = r_param - k * math.pi
        else:
            r_delta = 0.0

        # total delta estimate (half of rx deviation contributes to n^2 coefficient by construction)
        delta = delta_phi / 2.0 + r_delta
        if abs(delta) > 1e-6:
            continue

        out.append((i, block_end, a, m, k))
    return out


def apply(ops, match):
    i, block_end, a, m, k = match
    new = []
    new.append(Op("sdg", (), (a,)))
    new.append(Op("h", (), (a,)))
    new.append(Op("CR", (math.pi,), (a, m)))
    new.append(Op("h", (), (a,)))
    new.append(Op("s", (), (a,)))
    new.append(Op("h", (), (a,)))
    new.append(Op("CR", (math.pi,), (a, m)))
    new.append(Op("h", (), (a,)))
    new.append(Op("CR", (math.pi,), (a, m)))
    angle = 3 * math.pi / 2 + k * math.pi
    new.append(Op("R", (angle,), (m,)))
    return i, block_end, new


RULE = Rule(
    name="kerr_half_pi_colocate_by_dirty_pauli_triple_rewrite",
    kind="rewrite",
    contract="exact",
    stage="logical",
    trigger=trigger,
    apply=apply,
    idea="Replace an ancilla-mediated half-pi Kerr block H(a) CR(pi)(a,m) rx(phi~pi)(a) CR(-pi)(a,m) H(a) "
         "[R(k pi)(m)], where the ancilla a is a dirty co-located qubit of m (any state, untouched elsewhere in "
         "the window), by a 3-CR dirty-qubit construction: since CR(pi)=(-iZ)^n, A=-iZ,B=-iX,C=-iY satisfy "
         "A^n B^n C^n = s(n) a qubit scalar with s(n) period 4, and e^{-i(pi/2)n^2} = R(3pi/2) A^n B^n C^n exactly "
         "(verified n mod 4 = 0..3). B^n = H CR(pi) H, C^n = S H CR(pi) H Sdg (time order: C^n acts first), giving "
         "sdg,h,CR(pi),h,s,h,CR(pi),h,CR(pi),R(3pi/2+k pi) with the qubit returned to its input state untouched up "
         "to the enclosing scalar. All CR gates act on the natively coupled (q_m, m) pair, so routing inserts no "
         "SWAPs, trading 2 two-op gates for 3 but removing most ancilla-relocation SWAP overhead. Residual phase "
         "error from the angle-tolerant kickback's delta stays within the 1e-6 exact-contract tolerance, matching "
         "the admitted parity-kickback rule's own handling of the same delta. Kept only when the routed cost "
         "(duration, then 2-op count) decreases versus leaving the original clean-ancilla block in place.",
    source="Liu et al. 2407.10381-style Pauli-power/CR number-theoretic identity (A^n B^n C^n period-4 scalar); "
           "routing-aware ancilla-relocation rewrite for z2Higgs_small benchmark",
    meta={"target_parts": "z2Higgs_small terms 3,4,5 (Kerr on modes 0,1,2 with dirty co-located q0,q1,q2); "
                           "term 6 (mode 3) keeps clean local parity rule since ancilla already co-located"},
)
