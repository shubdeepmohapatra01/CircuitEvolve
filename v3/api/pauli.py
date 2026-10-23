"""Pauli frames: propagate a Pauli operator through Clifford gates (P -> C P C^dag) and test commutation.

A Pauli is (x, z, sign): x, z = int bitmasks over qubits (bit q set = X / Z part on qubit q; both = Y up to the
phase tracked in sign), sign = +1 / -1. Conjugation tables are derived once from the gate matrices.
"""
from __future__ import annotations

import numpy as np


def z_on(q: int):
    return (0, 1 << q, 1)


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
    for key in keys:
        m = np.array([[1]])
        for j in range(k):
            m = np.kron(m, _P1[(key[2 * j], key[2 * j + 1])])
        mats[key] = m
    out = {}
    for key, m in mats.items():
        c = U @ m @ U.conj().T
        for k2, m2 in mats.items():
            for sg in (1, -1):
                if np.allclose(c, sg * m2):
                    out[key] = (k2, sg)
    assert len(out) == len(keys), gate
    return out


_TABLES = {g: _table(g) for g in _GATES}


def conjugate(p, gate: str, qubits):
    """C P C^dag for one Clifford gate (h s sdg x z cx cz; cx qubits = (control, target))."""
    if gate not in _TABLES:
        raise ValueError(f"not a Clifford gate: {gate}")
    x, z, s = p
    key = tuple(b for q in qubits for b in ((x >> q) & 1, (z >> q) & 1))
    new, sg = _TABLES[gate][key]
    for j, q in enumerate(qubits):
        m = 1 << q
        x = (x & ~m) | (new[2 * j] << q)
        z = (z & ~m) | (new[2 * j + 1] << q)
    return (x, z, s * sg)


def commutes_with_z(p, q: int) -> bool:
    """[P, Z_q] = 0  <=>  P has no X part on q."""
    return not (p[0] >> q) & 1


def is_z(p, q: int):
    """+1 / -1 if P = +-Z_q exactly (identity elsewhere), else 0."""
    return p[2] if p[0] == 0 and p[1] == 1 << q else 0
