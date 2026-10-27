"""Pauli-exponential normal form: front-frame Paulis of all rotations, merge commuting-reachable equal-Pauli pairs."""
import math

from v4.api import Precondition, Rule
from v4.api import dv, pauli

_INV = {"s": "sdg", "sdg": "s"}
_CLIFF = ("h", "s", "sdg", "x", "z", "cx", "cz")
_TOL = 1e-9
_Q = math.pi / 4


def _on_grid(theta):
    r = theta / _Q
    return abs(r - round(r)) < _TOL / _Q * 4


def _reduce(theta):
    t = math.fmod(theta, 2 * math.pi)
    if t > math.pi:
        t -= 2 * math.pi
    elif t <= -math.pi:
        t += 2 * math.pi
    return t


def _commute(a, b):
    return (bin((a[0] & b[1]) ^ (a[1] & b[0])).count("1") & 1) == 0


def _records(ops):
    """[(op position, theta, (x, z) key, eta)] with front-frame Pauli of every rotation op."""
    recs = []
    prefix = []                       # Clifford ops seen so far
    for pos, op in enumerate(ops):
        g, qs, _ = op
        th = dv.rotation(op)
        if th is None:
            if g not in _CLIFF:
                return None
            prefix.append((_INV.get(g, g), qs))
            continue
        p = pauli.z_on(qs[0])
        for gi, qi in reversed(prefix):
            p = pauli.conjugate(p, gi, qi)
        recs.append((pos, th, (p[0], p[1]), p[2], op[0] == "rz" and not _on_grid(th)))
    return recs


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    recs = _records(c.ops)
    if not recs:
        return []
    cand = []
    for k in range(len(recs)):
        pk, tk, keyk, ek, nk = recs[k]
        for j in range(k - 1, -1, -1):
            pj, tj, keyj, ej, nj = recs[j]
            if keyj == keyk:
                s = ej * ek
                if nj or nk:
                    eff = tj + s * tk
                    ok = True
                    if not (nj and nk):
                        ok = _on_grid(eff)
                    if ok:
                        cand.append((-(abs(tj) + abs(tk)), pj, pk, s))
            elif not _commute((keyj[0], keyj[1]), (keyk[0], keyk[1])):
                break
    cand.sort()
    out, used = [], set()
    # report one at a time, but return a consistent list: disjoint pairs only
    for _, pj, pk, s in cand:
        if pj in used or pk in used:
            continue
        used.update((pj, pk))
        out.append((pj, pk, s))
    return out


def apply_match(c, m):
    pj, pk, s = m
    ops = list(c.ops)
    eff = _reduce(dv.rotation(ops[pj]) + s * dv.rotation(ops[pk]))
    qj = ops[pj][1]
    if abs(eff) < _TOL:
        del ops[pk]
        del ops[pj]
    else:
        ops[pj] = ("rz", qj, eff)
        del ops[pk]
    return dv.with_ops(c, ops)


RULE = Rule(
    name="pauli_exponential_commutation_merge",
    domain="dv",
    kind="procedure",
    contract="exact",
    source="Cowtan et al. 2019 (Pauli gadgets); Litinski 2019 (pi/8 Pauli rotations + final Clifford); Nam et al. 2018",
    idea="Move every rotation to the circuit front as a signed n-qubit Pauli exponential (X/Y/Z-type, multi-qubit), "
         "so Hadamards do not cut. Two rotations with equal Paulis merge (angles add with sign) if the later "
         "one commutes with all rotation Paulis between them; the edit is made in place in the original op list.",
    precondition=Precondition(families=("dv_angle",), needs=("rotations",),
        note="front-frames the rotations of a Clifford+Rz op list"),
    trigger=find_matches,
    apply=apply_match,
)
