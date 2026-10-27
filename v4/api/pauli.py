"""Pauli frames: propagate a Pauli through Cliffords (P -> C P C^dag), test commutation, and read a whole
circuit's rotations as signed multi-qubit Pauli exponentials.

A Pauli is `(x, z, sign)`: x, z are int bitmasks over qubits (bit q set = X / Z part on qubit q; both = Y
up to the phase tracked in `sign`), sign = +1 / -1. The conjugation tables are derived once from the gate
matrices, exactly as in v3 - `z_on`, `conjugate`, `commutes_with_z` and `is_z` return bit-identical
results. What is new (V4_README section 9):

    frames(ops)            [Record(pos, theta, x, z, sign, on_grid)] - every rotation of the circuit as the
                           signed Pauli exponential it is in the FRONT frame, computed in ONE forward sweep
                           over the op list. v3's two Pauli rules recomputed this per rotation, which is
                           O(rotations x ops); this is O(ops x qubits). On qpe_8 that is 2.1k conjugations
                           instead of 55k, and it was the single largest cost in the P2 book.
    key(p) / sign(p)       the (x, z) axis and the +-1 of a Pauli
    commutes(p, q)         general Pauli commutation (symplectic form), not just with Z on one qubit
    pauli_string(p, n)     'XIZY...' for logs and rule feedback
    weight(p)              number of qubits the Pauli acts on
    axis_eq(p, q)          same axis up to sign -> the two exponentials merge (angles add with that sign)
    CLIFFORDS              the gate names `conjugate` accepts
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

QUARTER = math.pi / 4
GRID_TOL = 1e-9
_INV = {"s": "sdg", "sdg": "s"}
CLIFFORDS = ("h", "s", "sdg", "x", "z", "cx", "cz")


def z_on(q: int):
    return (0, 1 << q, 1)


def x_on(q: int):
    return (1 << q, 0, 1)


def y_on(q: int):
    return (1 << q, 1 << q, 1)


_P1 = {(0, 0): np.eye(2), (1, 0): np.array([[0, 1], [1, 0]]), (1, 1): np.array([[0, -1j], [1j, 0]]),
       (0, 1): np.diag([1, -1])}                                   # (x, z) -> I X Y Z (Hermitian Y)
_GATES = {"h": np.array([[1, 1], [1, -1]]) / np.sqrt(2), "s": np.diag([1, 1j]), "sdg": np.diag([1, -1j]),
          "x": _P1[(1, 0)], "z": _P1[(0, 1)],
          "cx": np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]]),   # control = first qubit
          "cz": np.diag([1, 1, 1, -1])}


def _table(gate):
    """{local (x, z) bits tuple: (new bits tuple, sign)} from the gate matrix, by brute force."""
    U = _GATES[gate]
    k = 1 if U.shape[0] == 2 else 2
    keys = [tuple(v) for v in np.ndindex(*(2,) * (2 * k))]        # (x0, z0[, x1, z1]); qubit 0 = first arg
    mats = {}
    for key_ in keys:
        m = np.array([[1]])
        for j in range(k):
            m = np.kron(m, _P1[(key_[2 * j], key_[2 * j + 1])])
        mats[key_] = m
    out = {}
    for key_, m in mats.items():
        c = U @ m @ U.conj().T
        for k2, m2 in mats.items():
            for sg in (1, -1):
                if np.allclose(c, sg * m2):
                    out[key_] = (k2, sg)
    assert len(out) == len(keys), gate
    return out


_TABLES = {g: _table(g) for g in _GATES}

# Flat lookup tables: the same information as _TABLES, indexed by the packed local bits, so `conjugate` is
# a couple of shifts and one list index instead of a generator expression and a tuple build. Identical
# results - tests/test_p0.py checks every gate and every input against _TABLES.
_FLAT1 = {g: [None] * 4 for g in _GATES if _GATES[g].shape[0] == 2}
_FLAT2 = {g: [None] * 16 for g in _GATES if _GATES[g].shape[0] == 4}
for _g, _t in _TABLES.items():
    for _k, (_new, _sg) in _t.items():
        if len(_k) == 2:
            _FLAT1[_g][(_k[0] << 1) | _k[1]] = (_new[0], _new[1], _sg)
        else:
            _FLAT2[_g][(_k[0] << 3) | (_k[1] << 2) | (_k[2] << 1) | _k[3]] = (_new[0], _new[1], _new[2],
                                                                               _new[3], _sg)


def conjugate(p, gate: str, qubits):
    """C P C^dag for one Clifford gate (h s sdg x z cx cz; cx qubits = (control, target))."""
    x, z, s = p
    t1 = _FLAT1.get(gate)
    if t1 is not None:
        q = qubits[0]
        nx, nz, sg = t1[(((x >> q) & 1) << 1) | ((z >> q) & 1)]
        m = 1 << q
        return ((x & ~m) | (nx << q), (z & ~m) | (nz << q), -s if sg < 0 else s)
    t2 = _FLAT2.get(gate)
    if t2 is None:
        raise ValueError(f"not a Clifford gate: {gate}")
    q0, q1 = qubits[0], qubits[1]
    nx0, nz0, nx1, nz1, sg = t2[(((x >> q0) & 1) << 3) | (((z >> q0) & 1) << 2) |
                                (((x >> q1) & 1) << 1) | ((z >> q1) & 1)]
    m = (1 << q0) | (1 << q1)
    x = (x & ~m) | (nx0 << q0) | (nx1 << q1)
    z = (z & ~m) | (nz0 << q0) | (nz1 << q1)
    return (x, z, -s if sg < 0 else s)


def commutes_with_z(p, q: int) -> bool:
    """[P, Z_q] = 0  <=>  P has no X part on q."""
    return not (p[0] >> q) & 1


def is_z(p, q: int):
    """+1 / -1 if P = +-Z_q exactly (identity elsewhere), else 0."""
    return p[2] if p[0] == 0 and p[1] == 1 << q else 0


# ------------------------------------------------------------------------------------------ general
def key(p) -> tuple:
    """The axis of a Pauli, without its sign: two exponentials with equal keys merge."""
    return (p[0], p[1])


def sign(p) -> int:
    return p[2]


def commutes(p, q) -> bool:
    """General Pauli commutation: the symplectic form x_p.z_q + z_p.x_q is even."""
    return (bin((p[0] & q[1]) ^ (p[1] & q[0])).count("1") & 1) == 0


def weight(p) -> int:
    return bin(p[0] | p[1]).count("1")


def axis_eq(p, q) -> int:
    """+1 / -1 if P and Q are the same axis (so their exponentials merge with that relative sign), else 0."""
    if key(p) != key(q):
        return 0
    return p[2] * q[2]


def pauli_string(p, n: int) -> str:
    out = []
    for q in range(n):
        xq, zq = (p[0] >> q) & 1, (p[1] >> q) & 1
        out.append("IXZY"[(zq << 1) | xq] if (xq, zq) != (1, 1) else "Y")
    return ("-" if p[2] < 0 else "+") + "".join(out)


def on_grid(theta, tol: float = GRID_TOL) -> bool:
    if theta is None:
        return True
    r = float(theta) / QUARTER
    return abs(r - round(r)) * QUARTER <= tol


# ------------------------------------------------------------------------------------------ frames
@dataclass(frozen=True)
class Record:
    """One rotation of the circuit, as the signed Pauli exponential it is in the FRONT frame.

    `exp(-i theta/2 Z_q)` sitting after a Clifford prefix C equals `C exp(-i theta/2 P) C^dag` with
    P = C^dag Z_q C, so the whole circuit is an ordered product of Pauli exponentials followed by one
    Clifford. Two records with the same axis (`axis_eq`) whose Paulis commute with everything between them
    merge: the angles add with the relative sign.
    """
    pos: int                  # index in the op list
    theta: float
    x: int
    z: int
    sign: int
    on_grid: bool             # True = a Clifford/T gate, so gridsynth pays nothing for it

    @property
    def p(self) -> tuple:
        return (self.x, self.z, self.sign)

    @property
    def key(self) -> tuple:
        return (self.x, self.z)


def _popcount(v: int) -> int:
    return bin(v).count("1")


# Internal "XZ-ordered" Pauli form, used only by the tableau: (x, z, ph) means
#     i**ph * prod_q X_q**x_q Z_q**z_q
# in which multiplication is exact and carry-free. The public form is HERMITIAN: (x, z, sign) means
# sign * i**popcount(x & z) * prod X**x Z**z, so Y = (1, 1, +1) is the Hermitian Y = i X Z.
def _to_xz(p) -> tuple:
    x, z, s = p
    return (x, z, (_popcount(x & z) + (0 if s > 0 else 2)) % 4)


def _to_herm(p) -> tuple:
    x, z, ph = p
    d = (ph - _popcount(x & z)) % 4
    if d == 0:
        return (x, z, 1)
    if d == 2:
        return (x, z, -1)
    raise ValueError(f"not +-1 times a Hermitian Pauli: i^{ph} on (x={x:b}, z={z:b})")


def _mul(a, b) -> tuple:
    """Product of two XZ-ordered Paulis. Moving X past Z costs one minus sign per shared qubit."""
    ax, az, aph = a
    bx, bz, bph = b
    return (ax ^ bx, az ^ bz, (aph + bph + 2 * _popcount(az & bx)) % 4)


class Tableau:
    """The map Phi(P) = C^dag P C for a Clifford prefix C, as the images of X_q and Z_q.

    The front-frame Pauli of a rotation is exactly `Phi(Z_q)`, and Phi composes on the INSIDE
    (Phi_{j+1}(P) = Phi_j(g^dag P g)), which is why a per-qubit list of Z images cannot be updated in
    place: you need the images of X as well, and a product with its i-phases. With both stored, appending
    one Clifford gate touches only the 2 or 4 entries on that gate's qubits, so the whole sweep is
    O(ops) instead of v3's O(rotations x ops) - on qpe_8, 2.1k conjugations instead of 55k, which was the
    single largest cost in the whole P2 book.
    """

    __slots__ = ("n", "X", "Z")

    def __init__(self, n: int):
        self.n = n
        self.X = [(1 << q, 0, 0) for q in range(n)]      # Phi(X_q), XZ-ordered
        self.Z = [(0, 1 << q, 0) for q in range(n)]      # Phi(Z_q)

    def _image(self, local, q: int) -> tuple:
        """Phi of the single-qubit Pauli with local bits `local` = (x, z) on qubit q."""
        lx, lz = local
        if not lx and not lz:
            return (0, 0, 0)
        if lx and not lz:
            return self.X[q]
        if lz and not lx:
            return self.Z[q]
        return _mul((0, 0, 1), _mul(self.X[q], self.Z[q]))      # Y = i X Z

    def push(self, gate: str, qubits) -> None:
        """Append one Clifford gate g to the prefix: Phi <- Phi o conj_{g^dag}."""
        gi = _INV.get(gate, gate)
        t1 = _FLAT1.get(gi)
        if t1 is not None:
            q = qubits[0]
            newX = self._image((t1[2][0], t1[2][1]), q)                  # conj_{g^dag}(X_q): bits (1, 0)
            if t1[2][2] < 0:
                newX = _mul((0, 0, 2), newX)
            newZ = self._image((t1[1][0], t1[1][1]), q)                  # conj_{g^dag}(Z_q): bits (0, 1)
            if t1[1][2] < 0:
                newZ = _mul((0, 0, 2), newZ)
            self.X[q], self.Z[q] = newX, newZ
            return
        t2 = _FLAT2.get(gi)
        if t2 is None:
            raise ValueError(f"not a Clifford gate: {gate}")
        q0, q1 = qubits[0], qubits[1]
        out = {}
        for (which, q, idx) in (("X", q0, 0b1000), ("Z", q0, 0b0100), ("X", q1, 0b0010), ("Z", q1, 0b0001)):
            nx0, nz0, nx1, nz1, sg = t2[idx]
            img = _mul(self._image((nx0, nz0), q0), self._image((nx1, nz1), q1))
            if sg < 0:
                img = _mul((0, 0, 2), img)
            out[(which, q)] = img
        self.X[q0], self.Z[q0] = out[("X", q0)], out[("Z", q0)]
        self.X[q1], self.Z[q1] = out[("X", q1)], out[("Z", q1)]

    def z_image(self, q: int) -> tuple:
        """Phi(Z_q) as a HERMITIAN Pauli (x, z, sign) - the front-frame axis of a Z-rotation on q."""
        return _to_herm(self.Z[q])


def frames(ops, cliffords=CLIFFORDS) -> list | None:
    """Every rotation of `ops` as a front-frame `Record`, in ONE forward sweep over a Clifford tableau.

    Returns None if the op list contains a gate that is neither a Clifford from `cliffords` nor a
    Z-rotation (t / tdg / rz): the front-frame normal form is not defined then.
    """
    n = 0
    for op in ops:
        for q in op[1]:
            n = max(n, int(q) + 1)
    tab = Tableau(n)
    out = []
    for pos, op in enumerate(ops):
        g, qs = op[0], tuple(int(q) for q in op[1])
        a = op[2] if len(op) > 2 else None
        if g == "t":
            theta = QUARTER
        elif g == "tdg":
            theta = -QUARTER
        elif g == "rz":
            theta = float(a)
        else:
            if g not in cliffords:
                return None
            tab.push(g, qs)
            continue
        x, z, sg = tab.z_image(qs[0])
        out.append(Record(pos, theta, x, z, sg, on_grid(theta)))
    return out


def residual_clifford(ops, cliffords=CLIFFORDS) -> list:
    """The Clifford ops of `ops`, in order: the single Clifford that follows the Pauli-exponential product
    in the front-frame normal form."""
    return [op for op in ops if op[0] in cliffords]


__all__ = ["CLIFFORDS", "Record", "Tableau", "axis_eq", "commutes", "commutes_with_z", "conjugate", "frames", "is_z",
           "key", "on_grid", "pauli_string", "residual_clifford", "sign", "weight", "x_on", "y_on", "z_on"]
