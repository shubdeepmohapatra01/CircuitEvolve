from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

TOL = 1e-6


def _is_n_func(op):
    # a gate that is purely a function of photon number on a single qumode wire
    return op.name in ("R", "CD") and len(op.wires) == 1 and op.wires[0][0] == "qm"


def _is_full_swap_z_hop(op):
    # z_hop synthesized directly as CBS, or still-IR style: look for CBS with theta == +-pi/2 (full swap, Z-cond)
    if op.name != "CBS":
        return False
    if len(op.wires) != 3:
        return False
    theta = op.params[0]
    return abs(abs(theta) - math.pi / 2) <= 1e-5


def _qm_wire(op):
    for w in op.wires:
        if w[0] == "qm":
            return w
    return None


def trigger(ops):
    out = []
    for i, o in enumerate(ops):
        if not _is_n_func(o):
            continue
        m = o.wires[0]
        j = i + 1
        # find next op touching m (must be the CBS swap, nothing else in between on m)
        k = None
        blocked = False
        for idx in range(i + 1, len(ops)):
            if m in ops[idx].wires:
                k = idx
                break
        if k is None:
            continue
        if not _is_full_swap_z_hop(ops[k]):
            continue
        # identify which of the two qumode legs of the CBS is m, and the other leg
        qm_legs = [w for w in ops[k].wires if w[0] == "qm"]
        if m not in qm_legs or len(qm_legs) != 2:
            continue
        other = qm_legs[0] if qm_legs[1] == m else qm_legs[1]
        out.append((i, k, m, other))

        # also look backward: n-func right AFTER a full-swap hop -> can move before it on the other mode
    for i, o in enumerate(ops):
        if not _is_full_swap_z_hop(o):
            continue
        qm_legs = [w for w in o.wires if w[0] == "qm"]
        if len(qm_legs) != 2:
            continue
        # next op touching either leg
        for leg in qm_legs:
            k = None
            for idx in range(i + 1, len(ops)):
                if leg in ops[idx].wires:
                    k = idx
                    break
            if k is not None and _is_n_func(ops[k]) and ops[k].wires[0] == leg:
                other = qm_legs[0] if qm_legs[1] == leg else qm_legs[1]
                out.append((i, k, leg, other, "post"))
    return out


def apply(ops, m):
    if len(m) == 4:
        i, k, mode, other = m
        kerr_op = ops[i]
        hop_op = ops[k]
        new_kerr = Op(kerr_op.name, kerr_op.params, (other,))
        # relabel to other mode, move it to just after the hop
        new_seq = list(ops[i + 1:k]) + [hop_op, new_kerr]
        return i, k, new_seq
    else:
        i, k, leg, other, _tag = m
        hop_op = ops[i]
        kerr_op = ops[k]
        new_kerr = Op(kerr_op.name, kerr_op.params, (other,))
        new_seq = [new_kerr, hop_op] + list(ops[i + 1:k])
        return i, k, new_seq


RULE = Rule(
    name="kerr_relocate_through_full_swap_hop",
    kind="rewrite",
    contract="exact",
    stage="both",
    trigger=trigger,
    apply=apply,
    idea="A pi/2 conditional (Z-controlled) hop CBS(+-pi/2, phi) implements a full mode swap in each qubit branch: "
         "U = exp(i (pi/2) Z (e^{i phi} a^+ b + h.c.)) gives U a U^+ = -i Z e^{-i phi} b, U b U^+ = -i Z e^{i phi} a, "
         "so U n_a U^+ = n_b and U n_b U^+ = n_a exactly (Z^2 = 1, Z commutes with the modes). Hence for any function "
         "of photon number, f(n_a) immediately before the swap equals f(n_b) immediately after it, and vice versa: "
         "[f(n_a), then U] = [U, then f(n_b)]. R(theta) and CD(a) (both diagonal in / functions of photon number on "
         "one mode) sitting adjacent to a full-swap z_hop can therefore be relabelled to the other leg and slid to "
         "the opposite side of the hop, with any intervening ops on unrelated wires simply kept in place. This is an "
         "exact reordering of the IR/physical product, used to relocate Kerr-type terms to whichever mode ends up "
         "local to a cheap ancilla qubit, cutting routed SWAPs without changing the logical circuit.",
    source="Derived from the Heisenberg-picture mode-swap identity for a pi/2 conditional beamsplitter/hop "
           "(cf. Liu et al. 2407.10381 CV gate algebra); z2Higgs_small photon-content-flow analysis"
)
