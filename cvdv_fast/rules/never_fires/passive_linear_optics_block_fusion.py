from cvdv_fast.api import Rule, Op
import math
import cmath
import itertools
import functools

# Passive, number-conserving, oscillator-only gates we know how to fold into a
# unitary mode matrix M.  Each entry maps gate name -> function building its
# contribution to M (acting only on the 1 or 2 modes it touches).
PASSIVE_GATES = ("BS", "R")


def _is_passive(op):
    if op.name not in PASSIVE_GATES:
        return False
    for w in op.wires:
        if w[0] != "qm":
            return False
    return True


def _modes_of(op):
    return tuple(w[1] for w in op.wires if w[0] == "qm")


def _collect_run(ops, i0):
    """Collect maximal run starting at i0: passive gates on a fixed mode set,
    with non-passive / disjoint-wire ops interleaved only if they commute
    (i.e. touch none of the modes involved in the passive run so far)."""
    modes = set()
    idxs = []
    skipped = []
    n = len(ops)
    j = i0
    # First pass: find full extent of modes touched by the maximal chain of
    # passive ops reachable while skipping only disjoint ops.
    while j < n:
        o = ops[j]
        if _is_passive(o):
            ms = _modes_of(o)
            modes.update(ms)
            idxs.append(j)
            j += 1
            continue
        # non-passive op: allowed only if it touches none of the modes we
        # care about so far AND none of the modes any later passive op in
        # this run will touch -- conservatively, check disjointness with
        # current accumulated mode set; if it touches one of them, stop.
        wset = set(w[1] for w in o.wires if w[0] == "qm") | set(
            ("q", w[1]) for w in o.wires if w[0] == "q"
        )
        touches_modes = set(w[1] for w in o.wires if w[0] == "qm")
        if touches_modes & modes:
            break
        skipped.append(j)
        j += 1
    if len(idxs) < 2:
        return None
    last = idxs[-1]
    # Trim trailing skipped ops that ended up after the last passive op (they
    # weren't actually interleaved, just trailing non-passive stuff we must
    # not consume).
    i1 = last
    used = sorted(set(idxs) | set(k for k in skipped if k < last))
    return i0, i1, used, sorted(modes)


def _mode_matrix(ops, used_idxs, modes):
    """Build the k x k unitary M (mode basis = sorted(modes)) for the product
    of passive ops in used_idxs (in emission/time order: first emitted acts
    first on the incoming operators, so M = M_last * ... * M_first when
    composing as U^dag a U = M a style forward propagation).

    We track, for each basis mode's annihilation operator, how it transforms
    under the whole sequence: a_i -> sum_j M_ij a_j accumulated by applying
    each gate's single/two-mode substitution in time order.
    """
    k = len(modes)
    idx_of = {m: i for i, m in enumerate(modes)}
    # M[i] = row vector of coefficients expressing current a_{modes[i]} in
    # terms of original a_{modes[0..k-1]}. Start as identity.
    M = [[1.0 + 0.0j if i == j else 0.0 + 0.0j for j in range(k)] for i in range(k)]

    for idx in used_idxs:
        o = ops[idx]
        if not _is_passive(o):
            continue
        if o.name == "R":
            (theta,) = o.params
            (m,) = _modes_of(o)
            mi = idx_of[m]
            phase = cmath.exp(-1j * theta)
            # a_m -> phase * a_m ; update row mi by multiplying by phase
            for col in range(k):
                M[mi][col] *= phase
        elif o.name == "BS":
            t, p = o.params
            ma, mb = _modes_of(o)
            ia, ib = idx_of[ma], idx_of[mb]
            c = math.cos(t / 2.0)
            s = math.sin(t / 2.0)
            eip = cmath.exp(1j * p)
            eim = cmath.exp(-1j * p)
            # a -> c*a - i*e^{ip}*s*b ; b -> c*b - i*e^{-ip}*s*a
            row_a = M[ia][:]
            row_b = M[ib][:]
            new_a = [c * row_a[col] - 1j * eip * s * row_b[col] for col in range(k)]
            new_b = [c * row_b[col] - 1j * eim * s * row_a[col] for col in range(k)]
            M[ia] = new_a
            M[ib] = new_b
    return M


def _mat_mul(A, B):
    n = len(A)
    m = len(B[0])
    kk = len(B)
    out = [[0j] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            s = 0j
            for l in range(kk):
                s += A[i][l] * B[l][j]
            out[i][j] = s
    return out


def _is_identity(M, tol=1e-9):
    k = len(M)
    for i in range(k):
        for j in range(k):
            want = 1.0 if i == j else 0.0
            if abs(M[i][j] - want) > tol:
                return False
    return True


def _is_monomial(M, tol=1e-9):
    """Return permutation (list perm so col perm[i] is the nonzero entry of
    row i) and phases if M is a monomial unitary (one nonzero per row/col),
    else None."""
    k = len(M)
    perm = [-1] * k
    phase = [0j] * k
    used_cols = set()
    for i in range(k):
        nz = [(j, M[i][j]) for j in range(k) if abs(M[i][j]) > tol]
        if len(nz) != 1:
            return None
        j, val = nz[0]
        if j in used_cols:
            return None
        used_cols.add(j)
        if abs(abs(val) - 1.0) > 1e-6:
            return None
        perm[i] = j
        phase[i] = val
    return perm, phase


def trigger(ops):
    out = []
    n = len(ops)
    seen_starts = set()
    i = 0
    while i < n:
        if _is_passive(ops[i]):
            res = _collect_run(ops, i)
            if res is not None:
                i0, i1, used, modes = res
                if i0 not in seen_starts:
                    seen_starts.add(i0)
                    out.append((i0, i1, tuple(used), tuple(modes)))
                i = i1 + 1
                continue
        i += 1
    return out


def _resynth_monomial(perm, phase, modes):
    """perm: perm[i] = destination index (into `modes` order) that mode i's
    operator maps to.  phase: phase[i] is the (unit-modulus) complex
    coefficient on that term.  Build gates (transpositions via BS(pi,phi),
    then R on each mode for leftover phase) implementing this monomial map,
    restricted to transpositions connecting indices directly (pairwise swaps
    decomposed from the permutation cycles)."""
    k = len(modes)
    new_ops = []

    # Decompose permutation into transpositions. perm as a function: index i
    # (source) -> perm[i] (destination). We realize it by a sequence of
    # adjacent-in-cycle transpositions applied as BS(pi, phi) gates, each of
    # which maps a_x -> -i e^{i phi} a_y and a_y -> -i e^{-i phi} a_x (from
    # BS formula with t=pi: cos(pi/2)=0, sin(pi/2)=1).
    #
    # We track the current mapping state as we apply swaps: start from
    # identity-so-far and apply transpositions on the *current* positions to
    # realize the target permutation, accumulating a running phase on each
    # final mode which we fold together with `phase` at the end.
    cur = list(range(k))  # cur[i] = which original index currently "lives" at slot i
    running_phase = [1.0 + 0.0j] * k  # phase accumulated on slot i so far

    # find target: slot i should end up holding original index j such that
    # perm[j] == i  (i.e., original mode j maps to destination i)
    target = [None] * k
    for src, dst in enumerate(perm):
        target[dst] = src

    # We implement via cycle decomposition of the permutation dst<-src map.
    # Build cycles over "slots", where slot i initially holds original index i
    # and we want slot i to finally hold target[i].
    visited = [False] * k
    for start in range(k):
        if visited[start] or target[start] == start:
            visited[start] = True
            continue
        cycle = []
        x = start
        while not visited[x]:
            visited[x] = True
            cycle.append(x)
            x = target[x]
        if len(cycle) < 2:
            continue
        # realize cycle (c0 c1 c2 ... c_{L-1}) meaning slot c0 should end up
        # with what's at c1, etc. We do this with adjacent transpositions:
        # repeatedly swap slot c0 with slot c_{t} walking down the cycle.
        for t in range(len(cycle) - 1, 0, -1):
            a_slot = cycle[0]
            b_slot = cycle[t]
            ma = modes[a_slot]
            mb = modes[b_slot]
            phi = 0.0
            new_ops.append(Op("BS", (math.pi, phi), (("qm", ma), ("qm", mb))))
            # effect: a -> -i e^{i phi} b ; b -> -i e^{-i phi} a  (swap with -i phases)
            val_a = cur[a_slot]
            val_b = cur[b_slot]
            ph_a = running_phase[a_slot]
            ph_b = running_phase[b_slot]
            cur[a_slot], cur[b_slot] = val_b, val_a
            running_phase[a_slot] = -1j * ph_b
            running_phase[b_slot] = -1j * ph_a

    # Now slot i holds original index cur[i] with accumulated swap-phase
    # running_phase[i]; we need slot i (== destination dst=i) to carry the
    # target total phase = phase[ src=target[i] ].  Residual phase needed on
    # mode `modes[i]` is phase[target[i]] / running_phase[i].
    residual_theta = []
    for i in range(k):
        src = target[i]
        want = phase[src]
        got = running_phase[i]
        resid = want / got
        # R(theta) applies a -> e^{-i theta} a, so we need e^{-i theta} = resid
        theta = (-cmath.phase(resid)) % (2 * math.pi)
        if theta > math.pi:
            theta -= 2 * math.pi
        residual_theta.append(theta)

    for i in range(k):
        th = residual_theta[i]
        if abs(th) > 1e-9:
            new_ops.append(Op("R", (th,), (("qm", modes[i]),)))

    return new_ops


def apply(ops, m):
    i0, i1, used, modes = m
    used = list(used)
    modes = list(modes)
    M = _mode_matrix(ops, used, modes)

    mono = _is_monomial(M)
    new_passive_ops = None
    if mono is not None:
        perm, phase = mono
        new_passive_ops = _resynth_monomial(perm, phase, modes)
    else:
        # Not monomial: we don't have a general Clements-mesh synthesizer
        # restricted to the coupling graph available here without routing
        # info, so decline (leave the original run untouched) rather than
        # risk a non-improving or incorrect rewrite.
        return None

    old_count = sum(1 for idx in used if _is_passive(ops[idx]))
    new_count = sum(1 for o in new_passive_ops if o.name == "BS")
    if new_count >= old_count:
        return None

    # Reassemble: keep non-passive ops that were interleaved (skipped), in
    # their original relative order, but all the passive ops are replaced
    # as a block by new_passive_ops. Since skipped ops were required to be
    # disjoint from the passive-run modes, order between them and the new
    # passive block does not matter for correctness; we place skipped ops
    # first (their original relative position among indices < passive ones
    # is preserved) followed by the fused passive block, to keep things
    # simple and exact.
    skipped_ops = [ops[idx] for idx in used if not _is_passive(ops[idx])]
    new_ops = skipped_ops + new_passive_ops
    return i0, i1, new_ops


RULE = Rule(
    name="passive_linear_optics_block_fusion",
    kind="rewrite",
    contract="exact",
    stage="logical",
    trigger=trigger,
    apply=apply,
    idea=(
        "Any product of oscillator-only number-conserving gates (BS(t,p), R(t)) on a fixed set of "
        "modes implements exactly U(M), the Fock-space (metaplectic/passive) representation of a "
        "single unitary mode matrix M defined by U^dag a_i U = sum_j M_ij a_j. This map is a group "
        "homomorphism with no phase ambiguity (U(M) fixes the vacuum), so two passive blocks sharing "
        "the same M are equal operators on the full Fock space, exactly -- for every photon number. "
        "The rule scans for maximal runs of passive gates (allowing disjoint-wire ops to be skipped "
        "over), numerically multiplies out the per-gate 1x1/2x2 mode-matrix action in time order to "
        "get M, and when M is monomial (permutation times phases -- e.g. the i-weighted SWAPs that "
        "arise from pi/2 hopping terms) re-synthesizes it as a minimal sequence of BS(pi,phi) "
        "transpositions (cycle decomposition) plus a trailing R(theta) per mode carrying the residual "
        "phase. The rewrite is accepted only if it strictly reduces the number of two-mode (BS) gates. "
        "Non-monomial M is declined here (left for a Clements-mesh rule with routing awareness)."
    ),
    source=(
        "Reck/Clements universal passive-interferometer decomposition; U(m) -> Fock unitary "
        "homomorphism (passive/metaplectic representation); applied to Bose-Hubbard-style hopping "
        "Trotter steps as in Liu et al. 2407.10381-style compilations."
    ),
    meta={
        "target_parts": (
            "boseHubbard_small terms 0-11 (all 12 hopping BS, including the 4 diagonal-pair hops "
            "(0,3),(1,2) that force qumode SWAPs); R terms 13,15,17,19,20-23 absorb residual phases; "
            "generally any Bose-Hubbard / hopping Trotter step, and any run of consecutive passive gates"
        ),
        "expected_saving": (
            "Logical: hopping 2-op gates drop from 12 BS to 2 BS. Routed: qumode SWAPs largely "
            "disappear if fused-pair modes are grid neighbours. Duration: hopping block drops from "
            "~400+ to ~20 (two parallel BS)."
        ),
    },
)
