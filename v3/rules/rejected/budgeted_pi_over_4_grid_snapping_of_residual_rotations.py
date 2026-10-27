"""Budgeted pi/4 grid snapping: drop the tiny residual rz(delta) of a rotation so it becomes exactly Clifford+T."""
import math

from v3.api import Rule
from v3.api import dv

BUDGET = 5e-4          # eps/2 approx budget on the stage-1 circuits at eps = 1e-3
FRACTION = 0.9
TOL = 1e-9


def _normalize(a):
    a = math.fmod(a, 2 * math.pi)
    if a > math.pi:
        a -= 2 * math.pi
    elif a <= -math.pi:
        a += 2 * math.pi
    return a


def find_matches(c):
    """(position, m, d): snap rotation at `position` to the pi/4 multiple m at phase-aligned cost d, cheapest first."""
    if not dv.is_angle_circuit(c):
        return []
    out = []
    for i, op in enumerate(c.ops):
        a = dv.rotation(op)
        if a is None:
            continue
        a = _normalize(a)
        m = (math.pi / 4) * round(4 * a / math.pi)
        delta = a - m
        if abs(delta) <= TOL:
            continue
        d = 2 * abs(math.sin(delta / 4))
        if d <= FRACTION * BUDGET:
            out.append((i, m, d))
    out.sort(key=lambda t: (t[2], t[0]))
    return out


def apply_match(c, match):
    i, m, _ = match
    ops = list(c.ops)
    if not (0 <= i < len(ops)) or dv.rotation(ops[i]) is None:
        return c
    if abs(_normalize(m)) <= TOL:
        del ops[i]
    else:
        ops[i] = ("rz", ops[i][1], m)
    return dv.with_ops(c, ops)


RULE = Rule(
    name="budgeted_pi_over_4_grid_snapping_of_residual_rotations",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="Coppersmith 1994 / Barenco et al. 1996 (approximate QFT rotation truncation); Ross-Selinger 2016 cost model",
    idea="rz(a) = rz(m) rz(delta) with m the nearest multiple of pi/4; dropping rz(delta) costs exactly "
         "2|sin(delta/4)| in phase-aligned operator distance, and makes the gate exactly Clifford+T (or the identity "
         "if m = 0), saving its ~3 log2(1/eps_rz) gridsynth T gates. Candidates are emitted cheapest-distance first "
         "so the runner spends the otherwise unused approximation budget greedily.",
    trigger=find_matches,
    apply=apply_match,
)
