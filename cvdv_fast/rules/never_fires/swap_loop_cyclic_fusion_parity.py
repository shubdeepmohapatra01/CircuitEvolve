from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

# Gates that act purely on qubit wires: these commute with a BS on mode wires,
# so they can be slid across the gadget boundary without changing the unitary.
QUBIT_ONLY = {"h", "x", "y", "z", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "r"}


def _is_qubit_wires(op):
    return len(op.wires) > 0 and all(w[0] == "q" for w in op.wires)


def _is_bs_pi0(op):
    if op.name != "BS":
        return False
    if len(op.params) < 2:
        return False
    th = complex(op.params[0]).real
    ph = complex(op.params[1]).real
    return abs((th % (2 * math.pi)) - math.pi) < 1e-9 or abs((th % (2 * math.pi)) + math.pi - 2 * math.pi) < 1e-9 \
        and abs(math.sin(ph / 2)) < 1e-9 and abs(math.cos(ph / 2) - 1) < 1e-9 or \
        (abs((th % (2 * math.pi)) - math.pi) < 1e-9 and abs(ph % (2 * math.pi)) < 1e-9)


def _mode_pair(op):
    ms = tuple(w for w in op.wires if w[0] == "qm")
    if len(ms) != 2:
        return None
    return frozenset(ms)


def _find_matching_s(ops, start, mode_pair, end_limit):
    """Scan forward from `start` (inclusive) for a BS(pi,0) on exactly mode_pair,
    allowing only qubit-only gates to be skipped over. Return its index or None."""
    for k in range(start, end_limit):
        op = ops[k]
        if _is_qubit_wires(op):
            continue
        if op.name == "BS" and _mode_pair(op) == mode_pair and _is_bs_pi0(op):
            return k
        # any other op touching the mode pair (or anything not qubit-only and not the S) blocks fusion
        if _mode_pair(op) == mode_pair or (set(w for w in op.wires if w[0] == "qm") & set(mode_pair)):
            return None
        # gate touching unrelated wires: cannot commute past safely unless it's qubit-only (handled above)
        return None
    return None


def trigger(ops):
    out = []
    n = len(ops)
    for i, o in enumerate(ops):
        if o.name != "BS" or not _is_bs_pi0(o):
            continue
        mp = _mode_pair(o)
        if mp is None:
            continue
        # look ahead, skipping only qubit-only gates, for the next S on the same mode pair
        j = _find_matching_s(ops, i + 1, mp, n)
        if j is not None and j > i:
            # record the qubit-only gates in between so apply() can keep them in order
            mid = list(range(i + 1, j))
            out.append((i, j, mp))
    return out


def apply(ops, m):
    i, j, mp = m
    mj, mk = tuple(mp)
    mid = list(ops[i + 1:j])
    new_ops = list(mid) + [Op("R", (math.pi,), (mj,)), Op("R", (math.pi,), (mk,))]
    return i, j, new_ops


RULE = Rule(
    name="swap_loop_cyclic_fusion_parity",
    kind="rewrite",
    stage="both",
    contract="exact",
    trigger=trigger,
    apply=apply,
    idea=(
        "Two consecutive swap-loop gadgets (colocated_mode_swap_loop_pauli_zz) on the same mode pair "
        "(m_j, m_k), separated only by qubit-wire gates, share a junction S-S pair once the second "
        "gadget is cyclically rotated to start with S. Since the loop L = A*S acts as the identity on "
        "both modes (the rectangle closes), L commutes with S, so S*A = S*(A*S)*S^-1 = S*L*S^-1 = L: "
        "any cyclic rotation of the 8-gate word implements the same unitary. The basis-change gates "
        "between the two gadgets live on qubit wires only and commute with S (which acts on mode wires "
        "only), so they pass through unchanged. The adjacent S*S = BS(pi,0)^2 = BS(2pi,0) = "
        "exp(-i pi (a^+b+b^+a)); since a^+b+b^+a has eigenvalues n_a+n_b (mod 2) on the relevant "
        "subspace, exp(-i pi(a^+b+b^+a)) = R_a(pi) R_b(pi) exactly for any cutoff, for every photon "
        "number. Replacing the detected adjacent BS(pi,0), BS(pi,0) pair (with only qubit-only gates "
        "in between, which are kept in place) by R(pi) on each of the two mode wires realizes this "
        "identity, turning a two-op mode-mode gate pair into two one-op single-mode gates with no "
        "change to the overall unitary and no routing impact."
    ),
    source=(
        "Liu et al. 2407.10381-style BCH/closed-loop construction (as in colocated_mode_swap_loop_pauli_zz); "
        "cyclic-rotation + BS(pi,0)^2 = R(pi) x R(pi) parity identity used here to fuse adjacent swap loops"
    ),
    meta={
        "target_parts": (
            "heisenberg_small terms 0-1 (bond 01 XX->YY junction), 3-4 (bond 12), 6-7 (bond 23); "
            "any benchmark with consecutive Pauli-pair terms on the same neighbouring qubits "
            "(Heisenberg/XXZ/XY chains, Ising with transverse layers on the same bond)"
        ),
        "expected_saving": (
            "Per bond: 2 two-op BS(pi,0) are replaced by 2 one-op R(pi); 3 bonds give 6 fewer two-op "
            "gates and up to 6 more one-op gates (fewer if R(pi) on shared modes 1,2 subsequently "
            "cancel pairwise via merge_same_wire_rotations). Expected critical-path reduction "
            "~100-115 (duration ~1673 -> ~1560), gates 148 -> ~144-148, two-op 72 -> 66. No routing "
            "change since BS already acts on co-located neighbouring modes."
        ),
    },
)
