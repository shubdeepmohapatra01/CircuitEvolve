"""Pairwise lowering of a Toffoli and its own later inverse on a zero-valued wire to Gidney's measured AND."""
from v3.api import Rule
from v3.api import dv

_DIAG = {"z", "s", "sdg", "t", "tdg", "cz", "ccz"}
_ALLOWED = {"h", "x", "cx", "cz", "ccx", "ccz", "s", "sdg", "z", "t", "tdg", "and_compute", "and_uncompute", "measure"}


def _normalize(gates):
    """ccz legs -> ccx where h(q) ... h(q) brackets every op touching q (all ccz); h's removed."""
    n = len(gates)
    drop, repl = set(), {}
    for p in range(n):
        g = gates[p]
        if g.name != "h" or g.cond is not None or p in drop:
            continue
        q = g.qubits[0]
        zs, r = [], None
        for k in range(p + 1, n):
            h = gates[k]
            if q not in h.qubits:
                continue
            if h.name == "h" and h.cond is None:
                r = k
                break
            if h.name == "ccz" and h.cond is None and k not in repl:
                zs.append(k)
                continue
            break
        if r is None or not zs or r in drop:
            continue
        drop.update((p, r))
        for k in zs:
            others = [x for x in gates[k].qubits if x != q]
            repl[k] = dv.IRGate("ccx", tuple(others) + (q,))
    return [repl.get(k, gates[k]) for k in range(n) if k not in drop]


def _find(c):
    if not dv.is_ir_circuit(c):
        return None
    gates = c.gates
    if sum(1 for g in gates if g.name in ("ccx", "ccz")) < 2:
        return None
    if any(g.name not in _ALLOWED for g in gates):
        return None
    return _normalize(gates)


def _trigger(c):
    gates = _find(c)
    if gates is None:
        return []
    zero = {q: True for q in c.ancillas()}
    wver = {}
    pending = {}
    out = []
    for idx, g in enumerate(gates):
        qs = g.qubits
        if g.name in ("ccx", "and_compute", "and_uncompute") and g.cond is None:
            a, x, y = qs[2], qs[0], qs[1]
            if g.name == "ccx":
                p = pending.get(a)
                if p is not None and {p[1], p[2]} == {x, y} and p[3] == wver.get(x, 0) and p[4] == wver.get(y, 0):
                    out.append((p[0], idx, p[1], p[2], a))
                    pending.pop(a)
                    zero[a] = True
                    wver[a] = wver.get(a, 0) + 1
                    continue
                pending.pop(a, None)
                if zero.get(a):
                    pending[a] = (idx, x, y, wver.get(x, 0), wver.get(y, 0))
                zero[a] = False
                wver[a] = wver.get(a, 0) + 1
                continue
            writes = [a]
        elif g.name == "measure":
            writes = list(qs)
        elif g.name in _DIAG:
            writes = []
        elif g.name in ("x", "h", "cx", "ccx", "and_compute", "and_uncompute"):
            writes = [qs[-1]]
        else:
            writes = list(qs)
        for w in writes:
            zero[w] = False
            pending.pop(w, None)
            wver[w] = wver.get(w, 0) + 1
    return out


def _apply(c, m):
    gates = _find(c)
    if gates is None:
        return c
    i, j, x, y, a = m
    if not (i < j < len(gates)):
        return c
    for k in (i, j):
        if gates[k].name != "ccx" or gates[k].cond is not None or gates[k].qubits[2] != a \
                or set(gates[k].qubits[:2]) != {x, y}:
            return c
    new = list(gates)
    new[i] = dv.IRGate("and_compute", (x, y, a))
    new[j] = dv.IRGate("and_uncompute", (x, y, a))
    return dv.ir_with_gates(c, new)


RULE = Rule(
    name="toffoli_compute_uncompute_pair_measured_lowering",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney 2018 (arXiv:1709.06648) temporary logical AND; Barenco et al. 1995 Lemma 7.2; Jones 2013",
    idea="A ccx into a zero wire and a later identical ccx (controls untouched in between) are a compute/uncompute "
         "of x&y: replace by the 4-T and_compute and the measurement-based 0-T and_uncompute, by local dataflow only.",
    trigger=_trigger,
    apply=_apply,
)
