"""Share one temporary AND between two Toffoli-level gates whose control PRODUCTS have the same ANF."""
from v4.api import Rule
from v4.api import dv

_PHASE_ONLY = {"z", "s", "sdg", "t", "tdg", "cz"}
_MAX_TERMS = 512


def _mul(p, q):
    """Product of two ANFs (frozensets of variable bitmasks), u*u = u."""
    acc = set()
    for a in p:
        for b in q:
            acc ^= {a | b}
    return frozenset(acc)


def _fold_gadget(gates, k):
    """and_compute(a,b,x); cx/cz(x,t); and_uncompute(a,b,x) at k..k+2 -> (a, b, 'x'|'z', x, t), else None."""
    if k + 2 >= len(gates):
        return None
    g0, g1, g2 = gates[k], gates[k + 1], gates[k + 2]
    if g0.name != "and_compute" or g2.name != "and_uncompute" or g0.qubits != g2.qubits:
        return None
    if g0.cond is not None or g1.cond is not None or g2.cond is not None:
        return None
    a, b, x = g0.qubits
    if g1.name == "cx" and g1.qubits[0] == x and g1.qubits[1] not in (a, b, x):
        return (a, b, "x", x, g1.qubits[1])
    if g1.name == "cz" and x in g1.qubits:
        t = g1.qubits[0] if g1.qubits[1] == x else g1.qubits[1]
        if t not in (a, b, x):
            return (a, b, "z", x, t)
    return None


def _logical_ops(gates):
    """Fold h ccz h trigrams. Returns list of (lo, hi, name, qubits) or None if the circuit is unsupported."""
    ops, k, n = [], 0, len(gates)
    while k < n:
        g = gates[k]
        if g.cond is not None or g.cbit is not None or g.name == "measure":
            return None
        if g.name == "h" and k + 4 < n:
            f = _fold_gadget(gates, k + 1)
            if f is not None and gates[k + 4].name == "h" and gates[k + 4].qubits == g.qubits \
                    and gates[k + 4].cond is None and f[2] == "z" and f[4] == g.qubits[0]:
                ops.append((k, k + 4, "ccx", (f[0], f[1], f[4])))
                k += 5
                continue
        if g.name == "and_compute":
            f = _fold_gadget(gates, k)
            if f is not None:
                ops.append((k, k + 2, "ccx" if f[2] == "x" else "ccz", (f[0], f[1], f[4])))
                k += 3
                continue
        if g.name == "h":
            if k + 2 < n and gates[k + 2].name == "h" and gates[k + 2].qubits == g.qubits \
                    and gates[k + 1].name == "ccz" and gates[k + 1].cond is None \
                    and g.qubits[0] in gates[k + 1].qubits:
                t = g.qubits[0]
                cs = tuple(q for q in gates[k + 1].qubits if q != t)
                if len(cs) == 2:
                    ops.append((k, k + 2, "ccx", cs + (t,)))
                    k += 3
                    continue
            return None
        ops.append((k, k, g.name, g.qubits))
        k += 1
    return ops


def _simulate(c, ops):
    """For each logical op index, the ANF of every wire just BEFORE it. None if unsupported."""
    n = c.n_qubits
    reg = {q for r in c.registers.values() for q in r}
    P = []
    for q in range(n):
        P.append(frozenset([1 << q]) if (not reg or q in reg) else frozenset())
    before = []
    for _, _, name, qs in ops:
        before.append(list(P))
        if name == "x":
            P[qs[0]] = P[qs[0]] ^ frozenset([0])
        elif name == "cx":
            P[qs[1]] = P[qs[1]] ^ P[qs[0]]
        elif name == "ccx":
            P[qs[2]] = P[qs[2]] ^ _mul(P[qs[0]], P[qs[1]])
        elif name == "and_compute":
            P[qs[2]] = _mul(P[qs[0]], P[qs[1]])
        elif name == "and_uncompute":
            P[qs[2]] = frozenset()
        elif name == "ccz" or name in _PHASE_ONLY:
            pass
        else:
            return None
        if any(len(p) > _MAX_TERMS for p in P):
            return None
    return before


def _variants(name, qs):
    """(kind, c1, c2, target) choices for a Toffoli-level op."""
    if name == "ccx":
        return [("x", qs[0], qs[1], qs[2])]
    if name == "ccz":
        return [("z", qs[0], qs[1], qs[2]), ("z", qs[0], qs[2], qs[1]), ("z", qs[1], qs[2], qs[0])]
    return []


def find_matches(c):
    if not dv.is_ir_circuit(c):
        return []
    ops = _logical_ops(c.gates)
    if ops is None:
        return []
    tof = [i for i, o in enumerate(ops) if o[2] in ("ccx", "ccz")]
    if len(tof) < 2:
        return []
    before = _simulate(c, ops)
    if before is None:
        return []
    cand = {}
    for i in tof:
        lst = []
        for kind, c1, c2, t in _variants(ops[i][2], ops[i][3]):
            q = _mul(before[i][c1], before[i][c2])
            if q:
                lst.append((kind, c1, c2, t, q))
        cand[i] = lst
    found = []
    for a, i in enumerate(tof):
        done = False
        for vi in cand[i]:
            for j in tof[a + 1:]:
                for vj in cand[j]:
                    if vi[4] != vj[4]:
                        continue
                    ctrl = {vi[1], vi[2], vj[1], vj[2]}
                    if vi[3] in ctrl or vj[3] in ctrl:
                        continue
                    found.append((j - i, -i, (ops[i][0], ops[i][1], vi[0], vi[1], vi[2], vi[3],
                                              ops[j][0], ops[j][1], vj[0], vj[1], vj[2], vj[3])))
                    done = True
                    break
                if done:
                    break
            if done:
                break
    found.sort(key=lambda f: (f[0], f[1]))
    return [f[2] for f in found]


def apply_match(c, m):
    ilo, ihi, ki, c1, c2, ti, jlo, jhi, kj, d1, d2, tj = m
    if not dv.is_ir_circuit(c) or not (0 <= ilo <= ihi < jlo <= jhi < len(c.gates)):
        return c.copy()
    a = c.n_qubits
    G = dv.IRGate
    new = list(c.gates[:ilo])
    new += [G("and_compute", (c1, c2, a)), G("cx" if ki == "x" else "cz", (a, ti))]
    new += list(c.gates[ihi + 1:jlo])
    new += [G("cx" if kj == "x" else "cz", (a, tj)), G("and_uncompute", (d1, d2, a))]
    new += list(c.gates[jhi + 1:])
    return dv.ir_with_gates(c, new, n_qubits=a + 1)


RULE = Rule(
    name="shared_and_by_control_product_anf",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney, Quantum 2, 74 (2018) temporary logical AND; Cuccaro et al. quant-ph/0410184; ANF/phase-polynomial "
           "analysis (Amy-Maslov-Mosca)",
    idea="Two Toffoli-level gates need the same bit whenever the ANFs of the products of their control forms agree "
         "(u*(v^u^1) = u*v over GF(2)), even if the control pairs differ. Compute that bit once with a 4-T temporary "
         "AND, apply it to both targets with cx/cz, and uncompute by measurement (0 T) with a cz fix-up on the second "
         "gate's own controls. One pair per application, one measurement each.",
    trigger=find_matches,
    apply=apply_match,
)
