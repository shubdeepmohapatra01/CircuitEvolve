from cvdv_fast.api import Rule, Op
import math
import itertools

HALF_PI = math.pi / 2
EPS = 1e-9

# Grid coupling used for resynthesis (2x2 grid: 0-1,0-2,1-3,2-3). We detect
# coupled edges dynamically from the qumode wires seen in the block itself,
# falling back to this canonical set if the block only touches a subset.
GRID_EDGES = [(0, 1), (0, 2), (1, 3), (2, 3)]


def _as_float(p):
    if isinstance(p, complex):
        if abs(p.imag) > 1e-6:
            return None
        return float(p.real)
    return float(p)


def _quant(x):
    q = int(round(x / HALF_PI))
    if abs(x - q * HALF_PI) < EPS:
        return q % 4
    return None


def _mode_num(w):
    # wire is ('qm', j)
    return w[1]


def _is_qumode_wire(w):
    return isinstance(w, tuple) and len(w) == 2 and w[0] == "qm"


def _gate_monomial_info(op):
    """Return ('R', x, q) or ('BS', x, y, s, r) if op is a qualifying monomial
    passive gate on qumodes with quarter-pi parameters, else None."""
    if op.name == "R":
        if len(op.wires) != 1 or not _is_qumode_wire(op.wires[0]):
            return None
        phi = _as_float(op.params[0])
        if phi is None:
            return None
        q = _quant(phi)
        if q is None:
            return None
        x = _mode_num(op.wires[0])
        return ("R", x, q)
    if op.name == "BS":
        if len(op.wires) != 2:
            return None
        if not (_is_qumode_wire(op.wires[0]) and _is_qumode_wire(op.wires[1])):
            return None
        t = _as_float(op.params[0])
        p = _as_float(op.params[1])
        if t is None or p is None:
            return None
        s = _quant(t / 2.0)
        r = _quant(p)
        if s is None or r is None:
            return None
        x = _mode_num(op.wires[0])
        y = _mode_num(op.wires[1])
        return ("BS", x, y, s, r)
    return None


def _wires_touched(op):
    return set(w for w in op.wires)


def _identity_state(modes):
    sigma = {m: m for m in modes}
    k = {m: 0 for m in modes}
    return sigma, k


def _apply_R(sigma, k, x, q):
    # a_x -> e^{-i phi} a_x, phi = q*pi/2  => exponent contribution -q on row x
    # sigma unaffected; k[x] accumulates the new gate's effect composed AFTER
    # previous ones (time order = emission order; we compose row-substitution
    # incrementally gate-by-gate in emission order).
    row = None
    for src, dst in sigma.items():
        if dst == x:
            row = src
            break
    if row is None:
        return
    k[row] = (k[row] - q) % 4


def _apply_BS_swap_like(sigma, k, x, y, s, r):
    """Apply one BS(t,p) with t/2=s*pi/2, p=r*pi/2 to the running (sigma,k)
    state, where sigma/k describe a_x(initial) in terms of current content
    labels: for content label c with sigma[c] = current mode, k[c] = exponent.
    We update by finding which content currently sits at x and y and mixing."""
    if s % 2 == 0:
        # a_x -> (-1)^{s/2} a_x ; a_y -> (-1)^{s/2} a_y  (diagonal only)
        add = (2 * ((s // 2) % 2)) % 4
        for c, m in sigma.items():
            if m == x or m == y:
                k[c] = (k[c] + add) % 4
        return
    # s odd: a_x -> -i e^{ip} (-1)^{(s-1)/2} a_y ;  a_y -> -i e^{-ip} (-1)^{(s-1)/2} a_x
    half = (s - 1) // 2
    exp_x_row = (3 + r + 2 * half) % 4  # exponent applied when content ends at... see below
    exp_y_row = (3 - r + 2 * half) % 4

    cx = None
    cy = None
    for c, m in sigma.items():
        if m == x:
            cx = c
        elif m == y:
            cy = c
    # a_x(before) -> goes into row x contributes to new a_x expression? We track
    # Heisenberg evolution of content (input mode operators) under composition:
    # content currently expressed as coefficient*mode m; after this gate,
    # mode x's operator becomes combination of (old x, old y), i.e. the content
    # that was AT x moves to y (picking exponent exp_x_row relative to y) and
    # vice versa, because a_x(new, in terms of a_x(old)) definition flips:
    # we substitute content positions: content at x moves to y, content at y moves to x.
    if cx is not None:
        sigma[cx] = y
        k[cx] = (k[cx] + exp_x_row) % 4
    if cy is not None:
        sigma[cy] = x
        k[cy] = (k[cy] + exp_y_row) % 4


def _compute_block_matrix(ops, modes):
    sigma, k = _identity_state(modes)
    for op in ops:
        info = _gate_monomial_info(op)
        if info is None:
            return None
        if info[0] == "R":
            _, x, q = info
            _apply_R(sigma, k, x, q)
        else:
            _, x, y, s, r = info
            _apply_BS_swap_like(sigma, k, x, y, s, r)
    return sigma, k


def _dense_check(ops, modes, sigma, k, dim=4):
    """Cross-check via dense complex matrices on a small Fock cutoff-free
    'mode permutation matrix' representation (m x m, since passive monomial
    gates act linearly on mode operators)."""
    m = len(modes)
    idx = {mode: i for i, mode in enumerate(modes)}
    # Build M such that a_x(out) = sum_y M[x,y] a_y(in), applied in time order:
    # M_total = M_last * ... * M_first  (operators transform contravariantly,
    # but since we only need consistency between the two independent
    # computations, we just rebuild densely gate by gate the same way.)
    M = [[1.0 + 0j if i == j else 0.0 + 0j for j in range(m)] for i in range(m)]

    def mat_R(x, q):
        Mx = [[1.0 + 0j if i == j else 0.0 + 0j for j in range(m)] for i in range(m)]
        phi = q * HALF_PI
        Mx[idx[x]][idx[x]] = complex(math.cos(-phi), math.sin(-phi))
        return Mx

    def mat_BS(x, y, s, r):
        Mx = [[1.0 + 0j if i == j else 0.0 + 0j for j in range(m)] for i in range(m)]
        t = s * math.pi
        p = r * HALF_PI
        c = math.cos(t / 2.0)
        sN = math.sin(t / 2.0)
        ix, iy = idx[x], idx[y]
        Mx[ix][ix] = c
        Mx[ix][iy] = -1j * complex(math.cos(p), math.sin(p)) * sN
        Mx[iy][iy] = c
        Mx[iy][ix] = -1j * complex(math.cos(-p), math.sin(-p)) * sN
        return Mx

    def matmul(A, B):
        n = len(A)
        C = [[0j] * n for _ in range(n)]
        for i in range(n):
            for kk in range(n):
                if A[i][kk] == 0:
                    continue
                aik = A[i][kk]
                for j in range(n):
                    C[i][j] += aik * B[kk][j]
        return C

    for op in ops:
        info = _gate_monomial_info(op)
        if info[0] == "R":
            _, x, q = info
            Mg = mat_R(x, q)
        else:
            _, x, y, s, r = info
            Mg = mat_BS(x, y, s, r)
        M = matmul(Mg, M)

    # Build dense matrix from (sigma, k): a_c(final content) sits at mode sigma[c]
    # with phase i^{k[c]} relative to original a_c -> interpret as
    # M2[idx[sigma[c]]][idx[c]] = i^{k[c]}
    M2 = [[0.0 + 0j for _ in range(m)] for _ in range(m)]
    for c in modes:
        M2[idx[sigma[c]]][idx[c]] = (1j) ** k[c]

    for i in range(m):
        for j in range(m):
            if abs(M[i][j] - M2[i][j]) > 1e-6:
                return False
    return True


def _gather_prefix_block(ops):
    """Scan from the start, greedily opening all qumode wires, closing a wire
    on first non-qualifying touch. Returns (indices_in_block, modes_used) or
    (None, None) if nothing qualifies."""
    open_wires = set()
    for op in ops:
        for w in op.wires:
            if _is_qumode_wire(w):
                open_wires.add(w)
    if not open_wires:
        return None, None

    closed = set()
    block_indices = []
    for i, op in enumerate(ops):
        qwires = [w for w in op.wires if _is_qumode_wire(w)]
        if not qwires:
            continue  # qubit-only gates ignored
        if any(w in closed for w in qwires):
            for w in qwires:
                closed.add(w)
            continue
        info = _gate_monomial_info(op)
        if info is None:
            for w in qwires:
                closed.add(w)
            continue
        if len(qwires) == 1:
            wset = {qwires[0]}
        else:
            wset = set(qwires)
        if wset & closed:
            closed |= wset
            continue
        block_indices.append(i)
    return (block_indices if block_indices else None), None


def trigger(ops):
    if not ops:
        return []
    block_idx, _ = _gather_prefix_block(ops)
    if not block_idx:
        return []
    # Must be a genuine prefix cut: find the max index in block and ensure
    # the block is a valid earliest-contiguous-by-wire-commutation set
    # (already guaranteed by the scan). Require at least 2 gates and at
    # least one BS among them (otherwise nothing to gain).
    block_ops = [ops[i] for i in block_idx]
    if len(block_idx) < 2:
        return []
    if not any(o.name == "BS" for o in block_ops):
        return []
    i0 = block_idx[0]
    i1 = block_idx[-1]
    # Confirm contiguity requirement for replacement: our apply() will splice
    # out exactly the block positions and re-insert resynthesized gates plus
    # any interleaved non-block gates that lie strictly between i0 and i1
    # (gates on other wires, already commuting through by construction).
    return [(tuple(block_idx),)]


def _factor_permutation(sigma, modes, edges):
    """Factor the permutation moves (content -> final mode) into a sequence
    of transpositions along given coupled edges via BFS over S_m, returning
    a list of edges (x,y) to emit as swaps, in emission order, such that
    applying swap_(x,y) (content-swap) in that order reproduces sigma."""
    # current placement: where each original mode's content currently sits
    cur = {m: m for m in modes}  # content c currently at position cur[c]
    target = dict(sigma)  # content c should end at target[c]

    # position occupant lookup
    occ = {m: m for m in modes}  # position -> content currently there

    def swap_positions(x, y):
        cx = occ[x]
        cy = occ[y]
        occ[x], occ[y] = cy, cx
        cur[cx] = y
        cur[cy] = x

    emitted = []
    # Simple approach: repeatedly find a content not yet in place and route
    # it via BFS shortest path on the edge graph, swapping along the path.
    adj = {}
    for (a, b) in edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    def bfs_path(src, dst):
        if src == dst:
            return [src]
        visited = {src}
        parent = {src: None}
        queue = [src]
        while queue:
            nxt = []
            for u in queue:
                for v in adj.get(u, ()):
                    if v not in visited:
                        visited.add(v)
                        parent[v] = u
                        if v == dst:
                            path = [v]
                            while parent[path[-1]] is not None:
                                path.append(parent[path[-1]])
                            return list(reversed(path))
                        nxt.append(v)
            queue = nxt
        return None

    guard = 0
    while True:
        guard += 1
        if guard > 10000:
            return None
        pending = [c for c in modes if cur[c] != target[c]]
        if not pending:
            break
        c = pending[0]
        path = bfs_path(cur[c], target[c])
        if path is None or len(path) < 2:
            return None
        for i in range(len(path) - 1):
            x, y = path[i], path[i + 1]
            emitted.append((x, y))
            swap_positions(x, y)
    return emitted


def apply(ops, m):
    (block_idx_tuple,) = m
    block_idx = list(block_idx_tuple)
    i0 = block_idx[0]
    i1 = block_idx[-1]

    block_ops = [ops[i] for i in block_idx]
    modes = sorted({_mode_num(w) for op in block_ops for w in op.wires if _is_qumode_wire(w)})

    res = _compute_block_matrix(block_ops, modes)
    if res is None:
        return None
    sigma, k = res

    if not _dense_check(block_ops, modes, sigma, k):
        return None

    # Determine coupled edges among the modes actually present: prefer the
    # canonical grid edges restricted to this mode set; if not connecting
    # all modes, fall back to a complete graph on these modes (best effort —
    # the runner enforces physical-stage coupling, so if an edge we emit is
    # not actually coupled, downstream validation will reject the rewrite).
    present_edges = [(a, b) for (a, b) in GRID_EDGES if a in modes and b in modes]
    # check connectivity of 'modes' under present_edges
    adj = {mm: set() for mm in modes}
    for (a, b) in present_edges:
        adj[a].add(b)
        adj[b].add(a)

    def connected(edges_adj):
        if not modes:
            return True
        seen = {modes[0]}
        stack = [modes[0]]
        while stack:
            u = stack.pop()
            for v in edges_adj.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        return len(seen) == len(modes)

    if not connected(adj):
        present_edges = list(itertools.combinations(modes, 2))
        adj = {mm: set() for mm in modes}
        for (a, b) in present_edges:
            adj[a].add(b)
            adj[b].add(a)
        if not connected(adj):
            return None

    swap_edges = _factor_permutation(sigma, modes, present_edges)
    if swap_edges is None:
        return None

    new_ops = []
    for (x, y) in swap_edges:
        new_ops.append(Op("BS", (math.pi, 0.0), (("qm", x), ("qm", y))))

    # Compute residual diagonal exponents: recompute (sigma2, k2) of the
    # emitted swap network alone, then residual = k - k2 (mod 4), attributed
    # per content, then placed on the mode where that content ends up.
    swap_ops_info = [("BS", x, y, 1, 0) for (x, y) in swap_edges]
    sigma2, k2 = _identity_state(modes)
    for (_, x, y, s, r) in swap_ops_info:
        _apply_BS_swap_like(sigma2, k2, x, y, s, r)

    if sigma2 != sigma:
        return None

    residual = {c: (k[c] - k2[c]) % 4 for c in modes}

    for c in modes:
        qres = residual[c]
        if qres != 0:
            final_mode = sigma[c]
            new_ops.append(Op("R", (-qres * HALF_PI,), (("qm", final_mode),)))

    # Verify full replacement reproduces the same (sigma, k) exactly.
    check = _compute_block_matrix(new_ops, modes)
    if check is None:
        return None
    sigma_chk, k_chk = check
    if sigma_chk != sigma or k_chk != k:
        return None
    if not _dense_check(new_ops, modes, sigma_chk, k_chk):
        return None

    old_two_op = sum(1 for o in block_ops if len(o.wires) == 2)
    old_one_op = sum(1 for o in block_ops if len(o.wires) == 1)
    new_two_op = sum(1 for o in new_ops if len(o.wires) == 2)
    new_one_op = sum(1 for o in new_ops if len(o.wires) == 1)
    if (new_two_op, new_two_op + new_one_op) >= (old_two_op, old_two_op + old_one_op):
        if not (new_two_op < old_two_op or (new_two_op == old_two_op and new_one_op < old_one_op)):
            return None

    # Gates strictly between i0 and i1 that are NOT part of the block must be
    # preserved, re-emitted in their original relative order after the
    # resynthesized block (they commute with the whole block by construction
    # of the prefix scan, since they never touched a wire the block used
    # before being excluded -- any gate touching a block wire would have
    # closed it, preventing later block members on that wire; but since the
    # block here is scanned strictly in order and later same-wire gates are
    # excluded, any ops between i0..i1 not in block_idx act on wires disjoint
    # from all subsequent block wires at that point -- they are safe to move
    # before or after). We keep them immediately after, preserving order.
    block_set = set(block_idx)
    leftover = [ops[j] for j in range(i0, i1 + 1) if j not in block_set]

    return i0, i1, new_ops + leftover


RULE = Rule(
    name="physical_monomial_passive_prefix_resynthesis",
    kind="rewrite",
    contract="exact",
    stage="physical",
    trigger=trigger,
    apply=apply,
    idea="At the physical stage, collect the leading DAG-commuting prefix of passive gates (R with quarter-turn "
         "phase, BS with half/quarter-turn angle and quarter-turn phase) on qumode wires: these are exactly the "
         "monomial elements of U(m), a closed subgroup (permutation times powers of i per mode). Compose the block's "
         "action with pure integer Z4 phase/permutation arithmetic (cross-checked against the dense complex mode "
         "matrix), factor the resulting permutation into transpositions along coupled grid edges via BFS, emit one "
         "BS(pi,0) per transposition plus residual R(q*pi/2) phases, and replace the block only if the recomputed "
         "(permutation, phase) matches exactly and the gate cost is lower. Because U(M) is determined by M alone "
         "(fixes vacuum, no phase ambiguity) and M1->U(M1), M2->U(M2) compose as U(M1)U(M2)=U(M2 M1), equality of M "
         "implies operator equality on the whole Fock space, so the swap is exact on every cutoff.",
    source="Liu et al. 2407.10381 (passive/Gaussian monomial subgroup of U(m); Heisenberg propagation of mode "
           "operators through R/BS); router SWAP decomposition BS(pi,0)+2*R(-pi/2) from the Genesis routing pass",
    meta={"target_parts": "boseHubbard_small hop BS block and router-inserted qumode SWAPs preceding n2 parts; "
                           "general passive sections built from quarter/half-turn R and BS gates"},
)
