"""Phase polynomials: the affine parity label of every wire over a Hadamard-free segment.

Inside a Hadamard-free segment of {cx, x} and diagonal gates, every wire carries a classical affine
function of the input bits:

    label(q) = (parity mask p_q over the segment's input wires, constant bit c_q)

with the two update rules

    cx a, b :  p_b ^= p_a ;  c_b ^= c_a
    x  a    :  c_a ^= 1

A diagonal rotation rz(theta) on wire q therefore applies the phase exp(i theta (-1)^{<p_q, x> ^ c_q} ...)
i.e. it acts about the Z-PARITY operator labelled by (p_q, c_q). Two rotations with the SAME label act
about the same operator, commute, and their angles add. That identity is exact and needs no matrices.

This module is used twice:

* as a rule primitive - `labels(ops)` replaces the hand-rolled label tracking in v3's retired
  `phase_polynomial_rotation_merge`;
* as the WITNESS of the `algebraic` certificate (V4_README 6.2). The phase-folding class produced EVERY
  admitted angle rule in v3, and today each of its rewrites costs a 48 ms full-width 256x256 matrix build
  (120 of qft_8's 190 checks). Re-deriving the labels is O(ops) with no matrices, and unlike the matrix
  check at 11-20 qubits it is a PROOF rather than a Haar-statevector lower bound.

    labels(ops)                     -> LabelMap or None (None = the segment is not Hadamard-free)
    rotation_labels(ops)            -> [(pos, theta, label)] for every rotation in a Hadamard-free list
    equal_label_pairs(ops)          -> [(i, j, sign)] rotations that provably merge
    witness(old_ops, new_ops, n)    -> (ok, reason): the phase polynomials and the linear parts agree
"""
from __future__ import annotations

import math
from dataclasses import dataclass

QUARTER = math.pi / 4
CUT = ("h", "s", "sdg")           # s / sdg are diagonal, so they do NOT cut; see DIAGONAL below
DIAGONAL = ("z", "s", "sdg", "t", "tdg", "rz", "cz")
LINEAR = ("cx", "x")


@dataclass(frozen=True)
class LabelMap:
    """Per-wire affine parity labels after a Hadamard-free op list: `p[q]` mask, `c[q]` constant bit."""
    n: int
    p: tuple
    c: tuple

    def label(self, q: int) -> tuple:
        return (self.p[q], self.c[q])


def is_hadamard_free(ops) -> bool:
    return all(op[0] in DIAGONAL or op[0] in LINEAR for op in ops)


def labels(ops, n: int | None = None):
    """Affine parity label of every wire after `ops`. None if `ops` is not Hadamard-free.

    Diagonal gates do not change a label (they are phases); cx and x are the only linear updates."""
    if n is None:
        n = 1 + max((q for op in ops for q in op[1]), default=-1)
    p = [1 << q for q in range(n)]
    c = [0] * n
    for op in ops:
        g, qs = op[0], tuple(int(q) for q in op[1])
        if g in DIAGONAL:
            continue
        if g == "cx":
            a, b = qs
            p[b] ^= p[a]
            c[b] ^= c[a]
        elif g == "x":
            c[qs[0]] ^= 1
        else:
            return None
    return LabelMap(n, tuple(p), tuple(c))


def rotation_labels(ops, n: int | None = None):
    """[(position, theta, (mask, const))] for every t / tdg / rz in a Hadamard-free op list; None if the
    list is not Hadamard-free. The label is the one in force WHERE the rotation sits."""
    if n is None:
        n = 1 + max((q for op in ops for q in op[1]), default=-1)
    p = [1 << q for q in range(n)]
    c = [0] * n
    out = []
    for pos, op in enumerate(ops):
        g, qs = op[0], tuple(int(q) for q in op[1])
        a = op[2] if len(op) > 2 else None
        if g == "t":
            out.append((pos, QUARTER, (p[qs[0]], c[qs[0]])))
        elif g == "tdg":
            out.append((pos, -QUARTER, (p[qs[0]], c[qs[0]])))
        elif g == "rz":
            out.append((pos, float(a), (p[qs[0]], c[qs[0]])))
        elif g == "cx":
            x, y = qs
            p[y] ^= p[x]
            c[y] ^= c[x]
        elif g == "x":
            c[qs[0]] ^= 1
        elif g in DIAGONAL:
            continue
        else:
            return None
    return out


def polynomial(ops, n: int | None = None):
    """The phase polynomial of a Hadamard-free op list: {(mask, const): total angle}, plus the final
    LabelMap. Two op lists with the same polynomial AND the same LabelMap are equal up to global phase."""
    rots = rotation_labels(ops, n)
    if rots is None:
        return None
    poly: dict = {}
    for _pos, theta, lab in rots:
        if lab[0] == 0:                         # the label is a constant: a global phase, not observable
            continue
        poly[lab] = poly.get(lab, 0.0) + theta
    lm = labels(ops, n)
    return poly, lm


def equal_label_pairs(ops, n: int | None = None) -> list:
    """[(i, j, +1)] - positions of two rotations with the SAME parity label, so their angles add. The
    pairs are disjoint, so they can be applied one at a time."""
    rots = rotation_labels(ops, n)
    if rots is None:
        return []
    seen: dict = {}
    out, used = [], set()
    for pos, _theta, lab in rots:
        if lab[0] == 0:
            continue
        if lab in seen and seen[lab] not in used and pos not in used:
            out.append((seen[lab], pos, 1))
            used.update((seen[lab], pos))
            del seen[lab]
        else:
            seen[lab] = pos
    return out


def witness(old_ops, new_ops, n: int, tol: float = 1e-12) -> tuple:
    """The `algebraic` certificate for the phase-folding class: both sides Hadamard-free with the same
    phase polynomial (modulo 2pi per label) and the same affine label map.

    -> (ok, reason). `ok=True` is a PROOF: a Hadamard-free circuit is exactly (diagonal phase
    polynomial) composed with (affine permutation), and both factors are compared here, in O(ops) with no
    matrices.

    **`ok=False` is NOT a refutation.** The comparison is label-wise, and the labels are not independent:
    for a parity mask p, the indicators of (p, 0) and (p, 1) differ by a constant, since
    v_(p,1) = 1 - v_(p,0). So the observable phase depends only on the DIFFERENCES
    theta_(p,0) - theta_(p,1), and angle mass may legitimately move between the two labels of one mask
    without changing the circuit at all. Requiring each label to match is sufficient for equality and
    deliberately conservative; a mismatch means "this witness does not establish equality", and the
    caller must fall through to the exact or numeric check. An earlier version of the certificate layer
    reported this mismatch as a certified refutation, and rejected `same_pauli_merge` on hhl_8 - a rule
    v3 verified and the planted-bug gate admits.
    """
    a, b = polynomial(old_ops, n), polynomial(new_ops, n)
    if a is None or b is None:
        return False, "not Hadamard-free: the phase-polynomial witness does not apply"
    pa, la = a
    pb, lb = b
    if la != lb:
        return False, f"affine label maps differ: {la.p}/{la.c} vs {lb.p}/{lb.c}"
    for lab in set(pa) | set(pb):
        d = (pa.get(lab, 0.0) - pb.get(lab, 0.0)) / (2 * math.pi)
        if abs(d - round(d)) * 2 * math.pi > tol:
            return False, (f"phase polynomial differs on label (mask {lab[0]:#x}, const {lab[1]}): "
                           f"{pa.get(lab, 0.0):.12g} vs {pb.get(lab, 0.0):.12g}")
    return True, ""
