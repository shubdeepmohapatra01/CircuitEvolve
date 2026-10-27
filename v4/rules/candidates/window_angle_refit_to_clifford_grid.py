"""Over-parameterized-window numerical refit: pin rz angles to multiples of pi/4, refit the rest (approx)."""
import math

import numpy as np
from scipy.optimize import least_squares

from v4.api import Rule
from v4.api import dv

DELTA_W = 2e-6
MAX_WINDOWS = 100
MAX_SUPPORT = 3
MAX_OPS = 40
N_STARTS = 8
GRID = math.pi / 4

_S = np.diag([1, 1j])
_FIXED = {
    "h": np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2),
    "s": _S,
    "sdg": _S.conj(),
    "x": np.array([[0, 1], [1, 0]], dtype=complex),
    "z": np.diag([1, -1]).astype(complex),
    "t": np.diag([1, np.exp(1j * GRID)]),
    "tdg": np.diag([1, np.exp(-1j * GRID)]),
}


def _is_grid(a):
    r = a / GRID
    return abs(r - round(r)) < 1e-9


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def _apply1(U, m, q, G):
    U = np.moveaxis(U, q, 0)
    sh = U.shape
    U = (G @ U.reshape(2, -1)).reshape(sh)
    return np.moveaxis(U, 0, q)


def _apply2(U, m, qa, qb, G):
    U = np.moveaxis(U, (qa, qb), (0, 1))
    sh = U.shape
    U = (G @ U.reshape(4, -1)).reshape(sh)
    return np.moveaxis(U, (0, 1), (qa, qb))


_CX = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)
_CZ = np.diag([1, 1, 1, -1]).astype(complex)


def _unitary(wops, m, free_pos, theta):
    """wops: list of (name, local qubits, angle); free_pos: op index -> theta index."""
    D = 2 ** m
    U = np.eye(D, dtype=complex).reshape((2,) * m + (D,))
    for i, (g, qs, a) in enumerate(wops):
        if i in free_pos:
            G = np.diag([1, np.exp(1j * theta[free_pos[i]])])
            U = _apply1(U, m, qs[0], G)
        elif g == "rz":
            U = _apply1(U, m, qs[0], np.diag([1, np.exp(1j * a)]))
        elif g == "cx":
            U = _apply2(U, m, qs[0], qs[1], _CX)
        elif g == "cz":
            U = _apply2(U, m, qs[0], qs[1], _CZ)
        else:
            U = _apply1(U, m, qs[0], _FIXED[g])
    return U.reshape(D, D)


def _dist(U, U0):
    """min_phi ||e^{i phi} U - U0||_2 (exact: smallest arc containing the eigenphases of U^dag U0)."""
    M = U.conj().T @ U0
    ph = np.sort(np.angle(np.linalg.eigvals(M)))
    gaps = np.diff(np.concatenate([ph, [ph[0] + 2 * math.pi]]))
    w = 2 * math.pi - gaps.max()
    return 2 * math.sin(min(w, math.pi) / 4) if w < 2 * math.pi else 2.0


def _resid(x, wops, m, free_pos, free_idx, pinned, U0):
    theta = np.zeros(len(free_pos))
    for k, v in pinned.items():
        theta[k] = v
    theta[free_idx] = x
    U = _unitary(wops, m, free_pos, theta)
    tr = np.trace(U.conj().T @ U0)
    ph = np.exp(1j * np.angle(tr)) if abs(tr) > 1e-15 else 1.0
    d = (ph * U - U0).ravel()
    return np.concatenate([d.real, d.imag])


def _refit(wops, m, free_pos, theta0, pinned, U0, rng_seed):
    """Best (distance, theta) over 8 starts with the pinned angles fixed."""
    nf = len(free_pos)
    free_idx = np.array([k for k in range(nf) if k not in pinned], dtype=int)
    full = np.array(theta0, dtype=float)
    for k, v in pinned.items():
        full[k] = v
    if len(free_idx) == 0:
        return _dist(_unitary(wops, m, free_pos, full), U0), full
    rng = np.random.RandomState(rng_seed)
    best = (np.inf, full)
    for s in range(N_STARTS):
        x0 = np.array(theta0, dtype=float)[free_idx]
        if s:
            x0 = x0 + rng.normal(0, 0.5, size=len(free_idx))
        res = least_squares(_resid, x0, args=(wops, m, free_pos, free_idx, pinned, U0),
                            xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=30)
        th = full.copy()
        th[free_idx] = res.x
        d = _dist(_unitary(wops, m, free_pos, th), U0)
        if d < best[0]:
            best = (d, th)
        if d <= DELTA_W or (s == 1 and best[0] > 0.3):
            break
    return best


def _windows(ops):
    out, start, sup = [], 0, set()
    for i, (g, qs, a) in enumerate(ops):
        new = sup | set(qs)
        if len(new) > MAX_SUPPORT or i - start >= MAX_OPS:
            out.append((start, i))
            start, new = i, set(qs)
        sup = new
    out.append((start, len(ops)))
    return out


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    ops = list(c.ops)
    cands = []
    for a, b in _windows(ops):
        free = [i for i in range(a, b) if ops[i][0] == "rz" and not _is_grid(float(ops[i][2]))]
        if len(free) >= 3:
            cands.append((a, b, free))
    cands.sort(key=lambda w: (-len(w[2]), w[0]))
    matches = []
    for a, b, free in cands:
        if len(matches) >= MAX_WINDOWS:
            break
        qubits = sorted({q for g, qs, _ in ops[a:b] for q in qs})
        loc = {q: j for j, q in enumerate(qubits)}
        m = len(qubits)
        wops = [(g, tuple(loc[q] for q in qs), (float(x) if g == "rz" else None)) for g, qs, x in ops[a:b]]
        free_pos = {i - a: k for k, i in enumerate(free)}
        theta0 = np.array([float(ops[i][2]) for i in free])
        U0 = _unitary(wops, m, free_pos, theta0)
        cur = theta0.copy()
        pinned = {}
        for k in sorted(range(len(free)), key=lambda k: (-abs(_wrap(theta0[k])), k)):
            t = _wrap(theta0[k])
            near = round(t / GRID) * GRID
            vals = [near] + [v for v in (0.0, GRID, -GRID, math.pi / 2, -math.pi / 2) if abs(v - near) > 1e-9]
            for g in vals:
                trial = dict(pinned)
                trial[k] = g
                d, th = _refit(wops, m, free_pos, cur, trial, U0, 1000 + a * 7 + k)
                if d <= DELTA_W:
                    pinned = trial
                    cur = th
                    break
        if pinned:
            new = tuple(float(pinned[k]) if k in pinned else float(cur[k]) for k in range(len(free)))
            matches.append((a, b, tuple(free), new))
    return matches


def apply_match(c, m):
    if not dv.is_angle_circuit(c):
        return c
    a, b, free, new = m
    ops = list(c.ops)
    for i, ang in zip(free, new):
        ops[i] = ("rz", ops[i][1], float(ang))
    return dv.with_ops(c, ops)


RULE = Rule(
    name="window_angle_refit_to_clifford_grid",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="Younis et al. QFAST/QSearch/BQSKit instantiation; Madden-Simonetto best approximate compiling; gridsynth (Ross-Selinger)",
    idea="In <=3-qubit windows with >=3 non-pi/4 rotations, greedily pin angles to multiples of pi/4 and refit "
         "the remaining angles numerically so the window unitary stays within 2e-6 (phase-aligned operator norm); "
         "pinned rotations become exact Clifford/T gates and no longer cost gridsynth T.",
    trigger=find_matches,
    apply=apply_match,
)
