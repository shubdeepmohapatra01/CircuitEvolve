"""Phase-gradient catalysis: probe version (trigger per card; apply only adds the clean catalyst register)."""
import math

from v4.api import Rule
from v4.api import dv

TWO_PI = 2 * math.pi
MIN_ROTATIONS = 8


def _residual_depth(theta):
    """Smallest m <= 12 with theta - nearest multiple of pi/4 an integer multiple of 2*pi/2^m, else None."""
    t = math.fmod(theta, TWO_PI)
    r = t - round(t / (math.pi / 4)) * (math.pi / 4)
    for m in range(3, 13):
        u = r * (1 << m) / TWO_PI
        if abs(u - round(u)) < 1e-9:
            return m
    return None


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    depths = []
    for op in c.ops:
        if op[0] != "rz":
            continue
        t = float(op[2])
        if abs(t / (math.pi / 4) - round(t / (math.pi / 4))) < 1e-9:
            continue
        d = _residual_depth(t)
        if d is None:
            return []
        depths.append(d)
    if len(depths) < MIN_ROTATIONS:
        return []
    return [max(depths)]


def apply_match(c, m):
    n = c.n
    ops = []
    for b in range(m):                       # catalyst prep: H then rz(2 pi 2^b / 2^m) on qubit n+b
        ops.append(("h", (n + b,), None))
        ops.append(("rz", (n + b,), TWO_PI * (1 << b) / (1 << m)))
    ops += list(c.ops)
    for b in reversed(range(m)):             # unprep
        ops.append(("rz", (n + b,), -TWO_PI * (1 << b) / (1 << m)))
        ops.append(("h", (n + b,), None))
    return dv.Circuit(n + m, dv.normalize(ops), dict(c.meta))


RULE = Rule(
    name="phase_gradient_catalysis_dyadic_rotations",
    domain="dv",
    kind="resource",
    contract="relaxed",
    source="Kitaev-Shen-Vyalyi 2002; Gidney 2018 (arXiv:1709.06648); Gidney-Ekera 2021",
    idea="A phase-gradient register |grad_m> is an eigenvector of constant addition, so controlled addition of c "
         "into it acts as a Z-rotation by -2 pi c / 2^m on the control with no synthesis; dyadic QFT rotations "
         "become adders built from measurement-uncomputed ANDs, and the catalyst is reused and uncomputed free.",
    trigger=find_matches,
    apply=apply_match,
)
