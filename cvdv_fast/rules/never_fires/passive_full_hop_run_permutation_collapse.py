from cvdv_fast.api import Rule, Op
import math
import itertools

TWO_PI = 2 * math.pi
HALF_PI = math.pi / 2
TOL = 1e-9


def _is_mult(x, step, mod):
    """Is float x an integer multiple of `step`, modulo `mod`? Returns k mod (mod/step), or None."""
    n_steps = round(mod / step)
    k = round(x / step)
    r = x - k * step
    if abs(r) > TOL and abs(abs(r) - mod) > TOL:
        return None
    return k % n_steps


def _mode_wire(w):
    return w[0] == "qm"


def _is_passive_mode_only_gate(op):
    if op.name == "BS":
        return all(_mode_wire(w) for w in op.wires)
    if op.name == "R":
        return all(_mode_wire(w) for w in op.wires)
    return False


def _real(x):
    return float(x.real) if isinstance(x, complex) else float(x)


def _classify_bs(op):
    t = _real(op.params[0])
    p = _real(op.params[1])
    t_mod4pi = t % (4 * math.pi)
    if abs(t_mod4pi - math.pi) < 1e-6:
        branch = +1
    elif abs(t_mod4pi - 3 * math.pi) < 1e-6:
        branch = -1
    else:
        return None
    kp = _is_mult(p, HALF_PI, TWO_PI)
    if kp is None:
        return None
    return branch, kp


def _classify_r(op):
    phi = _real(op.params[0])
    k = _is_mult(phi, HALF_PI, TWO_PI)
    if k is None:
        return None
    return k % 4


def _find_run(ops, start):
    if not _is_passive_mode_only_gate(ops[start]):
        return None
    if ops[start].name == "BS":
        if _classify_bs(ops[start]) is None:
            return None
    else:
        if _classify_r(ops[start]) is None:
            return None
    i = start
    n = len(ops)
    while i + 1 < n:
        nxt = ops[i + 1]
        if not _is_passive_mode_only_gate(nxt):
            break
        if nxt.name == "BS":
            if _classify_bs(nxt) is None:
                break
        else:
            if _classify_r(nxt) is None:
                break
        i += 1
    return i


def _modes_in_run(ops, i0, i1):
    modes = set()
    for k in range(i0, i1 + 1):
        for w in ops[k].wires:
            modes.add(w[1])
    return modes


def _simulate_run(ops, i0, i1, modes_sorted):
    """Content tracking on slots indexed by position in modes_sorted.
    slot_content[slot] = index (into modes_sorted) of the content currently occupying that slot.
    slot_phase[slot] = accumulated phase exponent of (-i), mod 4, for the content in that slot.
    Returns (final_slot_of_content, final_phase_of_content), both lists indexed by original content index."""
    idx_of = {m: k for k, m in enumerate(modes_sorted)}
    slot_content = list(range(len(modes_sorted)))
    slot_phase = [0] * len(modes_sorted)

    def slot_of_mode(m):
        return idx_of[m]

    for k in range(i0, i1 + 1):
        op = ops[k]
        if op.name == "BS":
            res = _classify_bs(op)
            if res is None:
                return None
            branch, kp = res
            wx, wy = op.wires[0], op.wires[1]
            sx, sy = slot_of_mode(wx[1]), slot_of_mode(wy[1])
            base = 0 if branch == 1 else 2  # factor -i = (-i)^1 (branch +1); factor +i = (-i)^3 (branch -1)
            cx = slot_content[sx]
            cy = slot_content[sy]
            px = slot_phase[sx]
            py = slot_phase[sy]
            new_phase_x_to_y = (px + base + kp) % 4
            new_phase_y_to_x = (py + base - kp) % 4
            slot_content[sx], slot_content[sy] = cy, cx
            slot_phase[sx], slot_phase[sy] = new_phase_y_to_x, new_phase_x_to_y
        else:  # R
            k4 = _classify_r(op)
            if k4 is None:
                return None
            w = op.wires[0]
            s = slot_of_mode(w[1])
            slot_phase[s] = (slot_phase[s] + k4) % 4

    final_slot_of_content = [None] * len(modes_sorted)
    final_phase_of_content = [None] * len(modes_sorted)
    for slot, content in enumerate(slot_content):
        final_slot_of_content[content] = slot
        final_phase_of_content[content] = slot_phase[slot]
    return final_slot_of_content, final_phase_of_content


def _bfs_transposition_decomposition(perm, edges, max_len=6):
    """perm: list, perm[k] = final slot index for content starting at slot k. Find shortest sequence of
    edge-transpositions (edges = list of (i,j) slot-index pairs) composing to perm, via BFS (states are
    permutation tuples, limited to small n so this is fine)."""
    n = len(perm)
    target = tuple(perm)
    start = tuple(range(n))
    if start == target:
        return []

    def apply_transposition(state, e):
        i, j = e
        lst = list(state)
        lst[i], lst[j] = lst[j], lst[i]
        return tuple(lst)

    visited = {start: []}
    frontier = [start]
    depth = 0
    while frontier:
        if depth >= max_len:
            return None
        new_frontier = []
        for cur in frontier:
            for e in edges:
                nxt = apply_transposition(cur, e)
                if nxt not in visited:
                    seq = visited[cur] + [e]
                    if nxt == target:
                        return seq
                    visited[nxt] = seq
                    new_frontier.append(nxt)
        frontier = new_frontier
        depth += 1
    return None


def trigger(ops):
    out = []
    i = 0
    n = len(ops)
    while i < n:
        if _is_passive_mode_only_gate(ops[i]):
            i1 = _find_run(ops, i)
            if i1 is not None and i1 > i:
                modes = sorted(_modes_in_run(ops, i, i1))
                if len(modes) >= 2:
                    edges_raw = set()
                    for k in range(i, i1 + 1):
                        if ops[k].name == "BS":
                            w0, w1 = ops[k].wires[0][1], ops[k].wires[1][1]
                            edges_raw.add(frozenset((w0, w1)))
                    sim = _simulate_run(ops, i, i1, modes)
                    if sim is not None:
                        out.append((i, i1, tuple(modes),
                                    tuple(sorted(edges_raw, key=lambda s: tuple(sorted(s))))))
                    i = i1 + 1
                    continue
            i = i + 1
        else:
            i += 1
    return out


def apply(ops, m):
    i0, i1, modes_sorted, edges_fs = m
    modes_sorted = list(modes_sorted)
    n = len(modes_sorted)
    idx_of = {mm: k for k, mm in enumerate(modes_sorted)}
    edges = [tuple(sorted((idx_of[list(fs)[0]], idx_of[list(fs)[1]]))) for fs in edges_fs]

    sim = _simulate_run(ops, i0, i1, modes_sorted)
    if sim is None:
        raise ValueError("could not simulate run")
    final_slot_of_content, final_phase_of_content = sim

    perm = final_slot_of_content

    decomp = _bfs_transposition_decomposition(perm, edges)
    if decomp is None:
        raise ValueError("no transposition decomposition on coupled edges")

    new_ops = []
    for (a, b) in decomp:
        wa = ("qm", modes_sorted[a])
        wb = ("qm", modes_sorted[b])
        new_ops.append(Op("BS", (math.pi, 0.0), (wa, wb)))

    # recompute phases produced by these BS(pi,0) gates (branch=+1 => base=0, kp=0) in the same slot bookkeeping
    slot_content = list(range(n))
    slot_phase = [0] * n
    for (a, b) in decomp:
        cx = slot_content[a]
        cy = slot_content[b]
        px = slot_phase[a]
        py = slot_phase[b]
        new_phase_x_to_y = px % 4
        new_phase_y_to_x = py % 4
        slot_content[a], slot_content[b] = cy, cx
        slot_phase[a], slot_phase[b] = new_phase_y_to_x, new_phase_x_to_y

    recon_final_slot = [None] * n
    recon_final_phase = [None] * n
    for slot, content in enumerate(slot_content):
        recon_final_slot[content] = slot
        recon_final_phase[content] = slot_phase[slot]

    if recon_final_slot != perm:
        raise ValueError("permutation mismatch after resynthesis")

    for k in range(n):
        d = (final_phase_of_content[k] - recon_final_phase[k]) % 4
        if d != 0:
            final_mode = modes_sorted[perm[k]]
            new_ops.append(Op("R", (float(d) * HALF_PI,), (("qm", final_mode),)))

    return i0, i1, new_ops


RULE = Rule(
    name="passive_full_hop_run_permutation_collapse",
    kind="rewrite",
    contract="exact",
    stage="logical",
    trigger=trigger,
    apply=apply,
    idea="A maximal contiguous run of oscillator-only passive gates (BS at t=pi mod 2pi, phase a multiple of "
         "pi/2; R at phi a multiple of pi/2) is, on the single-photon subspace, exactly a monomial matrix "
         "M = Perm(sigma) * diag(i^{c_x}); since passive linear optics U(m)->Fock is a phase-free homomorphism "
         "fixing vacuum, two such circuits agree on all of Fock space iff their m x m matrices agree. Content "
         "tracking through the run (integer phases mod 4, ints only) gives sigma and per-content phases exactly; "
         "sigma is then resynthesized as a shortest sequence of BS(pi,0) transpositions along already-coupled "
         "qumode edges (BFS), and the residual integer phase per final mode is emitted as a single R(k*pi/2). "
         "This collapses e.g. a 12-BS all-pairs hopping block (which needs 24 router SWAPs when routed naively) "
         "into 2 BS + 4 R with zero router SWAPs, verified by exact integer matrix recomputation before acceptance.",
    source="boseHubbard_small hop-block analysis; U(m) passive-linear-optics homomorphism (Reck/Clements-style "
           "monomial subgroup), transposition/permutation collapse with Z4 phase bookkeeping",
)
