"""Whole-circuit specification recognition: a Hadamard-free Toffoli adder is rebuilt as Gidney's temporary-AND adder."""
from v3.api import Rule
from v3.api import dv

MAX_VARS = 20


def _fold(c):
    """Fold h(q) ccz h(q) trigrams to ccx; return a list of (name, qubits) over x/cx/ccx or None."""
    gs = list(c.gates)
    out, i = [], 0
    while i < len(gs):
        g = gs[i]
        if g.cond is not None or g.cbit is not None:
            return None
        if g.name == "h":
            if i + 2 < len(gs) and gs[i + 1].name == "ccz" and gs[i + 2].name == "h" \
                    and gs[i + 2].qubits == g.qubits and gs[i + 1].cond is None and gs[i + 2].cond is None \
                    and g.qubits[0] in gs[i + 1].qubits:
                t = g.qubits[0]
                ctl = tuple(q for q in gs[i + 1].qubits if q != t)
                out.append(("ccx", ctl + (t,)))
                i += 3
                continue
            return None
        if g.name in ("x", "cx", "ccx"):
            out.append((g.name, tuple(g.qubits)))
            i += 1
            continue
        return None
    return out


def _var_table(j, k):
    w = 1 << (j + 1)
    block = ((1 << (1 << j)) - 1) << (1 << j)
    total = 1 << k
    return block * (((1 << total) - 1) // ((1 << w) - 1))


def _recognise(c):
    if not dv.is_ir_circuit(c):
        return None
    ops = _fold(c)
    if ops is None:
        return None
    n_cc = sum(1 for g in c.gates if g.name in ("ccx", "ccz"))
    nq = c.n_qubits
    reg = {q for r in c.registers.values() for q in r}
    if reg:
        options = [[q for q in range(nq) if q in reg]]
    else:
        # no declared registers: try each single wire as a pinned-clean carry-in ancilla, then none
        options = [[q for q in range(nq) if q != w] for w in range(nq)] + [list(range(nq))]
    best = None
    for data in options:
        r = _try(c, ops, n_cc, data)
        if r is not None and (best is None or r[0] < best[0]):
            best = r
    return None if best is None else best[1]


def _try(c, ops, n_cc, data):
    nq = c.n_qubits
    if len(data) > MAX_VARS or len(data) < 7:
        return None
    k = len(data)
    total = 1 << k
    ones = (1 << total) - 1
    V = [0] * nq
    for j, q in enumerate(data):
        V[q] = _var_table(j, k)
    O = list(V)
    for name, qs in ops:
        if name == "x":
            O[qs[0]] ^= ones
        elif name == "cx":
            O[qs[1]] ^= O[qs[0]]
        else:
            O[qs[2]] ^= O[qs[0]] & O[qs[1]]
    best = None
    cin_opts = [None] + [q for q in data if O[q] == V[q]]
    for cin in cin_opts:
        C = [0 if cin is None else V[cin]]
        used = set() if cin is None else {cin}
        P, Q = [], []
        while True:
            found = None
            for q in data:
                if q in used:
                    continue
                for p in data:
                    if p in used or p == q or O[p] != V[p]:
                        continue
                    if O[q] == V[q] ^ V[p] ^ C[-1]:
                        found = (p, q)
                        break
                if found:
                    break
            if not found:
                break
            p, q = found
            P.append(p)
            Q.append(q)
            used |= {p, q}
            a, b = V[p], V[q]
            C.append((a & b) ^ (C[-1] & (a ^ b)))
        for n in range(len(P), 2, -1):
            pu, qu = set(P[:n]), set(Q[:n])
            if cin is not None:
                pu.add(cin)
            base = pu | qu
            # fix the carry list for this n
            for cout in [None] + [w for w in range(nq) if w not in base]:
                if cout is not None and O[cout] != V[cout] ^ C[n]:
                    continue
                excl = base | ({cout} if cout is not None else set())
                if any(O[w] != V[w] for w in range(nq) if w not in excl):
                    continue
                if cout is None and any(w in base for w in ()):
                    continue
                if cout is None:
                    # the chain steps beyond n would have to be absent from the rest: already enforced above
                    pass
                ands = n if cout is not None else n - 1
                if ands >= n_cc:
                    continue
                key = (-n, ands)
                if best is None or key < best[0]:
                    best = (key, (tuple(P[:n]), tuple(Q[:n]), -1 if cin is None else cin,
                                  -1 if cout is None else cout))
    return best


def find_matches(c):
    m = _recognise(c)
    return [m] if m is not None else []


def apply_match(c, m):
    P, Q, cin, cout = m
    n = len(P)
    nxt = c.n_qubits
    gates = []

    def add(name, *qs):
        gates.append(dv.IRGate(name, tuple(qs)))

    t = {}
    carry = {0: None if cin < 0 else cin}
    for i in range(n):
        a, b = P[i], Q[i]
        ci = carry[i]
        last = i == n - 1
        if last and cout < 0:
            add("cx", a, b)
            add("cx", ci, b)
            continue
        if ci is not None:
            add("cx", ci, a)
            add("cx", ci, b)
        t[i] = nxt
        nxt += 1
        add("and_compute", a, b, t[i])
        if ci is not None:
            add("cx", ci, t[i])
        carry[i + 1] = t[i]
    if cout >= 0:
        add("cx", t[n - 1], cout)
    n_meas = c.n_cbits
    for i in reversed(range(n)):
        if i not in t:
            continue
        a, b = P[i], Q[i]
        ci = carry[i]
        if ci is not None:
            add("cx", ci, t[i])
        # and_uncompute: H, X-basis measurement, classically controlled CZ on the factors
        add("and_uncompute", a, b, t[i])
        if ci is not None:
            add("cx", ci, a)
        add("cx", a, b)
    return dv.ir_with_gates(c, gates, n_qubits=nxt, n_cbits=n_meas)


RULE = Rule(
    name="adder_spec_recognition_gidney_carry_chain_rebuild",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney 2018 'Halving the cost of quantum addition'; Cuccaro et al. quant-ph/0410184",
    idea="Fold h-ccz-h into ccx, compute each wire's Boolean function (truth table = ANF-equivalent) and match the "
         "ripple-carry addition specification (A restored, B = A+B+carry, optional carry-out, all else identity). "
         "On a match, rebuild the whole circuit as Gidney's temporary-AND adder: one 4-T and_compute per carry, "
         "measurement-based 0-T uncompute in reverse, on the same wires plus clean ancillas.",
    trigger=find_matches,
    apply=apply_match,
)
