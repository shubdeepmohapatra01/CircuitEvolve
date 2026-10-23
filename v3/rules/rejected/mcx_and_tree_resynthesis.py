"""Recognize a Toffoli-level segment that is a multi-controlled X and re-emit it as Gidney's AND ladder."""
from v3.api import Rule
from v3.api import dv

ELIGIBLE = ("ccz", "ccx", "cx", "x", "h")
MIN_CONTROLS = 4
MAX_FREE = 22


def _segments(gates):
    out, start = [], None
    for i, g in enumerate(gates):
        ok = g.name in ELIGIBLE and g.cond is None
        if ok and start is None:
            start = i
        if not ok and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(gates)))
    return out


def _classical_ops(gates):
    """Segment gates -> list of ('x',q) / ('cx',a,t) / ('ccx',a,b,t); None if an h is not in a sandwich."""
    ops, used = [], set()
    n = len(gates)
    for p, g in enumerate(gates):
        if p in used:
            continue
        if g.name == "h":
            q = g.qubits[0]
            run, s = [], None
            for j in range(p + 1, n):
                if q not in gates[j].qubits:
                    continue
                if gates[j].name == "ccz":
                    run.append(j)
                    continue
                if gates[j].name == "h" and j not in used:
                    s = j
                break
            if s is None or not run:
                return None
            used.add(s)
            used.update(run)
            for r in run:
                a, b = [x for x in gates[r].qubits if x != q]
                ops.append((r, ("ccx", a, b, q)))
            continue
        if g.name == "ccz":
            return None  # bare ccz (not inside a sandwich) is not classical
        ops.append((p, (g.name,) + tuple(g.qubits)))
    ops.sort(key=lambda t: t[0])
    return [o for _, o in ops]


def _analyze(c, lo, hi):
    gates = c.gates[lo:hi]
    ops = _classical_ops(gates)
    if not ops:
        return None
    touched = sorted({q for g in gates for q in g.qubits})
    earlier = {q for g in c.gates[:lo] for q in g.qubits}
    registered = {q for reg in c.registers.values() for q in reg}
    anc = [q for q in touched if q not in registered and q not in earlier] if registered else []
    free = [q for q in touched if q not in anc]
    m = len(free)
    if m > MAX_FREE or m < MIN_CONTROLS + 1:
        return None
    full = (1 << (1 << m)) - 1
    var = {}
    for k, q in enumerate(free):
        # truth table bit r of wire q = bit k of row r
        blk = 1 << k
        mask = ((1 << blk) - 1) << blk
        length = 2 * blk
        while length < (1 << m):
            mask |= mask << length
            length *= 2
        var[q] = mask
    val = dict(var)
    for q in anc:
        val[q] = 0
    for op in ops:
        if op[0] == "x":
            val[op[1]] ^= full
        elif op[0] == "cx":
            val[op[2]] ^= val[op[1]]
        else:
            val[op[3]] ^= val[op[1]] & val[op[2]]
    if any(val[q] != 0 for q in anc):
        return None
    changed = [q for q in free if val[q] != var[q]]
    if len(changed) != 1:
        return None
    t = changed[0]
    d = val[t] ^ var[t]
    if d == 0:
        return None
    S = [w for w in free if w != t and (d & ~var[w]) == 0]
    conj = full
    for w in S:
        conj &= var[w]
    if conj != d or len(S) < MIN_CONTROLS:
        return None
    return t, tuple(S), tuple(anc)


def find_matches(c):
    if not dv.is_ir_circuit(c):
        return []
    out = []
    for lo, hi in _segments(c.gates):
        if hi - lo < 4:
            continue
        r = _analyze(c, lo, hi)
        if r is not None:
            out.append((lo, hi, r[0], r[1], r[2]))
    return out


def apply_match(c, m):
    lo, hi, t, S, spare = m
    k = len(S)
    n0 = c.n_qubits
    # reuse the segment's own idle |0> wires as clean ancillas; only append wires if there are too few
    anc = list(spare[:k - 1])
    extra = k - 1 - len(anc)
    anc += [n0 + i for i in range(extra)]
    new = []
    G = dv.IRGate
    new.append(G("and_compute", (S[0], S[1], anc[0])))
    for i in range(1, k - 1):
        new.append(G("and_compute", (anc[i - 1], S[i + 1], anc[i])))
    new.append(G("cx", (anc[-1], t)))
    for i in range(k - 2, 0, -1):
        new.append(G("and_uncompute", (anc[i - 1], S[i + 1], anc[i])))
    new.append(G("and_uncompute", (S[0], S[1], anc[0])))
    gates = list(c.gates[:lo]) + new + list(c.gates[hi:])
    return dv.ir_with_gates(c, gates, n_qubits=n0 + extra)


RULE = Rule(
    name="mcx_and_tree_resynthesis",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney 2018 (arXiv:1709.06648) temporary logical AND; Barenco et al. 1995 Lemma 7.2",
    idea="A Toffoli-level segment that exactly computes t ^= AND(c1..ck) is replaced by a ladder of k-1 4-T "
         "and_compute gadgets on clean ancillas, one cx onto the target, and k-1 zero-T measurement-based "
         "uncomputes; the dirty-ancilla restoration work of the borrowed-ancilla construction is dropped.",
    trigger=find_matches,
    apply=apply_match,
)
