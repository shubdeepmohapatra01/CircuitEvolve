"""Function-level XAG resynthesis of a Hadamard-free classical Toffoli-level circuit (4 T per AND node)."""
from itertools import combinations

import numpy as np

from v3.api import Rule
from v3.api import dv

_MAX_VARS = 16
_FALLBACK_CAP = 3000
_CACHE = {}


class _Fail(Exception):
    pass


# ---------------------------------------------------------------- folding h ccz h -> ccx
def _fold(c):
    """[(name, qubits)] over x cx ccx after folding every h(q) ccz(.,.,q) h(q); None if not classical."""
    gs = []
    for g in c.gates:
        if g.name not in ("x", "cx", "ccx", "ccz", "h") or g.cond is not None or g.cbit is not None:
            return None
        gs.append([g.name, tuple(g.qubits)])
    alive = [True] * len(gs)
    for k in range(len(gs)):
        if gs[k][0] != "ccz":
            continue
        qs = gs[k][1]
        for q in reversed(qs):
            i = next((a for a in range(k - 1, -1, -1) if alive[a] and q in gs[a][1]), None)
            j = next((b for b in range(k + 1, len(gs)) if alive[b] and q in gs[b][1]), None)
            if i is None or j is None:
                continue
            if gs[i] == ["h", (q,)] and gs[j] == ["h", (q,)]:
                alive[i] = alive[j] = False
                gs[k] = ["ccx", tuple(x for x in qs if x != q) + (q,)]
                break
    out = [(n, q) for (n, q), a in zip(gs, alive) if a]
    if any(n in ("h", "ccz") for n, _ in out):
        return None
    return out


# ---------------------------------------------------------------- GF(2) helpers on truth-table ints
def _var_tts(k):
    n = 1 << k
    full = (1 << n) - 1
    out = []
    for j in range(k):
        half = 1 << j
        unit = ((1 << half) - 1) << half
        rep = full // ((1 << (2 * half)) - 1)
        out.append(unit * rep)
    return out, full


class _Basis:
    def __init__(self):
        self.b = {}
        self.piv = []

    def insert(self, v, combo=0):
        while v:
            p = v.bit_length() - 1
            if p in self.b:
                bv, bc = self.b[p]
                v ^= bv
                combo ^= bc
            else:
                self.b[p] = (v, combo)
                self.piv = sorted(self.b, reverse=True)
                return

    def reduce(self, v):
        for p in self.piv:
            if (v >> p) & 1:
                v ^= self.b[p][0]
        return v


def _express(target, items, full):
    """target as XOR of item tts (+ constant 1): (labels, const) or None."""
    bs = _Basis()
    nconst = len(items)
    bs.insert(full, 1 << nconst)
    for i, (_, tt) in enumerate(items):
        bs.insert(tt, 1 << i)
    v, combo = target, 0
    while v:
        p = v.bit_length() - 1
        if p not in bs.b:
            return None
        bv, bc = bs.b[p]
        v ^= bv
        combo ^= bc
    return [items[i][0] for i in range(nconst) if (combo >> i) & 1], bool((combo >> nconst) & 1)


def _stats(tt, k, pop):
    n = 1 << k
    raw = tt.to_bytes(max(n // 8, 1), "little")
    arr = np.unpackbits(np.frombuffer(raw, np.uint8), bitorder="little")[:n].copy()
    for i in range(k):
        a = arr.reshape(-1, 2, 1 << i)
        a[:, 1, :] ^= a[:, 0, :]
    idx = np.nonzero(arr)[0]
    if idx.size == 0:
        return (0, 0)
    return (int(pop[idx].max()), int(idx.size))


# ---------------------------------------------------------------- planning
def _simulate(ops, n, V, vt, full):
    st = [0] * n
    for p, w in enumerate(V):
        st[w] = vt[p]
    for name, qs in ops:
        if name == "x":
            st[qs[0]] ^= full
        elif name == "cx":
            st[qs[1]] ^= st[qs[0]]
        else:
            st[qs[2]] ^= st[qs[0]] & st[qs[1]]
    return st


def _extract(O, vt, full, k, limit):
    """Greedy AND extraction. Returns list of (g_tt, h_tt) or raises _Fail."""
    pop = np.array([bin(i).count("1") for i in range(1 << k)], dtype=np.int64)
    sig = list(vt)
    nodes = []
    targets = sorted(set(O))
    while True:
        bs = _Basis()
        bs.insert(full)
        for s in sig:
            bs.insert(s)
        unresolved = [t for t in targets if bs.reduce(t)]
        if not unresolved:
            return nodes
        if len(nodes) >= limit:
            raise _Fail("too many AND nodes")
        stats = {t: _stats(bs.reduce(t), k, pop) for t in unresolved}
        order = sorted(unresolved, key=lambda t: (stats[t], t))
        rts = [bs.reduce(t) for t in order]
        pick = None
        # For a candidate factor g (sum of <= width signals) the best partner h is found EXACTLY by GF(2) linear
        # algebra: h -> reduce(g*h) is linear in h over the span of the available signals.
        for width in (2, 3):
            best = None                       # (target rank, g, h)
            for sup in range(1, width + 1):
                for comb in combinations(range(len(sig)), sup):
                    g = 0
                    for i in comb:
                        g ^= sig[i]
                    cb = _Basis()
                    for i, s in enumerate(sig):
                        cb.insert(bs.reduce(g & s), 1 << i)
                    for rank, rt in enumerate(rts):
                        if best is not None and rank >= best[0]:
                            break
                        v, combo = rt, 0
                        while v:
                            p = v.bit_length() - 1
                            if p not in cb.b:
                                break
                            v ^= cb.b[p][0]
                            combo ^= cb.b[p][1]
                        if v:
                            continue
                        h = 0
                        for i in range(len(sig)):
                            if (combo >> i) & 1:
                                h ^= sig[i]
                        if h and h != g:
                            best = (rank, g, h)
                            break
                    if best is not None and best[0] == 0:
                        break
                if best is not None and best[0] == 0:
                    break
            if best is not None:
                pick = (best[1], best[2])
                break
        if pick is None:
            raise _Fail("no progress")
        nodes.append(pick)
        sig.append(pick[0] & pick[1])


def _plan(c):
    if not dv.is_ir_circuit(c):
        return None
    key = (c.n_qubits, c.n_cbits, tuple(c.gates), tuple(sorted((a, tuple(b)) for a, b in c.registers.items())))
    if key in _CACHE:
        return _CACHE[key]
    try:
        plan = _build_plan(c)
    except _Fail as e:
        plan = None
    if len(_CACHE) > 64:
        _CACHE.clear()
    _CACHE[key] = plan
    return plan


def _build_plan(c):
    ops = _fold(c)
    if ops is None:
        raise _Fail("not classical")
    ncc = sum(1 for n, _ in ops if n == "ccx")
    if ncc < 2 or ncc != sum(1 for g in c.gates if g.name in ("ccx", "ccz")):
        raise _Fail("not enough / mixed gates")
    n0 = c.n_qubits
    reg = sorted({q for qs in c.registers.values() for q in qs})
    V = reg if reg else list(range(n0))
    k = len(V)
    if k < 3 or k > _MAX_VARS:
        raise _Fail("variable count")
    vt, full = _var_tts(k)
    O = _simulate(ops, n0, V, vt, full)
    nodes = _extract(O, vt, full, k, ncc - 1)
    A = len(nodes)
    if not A or 4 * A >= 4 * ncc:
        raise _Fail("no gain")
    node_tt = [g & h for g, h in nodes]

    out = []
    nxt = [n0]
    scratch = []

    def new_wire():
        nxt[0] += 1
        return nxt[0] - 1

    def scratch_wire(slot):
        if not scratch:
            scratch.extend([new_wire(), new_wire()])
        return scratch[slot]

    def build(target, avail, slot):
        for w, tt in avail:
            if tt == target:
                return w, [], []
        sol = _express(target, avail, full)
        if sol is None:
            raise _Fail("factor not expressible")
        ws, const = sol
        s = scratch_wire(slot)
        pre = [("cx", (w, s)) for w in ws] + ([("x", (s,))] if const else [])
        return s, pre, pre[::-1]

    def pair(g, h, avail, data):
        """wires holding g and h; built in place on data wires when possible, else on scratch wires."""
        av = list(avail)
        pre = []
        res = []
        used = set()
        for slot, target in enumerate((g, h)):
            hit = next((w for w, tt in av if tt == target and w not in used), None)
            if hit is not None:
                res.append(hit)
                used.add(hit)
                continue
            sol = _express(target, av, full)
            if sol is None:
                raise _Fail("factor not expressible")
            ws, const = sol
            piv = next((w for w in ws if w in data and w not in used), None)
            if piv is None:
                piv = scratch_wire(slot)
                ops = [("cx", (w, piv)) for w in ws] + ([("x", (piv,))] if const else [])
                new_tt = target
                av = [(w, tt) for w, tt in av if w != piv] + [(piv, new_tt)]
            else:
                ops = [("cx", (w, piv)) for w in ws if w != piv] + ([("x", (piv,))] if const else [])
                av = [(w, (target if w == piv else tt)) for w, tt in av]
            pre.extend(ops)
            res.append(piv)
            used.add(piv)
        return res[0], res[1], pre, pre[::-1]

    def emit(seq):
        out.extend(seq)

    # 1. compute AND nodes
    anc = []
    avail = [(w, vt[p]) for p, w in enumerate(V)]
    for m, (g, h) in enumerate(nodes):
        gw, hw, pre, undo = pair(g, h, avail, set(range(n0)))
        a = new_wire()
        emit(pre + [("and_compute", (gw, hw, a))] + undo)
        anc.append(a)
        avail.append((a, node_tt[m]))

    # 2. outputs
    items = [(("v", w), vt[p]) for p, w in enumerate(V)] + [(("n", m), node_tt[m]) for m in range(A)]
    sols = []
    for w in range(n0):
        s = _express(O[w], items, full)
        if s is None:
            raise _Fail("output not in span")
        sols.append(s)
    Vset = set(V)
    for w in range(n0):
        if w not in Vset:
            for lab in sols[w][0]:
                if lab[0] == "v":
                    emit([("cx", (lab[1], w))])
    rows = []
    for w in V:
        r = 0
        for lab in sols[w][0]:
            if lab[0] == "v":
                r |= 1 << V.index(lab[1])
        rows.append(r)
    cops = []
    for j in range(k):
        if not (rows[j] >> j) & 1:
            r = next((r for r in range(j + 1, k) if (rows[r] >> j) & 1), None)
            if r is None:
                raise _Fail("singular linear part")
            rows[j] ^= rows[r]
            cops.append((j, r))
        for i in range(k):
            if i != j and (rows[i] >> j) & 1:
                rows[i] ^= rows[j]
                cops.append((i, j))
    for i, j in reversed(cops):
        emit([("cx", (V[j], V[i]))])
    for w in range(n0):
        for lab in sols[w][0]:
            if lab[0] == "n":
                emit([("cx", (anc[lab[1]], w))])
    for w in range(n0):
        if sols[w][1]:
            emit([("x", (w,))])

    # 3. release in reverse order
    for m in range(A - 1, -1, -1):
        av = [(w, O[w]) for w in range(n0)] + [(anc[j], node_tt[j]) for j in range(m)]
        g, h = nodes[m]
        gw, hw, pre, undo = pair(g, h, av, set(range(n0)))
        emit(pre + [("and_uncompute", (gw, hw, anc[m]))] + undo)
    # self-check on truth tables (classical semantics of the gadgets; a failed uncompute precondition = bad plan)
    st = [0] * nxt[0]
    for p, w in enumerate(V):
        st[w] = vt[p]
    for name, qs in out:
        if name == "x":
            st[qs[0]] ^= full
        elif name == "cx":
            st[qs[1]] ^= st[qs[0]]
        elif name == "and_compute":
            if st[qs[2]]:
                raise _Fail("self-check: compute target not clean")
            st[qs[2]] = st[qs[0]] & st[qs[1]]
        else:
            if st[qs[2]] != st[qs[0]] & st[qs[1]]:
                raise _Fail("self-check: uncompute precondition")
            st[qs[2]] = 0
    if st[:n0] != O or any(st[n0:]):
        raise _Fail("self-check: final state differs")
    return dict(gates=out, nq=nxt[0], A=A, ncc=ncc)


# ---------------------------------------------------------------- rule interface
def find_matches(c):
    p = _plan(c)
    return [("xag", p["A"], p["ncc"])] if p else []


def apply_match(c, m):
    p = _plan(c)
    if not p:
        return c.copy()
    gates = [dv.IRGate(n, tuple(q)) for n, q in p["gates"]]
    return dv.ir_with_gates(c, gates, n_qubits=p["nq"])


RULE = Rule(
    name="xag_multiplicative_complexity_resynthesis",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Meuli-Soeken-Roetteler-Haener 2022 (XAGs for quantum compilation); Boyar-Peralta-Pochuev; "
           "Gidney 2018 (temporary AND, measurement-based uncompute)",
    idea="Fold h-ccz-h into ccx, compute the exact Boolean function of every wire, extract AND nodes greedily over "
         "GF(2)-linear combinations of already available signals, compute each node with the 4-T Gidney AND "
         "gadget, write outputs as linear forms over inputs and nodes, then release nodes in reverse with the "
         "0-T measurement-based uncompute. T-cost = 4 per AND node, XORs free.",
    trigger=find_matches,
    apply=apply_match,
)
