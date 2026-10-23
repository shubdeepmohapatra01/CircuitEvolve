"""Merge two Pauli exponentials with the same Pauli axis when no anticommutation CHAIN links them (DAG reachability)."""
import math

from v3.api import Rule
from v3.api import dv, pauli

_INV = {"h": "h", "s": "sdg", "sdg": "s", "x": "x", "z": "z", "cx": "cx", "cz": "cz"}
_TOL = 1e-9


def _norm(a):
    """angle mod 2*pi into (-pi, pi]."""
    a = math.fmod(a, 2 * math.pi)
    if a > math.pi:
        a -= 2 * math.pi
    elif a <= -math.pi:
        a += 2 * math.pi
    return a


def _on_grid(a):
    r = a / (math.pi / 4)
    return abs(r - round(r)) < _TOL


def _anti(p, q):
    return bin((p[0] & q[1]) ^ (p[1] & q[0])).count("1") & 1 == 1


def _nodes(ops):
    """[(op index, angle, signed Pauli)] with every rotation's axis conjugated back through preceding Cliffords."""
    nodes = []
    for k, op in enumerate(ops):
        a = dv.rotation(op)
        if a is None:
            continue
        p = pauli.z_on(op[1][0])
        for j in range(k - 1, -1, -1):
            g, qs, _ = ops[j]
            if dv.rotation(ops[j]) is not None:
                continue
            p = pauli.conjugate(p, _INV[g], qs)
        nodes.append((k, _norm(a), p))
    return nodes


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    ops = c.ops
    try:
        nodes = _nodes(ops)
    except (ValueError, KeyError):
        return []
    m = len(nodes)
    out = []
    for a in range(m):
        ka, ta, pa = nodes[a]
        reached = [False] * m
        rlist = [a]
        blockers = 0
        for b in range(a + 1, m):
            pb = nodes[b][2]
            if any(_anti(nodes[r][2], pb) for r in rlist):
                reached[b] = True
                rlist.append(b)
            if pb[0] == pa[0] and pb[1] == pa[1]:
                if reached[b]:
                    continue
                kb, tb, _ = nodes[b]
                if blockers == 0:
                    break                           # adjacent up to commuting nodes: the book rule's case
                if _on_grid(ta) != _on_grid(tb):
                    break
                s = pa[2] * pb[2]
                tot = _norm(ta + s * tb)
                cls = 0 if abs(tot) < _TOL else (1 if _on_grid(tot) else 2)
                out.append((cls, blockers, ka, kb, s))
                break
            if _anti(pa, pb):
                blockers += 1
    out.sort()
    return [(ka, kb, s) for _, _, ka, kb, s in out]


def apply_match(c, mt):
    if not dv.is_angle_circuit(c):
        return c
    ka, kb, s = mt
    ops = list(c.ops)
    ta, tb = dv.rotation(ops[ka]), dv.rotation(ops[kb])
    tot = _norm(ta + s * tb)
    ops[ka] = ("rz", ops[ka][1], tot)
    del ops[kb]
    return dv.with_ops(c, ops)


RULE = Rule(
    name="pauli_exponential_dag_reachability_merge",
    domain="dv",
    kind="procedure",
    contract="exact",
    source="Cowtan et al. QPL 2019 (phase gadget commutation scheduling); Nam et al. 2018 (rotation merging); "
           "topological-order argument on the anticommutation DAG",
    idea="Conjugating every rotation axis back through the Cliffords turns the circuit into an ordered product of "
         "signed Pauli exponentials; exponentials of commuting Paulis commute, so any topological order of the "
         "anticommutation DAG gives the same unitary. Two exponentials on the same Pauli can be made adjacent iff "
         "there is no directed anticommutation path between them, and then they merge by adding angles (+-).",
    trigger=find_matches,
    apply=apply_match,
)
