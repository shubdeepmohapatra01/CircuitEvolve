"""Sparse exact simulator, branch-wise over measurement outcomes.

A state is a dict {basis index: amplitude in D[ω]}; bit q of the index is qubit q. On basis inputs,
arithmetic circuits keep only a handful of non-zero amplitudes, so cost scales with the sparsity of
the state, not with 2^n_qubits. Measurements are not renormalized: each branch carries its
unnormalized post-measurement state, i.e. the Kraus operator K_m applied to the input.
"""
from __future__ import annotations

import numpy as np

from .ir import Circuit, Gate
from .ring import D, INV_SQRT2

_W = [D.omega_pow(j) for j in range(8)]
_PHASE = {"z": 4, "s": 2, "sdg": 6, "t": 1, "tdg": 7}


def _apply(state: dict, g: Gate) -> dict:
    n, q = g.name, g.qubits
    if n == "x":
        m = 1 << q[0]
        return {k ^ m: a for k, a in state.items()}
    if n == "cx":
        c, t = 1 << q[0], 1 << q[1]
        return {(k ^ t if k & c else k): a for k, a in state.items()}
    if n == "ccx":
        c = (1 << q[0]) | (1 << q[1])
        t = 1 << q[2]
        return {(k ^ t if (k & c) == c else k): a for k, a in state.items()}
    if n in _PHASE:
        m, w = 1 << q[0], _W[_PHASE[n]]
        return {k: (a * w if k & m else a) for k, a in state.items()}
    if n in ("cz", "ccz"):
        m = 0
        for qq in q:
            m |= 1 << qq
        return {k: (-a if (k & m) == m else a) for k, a in state.items()}
    if n == "h":
        m = 1 << q[0]
        out: dict = {}
        for k, a in state.items():
            a2 = a * INV_SQRT2
            k0, k1 = k & ~m, k | m
            out[k0] = out[k0] + a2 if k0 in out else a2
            b1 = -a2 if k & m else a2
            out[k1] = out[k1] + b1 if k1 in out else b1
        return {k: a for k, a in out.items() if not a.is_zero()}
    raise ValueError(f"cannot simulate gate {n!r}")


def run(circ: Circuit, inp: int, outcomes: tuple | None = None) -> dict:
    """Simulate `circ` on basis state |inp>.

    Returns {outcome tuple (in measurement order): unnormalized final state}. Branches whose
    projected state is zero are omitted. If `outcomes` is given, only that branch is followed.
    """
    c = circ.expand("gadgets")
    gates = c.gates
    results: dict = {}
    stack = [(0, {inp: D((1, 0, 0, 0))}, (0,) * c.n_cbits, ())]
    while stack:
        i, st, cb, seq = stack.pop()
        while i < len(gates):
            g = gates[i]
            i += 1
            if g.cond is not None and not cb[g.cond]:
                continue
            if g.name == "measure":
                m = 1 << g.qubits[0]
                choices = (0, 1) if outcomes is None else (outcomes[len(seq)],)
                branches = []
                for r in choices:
                    proj = {k: a for k, a in st.items() if bool(k & m) == bool(r)}
                    if proj:
                        cb2 = list(cb)
                        cb2[g.cbit] = r
                        branches.append((proj, tuple(cb2), seq + (r,)))
                if not branches:
                    st = None
                    break
                for proj, cb2, seq2 in branches[1:]:
                    stack.append((i, proj, cb2, seq2))
                st, cb, seq = branches[0]
                continue
            st = _apply(st, g)
        if st is not None and st:
            results[seq] = st
    return results


def n_measurements(circ: Circuit) -> int:
    return sum(1 for g in circ.expand("gadgets").gates if g.name == "measure")


def unitary(circ: Circuit) -> np.ndarray:
    """Dense unitary of a measurement-free circuit (for cross-checks on small circuits)."""
    if n_measurements(circ):
        raise ValueError("circuit contains measurements")
    dim = 1 << circ.n_qubits
    U = np.zeros((dim, dim), dtype=complex)
    for x in range(dim):
        (st,) = run(circ, x).values()
        for k, a in st.items():
            U[k, x] = complex(a)
    return U


# ---------------------------------------------------------------------------------------------
# Classical (bit-level) simulator for reversible circuits, vectorized over many inputs.
# ---------------------------------------------------------------------------------------------
class NotClassical(ValueError):
    """Raised when a circuit contains gates with no classical (permutation) semantics."""


class PreconditionViolated(ValueError):
    """A gadget precondition (and_compute: t = 0; and_uncompute: t = a·b) failed on some input."""


_DIAGONAL = {"z", "s", "sdg", "t", "tdg", "cz", "ccz"}


def run_classical(circ: Circuit, inputs) -> np.ndarray:
    """Apply the permutation part of `circ` to basis inputs.

    inputs: sequence of Python ints (basis indices). Returns a bool array (len(inputs), n_qubits).
    Diagonal gates are ignored (they only change phases); h / measure / classical control raise
    NotClassical. Gadgets use their specified semantics and have their preconditions checked.
    """
    nq = circ.n_qubits
    B = np.array([[(x >> q) & 1 for q in range(nq)] for x in inputs], dtype=bool)
    for g in circ.gates:
        if g.cond is not None or g.name in ("h", "measure"):
            raise NotClassical(g.name)
        q = g.qubits
        if g.name == "x":
            B[:, q[0]] ^= True
        elif g.name == "cx":
            B[:, q[1]] ^= B[:, q[0]]
        elif g.name == "ccx":
            B[:, q[2]] ^= B[:, q[0]] & B[:, q[1]]
        elif g.name == "and_compute":
            if B[:, q[2]].any():
                raise PreconditionViolated(f"and_compute target q{q[2]} not |0>")
            B[:, q[2]] = B[:, q[0]] & B[:, q[1]]
        elif g.name == "and_uncompute":
            if (B[:, q[2]] != (B[:, q[0]] & B[:, q[1]])).any():
                raise PreconditionViolated(f"and_uncompute target q{q[2]} != a·b")
            B[:, q[2]] = False
        elif g.name in _DIAGONAL:
            pass
        else:
            raise NotClassical(g.name)
    return B


def bits_to_ints(B: np.ndarray) -> list:
    w = [1 << q for q in range(B.shape[1])]
    return [sum(wq for wq, b in zip(w, row) if b) for row in B]
