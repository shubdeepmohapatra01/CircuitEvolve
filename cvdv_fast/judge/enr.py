"""FROZEN verifier core for cvdv_fast: hybrid qubit-qumode simulation on a total-photon-bounded basis.

Hilbert space: every qubit wire is a dense 2-level factor; all qumode wires share one excitation-number-
restricted (ENR) basis {|n_1..n_M> : sum n_i <= K}. Truncation = exponentiate the generator projected onto
that basis (consistent for every gate). Results are trusted only if K = 6 and K = 8 agree.

Gate conventions = Genesis Table 2 = Liu et al. (arXiv:2407.10381):
    R(t)=exp(-i t n)  D(a)=exp(a a^+ - a* a)  BS(t,p)=exp(-i t/2 (e^{ip} a^+ b + e^{-ip} a b^+))
    CR(t)=exp(-i t/2 sz n)  CP=CR(pi)  CD(a)=exp(sz (a a^+ - a* a))  CBS(t,p)=exp(-i t/2 sz (...BS...))
    RB(t)=exp(-i sx (t a^+ + t* a));  qubit gates h x y z s sdg t tdg rx ry rz r(t,p)
sz acts on the qubit operand as diag(+1,-1) (|0> -> +1).

State layout: array (D, Q, P): D = ENR dim, Q = 2**n_qubits (qubit 0 most significant), P = probe columns.
"""
from __future__ import annotations

import itertools
import math
from functools import lru_cache

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import expm_multiply

# ----------------------------------------------------------------------------------------- ENR basis
@lru_cache(maxsize=64)
def enr_basis(M: int, K: int):
    """List of occupation tuples (sum <= K) in a fixed order + index dict."""
    states = [s for tot in range(K + 1) for s in _compositions(M, tot)]
    return states, {s: i for i, s in enumerate(states)}


def _compositions(M, tot):
    if M == 0:
        if tot == 0:
            yield ()
        return
    for k in range(tot, -1, -1):
        for rest in _compositions(M - 1, tot - k):
            yield (k,) + rest


@lru_cache(maxsize=256)
def ann_op(M: int, K: int, i: int) -> sp.csr_matrix:
    """Annihilation operator on mode i in the ENR basis."""
    states, idx = enr_basis(M, K)
    rows, cols, vals = [], [], []
    for c, s in enumerate(states):
        if s[i] > 0:
            t = list(s); t[i] -= 1
            rows.append(idx[tuple(t)]); cols.append(c); vals.append(math.sqrt(s[i]))
    D = len(states)
    return sp.csr_matrix((np.array(vals, dtype=complex), (rows, cols)), shape=(D, D))


@lru_cache(maxsize=256)
def num_diag(M: int, K: int, i: int) -> np.ndarray:
    states, _ = enr_basis(M, K)
    return np.array([s[i] for s in states], dtype=float)


QG = {
    "h": np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2),
    "x": np.array([[0, 1], [1, 0]], dtype=complex),
    "y": np.array([[0, -1j], [1j, 0]], dtype=complex),
    "z": np.diag([1, -1]).astype(complex),
    "s": np.diag([1, 1j]),
    "sdg": np.diag([1, -1j]),
    "t": np.diag([1, np.exp(1j * math.pi / 4)]),
    "tdg": np.diag([1, np.exp(-1j * math.pi / 4)]),
}
PAULI = {"I": np.eye(2, dtype=complex), "X": QG["x"], "Y": QG["y"], "Z": QG["z"]}


def qubit_matrix(name, params):
    p = [complex(x).real for x in params]
    if name in QG:
        return QG[name]
    if name == "rx":
        c, s = math.cos(p[0] / 2), math.sin(p[0] / 2)
        return np.array([[c, -1j * s], [-1j * s, c]])
    if name == "ry":
        c, s = math.cos(p[0] / 2), math.sin(p[0] / 2)
        return np.array([[c, -s], [s, c]], dtype=complex)
    if name == "rz":
        return np.diag([np.exp(-1j * p[0] / 2), np.exp(1j * p[0] / 2)])
    if name == "r":
        th, ph = p
        c, s = math.cos(th / 2), math.sin(th / 2)
        return np.array([[c, -1j * s * np.exp(-1j * ph)], [-1j * s * np.exp(1j * ph), c]])
    raise KeyError(name)


class Space:
    """Wire layout: qubit wires and qumode wires (any labels), ENR cutoff K."""

    def __init__(self, qubits, modes, K):
        self.qubits = list(qubits)
        self.modes = list(modes)
        self.K = K
        self.qi = {w: i for i, w in enumerate(self.qubits)}
        self.mi = {w: i for i, w in enumerate(self.modes)}
        self.nq, self.M = len(self.qubits), len(self.modes)
        self.states, self.idx = enr_basis(self.M, K)
        self.D, self.Q = len(self.states), 2 ** self.nq

    def a(self, w):
        return ann_op(self.M, self.K, self.mi[w])

    def n(self, w):
        return num_diag(self.M, self.K, self.mi[w])

    # --- state helpers
    def _qsplit(self, psi, q):
        j = self.qi[q]
        D, Q, P = psi.shape
        return psi.reshape(D, 2 ** j, 2, Q // 2 ** (j + 1), P)

    def apply_qubit(self, psi, U, q):
        v = self._qsplit(psi, q)
        return np.einsum("ab,xibjp->xiajp", U, v).reshape(psi.shape)

    def apply_mode_gen(self, psi, G):
        """psi <- exp(G) psi along the mode axis (G sparse D x D)."""
        D, Q, P = psi.shape
        return expm_multiply(G, psi.reshape(D, Q * P)).reshape(D, Q, P)

    def apply_controlled(self, psi, q, Gfun):
        """Gate exp(sz (x) G'): qubit value b in {0,1} gets exp((+1 | -1) G')."""
        v = self._qsplit(psi, q).copy()
        for b, sgn in ((0, 1.0), (1, -1.0)):
            sub = v[:, :, b, :, :]
            shp = sub.shape
            G = Gfun(sgn)
            if isinstance(G, np.ndarray):  # diagonal phase vector
                sub = sub * G.reshape(-1, 1, 1, 1)
            else:
                sub = expm_multiply(G, sub.reshape(shp[0], -1)).reshape(shp)
            v[:, :, b, :, :] = sub
        return v.reshape(psi.shape)

    def apply(self, psi, op):
        name, prm, w = op.name, [complex(x) for x in op.params], op.wires
        if name in QG or name in ("rx", "ry", "rz", "r"):
            return self.apply_qubit(psi, qubit_matrix(name, prm), w[0])
        if name == "R":
            ph = np.exp(-1j * prm[0].real * self.n(w[0]))
            return psi * ph.reshape(-1, 1, 1)
        if name == "D":
            a = self.a(w[0]); al = prm[0]
            return self.apply_mode_gen(psi, al * a.getH() - np.conj(al) * a)
        if name == "BS":
            th, ph = prm[0].real, prm[1].real
            a, b = self.a(w[0]), self.a(w[1])
            G = -1j * th / 2 * (np.exp(1j * ph) * (a.getH() @ b) + np.exp(-1j * ph) * (b.getH() @ a))  # normal order
            return self.apply_mode_gen(psi, G.tocsr())
        if name in ("CR", "CP"):
            th = math.pi if name == "CP" else prm[0].real
            nn = self.n(w[1])
            return self.apply_controlled(psi, w[0], lambda s: np.exp(-1j * th / 2 * s * nn))
        if name == "CD":
            a = self.a(w[1]); al = prm[0]
            g0 = (al * a.getH() - np.conj(al) * a).tocsr()
            return self.apply_controlled(psi, w[0], lambda s: s * g0)
        if name == "CBS":
            th, ph = prm[0].real, prm[1].real
            a, b = self.a(w[1]), self.a(w[2])
            g0 = (-1j * th / 2 * (np.exp(1j * ph) * (a.getH() @ b) + np.exp(-1j * ph) * (b.getH() @ a))).tocsr()
            return self.apply_controlled(psi, w[0], lambda s: s * g0)
        if name == "RB":
            th = prm[0]; a = self.a(w[1])
            g0 = (-1j * (th * a.getH() + np.conj(th) * a)).tocsr()
            psi = self.apply_qubit(psi, QG["h"], w[0])
            psi = self.apply_controlled(psi, w[0], lambda s: s * g0)
            return self.apply_qubit(psi, QG["h"], w[0])
        raise KeyError(f"unknown gate {name}")

    def run(self, psi, ops):
        for o in ops:
            psi = self.apply(psi, o)
        return psi

    # --- Hamiltonian terms (cvdv.terms.Poly: {(pauli((q,s),..), boson((m,p_dag,p_ann),..)): c})
    def term_generator(self, H):
        """Sparse -iH on the (D * Q) flattened space (index d*Q + q)."""
        tot = None
        for (pa, bo), c in H.c.items():
            if abs(c) < 1e-15:
                continue
            # globally normal-ordered (all creations left of all annihilations): exact for the untruncated
            # algebra (different modes commute) and keeps the ENR-truncated generator Hermitian
            cre = sp.identity(self.D, dtype=complex, format="csr")
            ann = sp.identity(self.D, dtype=complex, format="csr")
            for (m, pd, pn) in bo:
                a = self.a(("qm", m))
                for _ in range(pd):
                    cre = cre @ a.getH()
                for _ in range(pn):
                    ann = ann @ a
            B = cre @ ann
            mats = [PAULI["I"]] * self.nq
            for (q, s) in pa:
                mats[self.qi[("q", q)]] = PAULI[s]
            P = sp.csr_matrix(_kron(mats))
            T = sp.kron(B, P, format="csr") * c
            tot = T if tot is None else tot + T
        if tot is None:
            tot = sp.csr_matrix((self.D * self.Q, self.D * self.Q), dtype=complex)
        return (-1j * tot).tocsr()

    def apply_term(self, psi, G):
        D, Q, P = psi.shape
        return expm_multiply(G, psi.reshape(D * Q, P)).reshape(D, Q, P)

    def top_leak(self, psi):
        tot = np.array([sum(s) for s in self.states])
        w = np.abs(psi) ** 2
        return float(w[tot == self.K].sum() / max(w.sum(), 1e-300))


def _kron(ms):
    out = np.array([[1.0 + 0j]])
    for m in ms:
        out = np.kron(out, m)
    return out


# ----------------------------------------------------------------------------------------- probes
def probe_subspace(space: Space, sys_qubits, sys_modes, n_probe: int):
    """Basis columns of S = {system qubits arbitrary, system modes total <= n_probe, ancillas |0>/vac}."""
    cols = []
    smi = [space.mi[w] for w in sys_modes]
    sqi = [space.qi[w] for w in sys_qubits]
    for d, s in enumerate(space.states):
        if sum(s) > n_probe or any(s[i] for i in range(space.M) if i not in smi):
            continue
        for bits in itertools.product((0, 1), repeat=len(sqi)):
            qb = [0] * space.nq
            for j, b in zip(sqi, bits):
                qb[j] = b
            q = int("".join(map(str, qb)), 2) if space.nq else 0
            cols.append((d, q))
    return cols


def basis_block(space: Space, cols):
    psi = np.zeros((space.D, space.Q, len(cols)), dtype=complex)
    for p, (d, q) in enumerate(cols):
        psi[d, q, p] = 1.0
    return psi


def haar_block(space, cols, n, seed):
    rng = np.random.default_rng(seed)
    B = basis_block(space, cols).reshape(space.D * space.Q, len(cols))
    C = rng.normal(size=(len(cols), n)) + 1j * rng.normal(size=(len(cols), n))
    C /= np.linalg.norm(C, axis=0, keepdims=True)
    return (B @ C).reshape(space.D, space.Q, n)


def phase_aligned_dist(W, X):
    """min-ish over phi of ||W - e^{i phi} X||_2 for column blocks (phase from tr(X^+ W))."""
    W2 = W.reshape(-1, W.shape[-1]); X2 = X.reshape(-1, X.shape[-1])
    tr = np.vdot(X2, W2)
    ph = tr / abs(tr) if abs(tr) > 1e-300 else 1.0
    return float(np.linalg.norm(W2 - ph * X2, 2))
