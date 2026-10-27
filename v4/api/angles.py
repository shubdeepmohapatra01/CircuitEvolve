"""Angles on the dyadic grid - the lever Dyadic Phase Fixing uses (V4_README section 4.2).

An Rz at a multiple of pi/4 is a Clifford / T gate and costs the frozen metric NOTHING to synthesize; any
other angle goes to gridsynth at eps_rz and costs ~3 log2(1/eps_rz) T. So moving an angle onto the grid
k*pi/2^m is worth a lot of T, and it is legal exactly when the error it introduces is PAID FOR out of the
ledger (v4/ledger.py). That trade is what DPF exploits and what v3's rules never did.

    dyadic(theta, kmax)        -> Dyadic(k, m, angle, distance): the nearest k*pi/2^m with m <= kmax
    grid_distance(theta, m)    operator distance of snapping theta onto the 2^-m grid (= |dtheta| / 2)
    on_grid(theta)             is theta already a multiple of pi/4
    fixable(angles, kmax, eps) which angles can be snapped at level <= kmax inside a total budget eps
    greedy_fix(angles, kmax, budget) DPF's own schedule: snap the angles nearest the grid first, while the
                               budget lasts; returns (new angles, spent, [indices fixed])

`distance` is the phase-aligned OPERATOR distance of rz(theta) vs rz(theta'), which is
|exp(-i d/2) - exp(+i d/2)| / ... = |sin(d/2)| with d = theta - theta' - exactly what the judge measures
on a one-rotation window, so a rule can price its own snap before proposing it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

QUARTER = math.pi / 4
GRID_TOL = 1e-9


@dataclass(frozen=True)
class Dyadic:
    k: int                 # numerator
    m: int                 # level: the angle is k * pi / 2^m
    angle: float           # k * pi / 2^m
    distance: float        # phase-aligned operator distance from the original rz to this one
    delta: float           # angle - original


def on_grid(theta, tol: float = GRID_TOL) -> bool:
    if theta is None:
        return True
    r = float(theta) / QUARTER
    return abs(r - round(r)) * QUARTER <= tol


def rz_distance(dtheta: float) -> float:
    """Phase-aligned operator distance between rz(theta) and rz(theta + dtheta): |sin(dtheta / 2)|."""
    return abs(math.sin(float(dtheta) / 2.0))


def dyadic(theta: float, m: int) -> Dyadic:
    """The nearest multiple of pi / 2^m to theta."""
    step = math.pi / (1 << int(m))
    k = int(round(float(theta) / step))
    a = k * step
    return Dyadic(k, int(m), a, rz_distance(a - float(theta)), a - float(theta))


def nearest(theta: float, kmax: int = 10) -> Dyadic:
    """The cheapest snap of theta: the COARSEST level m <= kmax whose nearest point is closest. Levels are
    nested (2^-m divides 2^-(m+1)), so the distance is non-increasing in m; this returns level kmax's
    point but reports the coarsest level it also lies on, which is what sets its T cost."""
    best = dyadic(theta, kmax)
    for m in range(2, int(kmax) + 1):
        d = dyadic(theta, m)
        if abs(d.angle - best.angle) <= 1e-15:
            return d                              # same point, coarser level: cheaper to lower
    return best


def grid_levels(theta: float, kmax: int = 10, budget: float = math.inf) -> list:
    """Every level m in 2..kmax whose nearest point is within `budget`, cheapest level first."""
    return [d for d in (dyadic(theta, m) for m in range(2, int(kmax) + 1)) if d.distance <= budget]


def fixable(angles, kmax: int = 10, budget: float = math.inf) -> dict:
    """{index: Dyadic} for the angles that can be snapped to level <= kmax within `budget` EACH."""
    out = {}
    for i, a in enumerate(angles):
        if on_grid(a):
            continue
        d = nearest(a, kmax)
        if d.distance <= budget:
            out[i] = d
    return out


def greedy_fix(angles, kmax: int = 10, budget: float = math.inf) -> tuple:
    """DPF's schedule: snap the Rz nearest a grid point first, while the TOTAL budget lasts.

    -> (new angles, total distance spent, [(index, Dyadic)] in the order they were fixed)."""
    out = list(float(a) for a in angles)
    cands = sorted(fixable(out, kmax).items(), key=lambda kv: kv[1].distance)
    spent, fixed = 0.0, []
    for i, d in cands:
        if spent + d.distance > budget:
            continue
        out[i] = d.angle
        spent += d.distance
        fixed.append((i, d))
    return out, spent, fixed
