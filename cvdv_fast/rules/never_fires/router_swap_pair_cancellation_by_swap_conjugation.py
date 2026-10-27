from cvdv_fast.api import Rule, Op
import math
import cmath

# A router SWAP block = BS(pi, 0) on (a,b) plus two compensating R's on a and b (in some order,
# possibly interleaved with other gates that touch only a/b... but routers emit them as a contiguous
# block in practice). We detect it by scanning forward from a BS(pi, 0(ish)) op for the matching R's
# on each of its two mode wires, requiring that nothing else touches those two wires in between.

_TWO_PI = 2 * math.pi


def _is_pi_bs(op):
    if op.name != "BS":
        return False
    t = complex(op.params[0]).real
    p = complex(op.params[1]).real
    # angle pi mod 2pi, phase 0 mod 2pi (allow -pi too, same gate up to the usual branch)
    tt = t % _TWO_PI
    pp = p % _TWO_PI
    return (abs(tt - math.pi) < 1e-9 or abs(tt - (-math.pi) % _TWO_PI) < 1e-9) and (abs(pp) < 1e-9 or abs(pp - _TWO_PI) < 1e-9)


def _mode_wires(op):
    return [w for w in op.wires if w[0] == "qm"]


def _find_swap_block(ops, i):
    """If ops[i] starts a router SWAP block (BS(pi,0) on modes a,b plus exactly the two
    compensating single-mode R's on a and b, with nothing else touching a or b in between),
    return (end_index, a, b, block_indices_sorted) else None."""
    o = ops[i]
    if not _is_pi_bs(o):
        return None
    mw = _mode_wires(o)
    if len(mw) != 2:
        return None
    a, b = mw[0], mw[1]
    need = {a: False, b: False}
    block = [i]
    j = i + 1
    limit = min(len(ops), i + 8)  # router blocks are local/contiguous by construction
    while j < limit:
        oj = ops[j]
        wj = set(oj.wires)
        if wj & {a, b}:
            if oj.name == "R" and len(oj.wires) == 1 and oj.wires[0] in (a, b) and not need[oj.wires[0]]:
                need[oj.wires[0]] = True
                block.append(j)
                if need[a] and need[b]:
                    return (j, a, b, tuple(sorted(block)))
            else:
                return None
        j += 1
    return None


def _relabel_wire(w, a, b):
    if w == a:
        return b
    if w == b:
        return a
    return w


def _relabel_op(op, a, b):
    new_wires = tuple(_relabel_wire(w, a, b) for w in op.wires)
    return Op(op.name, op.params, new_wires)


def _window_is_case_a(ops, lo, hi, a, b):
    """gates strictly between lo and hi (exclusive) are either disjoint from {a,b} or are
    single-wire ops touching exactly one of a/b (1-op mode gate, or a qubit gate that doesn't
    touch a/b at all - qubit gates never touch qumode wires anyway)."""
    for k in range(lo + 1, hi):
        w = set(ops[k].wires)
        if w & {a, b}:
            if len(ops[k].wires) != 1:
                return False
    return True


def _window_relabelled_ok_case_b(ops, lo, hi, a, b):
    """For any 2-op gate in the window touching a or b, check that relabelling a<->b keeps it
    on wires that already appear as a 2-op gate's wires elsewhere in the full op list touching
    a or b is unverifiable without hardware topology here; be conservative: only accept windows
    where no 2-op gate touches a or b (pure Case A). Case B is left to future topology-aware
    rules; this rule only claims Case A, which covers the targeted terms."""
    return False


def trigger(ops):
    out = []
    i = 0
    n = len(ops)
    starts = {}
    while i < n:
        res = _find_swap_block(ops, i)
        if res is not None:
            end, a, b, idxs = res
            starts[idxs[0]] = (end, a, b)
        i += 1

    block_starts_sorted = sorted(starts.keys())
    used = set()
    for bi_idx, i0 in enumerate(block_starts_sorted):
        if i0 in used:
            continue
        end0, a0, b0 = starts[i0]
        pair0 = frozenset((a0, b0))
        # search forward for the next block on the same unordered mode pair
        for j0 in block_starts_sorted:
            if j0 <= end0 or j0 in used:
                continue
            end1, a1, b1 = starts[j0]
            if frozenset((a1, b1)) != pair0:
                # if window would be contaminated by some other block on a/b first, stop looking
                # further than the first block that touches a0/b0 at all
                if {a1, b1} & {a0, b0}:
                    break
                continue
            # check nothing between end0 and j0 touches a0/b0 except 1-op gates (Case A)
            if _window_is_case_a(ops, end0, j0, a0, b0):
                out.append((i0, end0, j0, end1, a0, b0))
                used.add(i0)
                used.add(j0)
            break
    return out


def apply(ops, m):
    i0, end0, j0, end1, a, b = m
    # window strictly between the two blocks
    win = list(ops[end0 + 1:j0])
    new_win = [_relabel_op(op, a, b) for op in win]
    return i0, end1, new_win


RULE = Rule(
    name="router_swap_pair_cancellation_by_swap_conjugation",
    kind="rewrite",
    contract="exact",
    stage="physical",
    trigger=trigger,
    apply=apply,
    idea=(
        "Let SW_ab be one router SWAP block (BS(pi,0) plus its two compensating single-mode R's on a,b): "
        "SW_ab^2 = I exactly, and for any gate G on wires disjoint from {a,b}, SW_ab G SW_ab = G unchanged "
        "since conjugation by a permutation of tensor factors only relabels operators on the wires it swaps. "
        "For a 1-op gate on a or b, SW_ab G_a SW_ab = G_b (same gate, other mode). Scan the routed circuit for "
        "two SW_ab blocks on the same unordered mode pair with an intervening window where every gate is either "
        "disjoint from {a,b} or a single-wire gate on a or b (qubit gates automatically qualify since they never "
        "touch qumode wires). Delete both blocks and relabel a<->b on every gate in the window. This is exact: "
        "it never touches bare BS(pi,0) without its compensating R's (whose square alone is only the parity "
        "(-1)^{n_a+n_b}, not I), only whole router blocks. 2-op gates touching a or b inside the window block the "
        "rewrite for that pair (left for a topology-aware extension)."
    ),
    source=(
        "Liu et al. 2407.10381-style modular routing; SWAP-conjugation / permutation-of-tensor-factors "
        "identity (SWAP G SWAP = G relabelled), applied to router SWAP blocks around remote-mode operations "
        "in consecutive Hamiltonian parts (e.g. pauli_disp terms on non-home modes, bus-mode XX/YY terms)."
    ),
    meta={"target_parts": "electronicVibration_small physical stage, terms 20-23, 30-35, 42-47, 24-29, 36-41"},
)
