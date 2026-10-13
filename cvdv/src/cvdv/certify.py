"""Per-instance error certificate (L2), FROZEN once the acceptance suite passes.

For a term exp(-iH) on system wires W and an emitted gate list V acting on W plus ancillas A
(qubits start in |0>, qumodes in vacuum), the certificate is

    eps = min_φ || V (|ψ> ⊗ |0_A>) - e^{iφ} (exp(-iH)|ψ>) ⊗ |0_A> ||   maximised over |ψ> in S,

i.e. the operator norm of (V - e^{iφ} U ⊗ |0_A><0_A|) restricted to
    S = span{ qubit basis ⊗ Fock states of the system qumodes with total photon number <= n_max }.
φ = arg tr(T_S† V_S) (one global phase for the whole subspace).  The ancilla must come back to
|0>: garbage left on an ancilla counts as error, so a certified block may reuse its ancillas.

S is invariant under every number-conserving H (n, n², hopping, Z n, Pauli, Z·hopping), and the
subspace bound then composes over a product of terms by the triangle inequality:
    || Π V_k - Π U_k ||_S <= Σ eps_k.
Displacement-type terms (D, CD, P ⊗ (α a† - α* a)) do not preserve S; their certificate is reported
with flag `invariant=False`.

Truncation: computed at two cutoffs N1 = n_max + margin and N2 = N1 + margin2; the certificate is
max(eps(N1), eps(N2)) and is marked unreliable if they differ by more than `trunc_tol` (absolute)
or if the top-level population exceeds `leak_tol`.
"""
from __future__ import annotations

import itertools

import numpy as np

from .sim import Register, run
from .spec import spec_unitary

NUMBER_CONSERVING = {"n", "n2", "hop", "z_n", "z_hop", "pauli", "pauli_n", "pauli_hop"}


def subspace_basis(sys_wires, n_max):
    qs = [w for w in sys_wires if w[0] == "q"]
    ms = [w for w in sys_wires if w[0] == "qm"]
    fock = [f for f in itertools.product(range(n_max + 1), repeat=len(ms)) if sum(f) <= n_max]
    return [(qb, f) for qb in itertools.product((0, 1), repeat=len(qs)) for f in fock], qs, ms


def _eps_at(H, sys_wires, ops, N, n_max, pad):
    wires = sorted(set(sys_wires) | {w for o in ops for w in o.wires})
    reg = Register(wires, N)
    basis, qs, ms = subspace_basis(sys_wires, n_max)
    K = len(basis)
    psi = np.zeros(reg.dims + (K,), dtype=complex)
    for k, (qb, f) in enumerate(basis):
        idx = [0] * len(wires)
        for w, b in zip(qs, qb):
            idx[reg.index[w]] = b
        for w, n in zip(ms, f):
            idx[reg.index[w]] = n
        psi[tuple(idx) + (k,)] = 1
    V = run(reg, psi, ops, pad=pad)
    U = spec_unitary(H, list(sys_wires), N, pad=pad)
    T = reg.apply(psi, U, list(sys_wires))
    Vm, Tm = V.reshape(-1, K), T.reshape(-1, K)
    ph = np.angle(np.trace(Tm.conj().T @ Vm))
    E = Vm - np.exp(1j * ph) * Tm
    eps = float(np.linalg.svd(E, compute_uv=False)[0])
    p = np.abs(V) ** 2
    leak = 0.0
    for i, w in enumerate(wires):
        if w[0] == "qm":
            leak = max(leak, float(np.take(p, N - 1, axis=i).sum(axis=tuple(range(len(wires) - 1))).max()))
    return eps, leak


def certify(H, ops, kind: str, n_max: int = 4, margin: int = 12, margin2: int = 12, pad: int = 16,
            trunc_tol: float = 1e-9, leak_tol: float = 1e-10, N_cap: int = 64):
    sys_wires = tuple(H.wires())
    N1 = n_max + margin
    N2 = N1 + margin2
    e1, l1 = _eps_at(H, sys_wires, ops, N1, n_max, pad)
    while True:  # adaptive: raise the cutoff until two consecutive cutoffs agree (or N_cap)
        e2, l2 = _eps_at(H, sys_wires, ops, N2, n_max, pad)
        reliable = abs(e1 - e2) <= max(trunc_tol, 1e-3 * max(e1, e2)) and l2 <= leak_tol
        if reliable or N2 + margin2 > N_cap:
            break
        N1, e1, l1 = N2, e2, l2
        N2 = N1 + margin2
    return {"eps": max(e1, e2), "eps_N1": e1, "eps_N2": e2, "N": (N1, N2), "n_max": n_max,
            "leak": l2, "reliable": bool(reliable), "invariant": kind in NUMBER_CONSERVING}
