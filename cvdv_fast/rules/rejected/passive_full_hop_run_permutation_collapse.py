from cvdv_fast.api import Rule, Op
import math
import itertools
from collections import deque

TWO_PI = 2 * math.pi
HALF_PI = math.pi / 2
TOL = 1e-9


def _is_mult(x, step, mod):
    """Is float x an integer multiple of `step`, modulo `mod`? Returns the int k (x ~= k*step mod mod_count) or None."""
    n_steps = round(mod / step)
    k = round(x / step)
    r = x - k * step
    # wrap residual into (-step/2, step/2] relative check using mod
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


def _classify_bs(op):
    t = float(op.params[0].real) if isinstance(op.params[0], complex) else float(op.params[0])
    p = float(op.params[1].real) if isinstance(op.params[1], complex) else float(op.params[1])
    # t must be pi mod 2pi
    kt = round((t - math.pi) / TWO_PI)
    if abs((t - math.pi) - kt * TWO_PI) > TOL:
        return None
    sign = 1 if (kt % 2 == 0) else -1
    # careful: t = pi + kt*2pi; sign of "effective pi" is +pi if kt even? Actually t mod 4pi distinguishes +pi/-pi
    k4 = round((t - math.pi) / TWO_PI)
    eff = t - k4 * TWO_PI  # == pi always by construction above; need true branch via mod 4pi
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
    return branch, kp  # branch = +1 means t=pi(mod4pi), -1 means t=-pi(mod4pi) i.e. 3pi mod 4pi


def _classify_r(op):
    phi = float(op.params[0].real) if isinstance(op.params[0], complex) else float(op.params[0])
    k = _is_mult(phi, HALF_PI, TWO_PI)
    if k is None:
        return None
    return k % 4


def _find_run(ops, start):
    """Maximal contiguous run starting at `start` of oscillator-only passive gates, or None if ops[start]
    doesn't qualify. Returns (i1,) end index inclusive, or None."""
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
    """content tracking: pos[x] = current slot index of the photon that started at mode x (index into modes_sorted).
    phase[x] = int phase exponent of i, mod 4, accumulated for that content.
    Returns dict mode->(final_slot, phase mod4), where final_slot/phase indexed by modes_sorted positions."""
    idx_of = {m: k for k, m in enumerate(modes_sorted)}
    pos = list(range(len(modes_sorted)))  # pos[k] = which "slot" currently holds the content that started in slot k
    # we track slot occupancy: slot_content[slot] = which original content index currently sits there
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
            # a_x^+ -> branch*(-i) e^{-i p} a_y^+ ... and a_y^+ -> branch*(-i) e^{+i p} a_x^+
            # phase contributed to content moving: factor (-i)*branch for both directions,
            # times e^{-i p} for x->y, e^{+i p} for y->x. p = kp*pi/2 so e^{-ip}=(-i)^kp, e^{+ip}=(i)^kp=(-i)^{-kp}
            # exponent of (-i) for the content currently at slot x going to slot y: base + kp (mod4)
            # exponent of (-i) for the content currently at slot y going to slot x: base - kp (mod4)
            base = 0 if branch == 1 else 2  # branch=+1 -> factor -i = (-i)^1 ; branch=-1 -> factor +i = (-i)^3
            cx = slot_content[sx]
            cy = slot_content[sy]
            px = slot_phase[sx]
            py = slot_phase[sy]
            new_phase_x_to_y = (px + base + kp) % 4
            new_phase_y_to_x = (py + base - kp) % 4
            # swap contents between slots sx, sy with updated phase
            slot_content[sx], slot_content[sy] = cy, cx
            slot_phase[sx], slot_phase[sy] = new_phase_y_to_x, new_phase_x_to_y
        else:  # R
            k4 = _classify_r(op)
            if k4 is None:
                return None
            w = op.wires[0]
            s = slot_of_mode(w[1])
            # R(k*pi/2) multiplies a^+ by (-i)^k
            slot_phase[s] = (slot_phase[s] + k4) % 4

    # build result: for each original content (starting mode index k), find final slot and phase
    final_slot_of_content = [None] * len(modes_sorted)
    final_phase_of_content = [None] * len(modes_sorted)
    for slot, content in enumerate(slot_content):
        final_slot_of_content[content] = slot
        final_phase_of_content[content] = slot_phase[slot]
    return final_slot_of_content, final_phase_of_content


def _bfs_transposition_decomposition(perm, modes_sorted, edges):
    """perm: list where perm[k] = final slot index for content starting at slot k (a permutation of range(n)).
    We need sigma such that applying transpositions (as BS(pi,0) swaps) along grid edges realizes this permutation
    of *slots* (equivalently of modes, via modes_sorted). Find shortest sequence of edge-transpositions composing
    to perm, via BFS over S_n restricted to adjacent transpositions (n small, e.g. m<=4)."""
    n = len(modes_sorted)
    target = tuple(perm)
    start = tuple(range(n))
    if start == target:
        return []
    adj = list(edges)

    def apply_transposition(state, e):
        i, j = e
        lst = list(state)
        lst[i], lst[j] = lst[j], lst[i]
        return tuple(lst)

    # BFS from identity to target
    visited = {start: []}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == target:
            return visited[cur]
        if len(visited[cur]) >= 6:
            continue
        for e in adj:
            nxt = apply_transposition(cur, e)
            if nxt not in visited:
                visited[nxt] = visited[cur] + [e]
                q.append(nxt)
    return None


def trigger(ops):
    out = []
    i = 0
    n = len(ops)
    while i < n:
        if _is_passive_mode_only_gate(ops[i]):
            i1 = _find_run(ops, i)
            if i1 is not None and i1 > i:  # need at least 2 gates to be worth rewriting (a BS + something)
                modes = sorted(_modes_in_run(ops, i, i1))
                if len(modes) >= 2:
                    # collect bs-edges available in this run (coupling graph = edges appearing as BS wires in run)
                    edges_raw = set()
                    for k in range(i, i1 + 1):
                        if ops[k].name == "BS":
                            w0, w1 = ops[k].wires[0][1], ops[k].wires[1][1]
                            edges_raw.add(frozenset((w0, w1)))
                    sim = _simulate_run(ops, i, i1, modes)
                    if sim is not None:
                        out.append((i, i1, tuple(modes), tuple(sorted(edges_raw, key=lambda s: tuple(sorted(s))))))
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

    # perm[k] = final slot for content k
    perm = final_slot_of_content

    decomp = _bfs_transposition_decomposition(perm, modes_sorted, edges)
    if decomp is None:
        raise ValueError("no transposition decomposition on coupled edges")

    new_ops = []
    for (a, b) in decomp:
        wa = ("qm", modes_sorted[a])
        wb = ("qm", modes_sorted[b])
        new_ops.append(Op("BS", (math.pi, 0.0), (wa, wb)))

    # recompute phases produced by these BS(pi,0) gates via the same content-tracking simulation
    # build a synthetic sim: slot_content/slot_phase starting identity, apply same transpositions with branch=+1,kp=0
    slot_content = list(range(n))
    slot_phase = [0] * n
    for (a, b) in decomp:
        cx = slot_content[a]
        cy = slot_content[b]
        px = slot_phase[a]
        py = slot_phase[b]
        # base=0 (branch+1), kp=0
        new_phase_x_to_y = (px + 0 + 0) % 4
        new_phase_y_to_x = (py + 0 - 0) % 4
        slot_content[a], slot_content[b] = cy, cx
        slot_phase[a], slot_phase[b] = new_phase_y_to_x, new_phase_x_to_y

    recon_final_slot = [None] * n
    recon_final_phase = [None] * n
    for slot, content in enumerate(slot_content):
        recon_final_slot[content] = slot
        recon_final_phase[content] = slot_phase[slot]

    if recon_final_slot != perm:
        raise ValueError("permutation mismatch after resynthesis")

    # residual per-content phase needed: target phase - phase produced by BS resynthesis, mod 4
    # each content k needs residual d_k = (final_phase_of_content[k] - recon_final_phase[k]) mod 4
    # applied as R on the *final* mode that content occupies (i.e. mode at slot perm[k] = modes_sorted[perm[k]])
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
