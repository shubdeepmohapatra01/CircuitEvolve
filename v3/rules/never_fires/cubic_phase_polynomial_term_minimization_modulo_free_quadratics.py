"""Reconstruction rule: a Toffoli-level segment y ^= Q(x) is the diagonal cubic phase polynomial f = sum_k y_k Q_k(x)
between two H layers on the targets. Re-express f modulo free degree-<=2 (Clifford) phases as a sum of fewer products of
three affine forms (flip-graph search over F2 factor triples), emit one 4-T AND gadget per product."""
import random

from v3.api import Rule
from v3.api import dv

_ALLOWED = {"h", "ccz", "ccx", "cx", "x"}
_KAR = {2: 3, 3: 6, 4: 9}
_MAX_VARS = 16
_STEPS = 800000


def _analyse(c):
    """Return (V, ys, f, pairs, lin) or None.
    V = variable wires, ys = active target wires, f = set of frozenset(var idx) (ANF of the phase polynomial),
    pairs = {frozenset(x var idx): ymask}, lin = linear (cx/x) gates in order."""
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
    mode = {y: False for y in ys}
    val = {y: set() for y in ys}
    lin = []
    for g in gates:
        if g.name == "h":
            mode[g.qubits[0]] = not mode[g.qubits[0]]
        elif g.name == "x":
            if mode[g.qubits[0]]:
                return None
            lin.append(g)
        elif g.name == "cx":
            ctl, tgt = g.qubits
            if ctl not in ys or mode[ctl] or mode[tgt]:
                return None
            lin.append(g)
            val[tgt] ^= val[ctl]
        elif g.name == "ccx":
            a, b, t = g.qubits
            if a in ys or b in ys or a == b or mode[t]:
                return None
            val[t] ^= {frozenset((a, b))}
        else:  # ccz
            tg = [q for q in g.qubits if q in ys]
            if len(tg) != 1 or len(set(g.qubits)) != 3 or not mode[tg[0]]:
                return None
            cs = frozenset(q for q in g.qubits if q != tg[0])
            val[tg[0]] ^= {cs}
    if any(mode.values()):
        return None
    act = sorted(y for y in ys if val[y])
    if not act:
        return None
    xs = sorted({w for y in act for m in val[y] for w in m})
    V = xs + act
    if len(V) > _MAX_VARS:
        return None
    idx = {w: i for i, w in enumerate(V)}
    f = set()
    pairs = {}
    for y in act:
        for m in val[y]:
            f ^= {frozenset(idx[w] for w in m) | {idx[y]}}
            key = frozenset(idx[w] for w in m)
            pairs[key] = pairs.get(key, 0) ^ (1 << idx[y])
    pairs = {k: v for k, v in pairs.items() if v}
    return V, tuple(act), f, pairs, tuple(lin)


def _book_count(pairs):
    """Number of AND gadgets the Karatsuba book rule would use (bilinear segments), else the distinct pair count."""
    n_pairs = len(pairs)
    adj = {}
    for p in pairs:
        a, b = tuple(p)
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    col = {}
    for root in sorted(adj):
        if root in col:
            continue
        col[root] = 0
        stack = [root]
        while stack:
            q = stack.pop()
            for r in sorted(adj[q]):
                if r not in col:
                    col[r] = 1 - col[q]
                    stack.append(r)
                elif col[r] == col[q]:
                    return n_pairs
    na = sum(1 for v in col.values() if v == 0)
    nb = len(col) - na
    if na == nb and na in _KAR:
        return min(n_pairs, _KAR[na])
    return n_pairs


def _dependent(a, b, c):
    return a == 0 or b == 0 or c == 0 or a == b or b == c or a == c or (a ^ b) == c


def _insert(terms, t):
    """Add term t to the list, dropping terms whose factors are dependent (free quadratic) and merging terms that
    share two factors (c m n + c m n' = c m (n+n'))."""
    stack = [t]
    while stack:
        t = stack.pop()
        if _dependent(*t):
            continue
        st = set(t)
        for k, u in enumerate(terms):
            com = st & set(u)
            if len(com) == 3:
                terms.pop(k)
                break
            if len(com) == 2:
                terms.pop(k)
                rt = [x for x in t if x not in com][0]
                ru = [x for x in u if x not in com][0]
                stack.append(tuple(com) + (rt ^ ru,))
                break
        else:
            terms.append(tuple(sorted(t)))


def _search(seed, rng, steps):
    cur = list(seed)
    best = list(cur)
    stuck = 0
    for _ in range(steps):
        if len(best) <= 3:
            break
        R = len(cur)
        if stuck > 3000 and R < len(best) + 2 and R >= 2:
            i, j = rng.sample(range(R), 2)
            ti, tj = list(cur[i]), list(cur[j])
            rng.shuffle(ti)
            rng.shuffle(tj)
            a, b, c = ti
            a2, b2, c2 = tj
            for k in sorted((i, j), reverse=True):
                cur.pop(k)
            for t in ((a ^ a2, b, c), (a2, b, c ^ c2), (a2, b ^ b2, c2)):
                _insert(cur, t)
            stuck = 0
            continue
        if stuck > 20000 and R > len(best):
            cur = list(best)
            stuck = 0
            continue
        i = rng.randrange(R)
        pa = rng.randrange(3)
        if rng.random() < 0.3:
            # free move: (L + M) M N = L M N + M N, and M N is quadratic (Clifford)
            t = list(cur[i])
            t[pa] ^= t[(pa + 1 + rng.randrange(2)) % 3]
            cur.pop(i)
            _insert(cur, tuple(t))
            if len(cur) < len(best):
                best = list(cur)
                stuck = 0
            else:
                stuck += 1
            continue
        cf = cur[i][pa]
        cand = [(j, pb) for j in range(R) if j != i for pb in range(3) if cur[j][pb] == cf]
        if not cand:
            stuck += 1
            continue
        j, pb = cand[rng.randrange(len(cand))]
        ti = [x for q, x in enumerate(cur[i]) if q != pa]
        tj = [x for q, x in enumerate(cur[j]) if q != pb]
        if rng.random() < 0.5:
            ti.reverse()
        if rng.random() < 0.5:
            tj.reverse()
        m1, n1 = ti
        m2, n2 = tj
        for k in (max(i, j), min(i, j)):
            cur.pop(k)
        _insert(cur, (cf, m1 ^ m2, n1))
        _insert(cur, (cf, m2, n1 ^ n2))
        if len(cur) < len(best):
            best = list(cur)
            stuck = 0
        elif len(cur) < R:
            stuck = 0
        else:
            stuck += 1
    return best


def _bits(m):
    out, i = [], 0
    while m:
        if m & 1:
            out.append(i)
        m >>= 1
        i += 1
    return out


def _product_anf(terms):
    acc = set()
    for L, M, N in terms:
        lb, mb, nb = _bits(L), _bits(M), _bits(N)
        for i in lb:
            for j in mb:
                for k in nb:
                    acc ^= {frozenset((i, j, k))}
    return acc


def find_matches(c):
    info = _analyse(c)
    if info is None:
        return []
    V, act, f, pairs, lin = info
    if not any(len(m) == 3 for m in f):
        return []
    r_book = _book_count(pairs)
    seed = []
    for key in sorted(pairs, key=lambda k: sorted(k)):
        p, q = sorted(key)
        seed.append((1 << p, 1 << q, pairs[key]))
    if len(seed) < 2 or len(seed) < r_book and False:
        return []
    raw = []
    for key in sorted(pairs, key=lambda k: sorted(k)):
        p, q = sorted(key)
        raw += [(1 << p, 1 << q, 1 << y) for y in _bits(pairs[key])]
    best = None
    for s, sd in ((12345, seed), (777, raw), (99, seed)):
        rng = random.Random(s)
        cand = _search(sd, rng, _STEPS)
        if best is None or len(cand) < len(best):
            best = cand
        if len(best) < r_book and len(best) <= 8:
            break
    if best is None or len(best) >= r_book:
        return []
    rem = f ^ _product_anf(best)
    if any(len(m) > 2 for m in rem):
        return []
    g = tuple(sorted(tuple(sorted(V[i] for i in m)) for m in rem if m))
    terms = tuple(tuple(t) for t in best)
    return [(tuple(V), act, terms, g, lin)]


def apply_match(c, m):
    if _analyse(c) is None:
        return c
    V, act, terms, g, lin = m
    G = dv.IRGate
    base = c.n_qubits
    p, q, s, t = base, base + 1, base + 2, base + 3
    gates = list(lin)
    gates += [G("h", (y,)) for y in act]
    for term in terms:
        fan = []
        for form, anc in zip(term, (p, q, s)):
            fan += [G("cx", (V[i], anc)) for i in _bits(form)]
        gates += fan
        gates.append(G("and_compute", (p, q, t)))
        gates.append(G("cz", (t, s)))
        gates.append(G("and_uncompute", (p, q, t)))
        gates += list(reversed(fan))
    for mon in g:
        if len(mon) == 2:
            gates.append(G("cz", mon))
        elif len(mon) == 1:
            gates.append(G("z", mon))
    gates += [G("h", (y,)) for y in act]
    return dv.ir_with_gates(c, gates, n_qubits=base + 4)


RULE = Rule(
    name="cubic_phase_polynomial_term_minimization_modulo_free_quadratics",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Heyfron-Campbell 2019 (TODD); Campbell-Howard 2017 (cubic phases modulo RM(2,n)); Gidney 2018 (4-T AND)",
    idea="A Toffoli-level segment y ^= Q(x) is H.diag((-1)^f).H with f = sum_k y_k Q_k(x) cubic. Quadratic and linear "
         "phases are Clifford, so f only has to be matched modulo degree <= 2: search (flip-graph moves on triples of "
         "affine forms, factors may mix registers, dependent triples vanish) for fewer than the book's number of "
         "products L.M.N; check the identity symbolically in the Boolean ring, emit each product as one 4-T AND gadget "
         "plus CZ, and the quadratic remainder as CZ/Z.",
    trigger=find_matches,
    apply=apply_match,
)
