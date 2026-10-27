"""Recognise a classical ccx/cx/x segment that is exactly t ^= AND(S) (|S| >= 4) by full truth-table simulation
with 2^n-bit integer masks, and re-emit it as Gidney's temporary-AND ladder on fresh clean ancillas."""
from v3.api import Rule
from v3.api import dv

MAX_WIRES = 20
MIN_CONTROLS = 4


def _col_masks(n):
    full = (1 << (1 << n)) - 1
    cols = []
    for i in range(n):
        half = 1 << i
        pat = ((1 << half) - 1) << half
        cols.append(full // ((1 << (2 * half)) - 1) * pat)
    return cols, full


def _scan(gates, start, cols, full):
    """Greedy classical segment from `start`. An h on a wire opens/closes a sandwich; a ccz with exactly one open
    leg q is a ccx onto q (h q; ccz; h q = ccx). Returns (end, masks) at the last point with no open sandwich."""
    f = list(cols)
    opened = set()
    best = (start, list(f))
    j = start
    while j < len(gates):
        g = gates[j]
        if g.cond is not None:
            break
        nm, qs = g.name, g.qubits
        if nm == "x":
            if qs[0] in opened:
                break
            f[qs[0]] ^= full
        elif nm == "cx":
            if qs[0] in opened or qs[1] in opened:
                break
            f[qs[1]] ^= f[qs[0]]
        elif nm == "ccx":
            if opened.intersection(qs):
                break
            f[qs[2]] ^= f[qs[0]] & f[qs[1]]
        elif nm == "h":
            opened ^= {qs[0]}
        elif nm == "ccz":
            op = [q for q in qs if q in opened]
            if len(op) != 1:
                break
            t = op[0]
            a, b = [q for q in qs if q != t]
            f[t] ^= f[a] & f[b]
        else:
            break
        j += 1
        if not opened:
            best = (j, list(f))
    return best


def _recognise(f, cols, full, n):
    changed = [q for q in range(n) if f[q] != cols[q]]
    if len(changed) != 1:
        return None
    t = changed[0]
    diff = f[t] ^ cols[t]
    S, acc = [], full
    for q in range(n):
        if q != t and diff & ~cols[q] == 0:
            S.append(q)
            acc &= cols[q]
    if len(S) < MIN_CONTROLS or acc != diff:
        return None
    return t, tuple(S)


def find_matches(c):
    if not dv.is_ir_circuit(c) or c.n_qubits > MAX_WIRES or c.n_qubits < MIN_CONTROLS + 1:
        return []
    gates, n = c.gates, c.n_qubits
    cols, full = _col_masks(n)
    out = []
    i = 0
    while i < len(gates):
        j, f = _scan(gates, i, cols, full)
        if j == i:
            i += 1
            continue
        m = _recognise(f, cols, full, n)
        if m is not None:
            out.append((i, j, m[0], m[1]))
        i = j
    return out


def apply_match(c, m):
    start, end, t, S = m
    n = c.n_qubits
    k = len(S)
    anc = list(range(n, n + k - 1))
    G = dv.IRGate
    new = [G("and_compute", (S[0], S[1], anc[0]))]
    for i in range(1, k - 1):
        new.append(G("and_compute", (anc[i - 1], S[i + 1], anc[i])))
    new.append(G("cx", (anc[-1], t)))
    for i in range(k - 2, 0, -1):
        new.append(G("and_uncompute", (anc[i - 1], S[i + 1], anc[i])))
    new.append(G("and_uncompute", (S[0], S[1], anc[0])))
    gates = list(c.gates[:start]) + new + list(c.gates[end:])
    return dv.ir_with_gates(c, gates, n_qubits=n + k - 1)


RULE = Rule(
    name="mcx_truthtable_recognition_and_ladder_resynthesis",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney 2018 (arXiv:1709.06648) temporary logical AND; Barenco et al. 1995 Lemma 7.2; Knuth TAOCP 7.1.3",
    idea="A classical ccx/cx/x segment whose full truth table (2^n-bit integer masks) is t ^= AND(S), |S|>=4, with "
         "every other wire the identity, is replaced by a ladder of k-1 and_compute gadgets on fresh clean "
         "ancillas, one cx into t, and k-1 zero-T measured and_uncomputes.",
    trigger=find_matches,
    apply=apply_match,
)
