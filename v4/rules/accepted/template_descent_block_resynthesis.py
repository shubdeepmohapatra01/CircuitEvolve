"""Skeleton-shrinking block resynthesis: delete one cx from a block's template, refit every rz angle against
the block's exact unitary, keep the shorter skeleton if the phase-aligned distance stays inside the block's
share and the (off-grid rotations, cx) cost strictly falls; recurse, then pin leftover angles to the grid."""
import random

import numpy as np

from v4.api import Precondition, Rule
from v4.api import blocks, budget, dv, refit, sim

SHARE = 1e-6          # per-block distance cap (a fit that works lands near 1e-12)
MAX_NFEV = 80
MAX_DELETIONS = 6     # cx deletions tried per descent level
MAX_BLOCKS = 400


def _offgrid(ops):
    return sum(1 for g, _, a in ops if g == "rz" and not dv.on_grid(a))


def _cx(ops):
    return sum(1 for g, _, _ in ops if g in ("cx", "cz"))


def _cost(ops):
    return (_offgrid(ops), _cx(ops))


def _pattern(ops):
    """(pattern, angles): every off-grid rz becomes a free slot, everything else a fixed gate."""
    pat, ang = [], []
    for g, qs, a in ops:
        if g == "rz" and not dv.on_grid(a):
            pat.append(("rz", tuple(qs)))
            ang.append(float(a))
        elif g == "rz":
            pat.append(("rz_fixed", tuple(qs), float(a)))
        else:
            pat.append((g, tuple(qs)))
    return pat, ang


def _template(pat):
    def template(angles):
        out, j = [], 0
        for e in pat:
            if e[0] == "rz":
                out.append(("rz", e[1], float(angles[j])))
                j += 1
            elif e[0] == "rz_fixed":
                out.append(("rz", e[1], e[2]))
            else:
                out.append((e[0], e[1], None))
        return out
    return template


def _entangle_order(pat, k):
    """Indices of two-qubit gates, ordered by how many rotation slots sit on their qubits (fewest first)."""
    idx = [i for i, e in enumerate(pat) if e[0] in ("cx", "cz")]
    def weight(i):
        qs = set(pat[i][1])
        return sum(1 for e in pat if e[0] == "rz" and qs & set(e[1]))
    return sorted(idx, key=lambda i: (weight(i), i))


def _descend(U, k, ops, x0):
    """Greedy descent from ops; returns the best (ops, distance) found, or None."""
    best, best_d = None, 0.0
    cur_pat, cur_x = _pattern(ops)[0], list(x0)
    cur_cost = _cost(ops)
    rng = random.Random(7)
    while True:
        improved = False
        for i in _entangle_order(cur_pat, k)[:MAX_DELETIONS]:
            pat = cur_pat[:i] + cur_pat[i + 1:]
            tmpl = _template(pat)
            nang = sum(1 for e in pat if e[0] == "rz")
            starts = [list(cur_x)[:nang] + [0.0] * max(0, nang - len(cur_x)),
                      [rng.uniform(-3.1, 3.1) for _ in range(nang)]]
            fit = None
            for s in starts:
                if nang == 0:
                    f = refit.Fit((), sim.hs_distance(U, sim.unitary(tmpl([]), k))["op"], True, 0)
                else:
                    f = refit.least_squares(tmpl, U, s, n=k, max_nfev=MAX_NFEV)
                if fit is None or f.distance < fit.distance:
                    fit = f
                if fit.distance <= SHARE * 1e-3:
                    break
            if fit.distance > SHARE:
                continue
            f2, _ = (refit.pin_to_grid(tmpl, U, fit.angles, k, SHARE) if nang else (fit, []))
            if f2.distance > SHARE:
                f2 = fit
            new_ops = tmpl(list(f2.angles))
            c = _cost([(g, q, a) for g, q, a in new_ops])
            if c < cur_cost:
                best, best_d = new_ops, f2.distance
                cur_pat, cur_x, cur_cost = pat, list(f2.angles), c
                improved = True
                break
        if not improved:
            break
    return (best, best_d) if best is not None else None


def trigger(c):
    if not dv.is_angle_circuit(c):
        return []
    out = []
    for b in blocks.blocks_with_rotations(c, 4, 40, minimum=3)[:MAX_BLOCKS]:
        if b.k < 2 or _cx(b.local_ops) < 2:
            continue
        try:
            U = sim.unitary(b.local_ops, b.k)
            ops = [(g, tuple(q), a) for g, q, a in b.local_ops]
            res = _descend(U, b.k, ops, _pattern(ops)[1])
        except Exception:
            continue
        if res is None:
            continue
        new_ops, d = res
        d_true = sim.hs_distance(U, sim.unitary(new_ops, b.k))["op"]
        if d_true <= SHARE and _cost(new_ops) < _cost(b.local_ops):
            out.append((b.lo, b.hi, tuple(new_ops), float(d_true), _cost(b.local_ops)[0] - _cost(new_ops)[0]))
    out.sort(key=lambda m: (-m[4], m[3], m[0]))
    return out


def apply(c, m):
    lo, hi, new_ops, d, _ = m
    if not dv.is_angle_circuit(c):
        return c
    ops = list(c.ops)
    # recover block qubits from the span
    qs = tuple(sorted({q for op in ops[lo:hi] for q in op[1]}))
    blk = blocks._make(0, lo, hi, set(qs), ops)
    if not budget.draw(d + 1e-12):
        return c
    return dv.with_ops(c, blocks.splice(ops, blk, list(new_ops)))


RULE = Rule(
    name="template_descent_block_resynthesis",
    domain="dv",
    kind="procedure",
    error_class="approx",
    resource_class="unitary",
    source="Younis et al. QFAST/QSearch template descent; Davis et al. LEAP; KAK parameter-count bound",
    idea="Delete one cx at a time from a width<=4 block's skeleton and refit all rz angles to the block's exact "
         "unitary; keep the shorter skeleton when the fit is within the block share and (off-grid rz, cx) falls.",
    precondition=Precondition(families=("dv_angle",), needs=("nonclifford_rz", "two_qubit"),
                              min_qubits=2, max_qubits=20),
    trigger=trigger,
    apply=apply,
)
