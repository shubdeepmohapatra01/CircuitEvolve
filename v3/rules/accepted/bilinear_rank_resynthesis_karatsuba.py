"""Reconstruction rule: a Toffoli-level segment that is a bilinear F2 map y ^= B(a, b) is re-synthesized from a
low-rank (Karatsuba) bilinear decomposition, one 4-T AND gadget per rank-1 term."""
from itertools import permutations

from v3.api import Rule
from v3.api import dv

_ALLOWED = {"h", "ccz", "ccx", "cx", "x"}


def _kar(n):
    """Karatsuba-style bilinear algorithm for n-term F2 polynomial product.
    Returns (prods, diag): prods = [(umask, vmask)], diag[s] = bitmask over prods whose XOR is coefficient s."""
    if n == 1:
        return [(1, 1)], [1]
    if n == 2:
        return [(1, 1), (2, 2), (3, 3)], [0b001, 0b111, 0b010]
    if n == 3:
        prods = [(1, 1), (2, 2), (4, 4), (3, 3), (5, 5), (6, 6)]
        return prods, [0b000001, 0b001011, 0b010111, 0b100110, 0b000100]
    h = (n + 1) // 2
    l = n - h
    lo_p, lo_d = _kar(h)
    hi_p, hi_d = _kar(l)
    mid_p, mid_d = _kar(h)
    full = (1 << n) - 1
    prods = list(lo_p)
    prods += [(u << h, v << h) for u, v in hi_p]
    prods += [((u | (u << h)) & full, (v | (v << h)) & full) for u, v in mid_p]
    off_hi, off_mid = len(lo_p), len(lo_p) + len(hi_p)
    diag = [0] * (2 * n - 1)
    for s, m in enumerate(lo_d):
        diag[s] ^= m
        diag[s + h] ^= m
    for s, m in enumerate(hi_d):
        diag[s + h] ^= m << off_hi
        diag[s + 2 * h] ^= m << off_hi
    for s, m in enumerate(mid_d):
        diag[s + h] ^= m << off_mid
    return prods, diag


def _analyse(c):
    """Return (A, B, Y, Mk, lin_gates) or None. Mk[k] = frozenset of (a_wire, b_wire) monomials on Y[k]."""
    if not dv.is_ir_circuit(c) or not c.gates:
        return None
    gates = c.gates
    if any(g.name not in _ALLOWED or g.cond is not None for g in gates):
        return None
    if not any(g.name in ("ccz", "ccx") for g in gates):
        return None
    ys = set()
    for g in gates:
        if g.name in ("h", "x", "cx"):
            ys.add(g.qubits[-1])
        elif g.name == "ccx":
            ys.add(g.qubits[2])
    ctrl = set()
    for g in gates:
        if g.name == "cx" and g.qubits[0] not in ys:
            return None
        if g.name == "ccx":
            if g.qubits[0] in ys or g.qubits[1] in ys:
                return None
            ctrl.update(g.qubits[:2])
    val = {y: set() for y in ys}   # monomials (frozenset pair) currently added to each Y wire
    inh = {y: False for y in ys}
    pairs = []
    lin = []
    for g in gates:
        if g.name == "h":
            t = g.qubits[0]
            inh[t] = not inh[t]
        elif g.name in ("cx", "x"):
            if any(inh[q] for q in g.qubits):
                return None
            lin.append(g)
            if g.name == "cx":
                val[g.qubits[1]] ^= val[g.qubits[0]]
        elif g.name == "ccx":
            t = g.qubits[2]
            if inh[t]:
                return None
            pairs.append(frozenset(g.qubits[:2]))
            val[t] ^= {frozenset(g.qubits[:2])}
        else:  # ccz
            tg = [q for q in g.qubits if q in ys]
            if len(tg) != 1 or not inh[tg[0]]:
                return None
            t = tg[0]
            cs = frozenset(q for q in g.qubits if q != t)
            if len(cs) != 2 or any(q in ys for q in cs):
                return None
            ctrl.update(cs)
            pairs.append(cs)
            val[t] ^= {cs}
    if any(inh.values()) or not pairs or ctrl & ys:
        return None
    # bipartite 2-colouring of the control-pair graph (must be connected)
    adj = {q: set() for q in ctrl}
    for p in pairs:
        a, b = tuple(p)
        adj[a].add(b)
        adj[b].add(a)
    root = min(ctrl)
    col = {root: 0}
    stack = [root]
    while stack:
        q = stack.pop()
        for r in sorted(adj[q]):
            if r not in col:
                col[r] = 1 - col[q]
                stack.append(r)
            elif col[r] == col[q]:
                return None
    if len(col) != len(ctrl):
        return None
    A = sorted(q for q in ctrl if col[q] == 0)
    B = sorted(q for q in ctrl if col[q] == 1)
    Y = sorted(ys)
    Mk = []
    for y in Y:
        mons = set()
        for p in val[y]:
            a, b = sorted(p, key=lambda q: col[q])
            mons.add((a, b))
        Mk.append(frozenset(mons))
    return A, B, Y, Mk, lin


def _decompose(A, B, Mk):
    """Karatsuba rank decomposition for polynomial-multiplication pattern. Returns (prods, coeffs) or None.
    prods = [(tuple A wires, tuple B wires)]; coeffs[k] = tuple of product indices."""
    n = len(A)
    if n != len(B) or n < 2 or n > 4:
        return None
    allm = set().union(*Mk) if Mk else set()
    if not allm:
        return None
    prods, diag = _kar(n)
    for pa in permutations(range(n)):
        for pb in permutations(range(n)):
            # local index i <-> wire A[pa[i]], j <-> B[pb[j]]
            la = {A[pa[i]]: i for i in range(n)}
            lb = {B[pb[j]]: j for j in range(n)}
            ok = True
            Dk = []
            for mons in Mk:
                loc = {(la[a], lb[b]) for a, b in mons}
                d = 0
                for s in range(2 * n - 1):
                    cells = [(i, s - i) for i in range(n) if 0 <= s - i < n]
                    inn = sum(1 for x in cells if x in loc)
                    if inn == len(cells):
                        d ^= diag[s]
                    elif inn != 0:
                        ok = False
                        break
                if not ok:
                    break
                Dk.append(d)
            if not ok:
                continue
            # symbolic check: sum of selected products equals M_k
            for k, mons in enumerate(Mk):
                loc = {(la[a], lb[b]) for a, b in mons}
                acc = set()
                for r, (u, v) in enumerate(prods):
                    if (Dk[k] >> r) & 1:
                        for i in range(n):
                            if (u >> i) & 1:
                                for j in range(n):
                                    if (v >> j) & 1:
                                        acc ^= {(i, j)}
                if acc != loc:
                    ok = False
                    break
            if not ok:
                continue
            used = [r for r in range(len(prods)) if any((d >> r) & 1 for d in Dk)]
            out_p = []
            for r in used:
                u, v = prods[r]
                out_p.append((tuple(A[pa[i]] for i in range(n) if (u >> i) & 1),
                              tuple(B[pb[j]] for j in range(n) if (v >> j) & 1)))
            coeffs = [tuple(idx for idx, r in enumerate(used) if (d >> r) & 1) for d in Dk]
            if len(out_p) < len(allm):
                return out_p, coeffs
            return None
    return None


def find_matches(c):
    info = _analyse(c)
    if info is None:
        return []
    A, B, Y, Mk, lin = info
    dec = _decompose(A, B, Mk)
    if dec is None:
        return []
    prods, coeffs = dec
    return [(tuple(Y), tuple(prods), tuple(coeffs))]


def apply_match(c, m):
    Y, prods, coeffs = m
    info = _analyse(c)
    if info is None:
        return c
    lin = info[4]
    gates = list(lin)
    s = c.n_qubits
    G = dv.IRGate
    for r, (us, vs) in enumerate(prods):
        p, q = us[0], vs[0]   # fan the other bits into the first wire in place (undone below)
        fan = [G("cx", (a, p)) for a in us[1:]] + [G("cx", (b, q)) for b in vs[1:]]
        gates += fan
        gates.append(G("and_compute", (p, q, s)))
        for k in coeffs_for(coeffs, r):
            gates.append(G("cx", (s, Y[k])))
        gates.append(G("and_uncompute", (p, q, s)))
        gates += list(reversed(fan))
    return dv.ir_with_gates(c, gates, n_qubits=c.n_qubits + 1)


def coeffs_for(coeffs, r):
    return [k for k, cs in enumerate(coeffs) if r in cs]


RULE = Rule(
    name="bilinear_rank_resynthesis_karatsuba",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Karatsuba-Ofman 1962; Kepley-Steinwandt 2015; Gidney 2018 (4-T AND, measurement-based uncompute)",
    idea="A Toffoli-level segment whose CCZ groups only add products of read-only registers A, B into targets Y is "
         "the classical bilinear map y ^= M(a,b). Recompute M from a rank decomposition (Karatsuba: 9 products for "
         "4x4 GF(2) polynomial multiplication instead of 16 monomials): fan the linear forms into two ancillas, "
         "AND them with a 4-T gadget, CX the result into the targets, uncompute by measurement (0 T).",
    trigger=find_matches,
    apply=apply_match,
)
