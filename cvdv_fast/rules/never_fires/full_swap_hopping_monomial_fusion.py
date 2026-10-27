from cvdv_fast.api import Rule, Op
import math
import cmath


def _wire_mode(w):
    # ('qm', j) -> j ; else None
    if len(w) == 2 and w[0] == "qm":
        return w[1]
    return None


def _is_full_swap_bs(op):
    # BS(t, p): e^{-it/2 (e^{ip} a^+ b + h.c.)} ; full-swap monomial needs t = pi (mod 2pi)
    # and p a multiple of pi/2.
    if op.name != "BS":
        return None
    if len(op.wires) != 2:
        return None
    m0 = _wire_mode(op.wires[0])
    m1 = _wire_mode(op.wires[1])
    if m0 is None or m1 is None:
        return None
    t, p = complex(op.params[0]).real, complex(op.params[1]).real
    # t = pi mod 2pi
    k = (t - math.pi) / (2 * math.pi)
    if abs(k - round(k)) > 1e-9:
        return None
    # p a multiple of pi/2
    q = p / (math.pi / 2)
    if abs(q - round(q)) > 1e-9:
        return None
    qmod = round(q) % 4
    return (m0, m1, qmod)


def _bs_monomial(m0, m1, qmod, n_modes, sigma, e):
    """Apply the monomial action of BS(pi, qmod*pi/2) on (m0,m1) to (sigma, e) in Heisenberg
    composition order (this BS acts first among already-composed gates, i.e. new gate is
    pre-applied on the input side: M_total = M_old * M_new, since time order = emission
    order and we are composing operators acting on the Heisenberg picture mode vector in
    emission order).

    Heisenberg action of BS(pi, p) on modes (j,k):
      U^+ a_j U = cos(pi/2)... for t=pi: U^+ a_j U = -i e^{ip} a_k
                  U^+ a_k U = -i e^{-ip} a_j
    (BS(t,p) = exp(-i t/2 (e^{ip} a^+_j a_k + h.c.)); standard beamsplitter Heisenberg relation:
      U^+ a_j U = cos(t/2) a_j - i sin(t/2) e^{ip} a_k
      U^+ a_k U = cos(t/2) a_k - i sin(t/2) e^{-ip} a_j
    at t = pi: cos(pi/2)=0, sin(pi/2)=1, giving
      U^+ a_j U = -i e^{ip} a_k ,  U^+ a_k U = -i e^{-ip} a_j

    We track monomial maps as: a_j -> i^{e[j]} a_{sigma[j]} (sigma: current index -> index
    this mode's operator maps to under the accumulated unitary's Heisenberg action composed
    so far, built up by LEFT-multiplying with each new gate's action since each new op is the
    next unitary to act, and Heisenberg actions compose in reverse operator order; here we
    just directly recompute composition term-by-term using functional composition of the
    per-step maps in emission order, which is what matters operationally).
    """
    # power of i for -i e^{ip}: -i = i^{-1} = i^3 ; e^{ip} = i^qmod
    e_j_to_k = (3 + qmod) % 4          # a_j -> i^{e_j_to_k} a_k
    e_k_to_j = (3 + (-qmod)) % 4       # a_k -> i^{e_k_to_j} a_j

    new_sigma = list(sigma)
    new_e = list(e)
    for src in range(n_modes):
        tgt = sigma[src]
        if tgt == m0:
            new_sigma[src] = m1
            new_e[src] = (e[src] + e_j_to_k) % 4
        elif tgt == m1:
            new_sigma[src] = m0
            new_e[src] = (e[src] + e_k_to_j) % 4
    return new_sigma, new_e


def _compose_run(run_matches, n_modes):
    sigma = list(range(n_modes))
    e = [0] * n_modes
    for (m0, m1, qmod) in run_matches:
        sigma, e = _bs_monomial(m0, m1, qmod, n_modes, sigma, e)
    return sigma, e


def _coupled_pairs_from_wires(ops, run_idx):
    pass


def trigger(ops):
    out = []
    n = len(ops)
    i = 0
    while i < n:
        info = _is_full_swap_bs(ops[i])
        if info is None:
            i += 1
            continue
        j = i
        modes_seen = set()
        run = []
        while j < n:
            info_j = _is_full_swap_bs(ops[j])
            if info_j is None:
                break
            m0, m1, qmod = info_j
            run.append((m0, m1, qmod))
            modes_seen.add(m0)
            modes_seen.add(m1)
            j += 1
        if len(run) >= 2:
            out.append((i, j - 1, tuple(run), tuple(sorted(modes_seen))))
        i = j if j > i else i + 1
    return out


def apply(ops, m):
    i0, i1, run, modes_touched = m
    n_modes = max(modes_touched) + 1

    sigma, e = _compose_run(list(run), n_modes)

    # build cycles of sigma restricted to touched modes (modes not touched are fixed points)
    visited = set()
    cycles = []
    for start in modes_touched:
        if start in visited or sigma[start] == start:
            visited.add(start)
            continue
        cyc = [start]
        visited.add(start)
        nxt = sigma[start]
        while nxt != start:
            cyc.append(nxt)
            visited.add(nxt)
            nxt = sigma[nxt]
        cycles.append(cyc)

    # Determine coupled pairs: gather all mode-mode pairs that appeared as BS wire pairs in the
    # original run; a cycle of length L decomposes into L-1 transpositions. We require each
    # transposition we emit to be between modes that were directly coupled in the original run
    # (same adjacency assumption as the source circuit respects routing); if a needed pair
    # wasn't present among the original coupled pairs, decline.
    coupled = set()
    for (a, b, _q) in run:
        coupled.add(frozenset((a, b)))

    new_ops = []
    e_emitted = [0] * n_modes
    sigma_emitted = list(range(n_modes))

    def emit_transposition(a, b):
        if frozenset((a, b)) not in coupled:
            return False
        new_ops.append(Op("BS", (-math.pi, 0.0), (("qm", a), ("qm", b))))
        nonlocal_sigma, nonlocal_e = _bs_monomial(a, b, 0, n_modes, sigma_emitted, e_emitted)
        sigma_emitted[:] = nonlocal_sigma
        e_emitted[:] = nonlocal_e
        return True

    for cyc in cycles:
        L = len(cyc)
        if L < 2:
            continue
        # decompose cycle (c0 c1 ... c_{L-1}) into adjacent-ish transpositions using only
        # pairs present in `coupled`; try the natural transposition chain first.
        ok = True
        # Standard decomposition: (c0 c1 ... c_{L-1}) = (c0 c1)(c1 c2)...(c_{L-2} c_{L-1})
        # applied in a specific order reproduces the cycle; we verify by directly checking
        # the resulting sigma_emitted against target sigma at the end instead of trusting
        # the decomposition formula, and bail out (decline) if it doesn't match.
        for k in range(L - 1):
            a, b = cyc[k], cyc[k + 1]
            if not emit_transposition(a, b):
                ok = False
                break
        if not ok:
            return None

    if sigma_emitted != sigma:
        return None

    # Now fix up phases with R gates: need e^{-i t_k} = i^{(e[k] - e_emitted[k]) mod 4}
    # R(t) = e^{-i t n}; Heisenberg: R^+ a R = e^{-it} a. So choose t_k such that
    # e^{-i t_k} = i^{diff}, i.e. t_k = -diff * pi/2 (mod 2pi), mapped into {0,-pi/2,pi,pi/2}.
    phase_map = {0: 0.0, 1: -math.pi / 2, 2: math.pi, 3: math.pi / 2}

    r_ops = []
    for k in range(n_modes):
        diff = (e[k] - e_emitted[k]) % 4
        if diff == 0:
            continue
        t_k = phase_map[diff]
        r_ops.append(Op("R", (t_k,), (("qm", k),)))

    new_ops.extend(r_ops)

    return i0, i1, new_ops


RULE = Rule(
    name="full_swap_hopping_monomial_fusion",
    kind="rewrite",
    contract="exact",
    stage="logical",
    trigger=trigger,
    apply=apply,
    idea=(
        "A run of consecutive full-swap hopping gates BS(t,p) with t = pi (mod 2pi) and p a "
        "multiple of pi/2 is monomial in the Heisenberg (passive) representation: each such gate "
        "sends a_j -> i^e a_k, a_k -> i^e' a_j for integers e,e' mod 4, and products of monomial "
        "maps are monomial (permutation sigma times powers of i on each mode, tracked with pure "
        "integer arithmetic, never floats or complex numbers). Composing the whole run gives a "
        "target (sigma, e). The rule re-synthesizes this exactly as: one BS(-pi,0) transposition "
        "per transposition in the cycle decomposition of sigma (each only emitted if the mode "
        "pair was actually coupled somewhere in the original run, so routing stays legal), "
        "followed by per-mode R(t_k) phase corrections with t_k in {0,-pi/2,pi,pi/2} fixing up any "
        "remaining power-of-i mismatch via R's exact Heisenberg action R^+ a R = e^{-it} a. Because "
        "passive unitaries are fixed by their action on mode operators and both circuits fix the "
        "vacuum, equal (sigma,e) implies exactly equal unitaries on the whole Fock space. The rule "
        "declines (returns None) whenever a needed transposition pair in the cycle decomposition "
        "was never directly coupled in the source run, so it never fabricates illegal 2-op gates."
    ),
    source=(
        "Monomial subgroup of U(m) = permutation matrices times U(1)^m (generalized permutation "
        "group), applied to passive linear-optical/bosonic networks; same style of exact "
        "group-homomorphism bookkeeping as Liu et al. 2407.10381's treatment of Heisenberg-Weyl "
        "composition, specialized to the pi/2-angle beamsplitter subgroup relevant to full-swap "
        "Bose-Hubbard hopping blocks."
    ),
)
