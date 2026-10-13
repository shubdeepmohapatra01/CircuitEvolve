"""Specification unitaries for classified terms: exp(-i H) on the term's local wires.

`poly_matrix(H, wires, N, pad)` builds the Hermitian matrix of a terms.Poly on local dimensions
(qubits 2, qumodes N + pad), exponentiates, and keeps the N-level block.  For number-conserving
H the block is exact; for displacement-type H the padding makes it accurate far below the cutoff.
"""
from __future__ import annotations

import numpy as np
from scipy.linalg import expm

from .sim import PAULI, ann, keep_block, kron


def poly_matrix(H, wires, N: int, pad: int = 0):
    dims = [2 if w[0] == "q" else N + pad for w in wires]
    pos = {w: i for i, w in enumerate(wires)}
    D = int(np.prod(dims))
    M = np.zeros((D, D), dtype=complex)
    for (p, b), c in H.c.items():
        mats = [np.eye(d, dtype=complex) for d in dims]
        for q, s in p:
            mats[pos[("q", q)]] = PAULI[s]
        for m, pp, qq in b:
            a = ann(dims[pos[("qm", m)]])
            mats[pos[("qm", m)]] = np.linalg.matrix_power(a.conj().T, pp) @ np.linalg.matrix_power(a, qq)
        M += c * kron(*mats)
    return M, dims


def spec_unitary(H, wires, N: int, pad: int = 16):
    M, dims = poly_matrix(H, wires, N, pad)
    U = expm(-1j * M)
    keep = [2 if w[0] == "q" else N for w in wires]
    return keep_block(U, dims, keep)
