"""Block / circuit cost: explicit T gates + gridsynth T for every rz whose angle is not k*pi/4.

Same counting as phase 0 (experiments/bqskit_baselines/common.py): pygridsynth
`gridsynth_gates(theta, eps)` at mpmath dps 128, eps_rz = 1e-9, T-count = number of 'T' in the word,
each word re-multiplied and checked against RZ(theta) (phase-aligned operator norm <= eps). Angles are
passed to gridsynth exactly as they appear when canonical=False (phase-0 counting of the classical
inputs, as in results/bqskit_baselines/). With canonical=True (the default, used for every block and
pipeline output) each angle is first reduced to [-pi, pi] (rz(x - 2pi) = -rz(x), a global phase), so
rewriting an angle mod 2pi can never count as a gain. Results are cached by the exact float angle.

Acceptance of a block rewrite uses `improves(new, old)`: T must not increase AND either the number of
synthesised rz drops, or (same rz) the explicit T count drops, or (same rz, same T) cx/gate count
drops. A rewrite whose only effect is a different gridsynth T for different angles of the same number
of rotations (angle "noise", typically +-4 T) is NOT an improvement.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from multiprocessing import get_context
from pathlib import Path

from . import REPO
from .circuit_io import classify_angle

EPS_RZ = 1e-9
CACHE_DIR = REPO / ".cache" / "blocks"


def word_distance(word: str, theta: float) -> float:
    import numpy as np
    s2 = 1 / math.sqrt(2)
    G = {"H": np.array([[s2, s2], [s2, -s2]], complex), "S": np.diag([1, 1j]),
         "T": np.diag([1, np.exp(1j * math.pi / 4)]), "X": np.array([[0, 1], [1, 0]], complex),
         "W": np.exp(1j * math.pi / 4) * np.eye(2)}
    U = np.eye(2, dtype=complex)
    for g in word:
        U = U @ G[g]
    R = np.diag([np.exp(-0.5j * theta), np.exp(0.5j * theta)])
    tr = np.trace(R.conj().T @ U)
    ph = tr / abs(tr) if abs(tr) > 0 else 1.0
    return float(np.linalg.norm(U - ph * R, 2))


def _gs_worker(args):
    theta, eps = args
    import mpmath
    from pygridsynth.gridsynth import gridsynth_gates
    mpmath.mp.dps = 128
    t0 = time.time()
    word = gridsynth_gates(mpmath.mpmathify(theta), mpmath.mpmathify(eps))
    word = word if isinstance(word, str) else str(word)
    return theta, word.count("T"), time.time() - t0, word_distance(word, theta)


class Gridsynth:
    """Cached gridsynth T-counts at a fixed eps. key = repr(float angle)."""

    def __init__(self, eps: float = EPS_RZ, path: Path | None = None, procs: int | None = None):
        self.eps = eps
        self.path = Path(path) if path else CACHE_DIR / f"gridsynth_{eps:g}.json"
        # serial by default: one call takes ~0.01-0.03 s, and a spawn pool hangs inside notebook kernels
        self.procs = procs or 1
        self._lock = threading.Lock()
        self.calls = 0
        self.data: dict[str, list] = {}
        if self.path.exists():
            self.data = json.loads(self.path.read_text())

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data))
        os.replace(tmp, self.path)

    def ensure(self, angles) -> None:
        miss = sorted({float(a) for a in angles if repr(float(a)) not in self.data})
        if not miss:
            return
        import multiprocessing as _mp
        if len(miss) <= 3 or self.procs <= 1 or _mp.current_process().name != "MainProcess":
            res = [_gs_worker((a, self.eps)) for a in miss]
        else:
            with get_context("spawn").Pool(min(self.procs, len(miss))) as pool:
                res = pool.map(_gs_worker, [(a, self.eps) for a in miss], chunksize=1)
        with self._lock:
            for a, tc, dt, d in res:
                if not d <= self.eps * 1.0000001:
                    raise RuntimeError(f"gridsynth word for {a!r} has distance {d} > eps")
                self.data[repr(a)] = [tc, dt, d]
            self.calls += len(res)
            self._save()

    def t(self, angle: float) -> int:
        self.ensure([angle])
        return self.data[repr(float(angle))][0]


def canonical_angle(a: float) -> float:
    return math.remainder(float(a), 2 * math.pi)


def rz_angles(ops, canonical: bool = True) -> list:
    """Angles of rz ops that need synthesis (not multiples of pi/4)."""
    f = canonical_angle if canonical else float
    return [f(a) for g, _, a in ops if g == "rz" and classify_angle(float(a)) is None]


def canonicalize(ops) -> list:
    """rz angles reduced to [-pi, pi] (exact up to global phase)."""
    return [(g, qs, canonical_angle(a)) if g == "rz" else (g, qs, a) for g, qs, a in ops]


def ops_cost(ops, gs: Gridsynth, canonical: bool = True) -> dict:
    """{'t': total T, 't_fixed', 't_gs', 'rz': #synthesised rz, 'cx', 'clifford_rz': rz at k*pi/4}."""
    t_fixed = sum(1 for g, _, _ in ops if g in ("t", "tdg"))
    angs = rz_angles(ops, canonical)
    # rz at an odd multiple of pi/4 costs one T
    for g, _, a in ops:
        if g == "rz" and classify_angle(float(a)) is not None:
            t_fixed += classify_angle(float(a)) % 2
    gs.ensure(angs)
    t_gs = sum(gs.data[repr(a)][0] for a in angs)
    cx = sum(1 for g, _, _ in ops if g in ("cx", "cz"))
    return dict(t=t_fixed + t_gs, t_fixed=t_fixed, t_gs=t_gs, rz=len(angs), cx=cx, gates=len(ops))


def cost_key(c: dict) -> tuple:
    """Ranking among verified improvements: T-count, then #synthesised rz, then 2q gates, then gates."""
    return (c["t"], c["rz"], c["cx"], c["gates"])


def improves(new: dict, old: dict) -> bool:
    """Structural improvement (see module docstring)."""
    if new["t"] > old["t"]:
        return False
    if new["rz"] != old["rz"]:
        return new["rz"] < old["rz"]
    if new["t_fixed"] != old["t_fixed"]:
        return new["t_fixed"] < old["t_fixed"] and new["t"] < old["t"]
    return new["t"] == old["t"] and (new["cx"], new["gates"]) < (old["cx"], old["gates"])
