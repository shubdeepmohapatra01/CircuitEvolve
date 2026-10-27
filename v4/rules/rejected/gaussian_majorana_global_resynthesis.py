"""Gaussian (free-fermion) global resynthesis: fold the whole op list into the single R in O(2n) it acts as on
the Majorana operators, Givens-factor R into adjacent-plane rotations, and re-emit those plus the residual
Clifford and a Pauli sign fix. Exact up to global phase; the rule self-checks with the judge's distance."""
import numpy as np

from v4.api import Precondition, Rule
from v4.api import dv, fermion, pauli, sim

_ALLOWED = ("h", "s", "sdg", "x", "z", "cx", "cz", "rz", "t", "tdg")
_TOL = 1e-10


def _off(ops):
    return sum(1 for op in ops if dv.is_rotation(op) and not dv.on_grid(dv.rotation(op)))


def _popcount(v):
    return bin(v).count("1")


def _plane_pauli(a, b, n):
    """(x, z, sigma): the positive Hermitian Pauli P0 of the plane (a, b), with -i g_a g_b = sigma * P0."""
    xa, za, _ = fermion.majorana_pauli(a, n)
    xb, zb, _ = fermion.majorana_pauli(b, n)
    k = ((a & 1) + (b & 1) + 2 * _popcount(za & xb) - 1) % 4     # g = i^k X^x Z^z, Y-type has k = 1
    x, z = xa ^ xb, za ^ zb
    d = (k - _popcount(x & z)) % 4
    return x, z, (1 if d == 0 else -1)


def _plane_ops(a, b, th, n, sigma_on):
    """exp(-i ang/2 P0) as ops, ang = th (times sigma when sigma_on)."""
    x, z, sigma = _plane_pauli(a, b, n)
    ang = dv.reduce_angle(th * (sigma if sigma_on else 1))
    if abs(ang) < 1e-15:
        return []
    qs = [q for q in range(n) if ((x | z) >> q) & 1]
    pre, post = [], []
    for q in qs:
        xq, zq = (x >> q) & 1, (z >> q) & 1
        if xq and zq:
            pre += [("sdg", (q,), None), ("h", (q,), None)]
            post += [("h", (q,), None), ("s", (q,), None)]
        elif xq:
            pre.append(("h", (q,), None))
            post.append(("h", (q,), None))
    chain = [("cx", (qs[i], qs[i + 1]), None) for i in range(len(qs) - 1)]
    return pre + chain + [("rz", (qs[-1],), ang)] + chain[::-1] + post


def _sign_ops(signs, n):
    """A Pauli whose conjugation flips exactly the Majoranas with sign -1 (product of g_j over S)."""
    flip = [j for j, s in enumerate(signs) if s < 0]
    if not flip:
        return []
    S = flip if len(flip) % 2 == 0 else [j for j in range(2 * n) if signs[j] > 0]
    x = z = 0
    for j in S:
        px, pz, _ = fermion.majorana_pauli(j, n)
        x ^= px
        z ^= pz
    return [("x", (q,), None) for q in range(n) if (x >> q) & 1] + \
           [("z", (q,), None) for q in range(n) if (z >> q) & 1]


def _candidates(c):
    ops, n = list(c.ops), c.n
    if any(op[0] not in _ALLOWED for op in ops):
        return []
    recs = pauli.frames(ops)
    if recs is None:
        return []
    planes = []
    for r in recs:
        ab = fermion.bilinear_of(r.p, n)
        if ab is None:
            return []
        planes.append((ab[0], ab[1], r.sign * r.theta))
    cliffs = pauli.residual_clifford(ops)
    out = []
    for sigma_on in (True, False):
        for tau in (1.0, -1.0):
            R = np.eye(2 * n)
            for a, b, th in planes:
                sg = _plane_pauli(a, b, n)[2] if sigma_on else 1
                R = fermion.plane_rotation(a, b, tau * sg * th, n) @ R
            if np.abs(R.T @ R - np.eye(2 * n)).max() > _TOL:
                continue
            rots, signs = fermion.givens(R)
            sgn = _sign_ops(signs, n)
            for rev in (False, True):
                rr = rots[::-1] if rev else rots
                body = []
                for a, b, th in rr:
                    body += _plane_ops(a, b, tau * th, n, sigma_on)
                out.append(sgn + body + cliffs)
                out.append(body + sgn + cliffs)
    return out


def _best(c):
    old = _off(c.ops)
    for cand in _candidates(c):
        if _off(cand) >= old:
            continue
        if sim.distance(list(c.ops), cand, c.n)["op"] <= 1e-9:
            return cand
    return None


def find_matches(c):
    if not dv.is_angle_circuit(c) or not 2 <= c.n <= 8:
        return []
    return [0] if _best(c) is not None else []


def apply_match(c, m):
    new = _best(c)
    return c if new is None else dv.with_ops(c, new)


RULE = Rule(
    name="gaussian_majorana_global_resynthesis",
    domain="dv",
    kind="procedure",
    source="Terhal & DiVincenzo PRA 65 032325; Jozsa & Miyake 2008; Kivlichan et al. PRL 120 110501",
    idea="A Gaussian circuit is one R in O(2n) on the Majoranas; compose all ops into R, Givens-factor it into at "
         "most n(2n-1) adjacent-plane rotations plus a sign Pauli, re-emit with the residual Clifford.",
    error_class="exact",
    resource_class="unitary",
    precondition=Precondition(families=("dv_angle",), needs=("rotations", "measurement_free"), min_qubits=2,
                              max_qubits=8, note="whole-circuit Gaussian"),
    trigger=find_matches,
    apply=apply_match,
)
