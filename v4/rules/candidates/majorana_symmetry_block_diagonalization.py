"""Symmetry-reduced Givens resynthesis of a Gaussian (free-fermion) circuit.

R in O(2n) is the circuit's action on the Majoranas. If R commutes with an involutive signed Majorana
permutation S, a pi/4 plane-rotation basis change W block-diagonalises S, hence R, and each block is
Givens-decomposed on its own: d(d-1)/2 off-grid rotations per block instead of 2n(2n-1)/2."""
import math

import numpy as np

from v4.api import Precondition, Rule
from v4.api import dv, fermion, pauli

_QUARTER = math.pi / 4
_COMMUTE_TOL = 1e-9
_VERIFY_TOL = 1e-8
_OFF_COST = 50


def _perms(n):
    N = 2 * n
    q_of = lambda j: divmod(j, 2)
    out = {
        "identity": list(range(N)),
        "reverse": [N - 1 - j for j in range(N)],
        "site_reflect": [2 * (n - 1 - q) + k for q, k in map(q_of, range(N))],
        "site_reflect_swap": [2 * (n - 1 - q) + 1 - k for q, k in map(q_of, range(N))],
        "swap_in_site": [2 * q + 1 - k for q, k in map(q_of, range(N))],
        "half_shift": [(j + n) % N for j in range(N)],
    }
    return out


def _signs(n):
    N = 2 * n
    pats = {
        "plus": [1] * N,
        "alt_j": [(-1) ** j for j in range(N)],
        "alt_q": [(-1) ** (j // 2) for j in range(N)],
        "half": [1 if j < n else -1 for j in range(N)],
        "half_site": [1 if j // 2 < n // 2 else -1 for j in range(N)],
        "even_only": [-1 if j % 2 == 0 else 1 for j in range(N)],
        "odd_site": [-1 if (j // 2) % 2 else 1 for j in range(N)],
    }
    base = list(pats.items())
    out = dict(base)
    for i, (na, a) in enumerate(base):
        for nb, b in base[i + 1:]:
            out[na + "*" + nb] = [x * y for x, y in zip(a, b)]
    return out


def _family(n):
    N = 2 * n
    perms, signs = _perms(n), _signs(n)
    out = []
    for pn, p in perms.items():
        for sn, e in signs.items():
            S = np.zeros((N, N))
            for j in range(N):
                S[p[j], j] = e[j]
            if np.allclose(S @ S, np.eye(N)) and not np.allclose(S, np.eye(N)) and not np.allclose(S, -np.eye(N)):
                out.append((pn + "/" + sn, S))
    return out


def _plane_ops(a, b, theta, n, cache):
    """Pauli-rotation ops realising plane_rotation(a, b, theta), sign calibrated against orthogonal_of."""
    xa, za, _ = fermion.majorana_pauli(a, n)
    xb, zb, _ = fermion.majorana_pauli(b, n)
    x, z = xa ^ xb, za ^ zb
    qs = [q for q in range(n) if ((x | z) >> q) & 1]

    def build(th):
        pre, post = [], []
        for q in qs:
            xq, zq = (x >> q) & 1, (z >> q) & 1
            if xq and zq:
                pre += [("sdg", (q,), None), ("h", (q,), None)]
                post = [("h", (q,), None), ("s", (q,), None)] + post
            elif xq:
                pre.append(("h", (q,), None))
                post = [("h", (q,), None)] + post
        chain = [("cx", (qs[i], qs[i + 1]), None) for i in range(len(qs) - 1)]
        return pre + chain + [("rz", (qs[-1],), float(th))] + chain[::-1] + post

    key = (a, b)
    if key not in cache:
        test = fermion.orthogonal_of(build(0.3), n)
        if test is not None and np.allclose(test, fermion.plane_rotation(a, b, 0.3, n), atol=1e-9):
            cache[key] = 1
        elif test is not None and np.allclose(test, fermion.plane_rotation(a, b, -0.3, n), atol=1e-9):
            cache[key] = -1
        else:
            cache[key] = 0
    s = cache[key]
    if s == 0:
        return None
    return build(s * theta)


def _snap(t):
    t = dv.reduce_angle(t)
    r = t / _QUARTER
    if abs(r - round(r)) * _QUARTER < 1e-9:
        return round(r) * _QUARTER
    return t


def _cost(ops):
    total = 0
    for op in ops:
        th = dv.rotation(op)
        if th is None:
            continue
        k = round(th / _QUARTER)
        total += (k % 2) if dv.on_grid(th) else _OFF_COST
    return total


def _build(c, R, S):
    """New op list realising R via the S-block form, or None."""
    n = c.n
    N = 2 * n
    W = np.eye(N)
    planes = []
    for j in range(N):
        k = int(np.argmax(np.abs(S[:, j])))
        if k > j:
            phi = _QUARTER * (1 if S[k, j] > 0 else -1)
            planes.append((j, k, phi))
            W = fermion.plane_rotation(j, k, phi, n) @ W
    M = W.T @ R @ W
    Sd = W.T @ S @ W
    if np.max(np.abs(Sd - np.diag(np.diag(Sd)))) > 1e-9:
        return None
    diag = np.round(np.diag(Sd))
    idx = [[i for i in range(N) if diag[i] == 1], [i for i in range(N) if diag[i] == -1]]
    mask = np.zeros((N, N), bool)
    for I in idx:
        mask[np.ix_(I, I)] = True
    if np.max(np.abs(M[~mask])) > 1e-8:
        return None
    cache = {}
    steps, flips = [], []
    for I in idx:
        if len(I) < 2:
            if len(I) == 1 and M[I[0], I[0]] < 0:
                flips.append(I[0])
            continue
        rots, sg = fermion.givens(M[np.ix_(I, I)])
        steps += [(I[a], I[b], th) for a, b, th in rots]
        flips += [I[p] for p, s in enumerate(sg) if s < 0]
    if len(flips) % 2:
        return None
    seq = [(j, k, -phi) for j, k, phi in planes]
    seq += [(flips[i], flips[i + 1], math.pi) for i in range(0, len(flips), 2)]
    seq += steps
    seq += [(j, k, phi) for j, k, phi in planes]
    net = []
    for a, b, th in seq:
        th = _snap(th)
        if abs(th) < 1e-12:
            continue
        o = _plane_ops(min(a, b), max(a, b), th if a < b else -th, n, cache)
        if o is None:
            return None
        net += o
    new = net + pauli.residual_clifford(c.ops)
    R2 = fermion.orthogonal_of(new, n)
    if R2 is None or np.max(np.abs(R2 - R)) > _VERIFY_TOL:
        return None
    return new


def _reflect(c):
    return dv.is_angle_circuit(c) and 2 <= c.n <= 14


def find_matches(c):
    if not _reflect(c):
        return []
    ops = c.ops
    if not fermion.is_gaussian(ops, c.n):
        return []
    recs = pauli.frames(ops)
    if not recs or any(fermion.bilinear_of(r.p, c.n) is None for r in recs):
        return []
    R = fermion.orthogonal_of(ops, c.n)
    if R is None:
        return []
    old = _cost(ops)
    best = None
    for name, S in _family(c.n):
        if np.linalg.norm(R @ S - S @ R) >= _COMMUTE_TOL:
            continue
        new = _build(c, R, S)
        if new is None:
            continue
        cost = _cost(new)
        if cost < old and (best is None or cost < best[0]):
            best = (cost, name)
    return [best[1]] if best else []


def apply_match(c, m):
    R = fermion.orthogonal_of(c.ops, c.n)
    if R is None:
        return c
    for name, S in _family(c.n):
        if name == m:
            new = _build(c, R, S)
            return c if new is None else dv.with_ops(c, new)
    return c


RULE = Rule(
    name="majorana_symmetry_block_diagonalization",
    domain="dv",
    kind="procedure",
    error_class="exact",
    resource_class="unitary",
    source="Kivlichan et al., PRL 120, 110501 (2018); Jiang et al., PRApplied 9, 044036 (2018); Clements et al., "
           "Optica 3, 1460 (2016); isotypic block decomposition of a commuting orthogonal matrix",
    idea="A Gaussian circuit is one R in O(2n) on the Majoranas. If R commutes with an involutive signed Majorana "
         "permutation S, a pi/4 plane-rotation basis change W block-diagonalises R into R_+ (+) R_-; Givens-decompose "
         "each block separately (d(d-1)/2 planes each instead of N(N-1)/2) and wrap with W, W^T. Exact up to "
         "global phase.",
    precondition=Precondition(families=("dv_angle",), needs=("rotations", "measurement_free"),
                              min_qubits=2, max_qubits=14,
                              note="Gaussian Clifford+Rz circuits only; the trigger checks Gaussianity and symmetry"),
    trigger=find_matches,
    apply=apply_match,
)
