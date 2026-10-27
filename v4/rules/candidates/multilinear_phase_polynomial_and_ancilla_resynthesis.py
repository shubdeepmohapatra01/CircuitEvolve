"""Hadamard-free segments: re-express the synthesized Z-rotations as a multilinear phase polynomial and emit one
rotation per monomial, higher monomials on AND ancillas (Gidney AND compute, unitary inverse as uncompute)."""
import math

from v4.api import Rule
from v4.api import dv

PI4 = math.pi / 4
SYNTH_COST = 32          # approx. gridsynth T-cost of one non-pi/4 rotation at the target eps
AND_COST = 8             # 4 T compute + 4 T unitary uncompute (no measurement in the Clifford+Rz op list)
MAX_SUPPORT = 8
MARGIN = 8

# Gidney temporary AND on (a, b, target)
_AND = [("h", 2), ("t", 2), ("cx", 0, 2), ("cx", 1, 2), ("cx", 2, 0), ("cx", 2, 1),
        ("tdg", 0), ("tdg", 1), ("t", 2), ("cx", 2, 0), ("cx", 2, 1), ("h", 2), ("s", 2)]
_DAG = {"t": "tdg", "tdg": "t", "s": "sdg", "sdg": "s", "h": "h"}


def _is_exact(a):
    k = a / PI4
    return abs(k - round(k)) < 1e-9


def _wrap(a):
    a = math.fmod(a, 2 * math.pi)
    if a > math.pi:
        a -= 2 * math.pi
    elif a <= -math.pi:
        a += 2 * math.pi
    return a


def _rounds(ops):
    """Exact reordering into [(segment_ops, barrier_h_ops)]: every h is deferred past all ops that do not depend
    on it (disjoint qubits commute), so each segment holds the Hadamard-free ops independent of the next h's."""
    rest, out = list(ops), []
    while rest:
        seg, hs, deferred, blocked = [], [], [], set()
        for op in rest:
            qs = set(op[1])
            if qs & blocked:
                deferred.append(op)
                blocked |= qs
            elif op[0] == "h":
                hs.append(op)
                blocked |= qs
            else:
                seg.append(op)
        out.append((seg, hs))
        rest = deferred
    return out


def _analyse(n, seg):
    """-> (kept_ops, poly {mask: alpha}, n_rot) or None. Non-pi/4 rotations are pulled back to segment inputs."""
    lab = {q: (1 << q, 0) for q in range(n)}
    kept, recs = [], []
    for op in seg:
        g, qs, _ = op
        if g == "cx":
            (mc, fc), (mt, ft) = lab[qs[0]], lab[qs[1]]
            lab[qs[1]] = (mc ^ mt, fc ^ ft)
        elif g == "x":
            m, f = lab[qs[0]]
            lab[qs[0]] = (m, f ^ 1)
        elif g in ("rz",) and not _is_exact(float(op[2])):
            m, f = lab[qs[0]]
            recs.append((-float(op[2]) if f else float(op[2]), m))
            continue
        elif g not in ("cz", "z", "s", "sdg", "t", "tdg", "rz"):
            return None
        kept.append(op)
    poly = {}
    for ang, m in recs:
        if bin(m).count("1") > MAX_SUPPORT:
            return None
        t = m
        while t:
            k = bin(t).count("1")
            poly[t] = poly.get(t, 0.0) + ang * (-((-2.0) ** k) / 2.0)
            t = (t - 1) & m
    res = {}
    for t, a in poly.items():
        a = _wrap(a)
        if abs(a) >= 1e-12:
            res[t] = a
    return kept, res, len(recs)


def _tcount(a):
    return int(round(a / PI4)) % 2 if _is_exact(a) else 0


def _cost_new(poly):
    cost = 0
    for t, a in poly.items():
        k = bin(t).count("1")
        cost += AND_COST * (k - 1)
        cost += tcost_rot(a)
    return cost


def tcost_rot(a):
    return _tcount(a) if _is_exact(a) else SYNTH_COST


def trigger(c):
    if not dv.is_angle_circuit(c):
        return []
    out = []
    for k, (seg, _) in enumerate(_rounds(c.ops)):
        r = _analyse(c.n, seg)
        if r is None:
            continue
        _, poly, n_old = r
        if n_old < 2:
            continue
        if SYNTH_COST * n_old - _cost_new(poly) > MARGIN:
            out.append(k)
    return out


def _bits(t):
    return [q for q in range(t.bit_length()) if (t >> q) & 1]


def apply(c, match):
    if not dv.is_angle_circuit(c):
        return c
    rounds = _rounds(c.ops)
    if not isinstance(match, int) or not 0 <= match < len(rounds):
        return c
    n = c.n
    r = _analyse(n, rounds[match][0])
    if r is None:
        return c
    kept, poly, _ = r
    need = max([bin(t).count("1") - 1 for t in poly] + [0])
    d = []
    for t in sorted(poly):
        qs = _bits(t)
        a = poly[t]
        if len(qs) == 1:
            d.append(("rz", (qs[0],), a))
            continue
        comp = []
        cur = qs[0]
        for j, q in enumerate(qs[1:]):
            anc = n + j
            for gt in _AND:
                m = {0: cur, 1: q, 2: anc}
                comp.append((gt[0], tuple(m[x] for x in gt[1:]), None))
            cur = anc
        d += comp
        d.append(("rz", (cur,), a))
        for g, q2, _ in reversed(comp):
            d.append((_DAG.get(g, g), q2, None))
    ops = []
    for k, (seg, hs) in enumerate(rounds):
        ops += (d + kept) if k == match else seg
        ops += hs
    return dv.with_ops(dv.Circuit(n + need, [], dict(c.meta)), ops)


RULE = Rule(
    name="multilinear_phase_polynomial_and_ancilla_resynthesis",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Amy-Maslov-Mosca 2014 (phase polynomials); Welch et al. 2014 (parity->monomial basis); "
           "Gidney 2018 (AND gadget)",
    idea="In a Hadamard-free segment all non-pi/4 rotations commute and pull back to parity phases on the segment "
         "inputs. Using p = 1/2 - 1/2 prod(1-2x_i) they become a multilinear polynomial; emit one rotation per "
         "monomial (degree>=2 on an AND ancilla). Fewer synthesized rotations and a looser per-rotation eps.",
    trigger=trigger,
    apply=apply,
)
