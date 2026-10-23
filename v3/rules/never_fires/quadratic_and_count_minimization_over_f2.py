"""Reconstruction rule: a Toffoli-level segment that is the classical F2 map y ^= Q(x) (Q quadratic) is re-synthesized
with fewer AND gadgets than the bilinear count, by searching QUADRATIC (non-bilinear) products L(x)&L'(x)."""
from v3.api import Rule
from v3.api import dv

_ALLOWED = {"h", "ccz", "ccx", "cx", "x"}
_KAR = [0, 1, 3, 6, 9]
_MAX_VARS = 9
_BEAM = 4
_DEC_CACHE = {}
_SEARCH_CACHE = {}


def _analyse(c):
    """Return (X, Y, Q, lin) or None. Q[k] = frozenset of frozenset({xa, xb}) monomials on Y[k]; X = read-only wires."""
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
    val = {y: set() for y in ys}
    inh = {y: False for y in ys}
    pairs = 0
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
            pairs += 1
            val[t] ^= {frozenset(g.qubits[:2])}
        else:
            tg = [q for q in g.qubits if q in ys]
            if len(tg) != 1 or not inh[tg[0]]:
                return None
            t = tg[0]
            cs = frozenset(q for q in g.qubits if q != t)
            if len(cs) != 2 or any(q in ys for q in cs):
                return None
            ctrl.update(cs)
            pairs += 1
            val[t] ^= {cs}
    if any(inh.values()) or not pairs or ctrl & ys:
        return None
    X = sorted(ctrl)
    Y = sorted(ys)
    return X, Y, [frozenset(val[y]) for y in Y], lin


def _baseline(X, Q):
    """AND count of the current book on this segment: bilinear (Karatsuba) bound if square bipartite, else #monomials."""
    mons = set().union(*Q) if Q else set()
    m = len(mons)
    adj = {q: set() for q in X}
    for p in mons:
        a, b = tuple(p)
        adj[a].add(b)
        adj[b].add(a)
    col = {}
    for root in X:
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
                    return m
    n0 = sum(1 for q in X if col[q] == 0)
    n1 = len(X) - n0
    if n0 == n1 and 1 <= n0 <= 4:
        return min(m, _KAR[n0])
    return m


def _sides(X, Q):
    """Variable bitmasks (side0, side1) of the bipartition of the control-pair graph, or None."""
    xi = {q: i for i, q in enumerate(X)}
    adj = {q: set() for q in X}
    for mons in Q:
        for p in mons:
            a, b = tuple(p)
            adj[a].add(b)
            adj[b].add(a)
    col = {}
    for root in X:
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
                    return None
    s = [0, 0]
    for q in X:
        s[col[q]] |= 1 << xi[q]
    return s[0], s[1]


# ---- alternating-form machinery: u*v (mod affine) <-> u^v in Lambda^2(F2^N), one bit per pair i<j ----
def _pair_index(N):
    idx = {}
    for i in range(N):
        for j in range(i + 1, N):
            idx[(i, j)] = len(idx)
    return idx


def _alt(u, v, idx, N):
    r = 0
    for i in range(N):
        if (u >> i) & 1:
            for j in range(N):
                if i != j and (v >> j) & 1:
                    r ^= 1 << idx[(i, j) if i < j else (j, i)]
    return r


def _decomposables(N):
    if N not in _DEC_CACHE:
        idx = _pair_index(N)
        dec = {}
        for u in range(1, 1 << N):
            for v in range(u + 1, 1 << N):
                a = _alt(u, v, idx, N)
                if a and a not in dec:
                    dec[a] = (u, v)
        _DEC_CACHE[N] = (idx, dec, sorted(dec))
    return _DEC_CACHE[N]


def _insert(basis, v):
    """Echelon insert (basis: dict highbit -> vec). Returns True if v was independent."""
    while v:
        h = v.bit_length() - 1
        if h in basis:
            v ^= basis[h]
        else:
            basis[h] = v
            return True
    return False


def _reduce(basis, v):
    while v:
        h = v.bit_length() - 1
        if h in basis:
            v ^= basis[h]
        else:
            break
    return v


def _span_elems(vecs):
    out = [0]
    for v in vecs:
        out += [e ^ v for e in out]
    return out


def _evaluate(Wl, Ub, dec):
    """Decomposables inside U = span(Ub); returns (missing, L) where missing = dim(W mod span(L))."""
    L = [e for e in _span_elems(list(Ub.values())) if e in dec]
    sb = {}
    for e in L:
        _insert(sb, e)
    missing = 0
    for w in Wl:
        if _insert(sb, w):
            missing += 1
    return missing, L


def _search(Wvecs, N, rmax, pool=None):
    """Beam search over subspaces U = W + span(free decomposables); success iff W lies in span(Dec & U).
    Returns independent decomposable alternating forms (<= rmax) whose span contains W, or None."""
    idx, dec, keys = _decomposables(N)
    if pool is not None:
        keys = pool
    Wb = {}
    for w in Wvecs:
        _insert(Wb, w)
    Wl = list(Wb.values())
    beam = [(dict(Wb), ())]
    for level in range(0, rmax - len(Wl) + 1):
        scored = []
        for Ub, hist in beam:
            if len(Ub) > rmax:
                continue
            miss, L = _evaluate(Wl, Ub, dec)
            if miss == 0:
                sb = {}
                basis = []
                for e in L:
                    if _insert(sb, e):
                        basis.append(e)
                if len(basis) <= rmax:
                    return basis
            scored.append((miss, -len(L), hist, Ub))
        if level == rmax - len(Wl):
            break
        cand = []
        for miss, nl, hist, Ub in sorted(scored, key=lambda s: (s[0], s[1], s[2]))[:_BEAM]:
            for k in keys:
                if _reduce(Ub, k) == 0:
                    continue
                U2 = dict(Ub)
                _insert(U2, k)
                m2, L2 = _evaluate(Wl, U2, dec)
                cand.append((m2, -len(L2), hist + (k,), U2))
        cand.sort(key=lambda s: (s[0], s[1], s[2]))
        beam = [(s[3], s[2]) for s in cand[:_BEAM]]
    return None


# ---- symbolic F2 polynomial check (Boolean ring: x*x = x) ----
def _prod_poly(u, v, N):
    acc = set()
    for i in range(N):
        if (u >> i) & 1:
            for j in range(N):
                if (v >> j) & 1:
                    acc ^= {frozenset((i, j))}
    return acc


def _solve(basis_vecs, target):
    """Express target as XOR of a subset of basis_vecs. Returns mask over basis or None."""
    piv = {}
    for k, v in enumerate(basis_vecs):
        m = 1 << k
        while v:
            h = v.bit_length() - 1
            if h in piv:
                v ^= piv[h][0]
                m ^= piv[h][1]
            else:
                piv[h] = (v, m)
                break
    t, m = target, 0
    while t:
        h = t.bit_length() - 1
        if h not in piv:
            return None
        t ^= piv[h][0]
        m ^= piv[h][1]
    return m


def _program(X, Q):
    """Verified quadratic program: (prods [(u,v)], coeffs [mask per Y], affine [(const, linmask) per Y]) or None."""
    N = len(X)
    if N < 2 or N > _MAX_VARS:
        return None
    xi = {q: i for i, q in enumerate(X)}
    R0 = _baseline(X, Q)
    if R0 < 2:
        return None
    idx, dec, keys = _decomposables(N)
    polys, forms = [], []
    for mons in Q:
        p = {frozenset(xi[q] for q in m) for m in mons}
        polys.append(p)
        f = 0
        for m in p:
            a, b = sorted(m)
            f ^= 1 << idx[(a, b)]
        forms.append(f)
    if not any(forms):
        return None
    sig = (N, tuple(forms), R0)
    if sig not in _SEARCH_CACHE:
        # bipartite pool (bilinear-shaped products) first, then the full quadratic pool
        side = _sides(X, Q)
        pool = None
        if side is not None:
            def _bip(k):
                u, v = dec[k]
                pl = (u, v, u ^ v)   # the 2-plane of the product; bilinear iff it holds a side-0 and a side-1 vector
                return (any(e & ~side[0] == 0 for e in pl) and any(e & ~side[1] == 0 for e in pl))
            pool = [k for k in keys if _bip(k)]
        res = _search(forms, N, R0 - 1, pool) if pool else None
        if res is None:
            res = _search(forms, N, R0 - 1)
        _SEARCH_CACHE[sig] = res
    basis = _SEARCH_CACHE[sig]
    if basis is None or len(basis) >= R0:
        return None
    prods = [dec[b] for b in basis]
    coeffs, affine = [], []
    for p, f in zip(polys, forms):
        mask = _solve(basis, f)
        if mask is None:
            return None
        acc = set()
        for r, (u, v) in enumerate(prods):
            if (mask >> r) & 1:
                acc ^= _prod_poly(u, v, N)
        resid = acc ^ p
        if any(len(m) > 1 for m in resid):
            return None
        const = 1 if frozenset() in resid else 0
        lm = 0
        for m in resid:
            if len(m) == 1:
                lm |= 1 << next(iter(m))
        full = set(acc)
        if const:
            full ^= {frozenset()}
        for i in range(N):
            if (lm >> i) & 1:
                full ^= {frozenset((i,))}
        if full != p:
            return None
        coeffs.append(mask)
        affine.append((const, lm))
    return tuple(prods), tuple(coeffs), tuple(affine)


def find_matches(c):
    info = _analyse(c)
    if info is None:
        return []
    X, Y, Q, lin = info
    prog = _program(X, Q)
    if prog is None:
        return []
    prods, coeffs, affine = prog
    return [(tuple(X), tuple(Y), prods, coeffs, affine)]


def apply_match(c, m):
    X, Y, prods, coeffs, affine = m
    info = _analyse(c)
    if info is None:
        return c
    G = dv.IRGate
    gates = list(info[3])
    p, q, s = c.n_qubits, c.n_qubits + 1, c.n_qubits + 2
    for r, (u, v) in enumerate(prods):
        fan = [G("cx", (X[i], p)) for i in range(len(X)) if (u >> i) & 1]
        fan += [G("cx", (X[i], q)) for i in range(len(X)) if (v >> i) & 1]
        gates += fan
        gates.append(G("and_compute", (p, q, s)))
        for k, mask in enumerate(coeffs):
            if (mask >> r) & 1:
                gates.append(G("cx", (s, Y[k])))
        gates.append(G("and_uncompute", (p, q, s)))
        gates += list(reversed(fan))
    for k, (const, lm) in enumerate(affine):
        if const:
            gates.append(G("x", (Y[k],)))
        for i in range(len(X)):
            if (lm >> i) & 1:
                gates.append(G("cx", (X[i], Y[k])))
    return dv.ir_with_gates(c, gates, n_qubits=c.n_qubits + 3)


RULE = Rule(
    name="quadratic_and_count_minimization_over_f2",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Boyar-Matthews-Peralta 2013 (multiplicative complexity, free XOR, x^2=x); Courtois et al. 2011/475; "
           "Barbulescu et al. WAIFI 2012; Gidney 2018 (4-T AND, measured uncompute)",
    idea="A Toffoli-level segment that only adds products of read-only bits into targets is the F2 map y ^= Q(x). "
         "Over F2 x^2 = x, so a product L(x)&L'(x) of arbitrary affine forms contributes its alternating (cross-term) "
         "part plus FREE affine self-terms. Search subspaces of decomposable products (u^v) whose span contains the "
         "polarizations of all Q_k, with fewer products than the bilinear count; verify symbolically over the Boolean "
         "ring; emit one 4-T AND gadget per product plus cx/x affine corrections.",
    trigger=find_matches,
    apply=apply_match,
)
