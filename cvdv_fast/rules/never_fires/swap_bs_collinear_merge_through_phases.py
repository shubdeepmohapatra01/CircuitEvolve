from cvdv_fast.api import Rule, Op
import math

TWO_PI = 2 * math.pi
FOUR_PI = 4 * math.pi
PI = math.pi
EPS = 1e-9


def _is_bs(op):
    return op.name == "BS"


def _is_r(op):
    return op.name == "R"


def _mod(x, m):
    y = x % m
    if y < 0:
        y += m
    return y


def _close(a, b, tol=1e-9, mod=None):
    if mod is None:
        return abs(a - b) < tol
    d = _mod(a - b, mod)
    return d < tol or (mod - d) < tol


def _find_window(ops, i0):
    """Starting at index i0 (a BS or R on some pair), find the maximal contiguous
    run of ops touching exactly the set of wires {x,y} where x,y are determined by
    the first BS found going forward from i0, with no other gate touching x or y
    outside the run besides BS/R gates on those wires."""
    o0 = ops[i0]
    if o0.name not in ("BS", "R"):
        return None
    if o0.name == "BS":
        xy = tuple(o0.wires)
    else:
        # R is single-wire; need to look ahead to find a BS to fix the pair,
        # otherwise this lone R isn't part of a two-mode window we care about here.
        xy = None

    # scan forward from i0 to find window end, collecting wire set
    wires_seen = set(o0.wires)
    j = i0
    n = len(ops)
    last = i0
    while j + 1 < n:
        nxt = ops[j + 1]
        wnxt = set(nxt.wires)
        if not (wnxt & wires_seen):
            # check if any later op interacts; if not touching current wires, stop scanning only
            # if nothing further ever touches our wires contiguously -- but intervening unrelated
            # ops break contiguity, so stop window here.
            break
        if nxt.name not in ("BS", "R"):
            break
        if xy is None:
            if nxt.name == "BS":
                xy = tuple(nxt.wires)
                wires_seen |= wnxt
            else:
                wires_seen |= wnxt
        else:
            if not wnxt.issubset(set(xy)):
                break
            wires_seen |= wnxt
        j += 1
        last = j

    if xy is None:
        return None
    x, y = xy
    # re-scan strictly within [i0, last] ensuring every op only touches {x,y}
    for k in range(i0, last + 1):
        if not set(ops[k].wires).issubset({x, y}):
            return None
        if ops[k].name not in ("BS", "R"):
            return None
    if last == i0:
        return None
    return i0, last, x, y


def trigger(ops):
    out = []
    n = len(ops)
    used_until = -1
    i = 0
    while i < n:
        o = ops[i]
        if o.name in ("BS", "R") and i > used_until:
            win = _find_window(ops, i)
            if win is not None:
                i0, i1, x, y = win
                # require at least 2 ops and at least one BS present
                seg = ops[i0:i1 + 1]
                if any(op.name == "BS" for op in seg):
                    out.append((i0, i1, x, y))
                    used_until = i1
        i += 1
    return out


def _bs_canon(t, p):
    # BS_xy(t, p+pi) = BS_xy(-t, p); canonicalise p into [0, pi)
    p = _mod(p, TWO_PI)
    if p >= PI:
        p -= PI
        t = -t
    return t, p


def apply(ops, m):
    i0, i1, x, y = m
    seg = list(ops[i0:i1 + 1])

    # Represent state: list of BS "slots" each (t, p) in canonical wire order (x,y),
    # plus trailing phase angles accumulated per wire (phi_x, phi_y), built by pushing
    # R gates through BS gates left-to-right (I1), and merging collinear BS (I3).
    bs_list = []  # list of [t, p] canonical, in temporal order after pushes
    phi_x = 0.0
    phi_y = 0.0

    for op in seg:
        if op.name == "R":
            (phi,) = op.params
            w = op.wires[0]
            if w == x:
                # R_x(phi) BS_xy(t,p) = BS_xy(t, p - phi) R_x(phi)
                # Pushing R_x(phi) to the right across all existing BS gates already
                # placed (they occur before this R in time since we process in order):
                # actually R occurs now, in time order after previously accumulated BS.
                # We push it further right (later in time) across subsequent BS gates,
                # so we just accumulate it as a pending phase that modifies future BS
                # params when they are appended, and also commutes trivially with past BS
                # (already fixed). So: add to running phi_x, and whenever a BS is appended
                # later, its p is shifted by -phi_x (if touches x) handled at append time.
                phi_x += phi
            elif w == y:
                phi_y += phi
            else:
                # shouldn't happen given window construction
                return i0, i1, seg
        elif op.name == "BS":
            t, p = op.params
            wx, wy = op.wires
            if (wx, wy) == (x, y):
                pass
            elif (wx, wy) == (y, x):
                # BS_yx(t,p) = BS_xy(t,-p)
                p = -p
            else:
                return i0, i1, seg
            # apply pending phase pushes: R_x(phi_x) BS(t,p) = BS(t, p - phi_x) R_x(phi_x)
            # R_y(phi_y) BS(t,p) = BS(t, p + phi_y) R_y(phi_y)
            # Since phi_x, phi_y are accumulated R's sitting just before this BS in time,
            # pushing them through to land after this BS (so they keep moving right):
            p_eff = p - phi_x + phi_y
            t_c, p_c = _bs_canon(t, p_eff)
            if bs_list and _close(bs_list[-1][1], p_c, tol=1e-9, mod=PI):
                # merge collinear (I3); use p_c for consistency, angles add
                bs_list[-1][0] += t_c
            else:
                bs_list.append([t_c, p_c])
        else:
            return i0, i1, seg

    # Apply periodicity reduction (I4) to each BS angle, done after full merge pass too
    # but we merge progressively; do a final merge pass since different p_c within
    # same slot list could still now be close after mod pi reduction already applied.
    merged = []
    for t_c, p_c in bs_list:
        t_r = _mod(t_c + 2 * PI, FOUR_PI) - 2 * PI  # into (-2pi, 2pi]
        if merged and _close(merged[-1][1], p_c, tol=1e-9, mod=PI):
            merged[-1][0] += t_r
        else:
            merged.append([t_r, p_c])

    new_ops = []
    extra_phi_x = 0.0
    extra_phi_y = 0.0

    for t_c, p_c in merged:
        t_r = _mod(t_c + 2 * PI, FOUR_PI) - 2 * PI
        if _close(abs(t_r), 0.0, tol=1e-9):
            continue
        if _close(abs(t_r), TWO_PI, tol=1e-9):
            # BS(2pi,p) = R_x(pi) R_y(pi)
            extra_phi_x += PI
            extra_phi_y += PI
            continue
        new_ops.append(Op("BS", (t_r, p_c), (x, y)))

    phi_x_total = _mod(phi_x + extra_phi_x, TWO_PI)
    phi_y_total = _mod(phi_y + extra_phi_y, TWO_PI)

    if phi_x_total > EPS and not _close(phi_x_total, TWO_PI, tol=1e-9):
        new_ops.append(Op("R", (phi_x_total,), (x,)))
    if phi_y_total > EPS and not _close(phi_y_total, TWO_PI, tol=1e-9):
        new_ops.append(Op("R", (phi_y_total,), (y,)))

    # count 2-op gates before/after
    old_two_op = sum(1 for op in seg if len(op.wires) == 2)
    new_two_op = sum(1 for op in new_ops if len(op.wires) == 2)
    if new_two_op >= old_two_op:
        return i0, i1, seg

    return i0, i1, new_ops


RULE = Rule(
    name="swap_bs_collinear_merge_through_phases",
    kind="rewrite",
    contract="exact",
    stage="physical",
    trigger=trigger,
    apply=apply,
    idea="Two-mode window rewrite on a coupled qumode pair (x,y): pushes single-wire R "
         "(phase-rotation) gates through BS beamsplitter gates using the exact conjugation "
         "identity R_x(phi) a_x^+ R_x(phi)^+ = e^{-i phi} a_x^+, which shifts the BS phase "
         "parameter p by -/+ phi; canonicalises wire order and p into [0,pi) via "
         "BS_yx(t,p)=BS_xy(t,-p) and BS_xy(t,p+pi)=BS_xy(-t,p); merges collinear BS gates "
         "sharing the same generator phase (I3); and reduces the BS angle mod 4pi using the "
         "integer-spectrum periodicity of the Schwinger generator G, replacing a 2pi BS by "
         "R(pi) on both wires. This cancels router SWAPs against adjacent hops/SWAPs on the "
         "same physical pair (e.g. SWAP_xy BS_xy(-pi,0) = R_x(-pi/2) R_y(-pi/2)), trading "
         "2-op gates for cheaper 1-op R gates while leaving the routed wire layout untouched. "
         "Only applied when the rewrite strictly reduces the 2-op gate count.",
    source="Liu et al. 2407.10381 passive beamsplitter / phase-space SU(2) subgroup "
           "identities; router SWAP decomposition SWAP_xy = R_x(-pi/2) R_y(-pi/2) BS_xy(pi,0)",
)
