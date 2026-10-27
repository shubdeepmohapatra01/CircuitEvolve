"""Merge same-axis Pauli exponentials inside a maximal commuting cluster of the front-frame product.

Circuit = (ordered product of Pauli exponentials) then (residual Clifford). Consecutive exponentials whose
Paulis pairwise commute may be permuted freely, so every pair with the same axis merges even when it does
not commute with rotations outside the cluster. A cluster's Paulis are simultaneously diagonalizable, and
two of them get the same parity label after diagonalization exactly when they have the same axis (the
diagonalizing Clifford is a bijection on Paulis), so the label collapse and the axis merge are the same
event. Each surviving axis is re-emitted as a Pauli gadget V^dag rz V; the window's own Cliffords follow.
"""
from v4.api import Precondition, Rule
from v4.api import dv, pauli
from v4.api.dv import reduce_angle


def _clusters(recs):
    """Consecutive maximal pairwise-commuting runs of records."""
    out, cur = [], []
    for r in recs:
        if all(pauli.commutes(r.p, q.p) for q in cur):
            cur.append(r)
        else:
            out.append(cur)
            cur = [r]
    if cur:
        out.append(cur)
    return out


def _merged(cluster):
    """[(x, z, angle)] per distinct axis, first-occurrence order; angle is relative to the +1 Pauli."""
    order, acc = [], {}
    for r in cluster:
        k = r.key
        if k not in acc:
            acc[k] = 0.0
            order.append(k)
        acc[k] += r.sign * r.theta
    return [(k[0], k[1], reduce_angle(acc[k])) for k in order]


def _off(theta):
    return not dv.on_grid(theta)


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    recs = pauli.frames(c.ops)
    if not recs or len(recs) < 2:
        return []
    out = []
    for cl in _clusters(recs):
        if len(cl) < 2 or len({r.key for r in cl}) == len(cl):
            continue
        old = sum(1 for r in cl if _off(r.theta))
        new = sum(1 for _, _, a in _merged(cl) if _off(a))
        if new < old:
            out.append((cl[0].pos, cl[-1].pos))
    return out


def _gadget(x, z, theta):
    """Time-ordered ops for exp(-i theta P/2), P = +(x, z) Hermitian Pauli."""
    supp = [q for q in range(max(x | z, 1).bit_length()) if ((x | z) >> q) & 1]
    p = (x, z, 1)
    pre = []
    for q in supp:
        xq, zq = (x >> q) & 1, (z >> q) & 1
        if xq and zq:
            pre += [("sdg", (q,), None), ("h", (q,), None)]
        elif xq:
            pre.append(("h", (q,), None))
    for g, qs, _ in pre:
        p = pauli.conjugate(p, g, qs)
    t = supp[-1]
    for q in supp[:-1]:
        pre.append(("cx", (q, t), None))
        p = pauli.conjugate(p, "cx", (q, t))
    assert p[0] == 0 and p[1] == 1 << t, p
    post = []
    for g, qs, _ in reversed(pre):
        post.append(({"sdg": "s", "s": "sdg"}.get(g, g), qs, None))
    return pre + [("rz", (t,), p[2] * theta)] + post


def apply_match(c, m):
    lo, hi = m
    ops = list(c.ops)
    win = ops[lo:hi + 1]
    recs = pauli.frames(win)
    new = []
    for x, z, a in _merged(recs):
        if abs(a) > 1e-12:
            new += _gadget(x, z, a)
    new += [op for op in win if op[0] in pauli.CLIFFORDS]
    return dv.with_ops(c, ops[:lo] + new + ops[hi + 1:])


RULE = Rule(
    name="commuting_pauli_cluster_diagonalization",
    domain="dv",
    kind="procedure",
    error_class="exact",
    resource_class="unitary",
    source="van den Berg & Temme, Quantum 4, 322 (2020); Aaronson-Gottesman; Amy-Azimzadeh-Mosca 2018",
    idea="Split the front-frame Pauli-exponential product into maximal commuting clusters; inside a cluster "
         "the order is free, so same-axis exponentials (equivalently, equal parity labels after simultaneous "
         "diagonalization) merge; re-emit one Pauli gadget per distinct axis.",
    precondition=Precondition(families=("dv_angle",), needs=("rotations", "nonclifford_rz"),
                              forbids=(), min_qubits=2, max_qubits=14,
                              note="needs >= 2 same-axis rotations inside one commuting cluster"),
    trigger=find_matches,
    apply=apply_match,
)
