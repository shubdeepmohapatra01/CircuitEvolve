"""Small-unitary simulation for rules: dense unitaries and the phase-aligned distance the judge uses.

The judge decides acceptance; this module exists so a rule can CHECK ITSELF before proposing a rewrite,
with the same arithmetic the judge will use, instead of rolling its own (every v3 refit rule did).

    unitary(ops, n)            dense 2^n x 2^n (qubit 0 = most significant index, the judge's convention)
    hs_distance(U, V)          {'op': phase-aligned operator norm, 'fro': normalised Frobenius}
    distance(a_ops, b_ops, n)  the same, straight from two op lists
    phase_align(U, V)          the scalar c minimising ||U - c V||, and that norm
    MAX_QUBITS                 above this a dense check is refused (the judge refuses it too)

The operator norm is the quantity the judge charges to the ledger, so a rule that keeps its own distance
below the allowance it drew will be accepted. `fro` is cheaper and is a lower bound; use it to screen.
"""
from __future__ import annotations

import math

import numpy as np

from circuitevolve.blocks.verify_block import distance as _distance, unitary as _unitary

MAX_QUBITS = 14


def unitary(ops, n: int) -> np.ndarray:
    if int(n) > MAX_QUBITS:
        raise ValueError(f"n={n} > MAX_QUBITS={MAX_QUBITS}: build the unitary of a window, not a circuit")
    return _unitary(list(ops), int(n))


def hs_distance(U, V) -> dict:
    """Phase-aligned distance between two unitaries: {'op', 'fro'}. Global phase is unobservable, so the
    best phase is divided out first (the judge does exactly this)."""
    return _distance(np.asarray(U), np.asarray(V))


def distance(a_ops, b_ops, n: int) -> dict:
    return hs_distance(unitary(a_ops, n), unitary(b_ops, n))


def phase_align(U, V) -> tuple:
    """(c, ||U - c V||_2) with |c| = 1 chosen to minimise the norm."""
    U, V = np.asarray(U), np.asarray(V)
    tr = np.trace(V.conj().T @ U)
    c = tr / abs(tr) if abs(tr) > 1e-300 else 1.0 + 0j
    return c, float(np.linalg.norm(U - c * V, 2))


def hs_cost(U, V) -> float:
    """BQSKit's Hilbert-Schmidt cost 1 - |Tr(U^dag V)| / N. Always <= the operator distance."""
    U, V = np.asarray(U), np.asarray(V)
    return float(1.0 - min(1.0, abs(np.trace(U.conj().T @ V)) / U.shape[0]))


def is_identity(U, tol: float = 1e-12) -> bool:
    U = np.asarray(U)
    return bool(np.allclose(U, np.eye(U.shape[0]) * (np.trace(U) / U.shape[0]), atol=tol))


def fro_lower_bound(a_ops, b_ops, n: int) -> float:
    """Cheap screen: the normalised Frobenius distance, a lower bound on the operator distance."""
    return distance(a_ops, b_ops, n)["fro"] / math.sqrt(2)
