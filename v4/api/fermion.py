"""Free fermions: Jordan-Wigner, Majorana bilinears and the Givens cascade.

`free_fermion_gaussian_resynthesis` is v4's single biggest original win (tfim_6 8560 -> 3354, -60.8%) and
every expensive part of it was this machinery. tfim_6 is also the one circuit where BOTH baseline levers
have zero headroom (0 foldable rotations, 0 fixable angles at any K) - so this module is where the
project's own advantage lives, and it belongs in the API rather than in one rule's body.

    majorana(q, kind)              the Majorana operator index of X / Y on wire q under Jordan-Wigner
    bilinear_of(pauli, n)          -> (a, b) if the Pauli is a Majorana bilinear i g_a g_b, else None
    is_gaussian(ops)               every non-Clifford rotation is about a Majorana bilinear
    plane_rotation(a, b, theta, m) the 2m x 2m orthogonal matrix of exp(-i theta/2 . i g_a g_b)
    orthogonal_of(ops)             the single R in O(2n) a Gaussian circuit acts as on the Majoranas
    givens(R)                      factor R into adjacent-plane rotations: [(a, b, theta)], <= n(2n-1)
    emit(rotations, n)             the plane rotations back as an op list of Pauli rotations

Convention: Jordan-Wigner with g_{2q} = Z_0..Z_{q-1} X_q and g_{2q+1} = Z_0..Z_{q-1} Y_q, so that
i g_{2q} g_{2q+1} = -Z_q and the Pauli pairs that appear in nearest-neighbour Hamiltonians (XX, YY, XY,
YX on adjacent wires, and Z on one wire) are all bilinears.
"""
from __future__ import annotations

import math

import numpy as np

from . import pauli as P


def majorana_pauli(j: int, n: int) -> tuple:
    """g_j as a Pauli (x, z, sign): g_{2q} = Z_0..Z_{q-1} X_q, g_{2q+1} = Z_0..Z_{q-1} Y_q."""
    q, kind = divmod(int(j), 2)
    if not 0 <= q < n:
        raise ValueError(f"majorana index {j} out of range for n={n}")
    tail = (1 << q) - 1                      # Z string on wires 0..q-1
    if kind == 0:
        return (1 << q, tail, 1)             # X_q with the Z tail
    return (1 << q, tail | (1 << q), 1)      # Y_q with the Z tail


def _pauli_table(n: int) -> dict:
    """{(x, z): (a, b)} for every bilinear i g_a g_b, a < b, on n wires."""
    out = {}
    paulis = [majorana_pauli(j, n) for j in range(2 * n)]
    for a in range(2 * n):
        for b in range(a + 1, 2 * n):
            pa, pb = paulis[a], paulis[b]
            x, z = pa[0] ^ pb[0], pa[1] ^ pb[1]
            out.setdefault((x, z), (a, b))
    return out


_TABLES: dict = {}


def bilinear_of(p, n: int):
    """(a, b) if the Pauli `p` is i g_a g_b (a < b) up to sign, else None."""
    if n not in _TABLES:
        _TABLES[n] = _pauli_table(n)
    return _TABLES[n].get((p[0], p[1]))


def is_gaussian(ops, n: int | None = None) -> bool:
    """True if every rotation of `ops`, front-framed, is about a Majorana bilinear."""
    recs = P.frames(ops)
    if recs is None:
        return False
    if n is None:
        n = 1 + max((q for op in ops for q in op[1]), default=-1)
    return all(r.on_grid or bilinear_of(r.p, n) is not None for r in recs)


def plane_rotation(a: int, b: int, theta: float, m: int) -> np.ndarray:
    """The 2m x 2m orthogonal matrix of exp(-i theta/2 . i g_a g_b) acting on the Majoranas:
    a rotation by theta in the (a, b) plane."""
    R = np.eye(2 * m)
    c, s = math.cos(theta), math.sin(theta)
    R[a, a], R[b, b] = c, c
    R[a, b], R[b, a] = -s, s
    return R


def orthogonal_of(ops, n: int | None = None):
    """The single R in O(2n) a Gaussian circuit acts as on the Majoranas, or None if it is not Gaussian.

    Each Pauli rotation about i g_a g_b by theta is one plane rotation; the circuit's R is their ordered
    product."""
    recs = P.frames(ops)
    if recs is None:
        return None
    if n is None:
        n = 1 + max((q for op in ops for q in op[1]), default=-1)
    R = np.eye(2 * n)
    for r in recs:
        ab = bilinear_of(r.p, n)
        if ab is None:
            if r.on_grid:
                continue
            return None
        a, b = ab
        R = plane_rotation(a, b, r.sign * r.theta, n) @ R
    return R


def givens(R, tol: float = 1e-12) -> tuple:
    """Factor R in O(2m) into ADJACENT-plane rotations.

    -> ([(a, a+1, theta)], signs). Reconstruct R exactly as

        Q = diag(signs)
        for a, b, th in rotations:  Q = plane_rotation(a, b, th, m) @ Q

    so the list is in APPLICATION order and `signs` is the residual +-1 diagonal (a Clifford: each -1 is
    a Majorana sign flip, i.e. an X or Z on one wire). At most m(2m-1) rotations, which is the Givens
    bound and what `free_fermion_gaussian_resynthesis` emits.
    """
    A = np.array(R, dtype=float)
    d = A.shape[0]
    collected = []
    for col in range(d - 1):
        for row in range(d - 1, col, -1):
            x, y = A[row - 1, col], A[row, col]
            if abs(y) <= tol:
                continue
            th = math.atan2(y, x)
            G = np.eye(d)
            c, s = math.cos(th), math.sin(th)
            G[row - 1, row - 1], G[row, row] = c, c
            G[row - 1, row], G[row, row - 1] = s, -s
            A = G @ A                                     # G_last ... G_1 R = diag(+-1)
            collected.append((row - 1, row, th))          # G = plane_rotation(a, b, -th), so G^T is +th
    signs = tuple(int(round(A[i, i])) for i in range(d))
    return list(reversed(collected)), signs


def emit(rotations, n: int) -> list:
    """Plane rotations [(a, b, theta)] back as a Pauli-rotation op list.

    Each bilinear i g_a g_b is one Pauli; the op list conjugates a Z-rotation into that Pauli frame with
    Cliffords. Adjacent planes (b = a + 1) give the short local forms: (2q, 2q+1) is Z_q, and
    (2q+1, 2q+2) is X_q X_{q+1} up to Cliffords."""
    out = []
    for a, b, th in rotations:
        if abs(th) < 1e-15:
            continue
        if b == a + 1 and a % 2 == 0:                     # i g_{2q} g_{2q+1} = -Z_q
            q = a // 2
            out.append(("rz", (q,), -float(th)))
        elif b == a + 1:                                  # i g_{2q+1} g_{2q+2} ~ X_q X_{q+1} conjugated
            q = (a - 1) // 2
            out += [("h", (q,), None), ("h", (q + 1,), None), ("cx", (q, q + 1), None),
                    ("rz", (q + 1,), float(th)), ("cx", (q, q + 1), None),
                    ("h", (q + 1,), None), ("h", (q,), None)]
        else:
            raise ValueError(f"emit only handles adjacent planes, got ({a}, {b})")
    return out


def majorana_rank(ops, n: int | None = None) -> int:
    """The number of independent Majorana PLANES the circuit's rotations touch - a cheap upper bound on
    how many plane rotations a Givens cascade can need."""
    recs = P.frames(ops)
    if recs is None:
        return -1
    if n is None:
        n = 1 + max((q for op in ops for q in op[1]), default=-1)
    seen = set()
    for r in recs:
        ab = bilinear_of(r.p, n)
        if ab:
            seen.update(ab)
    return len(seen)
