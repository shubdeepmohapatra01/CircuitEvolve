"""Reconstruction rule: lift an and_compute/and_uncompute + CX/X segment (or raw ccx / H-ccz-H groups) to an F2
straight-line AND program, search COMPLETELY (CDCL over stdlib) for a program with fewer AND steps in the free-XOR
multiplicative-complexity class (affine factors over the unchanged input wires and earlier AND results), verify the
witness symbolically in F2[v]/(v_i^2 - v_i), and re-emit it as 4-T AND gadgets with measured uncompute."""
import heapq
import time

from v3.api import Rule
from v3.api import dv

_ALLOWED = {"x", "cx", "and_compute", "and_uncompute", "ccx", "ccz", "h"}
DEG_CAP = 3            # monomial degree kept in the SAT encoding (the exact check afterwards sees every degree)
MAX_SUPPORT = 10
MAX_STEPS = 12
CONFLICT_BUDGET = 30000
TIME_BUDGET = 70.0     # seconds per R, encoding included
_CACHE = {}


# ------------------------------------------------------------------ Boolean polynomials (sets of masks) --------
def _mul(P, Q):
    out = set()
    for a in P:
        for b in Q:
            m = a | b
            if m in out:
                out.remove(m)
            else:
                out.add(m)
    return out


def _lift(c, var_wires=None):
    """Return dict(var_wires, val, n_and, n_ccx) or None. val[w] = set of monomial masks over var index."""
    if not dv.is_ir_circuit(c) or not c.gates:
        return None
    gates = c.gates
    if any(g.name not in _ALLOWED or g.cond is not None for g in gates):
        return None
    n = c.n_qubits
    if var_wires is None:
        first = {}
        for g in gates:
            for pos, q in enumerate(g.qubits):
                if q not in first:
                    first[q] = (g.name == "and_compute" and pos == 2)
        var_wires = [w for w in range(n) if not first.get(w, False)]
    vidx = {w: i for i, w in enumerate(var_wires)}
    val = {w: ({1 << vidx[w]} if w in vidx else set()) for w in range(n)}
    inh = {w: False for w in range(n)}
    n_and = n_ccx = 0
    for g in gates:
        qs = g.qubits
        if len(set(qs)) != len(qs) or any(q >= n for q in qs):
            return None
        if g.name == "h":
            inh[qs[0]] = not inh[qs[0]]
            continue
        if g.name == "ccz":
            tg = [q for q in qs if inh[q]]
            if len(tg) != 1:
                return None
            t = tg[0]
            a, b = [q for q in qs if q != t]
            val[t] = val[t] ^ _mul(val[a], val[b])
            n_ccx += 1
            continue
        if any(inh[q] for q in qs):
            return None
        if g.name == "x":
            val[qs[0]] = val[qs[0]] ^ {0}
        elif g.name == "cx":
            val[qs[1]] = val[qs[1]] ^ val[qs[0]]
        elif g.name == "ccx":
            val[qs[2]] = val[qs[2]] ^ _mul(val[qs[0]], val[qs[1]])
            n_ccx += 1
        elif g.name == "and_compute":
            if val[qs[2]]:
                return None
            val[qs[2]] = _mul(val[qs[0]], val[qs[1]])
            n_and += 1
        elif g.name == "and_uncompute":
            if val[qs[2]] != _mul(val[qs[0]], val[qs[1]]):
                return None
            val[qs[2]] = set()
    if any(inh.values()):
        return None
    for w in range(n):
        if w not in vidx and val[w]:
            return None
    return dict(var_wires=list(var_wires), vidx=vidx, val=val, n_and=n_and, n_ccx=n_ccx, n=n)


# ------------------------------------------------------------------ CNF builder ----------------------------------
class _Cnf:
    def __init__(self):
        self.nv = 1
        self.clauses = [[1]]
        self.T = 1
        self._and = {}
        self._xor = {}

    def new(self):
        self.nv += 1
        return self.nv

    def AND(self, a, b):
        T = self.T
        if a == -T or b == -T:
            return -T
        if a == T:
            return b
        if b == T:
            return a
        if a == b:
            return a
        if a == -b:
            return -T
        key = (a, b) if a < b else (b, a)
        z = self._and.get(key)
        if z is None:
            z = self.new()
            self._and[key] = z
            self.clauses += [[-z, a], [-z, b], [z, -a, -b]]
        return z

    def xor2(self, a, b):
        T = self.T
        if a == -T:
            return b
        if b == -T:
            return a
        if a == T:
            return -b
        if b == T:
            return -a
        if a == b:
            return -T
        if a == -b:
            return T
        key = (a, b) if a < b else (b, a)
        z = self._xor.get(key)
        if z is None:
            z = self.new()
            self._xor[key] = z
            self.clauses += [[-z, a, b], [-z, -a, -b], [z, -a, b], [z, a, -b]]
        return z

    def XOR(self, lits):
        acc = -self.T
        for l in lits:
            acc = self.xor2(acc, l)
        return acc

    def add(self, cl):
        self.clauses.append(list(cl))


# ------------------------------------------------------------------ CDCL ----------------------------------------
def _solve(nv, clauses, max_conflicts, deadline):
    """Complete CDCL (2-watched literals, 1UIP, VSIDS, phase saving, Luby restarts). Returns (status, model)."""
    val = [0] * (nv + 1)
    level = [0] * (nv + 1)
    reason = [None] * (nv + 1)
    phase = [False] * (nv + 1)
    act = [0.0] * (nv + 1)
    seen = [False] * (nv + 1)
    watches = [[] for _ in range(2 * nv + 2)]
    trail, lims = [], []
    st = {"q": 0, "inc": 1.0}

    def li(l):
        return 2 * l if l > 0 else -2 * l + 1

    def value(l):
        v = val[l if l > 0 else -l]
        return v if l > 0 else -v

    def enqueue(l, why):
        v = abs(l)
        val[v] = 1 if l > 0 else -1
        level[v] = len(lims)
        reason[v] = why
        trail.append(l)

    for cl in clauses:
        s = set(cl)
        if any(-l in s for l in s):
            continue
        cl = list(s)
        if not cl:
            return "UNSAT", None
        if len(cl) == 1:
            if value(cl[0]) == -1:
                return "UNSAT", None
            if value(cl[0]) == 0:
                enqueue(cl[0], None)
        else:
            watches[li(cl[0])].append(cl)
            watches[li(cl[1])].append(cl)

    def propagate():
        while st["q"] < len(trail):
            p = trail[st["q"]]
            st["q"] += 1
            fl = -p
            ws = watches[li(fl)]
            i = j = 0
            nws = len(ws)
            while i < nws:
                c = ws[i]
                i += 1
                if c[0] == fl:
                    c[0], c[1] = c[1], c[0]
                first = c[0]
                if value(first) == 1:
                    ws[j] = c
                    j += 1
                    continue
                for k in range(2, len(c)):
                    if value(c[k]) != -1:
                        c[1], c[k] = c[k], c[1]
                        watches[li(c[1])].append(c)
                        break
                else:
                    ws[j] = c
                    j += 1
                    if value(first) == -1:
                        while i < nws:
                            ws[j] = ws[i]
                            j += 1
                            i += 1
                        del ws[j:]
                        return c
                    enqueue(first, c)
            del ws[j:]
        return None

    heap = [(0.0, v) for v in range(1, nv + 1)]
    heapq.heapify(heap)

    def bump(v):
        act[v] += st["inc"]
        if act[v] > 1e100:
            for u in range(1, nv + 1):
                act[u] *= 1e-100
            st["inc"] *= 1e-100
        heapq.heappush(heap, (-act[v], v))

    def cancel(lv):
        if len(lims) <= lv:
            return
        for l in trail[lims[lv]:]:
            v = abs(l)
            phase[v] = l > 0
            val[v] = 0
            reason[v] = None
            heapq.heappush(heap, (-act[v], v))
        del trail[lims[lv]:]
        del lims[lv:]
        st["q"] = len(trail)

    def analyze(confl):
        learnt = [0]
        counter = 0
        p = None
        idx = len(trail) - 1
        cur = len(lims)
        c = confl
        while True:
            for q in c:
                if q == p:
                    continue
                v = abs(q)
                if not seen[v] and level[v] > 0:
                    seen[v] = True
                    bump(v)
                    if level[v] >= cur:
                        counter += 1
                    else:
                        learnt.append(q)
            while not seen[abs(trail[idx])]:
                idx -= 1
            p = trail[idx]
            idx -= 1
            c = reason[abs(p)]
            seen[abs(p)] = False
            counter -= 1
            if counter == 0:
                break
        learnt[0] = -p
        for q in learnt[1:]:
            seen[abs(q)] = False
        if len(learnt) == 1:
            bl = 0
        else:
            m = max(range(1, len(learnt)), key=lambda i: level[abs(learnt[i])])
            learnt[1], learnt[m] = learnt[m], learnt[1]
            bl = level[abs(learnt[1])]
        return learnt, bl

    def luby(i):
        k = 1
        while (1 << k) - 1 < i:
            k += 1
        while True:
            if i == (1 << k) - 1:
                return 1 << (k - 1)
            i -= (1 << (k - 1)) - 1
            k = 1
            while (1 << k) - 1 < i:
                k += 1

    conflicts = 0
    restarts = 1
    next_restart = 100 * luby(restarts)
    since = 0
    while True:
        confl = propagate()
        if confl is not None:
            conflicts += 1
            since += 1
            if not lims:
                return "UNSAT", None
            learnt, bl = analyze(confl)
            cancel(bl)
            if len(learnt) == 1:
                enqueue(learnt[0], None)
            else:
                watches[li(learnt[0])].append(learnt)
                watches[li(learnt[1])].append(learnt)
                enqueue(learnt[0], learnt)
            st["inc"] /= 0.95
            if conflicts >= max_conflicts or (conflicts % 64 == 0 and time.monotonic() > deadline):
                return "UNKNOWN", None
            continue
        if since >= next_restart:
            since = 0
            restarts += 1
            next_restart = 100 * luby(restarts)
            cancel(0)
            continue
        v = 0
        while heap:
            _, u = heapq.heappop(heap)
            if val[u] == 0:
                v = u
                break
        if v == 0:
            return "SAT", val
        lims.append(len(trail))
        enqueue(v if phase[v] else -v, None)


# ------------------------------------------------------------------ the complete search --------------------------
def _search(sup, G, ychg, R, deadline):
    """sup: global var indices of the free input wires (support); G: {y: set of masks over GLOBAL var idx}.
    Returns ("SAT", steps, outs) / ("UNSAT",) / ("UNKNOWN",). Steps are affine forms over sup and earlier results,
    constants fixed to 0 (x gates are free), steps ordered by L <= L' inside a step."""
    n = len(sup)
    loc = {g: i for i, g in enumerate(sup)}

    def tolocal(m):
        out = 0
        i = 0
        while m >> i:
            if (m >> i) & 1:
                out |= 1 << loc[i]
            i += 1
        return out

    cnf = _Cnf()
    T = cnf.T
    xs = [[cnf.new() for _ in range(n)] for _ in range(R)]
    xp = [[cnf.new() for _ in range(n)] for _ in range(R)]
    ms = [[cnf.new() for _ in range(r)] for r in range(R)]
    mp = [[cnf.new() for _ in range(r)] for r in range(R)]
    pop = [bin(m).count("1") for m in range(1 << n)]
    P = []
    for r in range(R):
        if time.monotonic() > deadline:
            return ("UNKNOWN",)
        facs = []
        for xv, mv in ((xs[r], ms[r]), (xp[r], mp[r])):
            acc = {}
            for i in range(n):
                acc.setdefault(1 << i, []).append(xv[i])
            for j in range(r):
                for m, lit in P[j].items():
                    acc.setdefault(m, []).append(cnf.AND(mv[j], lit))
            facs.append({m: cnf.XOR(l) for m, l in acc.items()})
            cnf.add(list(xv) + list(mv))                       # factor is not the zero form
        C1, C2 = facs
        acc = {}
        for m1, l1 in C1.items():
            for m2, l2 in C2.items():
                u = m1 | m2
                if pop[u] <= DEG_CAP:
                    acc.setdefault(u, []).append(cnf.AND(l1, l2))
        P.append({m: cnf.XOR(l) for m, l in acc.items()})
        # symmetry breaking: L <= L' lexicographically (bit order: support bits, then feedback bits)
        a_bits, b_bits = list(xs[r]) + list(ms[r]), list(xp[r]) + list(mp[r])
        e = T
        for al, bl in zip(a_bits, b_bits):
            cnf.add([-e, -al, bl])
            ne = cnf.new()
            cnf.add([ne, -e, al, bl])
            cnf.add([ne, -e, -al, -bl])
            e = ne
    a = {y: [cnf.new() for _ in range(R)] for y in ychg}
    monos = set()
    for Pr in P:
        monos |= set(Pr)
    for y in ychg:
        monos |= {tolocal(m) for m in G[y]}
    for y in ychg:
        tgt = {tolocal(m) for m in G[y]}
        for m in sorted(monos):
            if pop[m] < 2 or pop[m] > DEG_CAP:
                continue                                       # degree <= 1 is absorbed by the affine output form
            lits = [cnf.AND(a[y][r], P[r][m]) for r in range(R) if m in P[r]]
            z = cnf.XOR(lits)
            cnf.add([z] if m in tgt else [-z])
        if time.monotonic() > deadline:
            return ("UNKNOWN",)
    status, model = _solve(cnf.nv, cnf.clauses, CONFLICT_BUDGET, deadline)
    if status != "SAT":
        return (status,)

    def tr(l):
        return model[abs(l)] * (1 if l > 0 else -1) == 1

    steps = []
    for r in range(R):
        steps.append((tuple(sup[i] for i in range(n) if tr(xs[r][i])), tuple(j for j in range(r) if tr(ms[r][j])),
                      tuple(sup[i] for i in range(n) if tr(xp[r][i])), tuple(j for j in range(r) if tr(mp[r][j]))))
    outs = tuple((y, tuple(r for r in range(R) if tr(a[y][r]))) for y in ychg)
    return ("SAT", tuple(steps), outs)


def _expand(steps):
    """Exact symbolic expansion of the AND program in F2[v]/(v_i^2 - v_i): list of monomial sets."""
    P = []
    for lv, lf, rv, rf in steps:
        A = {1 << i for i in lv}
        for j in lf:
            A ^= P[j]
        B = {1 << i for i in rv}
        for j in rf:
            B ^= P[j]
        P.append(_mul(A, B))
    return P


def _residuals(lf, steps, outs):
    """Check every output exactly; return {y: affine residual (set of masks)} or None."""
    P = _expand(steps)
    changed = {lf["vidx"][w] for w in lf["var_wires"] if lf["val"][w] != {1 << lf["vidx"][w]}}
    res = {}
    for y, rs in outs:
        yi = lf["vidx"][y]
        G = lf["val"][y] ^ {1 << yi}
        acc = set()
        for r in rs:
            acc ^= P[r]
        resid = G ^ acc
        for m in resid:
            if bin(m).count("1") > 1:
                return None
            if m & sum(1 << i for i in changed):
                return None
        res[y] = resid
    return res


# ------------------------------------------------------------------ trigger / apply -----------------------------
def _find(c):
    lf = _lift(c)
    if lf is None:
        return None
    n_steps = lf["n_and"] + lf["n_ccx"]
    cost0 = 4 * lf["n_and"] + 7 * lf["n_ccx"]
    if n_steps < 2 or n_steps > MAX_STEPS:
        return None
    vw, vidx, val = lf["var_wires"], lf["vidx"], lf["val"]
    ychg = [w for w in vw if val[w] != {1 << vidx[w]}]
    if not ychg:
        return None
    changed_bits = sum(1 << vidx[w] for w in ychg)
    G = {}
    supm = 0
    for y in ychg:
        g = val[y] ^ {1 << vidx[y]}
        if any(m & changed_bits for m in g):
            return None                                        # outputs must read only unchanged wires
        G[y] = g
        for m in g:
            supm |= m
    sup = [i for i in range(len(vw)) if (supm >> i) & 1]
    if not sup or len(sup) > MAX_SUPPORT:
        return None
    rmax = (cost0 - 1) // 4
    for R in (rmax, rmax - 1):
        if R < 1:
            break
        out = _search(sup, G, ychg, R, time.monotonic() + TIME_BUDGET)
        if out[0] == "UNSAT":
            return None                                        # proved optimal in this class (R <= this is impossible)
        if out[0] == "SAT":
            _, steps, outs = out
            if _residuals(lf, steps, outs) is not None:
                return (R, steps, outs)
    return None


def find_matches(c):
    if not dv.is_ir_circuit(c):
        return []
    key = tuple((g.name, g.qubits, g.cond) for g in c.gates) + (c.n_qubits,)
    if key not in _CACHE:
        _CACHE[key] = _find(c)
    m = _CACHE[key]
    return [m] if m is not None else []


def apply_match(c, m):
    lf = _lift(c)
    if lf is None:
        return c
    R, steps, outs = m
    res = _residuals(lf, steps, outs)
    if res is None:
        return c
    n = c.n_qubits
    vw = lf["var_wires"]
    G = dv.IRGate
    pw, qw = n, n + 1
    deps = [set(s[1]) | set(s[3]) for s in steps]
    pending = [sum(1 for r2 in range(R) if j in deps[r2]) for j in range(R)]
    wire_of, free, nxt = {}, [], [n + 2]
    gates = []

    def alloc():
        if free:
            return free.pop()
        nxt[0] += 1
        return nxt[0] - 1

    def fan(r):
        lv, lfd, rv, rfd = steps[r]
        ins = [G("cx", (vw[i], pw)) for i in lv] + [G("cx", (wire_of[j], pw)) for j in lfd]
        ins += [G("cx", (vw[i], qw)) for i in rv] + [G("cx", (wire_of[j], qw)) for j in rfd]
        return ins

    done = set()

    def release(r):
        f = fan(r)
        gates.extend(f)
        gates.append(G("and_uncompute", (pw, qw, wire_of[r])))
        gates.extend(reversed(f))
        done.add(r)
        free.append(wire_of[r])
        for d in sorted(deps[r]):
            pending[d] -= 1
            if pending[d] == 0 and d in wire_of and d not in done and not later_use(d, r):
                release(d)

    def later_use(d, r):
        return False

    for r in range(R):
        wire_of[r] = alloc()
        f = fan(r)
        gates.extend(f)
        gates.append(G("and_compute", (pw, qw, wire_of[r])))
        gates.extend(reversed(f))
        for y, rs in outs:
            if r in rs:
                gates.append(G("cx", (wire_of[r], y)))
        if pending[r] == 0:
            release(r)
    for y, resid in res.items():
        for mk in sorted(resid):
            if mk == 0:
                gates.append(G("x", (y,)))
            else:
                gates.append(G("cx", (vw[mk.bit_length() - 1], y)))
    new = dv.ir_with_gates(c, gates, n_qubits=nxt[0])
    lf2 = _lift(new, var_wires=vw)
    if lf2 is None or any(lf2["val"][w] != lf["val"][w] for w in range(n)):
        return c
    if any(lf2["val"][w] for w in range(n, new.n_qubits)):
        return c
    return new


RULE = Rule(
    name="and_program_lifting_with_complete_multiplicative_complexity_search",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Boyar-Matthews-Peralta 2013; Mirwald-Schnorr 1992; Courtois-Hulme-Mourouzis 2011/475; Gidney 2018",
    idea="Lift an and_compute/and_uncompute + CX/X segment to a Boolean straight-line program over F2[v]/(v^2-v), "
         "search completely (CDCL, free XOR, AND-result feedback) for a program with fewer AND steps, accept only "
         "after exact coefficientwise re-expansion, and re-emit it as 4-T AND gadgets with measured uncompute.",
    trigger=find_matches,
    apply=apply_match,
)
