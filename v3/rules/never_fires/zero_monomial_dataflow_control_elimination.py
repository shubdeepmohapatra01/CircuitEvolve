"""Deletion-only pass: remove ccx/ccz ops whose control is provably |0> (clean scratch wires), via a tiny
per-wire monomial lattice and H-frame bits for shared Hadamards."""
from v3.api import Rule
from v3.api import dv

ZERO = "Z"
UNKNOWN = "U"
_OK = ("h", "x", "cx", "cz", "ccx", "ccz")


def _normalize(c):
    """-> list of (kind, controls, target) per gate (h -> ('h', (q,), q)), or None to decline."""
    f = {}
    out = []
    for g in c.gates:
        if g.name not in _OK or g.cond is not None or g.cbit is not None:
            return None
        qs = g.qubits
        if g.name == "h":
            f[qs[0]] = f.get(qs[0], 0) ^ 1
            out.append(("h", (), qs[0]))
            continue
        xs = [q for q in qs if f.get(q, 0)]
        if g.name == "ccz":
            if len(xs) != 1:
                return None
            t = xs[0]
            out.append(("ccx", tuple(q for q in qs if q != t), t))
            continue
        if xs:
            return None
        if g.name == "ccx":
            out.append(("ccx", (qs[0], qs[1]), qs[2]))
        elif g.name == "cx":
            out.append(("cx", (qs[0],), qs[1]))
        elif g.name == "x":
            out.append(("x", (), qs[0]))
        else:
            out.append(("cz", (qs[0], qs[1]), None))
    if any(f.values()):
        return None
    return out


def find_matches(c):
    if not dv.is_ir_circuit(c):
        return []
    norm = _normalize(c)
    if norm is None:
        return []
    written, read = set(), set()
    for kind, ctl, t in norm:
        if kind in ("ccx", "cx", "x"):
            written.add(t)
        if kind != "h":
            read.update(ctl)
    temps = written & read
    val = {q: (ZERO if q in temps else frozenset([q])) for q in range(c.n_qubits)}
    deleted = []
    for i, (kind, ctl, t) in enumerate(norm):
        if kind in ("h", "cz"):
            continue
        if kind == "x":
            val[t] = UNKNOWN
            continue
        vs = [val[q] for q in ctl]
        if any(v == ZERO for v in vs):
            if kind == "ccx":
                deleted.append(i)
            continue
        if any(v == UNKNOWN for v in vs):
            val[t] = UNKNOWN
            continue
        term = frozenset().union(*vs)
        cur = val[t]
        if cur == UNKNOWN:
            continue
        if cur == ZERO:
            val[t] = term
        elif cur == term:
            val[t] = ZERO
        else:
            val[t] = UNKNOWN
    if not deleted or any(val[q] != ZERO for q in temps):
        return []
    return [tuple(deleted)]


def apply_match(c, m):
    drop = set(m)
    return dv.ir_with_gates(c, [g for i, g in enumerate(c.gates) if i not in drop])


RULE = Rule(
    name="zero_monomial_dataflow_control_elimination",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Maslov-Dueck-Miller 2007 constant propagation in Toffoli networks; Barenco et al. 1995 Lemma 7.2",
    idea="A ccx/ccz with a control wire in |0> is the identity. Track each wire as ZERO / monomial of input bits / "
         "unknown (temporaries start ZERO, H frame bits read shared-Hadamard ccz as ccx), delete only ops with a "
         "ZERO control, and fire only if every temporary ends ZERO.",
    trigger=find_matches,
    apply=apply_match,
)
