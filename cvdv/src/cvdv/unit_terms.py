"""Canonical single-term test Hamiltonians for rule checks (one per kind / Pauli shape)."""
import numpy as np

from .terms import Poly


def n_(m):
    return Poly({((), ((m, 1, 1),)): 1.0})


def hop(j, k, th, ph, label=None):
    p = ((0, label),) if label else ()
    return Poly({(p, ((j, 1, 0), (k, 0, 1))): th * np.exp(1j * ph),
                 (p, ((j, 0, 1), (k, 1, 0))): th * np.exp(-1j * ph)})


def pauli(lab, th):
    return Poly({(tuple((i, s) for i, s in enumerate(lab)), ()): th})


def pauli_disp(lab, alpha):
    """H with exp(-iH) = exp(P (α a† - α* a)):  H = iα P a† - iα* P a."""
    p = tuple((i, s) for i, s in enumerate(lab))
    return Poly({(p, ((0, 1, 0),)): 1j * alpha, (p, ((0, 0, 1),)): -1j * np.conj(alpha)})


def cases():
    out = [("n", n_(0).scale(0.7)),
           ("hop", hop(0, 1, 0.4, 0.3)),
           ("z_n", Poly({(((0, "Z"),), ((0, 1, 1),)): -0.45})),
           ("z_hop", hop(0, 1, 0.6, 0.2, "Z")),
           ("disp", Poly({((), ((0, 1, 0),)): 0.3 + 0.2j, ((), ((0, 0, 1),)): 0.3 - 0.2j}))]
    for lab in ["Z", "X", "Y", "ZZ", "XY", "XZY", "YYXZ"]:
        out.append((f"pauli {lab}", pauli(lab, -0.37)))
    for lab in ["Z", "X", "XX", "YZ", "ZZZ"]:
        out.append((f"pauli_disp {lab}", pauli_disp(lab, 0.25 - 0.1j)))
    for th in (0.05, -0.05):
        out.append((f"n2 {th}", (n_(0) * n_(0)).scale(th)))
    return out
