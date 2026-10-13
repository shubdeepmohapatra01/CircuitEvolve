"""Truncated-Fock statevector simulator for hybrid qubit-qumode circuits.

Gate conventions follow Genesis Table 2 (Chen et al., ISCA'25), which match Liu et al. (2407.10381):

    R(θ)        exp(-i θ n)
    D(α)        exp(α a† - α* a)
    BS(θ, φ)    exp(-i θ/2 (e^{iφ} a† b + e^{-iφ} a b†))
    CR(θ)       exp(-i θ/2 σz n)
    CP          exp(-i π/2 σz n)
    CD(α)       exp(σz (α a† - α* a))
    CBS(θ, φ)   exp(-i θ/2 σz (e^{iφ} a† b + e^{-iφ} a b†))
    RB(θ)       exp(-i σx (θ a† - θ* a))
    r(θ, φ)     exp(-i θ/2 (cos φ σx + sin φ σy));  rx, ry, rz standard;  h x y z s sdg t tdg

Operand order is the CVDV-QASM order: qubits first, then qumodes (CBS: q, qm_a, qm_b; BS: a, b).

Truncation.  Number-conserving / diagonal gates (R, CR, CP, BS, CBS) are exact on the cutoff-N
space restricted to the probe sector.  Displacement-type gates (D, CD, RB) are built by
exponentiating the generator on N + pad levels and keeping the N×N block, which is accurate to
machine precision for amplitudes well below the cutoff.  Every simulation reports the population
on the top level of every mode (`leak`) so truncation artefacts are visible, and the verifier
repeats at a larger cutoff.

The ambiguous Genesis form `R(θ) q[i], qm[j]` (a rotation printed with a qubit operand) is
interpreted according to `r_with_qubit` = 'cr' (CR(θ), default) or 'mode' (R(θ) on the qumode).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.linalg import expm

from .qasm import Op

I2 = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.array([[1, 0], [0, -1]], dtype=complex)
PAULI = {"I": I2, "X": X, "Y": Y, "Z": Z}
S = np.diag([1, 1j])
T = np.diag([1, np.exp(1j * np.pi / 4)])
H = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)


def ann(n: int) -> np.ndarray:
    return np.diag(np.sqrt(np.arange(1, n, dtype=float)), 1).astype(complex)


def num(n: int) -> np.ndarray:
    return np.diag(np.arange(n, dtype=float)).astype(complex)


def kron(*ms):
    out = np.array([[1.0 + 0j]])
    for m in ms:
        out = np.kron(out, m)
    return out


def keep_block(U: np.ndarray, dims_full, dims_keep) -> np.ndarray:
    """Restrict an operator on prod(dims_full) to the sub-block with each index < dims_keep."""
    idx = np.indices(dims_keep).reshape(len(dims_keep), -1)
    flat = np.ravel_multi_index(idx, dims_full)
    return U[np.ix_(flat, flat)]


def qubit_matrix(name: str, params) -> np.ndarray:
    p = [complex(x).real for x in params]
    if name == "h":
        return H
    if name == "x":
        return X
    if name == "y":
        return Y
    if name == "z":
        return Z
    if name == "s":
        return S
    if name == "sdg":
        return S.conj().T
    if name == "t":
        return T
    if name == "tdg":
        return T.conj().T
    if name == "rx":
        return expm(-0.5j * p[0] * X)
    if name == "ry":
        return expm(-0.5j * p[0] * Y)
    if name == "rz":
        return expm(-0.5j * p[0] * Z)
    if name == "r":
        return expm(-0.5j * p[0] * (np.cos(p[1]) * X + np.sin(p[1]) * Y))
    raise KeyError(name)


QUBIT_GATES = {"h", "x", "y", "z", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "r"}
ISA_GENESIS = QUBIT_GATES | {"R", "D", "BS", "CR", "CP", "CD", "CBS", "RB"}


@lru_cache(maxsize=4096)
def _gate_cached(name, params, nq, nm, N, pad, r_with_qubit):
    params = tuple(complex(p) for p in params)
    if nm == 0:
        assert nq == 1, (name, nq)
        return qubit_matrix(name, params)
    if name == "R" and nq == 1 and nm == 1:
        name = "CR" if r_with_qubit == "cr" else "R_mode_with_idle_qubit"
    th = params[0] if params else 0
    if name == "R" and nq == 0:
        return np.diag(np.exp(-1j * th.real * np.arange(N)))
    if name == "R_mode_with_idle_qubit":
        return kron(I2, np.diag(np.exp(-1j * th.real * np.arange(N))))
    if name in ("CR", "CP"):
        ang = np.pi if name == "CP" else th.real
        n = np.arange(N)
        return np.diag(np.concatenate([np.exp(-0.5j * ang * n), np.exp(0.5j * ang * n)]))
    M = N + pad
    a = ann(M)
    if name == "D" and nq == 0:
        U = expm(th * a.conj().T - np.conj(th) * a)
        return U[:N, :N]
    if name == "CD":
        G = kron(Z, th * a.conj().T - np.conj(th) * a)
        return keep_block(expm(G), (2, M), (2, N))
    if name == "RB":
        G = -1j * kron(X, th * a.conj().T - np.conj(th) * a)
        return keep_block(expm(G), (2, M), (2, N))
    if name in ("BS", "CBS"):
        phi = params[1].real if len(params) > 1 else 0.0
        ia, ib = np.eye(M), np.eye(M)
        A, B = kron(a, ib), kron(ia, a)
        hop = np.exp(1j * phi) * A.conj().T @ B + np.exp(-1j * phi) * A @ B.conj().T
        if name == "BS":
            return keep_block(expm(-0.5j * th.real * hop), (M, M), (N, N))
        return keep_block(expm(-0.5j * th.real * kron(Z, hop)), (2, M, M), (2, N, N))
    raise KeyError(f"unsupported gate {name} on {nq} qubits / {nm} qumodes")


def gate_matrix(op: Op, N: int, pad: int = 12, r_with_qubit: str = "cr") -> np.ndarray:
    if op.name == "pauli":
        P = kron(*[PAULI[ch] for ch in op.label if ch != "I"])
        return expm(complex(op.params[0]) * P)
    return _gate_cached(op.name, tuple(op.params), len(op.qubits), len(op.qumodes), N, pad,
                        r_with_qubit)


class Register:
    """Statevector over an ordered list of wires; qubits dim 2, qumodes dim N."""

    def __init__(self, wires, N: int):
        self.wires = list(wires)
        self.N = N
        self.index = {w: i for i, w in enumerate(self.wires)}
        self.dims = tuple(2 if w[0] == "q" else N for w in self.wires)

    def zero(self):
        psi = np.zeros(self.dims, dtype=complex)
        psi[(0,) * len(self.dims)] = 1
        return psi

    def apply(self, psi: np.ndarray, U: np.ndarray, ws) -> np.ndarray:
        axes = [self.index[w] for w in ws]
        d = int(np.prod([self.dims[i] for i in axes]))
        assert U.shape == (d, d), (U.shape, ws)
        moved = np.moveaxis(psi, axes, list(range(len(axes))))
        sh = moved.shape
        out = (U @ moved.reshape(d, -1)).reshape(sh)
        return np.moveaxis(out, list(range(len(axes))), axes)

    def leak(self, psi: np.ndarray) -> float:
        """Max over qumodes of the population on the top Fock level."""
        p = np.abs(psi) ** 2
        worst = 0.0
        for i, w in enumerate(self.wires):
            if w[0] == "qm":
                worst = max(worst, float(np.take(p, self.N - 1, axis=i).sum()))
        return worst


def run(reg: Register, psi: np.ndarray, ops, pad: int = 12, r_with_qubit: str = "cr",
        wire_map=None) -> np.ndarray:
    """Apply ops in order.  `wire_map` optionally renames op wires (e.g. logical->register)."""
    for op in ops:
        ws = op.wires if wire_map is None else tuple(wire_map.get(w, w) for w in op.wires)
        psi = reg.apply(psi, gate_matrix(op, reg.N, pad, r_with_qubit), ws)
    return psi
