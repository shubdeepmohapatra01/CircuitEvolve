"""Equal-angle pair carry doubling: Rz(t) Rz(t) on bits x1, x2  ==  Rz(t) on (x1 xor x2), Rz(2t) on (x1 and x2).

For bits, x1 + x2 = (x1 xor x2) + 2 (x1 and x2), so e^{i t (x1+x2)} = e^{i t s} e^{2 i t c}. When 2t is a
multiple of pi/4 the second factor is a Clifford/T gate and gridsynth pays nothing for it: two off-grid
rotations become one. Each rotation's Pauli eigenvalue bit is copied to a clean ancilla by a CNOT ladder
(local Cliffords first for X/Y support), the AND is Gidney's 4-T temporary AND computed into a third
ancilla, and - because an op-list circuit has no measurement - uncomputed by its exact unitary inverse.

(The card writes Rz(-t) on the xor wire; diag(1, e^{i t s}) is Rz(+t) up to phase, which is what is used.)
"""
import math

from v4.api import Precondition, Rule
from v4.api import dv, pauli

TOL = 1e-9
MAX_WEIGHT = 6
_INV = {"s": "sdg", "sdg": "s", "t": "tdg", "tdg": "t"}


def _theta(op):
    th = dv.rotation(op)
    return None if th is None else dv.reduce_angle(th)


def _off_grid(op):
    th = dv.rotation(op)
    return th is not None and not dv.on_grid(th)


def _usable(th):
    return abs(th) > TOL and dv.on_grid(2 * abs(th))


def _walk(ops, i, j):
    """Rotation i's Pauli (actual frame, sign included) just before op j, or None if some rotation or
    gate between them blocks the slide."""
    p = pauli.z_on(ops[i][1][0])
    for k in range(i + 1, j):
        g, qs, _ = ops[k]
        if dv.rotation(ops[k]) is not None:
            if not pauli.commutes_with_z(p, qs[0]):
                return None
        elif g in pauli.CLIFFORDS:
            p = pauli.conjugate(p, g, qs)
        else:
            return None
    return p


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    ops = c.ops
    idx = [k for k, op in enumerate(ops) if _off_grid(op)]
    out, used = [], set()
    for a, i in enumerate(idx):
        if i in used:
            continue
        thi = _theta(ops[i])
        if not _usable(thi):
            continue
        p = pauli.z_on(ops[i][1][0])
        k = i + 1
        while k < len(ops):
            g, qs, _ = ops[k]
            if dv.rotation(ops[k]) is not None:
                q = qs[0]
                if not pauli.commutes_with_z(p, q):
                    break
                if (k not in used and _off_grid(ops[k]) and abs(abs(_theta(ops[k])) - abs(thi)) <= TOL
                        and not (p[0] == 0 and p[1] == (1 << q))
                        and pauli.weight(p) + 1 <= MAX_WEIGHT):
                    out.append((i, k))
                    used.update((i, k))
                    break
            elif g in pauli.CLIFFORDS:
                p = pauli.conjugate(p, g, qs)
            else:
                break
            k += 1
    return out


def _inverse(seq):
    out = []
    for g, qs, a in reversed(seq):
        out.append((_INV.get(g, g), qs, a))
    return out


def _and_compute(a, b, t):
    """Gidney temporary AND into a clean t (4 T)."""
    return [("h", (t,), None), ("t", (t,), None), ("cx", (a, t), None), ("cx", (b, t), None),
            ("cx", (t, a), None), ("cx", (t, b), None), ("tdg", (a,), None), ("tdg", (b,), None),
            ("t", (t,), None), ("cx", (t, a), None), ("cx", (t, b), None), ("h", (t,), None),
            ("s", (t,), None)]


def apply_match(c, m):
    if not dv.is_angle_circuit(c):
        return c
    i, j = m
    ops = list(c.ops)
    p = _walk(ops, i, j)
    if p is None:
        return c
    qj = ops[j][1][0]
    phi_i = p[2] * _theta(ops[i])
    phi_j = _theta(ops[j])
    theta = abs(phi_j)
    n = c.n
    a1, a2, cc = n, n + 1, n + 2

    basis, ladder = [], []
    for q in range(n):
        xb, zb = (p[0] >> q) & 1, (p[1] >> q) & 1
        if not (xb or zb):
            continue
        if xb and zb:
            basis += [("sdg", (q,), None), ("h", (q,), None)]
        elif xb:
            basis.append(("h", (q,), None))
        ladder.append(("cx", (q, a1), None))
    ladder.append(("cx", (qj, a2), None))
    flips = []
    if phi_i < 0:
        flips.append(("x", (a1,), None))
    if phi_j < 0:
        flips.append(("x", (a2,), None))

    comp = _and_compute(a1, a2, cc)
    core = (comp + [("cx", (a1, a2), None), ("rz", (a2,), theta), ("rz", (cc,), 2 * theta),
                    ("cx", (a1, a2), None)] + _inverse(comp))
    block = basis + ladder + flips + core + _inverse(flips) + _inverse(ladder) + _inverse(basis)

    new = ops[:i] + ops[i + 1:j] + block + ops[j + 1:]
    return dv.Circuit(n + 3, dv.normalize(new), dict(c.meta))


RULE = Rule(
    name="equal_angle_pair_carry_doubling",
    domain="dv",
    kind="rewrite",
    error_class="exact",
    resource_class="ancilla",
    precondition=Precondition(families=("dv_angle",), needs=("nonclifford_rz", "ancilla_room"),
                              min_qubits=2, max_qubits=20,
                              note="needs two off-grid rotations of equal |angle| whose double is on the pi/4 grid"),
    source="Kivlichan et al. Quantum 4, 296 (2020) Hamming weight phasing (k = 2 carry); "
           "Gidney Quantum 2, 74 (2018) temporary AND",
    idea="Two equal-angle rotations about commuting Paulis: e^{i t (x1+x2)} = e^{i t (x1 xor x2)} "
         "e^{2 i t (x1 and x2)}. Copy both eigenvalue bits to ancillas, compute the AND, rotate the xor wire by "
         "t and the carry wire by 2t (on the pi/4 grid, free), uncompute. One off-grid rotation disappears. "
         "Exact, zero error.",
    trigger=find_matches,
    apply=apply_match,
)
