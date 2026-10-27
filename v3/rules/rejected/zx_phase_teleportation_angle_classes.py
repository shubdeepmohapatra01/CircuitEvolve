"""Phase teleportation (Kissinger-van de Wetering 2020): a symbolic ZX reduction only DISCOVERS which rotations may
be summed; the original op list is then edited in place (angles / deletions only)."""
import math

from v3.api import Rule
from v3.api import dv

_PI4 = math.pi / 4
_GRID_TOL = 1e-10
_MAX_PASSES = 400
_NUM_PHASE = {"t": 1, "tdg": 7, "s": 2, "sdg": 6, "z": 4}


class _G:
    """Graph-like ZX diagram. adj[u][v] in {1: simple, 2: Hadamard}; ph = numeric phase in units of pi/4 (mod 8);
    sym[v] = {variable: sign} formal phase (only on gadget leaves, which are 1-valent)."""

    def __init__(self):
        self.adj, self.ph, self.sym, self.bnd = {}, {}, {}, set()
        self.n = 0
        self.cancelled = []

    def new(self, k=0, sym=None, boundary=False):
        v = self.n
        self.n += 1
        self.adj[v] = {}
        self.ph[v] = k % 8
        self.sym[v] = dict(sym) if sym else {}
        if boundary:
            self.bnd.add(v)
        return v

    def edge(self, a, b, t):
        self.adj[a][b] = t
        self.adj[b][a] = t

    def tog(self, a, b):
        if b in self.adj[a]:
            del self.adj[a][b]
            del self.adj[b][a]
        else:
            self.edge(a, b, 2)

    def rem(self, v):
        for w in self.adj[v]:
            del self.adj[w][v]
        del self.adj[v], self.ph[v], self.sym[v]

    # --- gadget structure ---
    def is_leaf(self, v):
        return bool(self.sym[v]) and len(self.adj[v]) == 1

    def leaves(self, v):
        return [x for x in self.adj[v] if self.is_leaf(x)]

    def negate_leaf(self, l):
        self.ph[l] = (-self.ph[l]) % 8
        self.sym[l] = {k: -s for k, s in self.sym[l].items()}

    # --- rewrites ---
    def fuse(self, a, b):
        """Spider-fuse b into a. The a-b edge must already be removed."""
        for w, t in list(self.adj[b].items()):
            del self.adj[w][b]
            if w == a:
                continue
            if w in self.bnd:
                self.edge(w, a, t)
            else:
                if t != 2:
                    raise RuntimeError("non-graph-like edge in fuse")
                self.tog(a, w)
        self.ph[a] = (self.ph[a] + self.ph[b]) % 8
        self.sym[a].update(self.sym[b])
        del self.adj[b], self.ph[b], self.sym[b]

    def join(self, a, b, t):
        """Add an edge a-b of type t between two vertices (a != b), resolving parallel edges soundly."""
        if a in self.bnd or b in self.bnd:
            self.edge(a, b, t)
            return
        ex = self.adj[a].get(b)
        if t == 2:
            if ex == 2:
                del self.adj[a][b]
                del self.adj[b][a]
            elif ex is None:
                self.edge(a, b, 2)
            else:
                raise RuntimeError("unexpected simple edge")
            return
        if ex == 2:                                  # H self-loop after fusion: +pi
            del self.adj[a][b]
            del self.adj[b][a]
            self.ph[a] = (self.ph[a] + 4) % 8
        self.fuse(a, b)

    def try_id(self, v):
        if v in self.bnd or self.ph[v] != 0 or self.sym[v] or len(self.adj[v]) != 2:
            return False
        a, b = list(self.adj[v])
        if self.is_leaf(a) or self.is_leaf(b) or self.leaves(a) or self.leaves(b):
            return False
        t = 1 if self.adj[v][a] == self.adj[v][b] else 2
        self.rem(v)
        if a in self.bnd and b in self.bnd:
            self.edge(a, b, t)
        else:
            self.join(a, b, t)
        return True

    def _interior(self, x):
        return (x in self.adj and x not in self.bnd and not self.sym[x]
                and all(n not in self.bnd and self.adj[x][n] == 2 for n in self.adj[x]))

    def try_lcomp(self, u):
        if u not in self.adj or self.ph[u] not in (2, 6) or not self._interior(u) or self.leaves(u):
            return False
        for n in sorted(self.adj[u]):
            if self.leaves(n):                       # shield a gadget axis: u -H- b -H- c -H- n  (HHH = H)
                b, c = self.new(0), self.new(0)
                del self.adj[u][n]
                del self.adj[n][u]
                self.edge(u, b, 2)
                self.edge(b, c, 2)
                self.edge(c, n, 2)
        N = sorted(self.adj[u])
        a = self.ph[u]
        for i in range(len(N)):
            for j in range(i + 1, len(N)):
                self.tog(N[i], N[j])
        for n in N:
            self.ph[n] = (self.ph[n] - a) % 8
        self.rem(u)
        return True

    def _pivotable(self, x):
        return (x in self.adj and self.ph[x] in (0, 4) and self._interior(x) and not self.leaves(x))

    def try_pivot(self, u):
        if not self._pivotable(u):
            return False
        for v in sorted(self.adj[u]):
            if self._pivotable(v):
                self._pivot(u, v)
                return True
        return False

    def _pivot(self, u, v):
        pa, pb = self.ph[u], self.ph[v]
        Nu, Nv = set(self.adj[u]) - {v}, set(self.adj[v]) - {u}
        A, B, C = sorted(Nu - Nv), sorted(Nv - Nu), sorted(Nu & Nv)
        for X, Y in ((A, B), (A, C), (B, C)):
            for x in X:
                for y in Y:
                    self.tog(x, y)
        for x in A:
            self.ph[x] = (self.ph[x] + pb) % 8
        for x in B:
            self.ph[x] = (self.ph[x] + pa) % 8
        for x in C:
            self.ph[x] = (self.ph[x] + pa + pb + 4) % 8
        self.rem(u)
        self.rem(v)

    def normalize_axes(self):
        for v in sorted(self.adj):
            if v in self.bnd or self.ph[v] != 4:
                continue
            ls = self.leaves(v)
            if len(ls) == 1:
                self.ph[v] = 0
                self.negate_leaf(ls[0])

    def gadget_fuse(self):
        groups, dead = {}, []
        for v in sorted(self.adj):
            if v in self.bnd or self.ph[v] != 0:
                continue
            ls = self.leaves(v)
            if len(ls) != 1:
                continue
            key = frozenset(self.adj[v]) - {ls[0]}
            if not key:
                dead.append(v)
            else:
                groups.setdefault(key, []).append(v)
        ch = False
        for v in dead:
            if v not in self.adj:
                continue
            ls = self.leaves(v)
            if len(self.adj[v]) == 1 and len(ls) == 1:
                self.cancelled.append(dict(self.sym[ls[0]]))
                self.rem(ls[0])
                self.rem(v)
                ch = True
        for key, g in sorted(groups.items(), key=lambda kv: kv[1][0]):
            live = []
            for v in g:
                if v in self.adj and self.ph[v] == 0:
                    ls = self.leaves(v)
                    if len(ls) == 1 and frozenset(self.adj[v]) - {ls[0]} == key:
                        live.append((v, ls[0]))
            if len(live) < 2:
                continue
            kv_, kl = live[0]
            for o, ol in live[1:]:
                self.ph[kl] = (self.ph[kl] + self.ph[ol]) % 8
                self.sym[kl].update(self.sym[ol])
                self.rem(ol)
                self.rem(o)
            ch = True
        return ch

    def simplify(self):
        for _ in range(_MAX_PASSES):
            ch = False
            self.normalize_axes()
            for v in sorted(self.adj):
                if v in self.adj and self.try_id(v):
                    ch = True
            for v in sorted(self.adj):
                if v in self.adj and self.try_lcomp(v):
                    ch = True
            self.normalize_axes()
            for v in sorted(self.adj):
                if v in self.adj and self.try_pivot(v):
                    ch = True
            self.normalize_axes()
            if self.gadget_fuse():
                ch = True
            if not ch:
                break


def _build(c):
    """Circuit -> raw ZX graph (Z spiders, simple/H edges) with one gadget per non-grid rz. None if unsupported."""
    g = _G()
    last = [g.new(boundary=True) for _ in range(c.n)]
    pend = [False] * c.n

    def put(q, v):
        g.edge(last[q], v, 2 if pend[q] else 1)
        pend[q] = False
        last[q] = v

    for idx, (name, qs, ang) in enumerate(c.ops):
        if name == "h":
            pend[qs[0]] = not pend[qs[0]]
        elif name in _NUM_PHASE:
            put(qs[0], g.new(_NUM_PHASE[name]))
        elif name == "x":
            q = qs[0]
            pend[q] = not pend[q]
            put(q, g.new(4))
            pend[q] = not pend[q]
        elif name == "rz":
            k = round(ang / _PI4)
            if abs(ang - k * _PI4) <= _GRID_TOL:
                put(qs[0], g.new(k))
            else:
                w = g.new(0)
                put(qs[0], w)
                m = g.new(0)
                leaf = g.new(0, sym={idx: 1})
                g.edge(w, m, 2)
                g.edge(m, leaf, 2)
        elif name == "cx":
            ctl, tgt = qs
            vc = g.new(0)
            put(ctl, vc)
            pend[tgt] = not pend[tgt]
            vt = g.new(0)
            put(tgt, vt)
            pend[tgt] = not pend[tgt]
            g.edge(vc, vt, 2)
        elif name == "cz":
            va, vb = g.new(0), g.new(0)
            put(qs[0], va)
            put(qs[1], vb)
            g.edge(va, vb, 2)
        else:
            return None
    for q in range(c.n):
        put(q, g.new(boundary=True))
    return g


def _to_graph_like(raw):
    parent = {v: v for v in raw.adj}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for u in raw.adj:
        for v, t in raw.adj[u].items():
            if t == 1 and u < v and u not in raw.bnd and v not in raw.bnd:
                ru, rv = find(u), find(v)
                if ru != rv:
                    parent[max(ru, rv)] = min(ru, rv)
    g = _G()
    g.n = raw.n
    for v in raw.adj:
        r = find(v)
        if r not in g.adj:
            g.adj[r], g.ph[r], g.sym[r] = {}, 0, {}
        if v in raw.bnd:
            g.bnd.add(v)
        else:
            g.ph[r] = (g.ph[r] + raw.ph[v]) % 8
            g.sym[r].update(raw.sym[v])
    par = {}
    for u in raw.adj:
        for v, t in raw.adj[u].items():
            if u >= v:
                continue
            if u in raw.bnd or v in raw.bnd:
                g.edge(find(u), find(v), t)
                continue
            if t == 1:
                continue
            ru, rv = find(u), find(v)
            if ru == rv:
                g.ph[ru] = (g.ph[ru] + 4) % 8
            else:
                key = (min(ru, rv), max(ru, rv))
                par[key] = par.get(key, 0) ^ 1
    for (a, b), odd in sorted(par.items()):
        if odd:
            g.edge(a, b, 2)
    return g


_CACHE = {}


def _classes(c):
    key = (c.n, tuple(c.ops))
    if key in _CACHE:
        return _CACHE[key]
    out = []
    raw = _build(c)
    if raw is not None:
        g = _to_graph_like(raw)
        g.simplify()
        found = []
        for cl in g.cancelled:
            found.append(("cancel", tuple(sorted(cl.items()))))
        for v in sorted(g.adj):
            if g.is_leaf(v) and len(g.sym[v]) >= 2:
                found.append(("fuse", tuple(sorted(g.sym[v].items()))))
        for kind, items in found:
            angs = tuple(float(c.ops[i][2]) for i, _ in items)
            out.append((kind, items, angs))
        out.sort(key=lambda m: (-len(m[1]), m[1][0][0]))
    _CACHE.clear()
    _CACHE[key] = out
    return out


def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    return list(_classes(c))


def apply_match(c, m):
    if not dv.is_angle_circuit(c):
        return c
    kind, items, angs = m
    ops = list(c.ops)
    for (i, _), a in zip(items, angs):
        if i >= len(ops) or ops[i][0] != "rz" or float(ops[i][2]) != a:
            return c
    drop = set()
    if kind == "cancel":
        drop = {i for i, _ in items}
    else:
        j0, s0 = items[0]
        theta = math.remainder(sum(s0 * s * a for (_, s), a in zip(items, angs)), 2 * math.pi)
        drop = {i for i, _ in items[1:]}
        if abs(theta) < 1e-12:
            drop.add(j0)
        else:
            ops[j0] = ("rz", ops[j0][1], theta)
    return dv.with_ops(c, [op for i, op in enumerate(ops) if i not in drop])


RULE = Rule(
    name="zx_phase_teleportation_angle_classes",
    domain="dv",
    kind="procedure",
    contract="exact",
    source="Kissinger & van de Wetering, PRA 102, 022406 (2020); Duncan-Kissinger-Perdrix-van de Wetering, Quantum 4, 279",
    idea="Replace each non-pi/4 rotation by a symbolic phase gadget, reduce the ZX diagram (fusion, identity, local "
         "complementation, pivoting, gadget fusion) which is sound for every value of the variables; gadgets that fuse "
         "identify rotations whose angles may be summed. Apply the sums to the original op list in place (first "
         "rotation gets the signed sum, the others are deleted), leaving all Cliffords and CNOTs untouched.",
    trigger=find_matches,
    apply=apply_match,
)
