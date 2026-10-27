"""Value memoization of Toffoli products over h-free classical segments (ANF value table over GF(2))."""
from v3.api import Rule
from v3.api import dv

CAP = 4096
CLASSICAL = ("x", "z", "cx", "cz", "ccx", "ccz")


def _fuse(gates):
    """Step 0: h(w) ccz h(w) with nothing else on w in between -> ccx (target w)."""
    n = len(gates)
    consumed = set()
    repl = {}
    last_on = {}
    for j, g in enumerate(gates):
        if g.name == "ccz" and g.cond is None and len(set(g.qubits)) == 3:
            # previous / next op touching each wire
            for w in g.qubits[::-1]:
                i = None
                for t in range(j - 1, -1, -1):
                    if w in gates[t].qubits:
                        i = t
                        break
                k = None
                for t in range(j + 1, n):
                    if w in gates[t].qubits:
                        k = t
                        break
                if i is None or k is None:
                    continue
                gi, gk = gates[i], gates[k]
                if gi.name == "h" and gk.name == "h" and gi.cond is None and gk.cond is None \
                        and i not in consumed and k not in consumed:
                    consumed.update((i, k))
                    others = tuple(q for q in g.qubits if q != w)
                    repl[j] = dv.IRGate("ccx", others + (w,))
                    break
    out = []
    for j, g in enumerate(gates):
        if j in consumed:
            continue
        out.append(repl.get(j, g))
    return out


def _mul(p, q):
    r = set()
    for a in p:
        for b in q:
            m = a | b
            if m in r:
                r.remove(m)
            else:
                r.add(m)
    return frozenset(r)


def _express(P, cands):
    """cands: list of (label, anf). Return list of labels (label None = constant 1) whose XOR is P, or None."""
    mons = {}
    def vec(a):
        v = 0
        for m in a:
            if m not in mons:
                mons[m] = len(mons)
            v |= 1 << mons[m]
        return v
    target = vec(P)
    basis = []  # (pivot_vec, combo_set)
    for lab, a in cands:
        v = vec(a)
        combo = {lab}
        for bv, bc in basis:
            if v ^ bv < v:
                v ^= bv
                combo = combo ^ bc
        if v:
            basis.append((v, combo))
            basis.sort(key=lambda t: -t[0])
    v, combo = target, set()
    for bv, bc in basis:
        if v ^ bv < v:
            v ^= bv
            combo = combo ^ bc
    return sorted(combo, key=lambda x: (x is None, x if x is not None else 0)) if v == 0 else None


def _segment_rewrite(gates, lo, hi, n):
    """Rewrite gates[lo:hi] (h-free classical). Return (new_gates, #reduced) ."""
    V = [frozenset({frozenset({q})}) for q in range(n)]
    ONE = frozenset({frozenset()})
    out, red = [], 0
    for idx in range(lo, hi):
        g = gates[idx]
        nm, q = g.name, g.qubits
        if nm == "x":
            V[q[0]] = V[q[0]] ^ ONE
            out.append(g)
        elif nm == "z" or nm == "cz":
            out.append(g)
        elif nm == "cx":
            V[q[1]] = V[q[1]] ^ V[q[0]]
            out.append(g)
        else:  # ccx / ccz
            if nm == "ccx":
                targets = [q[2]]
            else:
                targets = [q[2], q[1], q[0]]
            done = False
            for c in targets:
                a, b = [x for x in q if x != c]
                P = _mul(V[a], V[b])
                if len(P) > CAP:
                    break
                if not P:
                    sol = []
                elif P == ONE:
                    sol = [None]
                else:
                    sol = None
                    for w in range(n):
                        if w != c and V[w] == P:
                            sol = [w]
                            break
                    if sol is None:
                        cands = [(w, V[w]) for w in range(n) if w != c] + [(None, ONE)]
                        sol = _express(P, cands)
                if sol is None:
                    continue
                new = []
                for lab in sol:
                    if nm == "ccx":
                        new.append(dv.IRGate("x", (c,)) if lab is None else dv.IRGate("cx", (lab, c)))
                    else:
                        new.append(dv.IRGate("z", (c,)) if lab is None else dv.IRGate("cz", (lab, c)))
                out.extend(new)
                red += 1
                done = True
                if nm == "ccx":
                    V[c] = V[c] ^ P
                break
            if not done:
                out.append(g)
                if nm == "ccx":
                    P = _mul(V[q[0]], V[q[1]])
                    V[q[2]] = V[q[2]] ^ P
                    if len(V[q[2]]) > CAP:
                        return None, 0
    return out, red


def _segments(gates):
    segs, start = [], None
    for i, g in enumerate(gates + [None]):
        ok = g is not None and g.name in CLASSICAL and g.cond is None
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            segs.append((start, i))
            start = None
    return segs


def trigger(c):
    if not dv.is_ir_circuit(c):
        return []
    gates = _fuse(list(c.gates))
    matches = []
    for lo, hi in _segments(gates):
        if not any(g.name in ("ccx", "ccz") for g in gates[lo:hi]):
            continue
        new, red = _segment_rewrite(gates, lo, hi, c.n_qubits)
        if new is not None and red > 0:
            matches.append((lo, hi, red))
    matches.sort(key=lambda m: (-m[2], m[0]))
    return matches


def apply(c, m):
    lo, hi, _ = m
    gates = _fuse(list(c.gates))
    new, red = _segment_rewrite(gates, lo, hi, c.n_qubits)
    if new is None:
        return c.copy()
    return dv.ir_with_gates(c, gates[:lo] + new + gates[hi:])


RULE = Rule(
    name="and_value_memoization_over_classical_segments",
    domain="dv",
    kind="procedure",
    contract="exact",
    source="Gidney 2018; Boyar-Peralta 2008; Maslov-Dueck-Miller 2005; Amy-Maslov-Mosca 2014",
    idea="Fuse h-ccz-h to ccx; in each h-free classical segment track wire values as GF(2) ANF; a Toffoli whose "
         "control product equals a GF(2) combination of other live wire values (or 0/1) becomes CNOTs/X (0 T).",
    trigger=trigger,
    apply=apply,
)
