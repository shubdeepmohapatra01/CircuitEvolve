"""Phase-polynomial rotation merging in Hadamard-free segments (Nam et al. 2018; Amy-Maslov-Mosca 2014)."""
import math

from v3.api import Rule
from v3.api import dv

_TWO_PI = 2 * math.pi
_DIAG = {"t": math.pi / 4, "tdg": -math.pi / 4, "s": math.pi / 2, "sdg": -math.pi / 2, "z": math.pi}
_PERM = ("cx", "x")
_CLIFF_DIAG = ("s", "sdg", "z")


def _angle(op):
    if op[0] == "rz":
        return float(op[2])
    return _DIAG.get(op[0])


def _reduce(theta):
    t = math.fmod(theta, _TWO_PI)
    if t <= -math.pi:
        t += _TWO_PI
    elif t > math.pi:
        t -= _TWO_PI
    return t


def _groups(ops):
    """Yield (key, [(index, sign)]) for each parity key in each Hadamard-free segment."""
    n_q = 1 + max((q for op in ops for q in op[1]), default=0)
    out = []
    p = c = None

    def flush(groups):
        out.extend(groups.values())

    groups = {}
    for idx, op in enumerate(ops):
        g, qs, _ = op
        if g in _PERM or _angle(op) is not None:
            if p is None:
                p = [1 << q for q in range(n_q)]
                c = [0] * n_q
                groups = {}
            if g == "cx":
                a, b = qs
                p[b] ^= p[a]
                c[b] ^= c[a]
            elif g == "x":
                c[qs[0]] ^= 1
            else:
                q = qs[0]
                groups.setdefault(p[q], []).append((idx, -1 if c[q] else 1))
        else:
            if p is not None:
                flush(groups)
            p = c = None
            groups = {}
    if p is not None:
        flush(groups)
    return out


def find_matches(circuit):
    if not dv.is_angle_circuit(circuit):
        return []
    ops = circuit.ops
    matches = []
    for members in _groups(ops):
        for k in range(0, len(members) - 1, 2):
            (i, si), (j, sj) = members[k], members[k + 1]
            if ops[i][0] in _CLIFF_DIAG and ops[j][0] in _CLIFF_DIAG:
                continue
            matches.append((i, j))
    matches.sort(key=lambda m: -max(abs(_angle(ops[m[0]])), abs(_angle(ops[m[1]]))))
    return matches


def apply_match(circuit, match):
    i, j = match
    ops = list(circuit.ops)
    # recompute signs from the parity bookkeeping of the original circuit
    sign = {}
    for members in _groups(ops):
        for idx, s in members:
            sign[idx] = s
    si, sj = sign[i], sign[j]
    eff = _reduce(si * _angle(ops[i]) + sj * _angle(ops[j]))
    stored = si * eff
    if abs(eff) < 1e-12:
        new = []
    else:
        new = [("rz", ops[i][1], stored)]
    out = ops[:i] + new + ops[i + 1:j] + ops[j + 1:]
    return dv.with_ops(circuit, out)


RULE = Rule(
    name="phase_polynomial_rotation_merge",
    domain="dv",
    kind="procedure",
    contract="exact",
    source="Nam, Ross, Su, Childs, Maslov 2018 (rotation merging); Amy-Maslov-Mosca 2014 (phase polynomials)",
    idea="In a Hadamard-free segment of cx/x/diagonal gates, track each wire's affine parity label; two diagonal "
         "rotations whose labels are equal act about the same Z-parity operator and commute, so they add: "
         "rz(a) ... rz(+-b) -> rz(a +- b) at the first position, the second is deleted. Exact up to global phase.",
    trigger=find_matches,
    apply=apply_match,
)
