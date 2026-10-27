"""Global budget concentration: spend the shared error pool on the few rotations nearest the pi/4 grid.

Rz(theta) = Rz(theta*) Rz(theta - theta*), theta* the nearest multiple of pi/4. The first factor is a free
Clifford / T gate; the residual is dropped and its phase-aligned distance (angles.rz_distance) is drawn
from the shared ledger. Candidates are ranked by (T saved) / cost over the WHOLE circuit, so the pool goes
to the globally best rotations instead of being split between blocks.
"""
import math

from v4.api import Precondition, Rule
from v4.api import angles as A, budget, dv

# gridsynth gain proxy: a snap onto a pi/2 multiple removes a whole synthesized sequence, a snap onto an
# odd pi/4 multiple leaves one T behind. The synthesized length is common to all rotations, so the ratio
# 1 : (1 - 1/T_rz) is what orders them; T_rz ~ 50 is only used as a tie-break scale.
T_RZ = 50.0
MIN_COST = 1e-15
POOL = 5e-4                    # the shared pool's size, as a trigger-time view of it


def _snap(theta):
    d = A.dyadic(theta, 2)
    gain = T_RZ if d.k % 2 == 0 else T_RZ - 1.0
    return d.angle, d.distance, gain


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    left = max(budget.remaining(), POOL)          # apply() draws, so the ledger still has the last word
    out = []
    for i, op in enumerate(c.ops):
        if op[0] != "rz" or dv.on_grid(op[2]):
            continue
        target, cost, gain = _snap(float(op[2]))
        if cost <= left:
            out.append((gain / max(cost, MIN_COST), i, tuple(op[1]), float(op[2]), target, cost))
    out.sort(key=lambda m: (-m[0], m[1]))
    return [(i, qs, th, tgt, cost) for _, i, qs, th, tgt, cost in out]


def apply_match(c, m):
    i, qs, theta, target, cost = m
    if i >= len(c.ops):
        return c
    op = c.ops[i]
    if op[0] != "rz" or tuple(op[1]) != tuple(qs) or abs(float(op[2]) - theta) > 1e-12:
        return c
    if cost > budget.remaining():
        return c                                  # the runner prices and charges the measured distance
    ops = list(c.ops)
    ops[i] = ("rz", tuple(qs), float(target))
    return dv.with_ops(c, ops)


RULE = Rule(
    name="global_budget_concentration_near_clifford_angle_snapping",
    domain="dv",
    kind="procedure",
    error_class="approx",
    resource_class="unitary",
    precondition=Precondition(families=("dv_angle",), needs=("nonclifford_rz",), min_qubits=2,
                              max_qubits=20,
                              note="needs an off-grid rz within the pool's distance of the pi/4 grid"),
    source="Ross & Selinger arXiv:1403.2975 (3 log2(1/eps) cost law); Campbell PRA 95 042306 and "
           "Bocharov-Roetteler-Svore on non-uniform error allocation across rotations",
    idea="Rank every off-grid rotation of the whole circuit by (T saved)/(distance to the nearest pi/4 "
         "multiple) and snap the best ones while the shared error pool lasts, so the whole pool is "
         "concentrated on the globally cheapest snaps rather than divided between blocks.",
    trigger=find_matches,
    apply=apply_match,
)
