"""Shared helpers for the BQSKit / TKET / pyzx baseline pipelines (no LLM).

Gridsynth: pygridsynth.gridsynth.gridsynth_gates(theta, eps) — the exact call made by
bqskit-ft's GridSynthPass.run_rz (bqskit/ft/ftpasses/gridsynth.py), at mpmath.mp.dps = 128.
The returned word is over {H, S, T, X, W}; T-count = number of 'T' characters.
eps is pygridsynth's operator-norm error bound for each Rz approximation.
"""
from __future__ import annotations

import math
import os
import time
from multiprocessing import get_context
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
QASM = REPO / 'benchmarks' / 'bqskit_qseed' / 'qasm'
OUT = REPO / 'results' / 'bqskit_baselines'

EVAL = ['add/add_17', 'hhl/hhl_6', 'mult/mult_16', 'qft/qft_32', 'shor/shor_16']

# arXiv:2409.00433 Table 3, By Gate (T-count from published_baselines.csv; RZ counts from task brief)
PUBLISHED_BYGATE = {
    'add_17': dict(t=23562, rz=251),
    'hhl_6': dict(t=22571, rz=243),
    'mult_16': dict(t=100678, rz=1079),
    'qft_32': dict(t=101480, rz=1080),
    'shor_16': dict(t=74797, rz=816),
}

TWO_PI = 2 * math.pi


def norm_angle(theta: float) -> float:
    """Map to (-pi, pi]."""
    t = math.fmod(theta, TWO_PI)
    if t <= -math.pi:
        t += TWO_PI
    elif t > math.pi:
        t -= TWO_PI
    return t


def is_clifford_t_angle(theta: float, tol: float = 1e-9) -> int | None:
    """Return k in 0..7 if theta = k*pi/4 within tol, else None."""
    k = theta / (math.pi / 4)
    r = round(k)
    if abs(k - r) * (math.pi / 4) <= tol:
        return int(r) % 8
    return None


def _gs_worker(args):
    theta, eps = args
    import mpmath
    from pygridsynth.gridsynth import gridsynth_gates
    mpmath.mp.dps = 128
    t0 = time.time()
    word = gridsynth_gates(mpmath.mpmathify(theta), mpmath.mpmathify(eps))
    word = str(word) if not isinstance(word, str) else word
    dt = time.time() - t0
    return theta, word.count('T'), len(word), dt, word_distance(word, theta)


def word_distance(word: str, theta: float) -> float:
    """Phase-invariant operator-norm distance between the word (matrix order) and Rz(theta)."""
    import numpy as np
    s2 = 1 / math.sqrt(2)
    G = {'H': np.array([[s2, s2], [s2, -s2]], complex), 'S': np.diag([1, 1j]),
         'T': np.diag([1, np.exp(1j * math.pi / 4)]), 'X': np.array([[0, 1], [1, 0]], complex),
         'W': np.exp(1j * math.pi / 4) * np.eye(2)}
    U = np.eye(2, dtype=complex)
    for g in word:
        U = U @ G[g]
    R = np.diag([np.exp(-0.5j * theta), np.exp(0.5j * theta)])
    tr = np.trace(R.conj().T @ U)
    ph = tr / abs(tr) if abs(tr) > 0 else 1.0
    return float(np.linalg.norm(U - ph * R, 2))


def gridsynth_tcounts(angles, eps: float, procs: int | None = None) -> dict[float, tuple]:
    """gridsynth(theta, eps) for each DISTINCT angle (exact float key).

    Returns {theta: (t_count, word_len, seconds, verified_distance)}.
    """
    uniq = sorted(set(float(a) for a in angles))
    if not uniq:
        return {}
    procs = procs or max(1, (os.cpu_count() or 2) - 2)
    with get_context('spawn').Pool(procs) as pool:
        res = pool.map(_gs_worker, [(a, eps) for a in uniq], chunksize=4)
    return {a: (tc, ln, dt, d) for a, tc, ln, dt, d in res}


def gridsynth_summary(angles, eps: float, cache: dict | None = None) -> dict:
    """Total gridsynth T-count / time over a list of RZ angles (with repeats)."""
    cache = cache if cache is not None else {}
    missing = [a for a in set(map(float, angles)) if a not in cache]
    cache.update(gridsynth_tcounts(missing, eps))
    tc = sum(cache[float(a)][0] for a in angles)
    secs = sum(cache[float(a)][2] for a in set(map(float, angles)))
    maxd = max((cache[float(a)][3] for a in angles), default=0.0)
    return dict(gs_t=tc, gs_seconds_distinct=secs, gs_max_dist=maxd,
                distinct_angles=len(set(map(float, angles))))
