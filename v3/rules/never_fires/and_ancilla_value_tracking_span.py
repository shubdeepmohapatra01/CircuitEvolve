"""Keep one temporary-AND ancilla live over a span of ccz/ccx gates sharing a control pair; X gates on the controls
are repaired with a free cx onto the ancilla."""
from itertools import combinations

from v3.api import Rule
from v3.api import dv

_DIAG = ("z", "cz", "ccz")


def _hard_write(g, w):
    """Does gate g (which may touch wire w) change the computational-basis value of w irrecoverably?"""
    if w not in g.qubits:
        return False
    if g.cond is not None:
        return True
    n = g.name
    if n == "x":
        return False
    if n in _DIAG:
        return False
    if n in ("cx", "ccx"):
        return g.qubits[-1] == w
    return True


def _is_x(g, w):
    return g.name == "x" and g.qubits == (w,) and g.cond is None


def _gap_legal(gates, lo, hi, a, b):
    for k in range(lo + 1, hi):
        g = gates[k]
        if _hard_write(g, a) or _hard_write(g, b):
            return False
    return True


def find_matches(c):
    if not dv.is_ir_circuit(c):
        return []
    gates = c.gates
    groups = {}
    for i, g in enumerate(gates):
        if g.name not in ("ccz", "ccx") or g.cond is not None or len(set(g.qubits)) != 3:
            continue
        if g.name == "ccx":
            pairs = [tuple(sorted(g.qubits[:2]))]
        else:
            pairs = [tuple(sorted(p)) for p in combinations(g.qubits, 2)]
        for p in pairs:
            groups.setdefault(p, []).append(i)
    cands = []
    for pair, idxs in sorted(groups.items()):
        a, b = pair
        run = [idxs[0]]
        runs = []
        for i in idxs[1:]:
            if _gap_legal(gates, run[-1], i, a, b):
                run.append(i)
            else:
                runs.append(run)
                run = [i]
        runs.append(run)
        for r in runs:
            if len(r) >= 2:
                cands.append((pair, r))
    cands.sort(key=lambda pr: (-len(pr[1]), pr[1][-1] - pr[1][0], pr[0], pr[1][0]))
    used, out = set(), []
    for pair, r in cands:
        r = [i for i in r if i not in used]
        if len(r) < 2:
            continue
        out.append((pair, tuple(r)))
        used.update(r)
    return out


def apply_match(c, m):
    if not dv.is_ir_circuit(c):
        return c
    (a, b), members = m
    gates = c.gates
    t = c.n_qubits
    first, last = members[0], members[-1]
    mem = set(members)
    new = []
    for i, g in enumerate(gates):
        if i == first:
            new.append(dv.IRGate("and_compute", (a, b, t)))
        if i in mem:
            third = [q for q in g.qubits if q not in (a, b)][0]
            new.append(dv.IRGate("cz" if g.name == "ccz" else "cx", (t, third)))
        else:
            new.append(g)
        if first < i < last:
            if _is_x(g, a):
                new.append(dv.IRGate("cx", (b, t)))
            elif _is_x(g, b):
                new.append(dv.IRGate("cx", (a, t)))
        if i == last:
            new.append(dv.IRGate("and_uncompute", (a, b, t)))
    return dv.ir_with_gates(c, new, n_qubits=c.n_qubits + 1)


RULE = Rule(
    name="and_ancilla_value_tracking_span",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney 2018 (temporary logical AND); Jones 2013; Gidney-Ekera 2021 AND-ancilla reuse",
    idea="One AND ancilla t = a AND b serves every ccz/ccx on control pair {a,b} in a span (4 T total). "
         "x(a) inside the span is repaired by cx(b,t) (t = (a^1)b = b ^ ab), x(b) by cx(a,t); diagonal gates "
         "and control uses leave t valid, any other write to a or b ends the span.",
    trigger=find_matches,
    apply=apply_match,
)
