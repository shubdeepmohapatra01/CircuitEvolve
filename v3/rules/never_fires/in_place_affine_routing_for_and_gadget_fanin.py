"""Resource rule: route the linear forms of AND-gadget inputs in place on the read-only source wires, dropping the
dedicated fan-in ancillas (and any duplicate AND-result ancillas)."""
from v3.api import Rule
from v3.api import dv

_ALLOWED = {"x", "cx", "cz", "and_compute", "and_uncompute"}


def _solve(rows, u):
    """Coefficient mask c with XOR of rows[i] (i in c) == u, or None."""
    basis = []  # (vector, coeff)
    for i, r in enumerate(rows):
        v, cf = r, 1 << i
        for bv, bc in basis:
            if v ^ bv < v:
                v ^= bv
                cf ^= bc
        if v:
            basis.append((v, cf))
            basis.sort(reverse=True)
    v, cf = u, 0
    for bv, bc in basis:
        if v ^ bv < v:
            v ^= bv
            cf ^= bc
    return cf if v == 0 else None


def _route(cur, u):
    """CX list (ctrl_idx, tgt_idx) acting on register rows so that row 0 becomes u. Mutates cur."""
    ops = []
    for _ in range(3):
        c = _solve(cur, u)
        if c is None:
            return None
        if c & 1:
            for j in range(len(cur)):
                if j and (c >> j) & 1:
                    ops.append((j, 0))
                    cur[0] ^= cur[j]
            return ops if cur[0] == u else None
        j0 = (c & -c).bit_length() - 1
        ops.append((0, j0))
        cur[j0] ^= cur[0]
        ops.append((j0, 0))
        cur[0] ^= cur[j0]
    return None


def _restore(cur):
    ops = []
    n = len(cur)
    for i in range(n):
        if not (cur[i] >> i) & 1:
            j = next((k for k in range(n) if k != i and (cur[k] >> i) & 1), None)
            if j is None:
                return None
            ops.append((j, i))
            cur[i] ^= cur[j]
        for k in range(n):
            if k != i and (cur[k] >> i) & 1:
                ops.append((i, k))
                cur[k] ^= cur[i]
    return ops if all(cur[i] == 1 << i for i in range(n)) else None


def _analyse(c):
    if not dv.is_ir_circuit(c) or not c.gates:
        return None
    gates = list(c.gates)
    if any(g.name not in _ALLOWED or g.cond is not None for g in gates):
        return None
    if sum(1 for g in gates if g.name == "and_compute") < 2:
        return None
    written = set()
    for g in gates:
        if g.name in ("x", "cx"):
            written.add(g.qubits[-1])
        elif g.name in ("and_compute", "and_uncompute"):
            written.add(g.qubits[2])
    reg = {q for r in c.registers.values() for q in r}
    F = set()
    for g in gates:
        if g.name == "and_compute":
            for q in g.qubits[:2]:
                if q in written:
                    F.add(q)
    if len(F) < 2 or F & reg:
        return None
    # pass 1: symbolic forms; classify gates
    val = {f: 0 for f in F}

    def form(q):
        return val[q] if q in F else 1 << q

    kinds = []      # per gate: 'fan' | 'compute' | 'uncompute' | 'other'
    comp = []       # (gate index, p_form, q_form, s)
    open_ = {}      # s -> (pform, qform, p, q)
    for idx, g in enumerate(gates):
        nm, qs = g.name, g.qubits
        if nm == "cx" and qs[1] in F:
            if qs[0] not in F and qs[0] in written:
                return None
            val[qs[1]] ^= form(qs[0])
            kinds.append("fan")
        elif nm == "x" and qs[0] in F:
            return None
        elif nm == "and_compute":
            p, q, s = qs
            if s in F or s in open_ or form(p) == 0 or form(q) == 0:
                return None
            open_[s] = (form(p), form(q), p, q)
            comp.append((idx, form(p), form(q), s))
            kinds.append("compute")
        elif nm == "and_uncompute":
            p, q, s = qs
            if s not in open_:
                return None
            pf, qf, p0, q0 = open_.pop(s)
            if (p, q) != (p0, q0) or form(p) != pf or form(q) != qf:
                return None
            kinds.append("uncompute")
        else:
            if any(q in F for q in qs):
                return None
            kinds.append("other")
    if open_ or any(val[f] for f in F):
        return None
    pmask = 0
    qmask = 0
    for _, pf, qf, _ in comp:
        pmask |= pf
        qmask |= qf
    if pmask & qmask:
        return None
    A = [w for w in range(c.n_qubits) if (pmask >> w) & 1]
    B = [w for w in range(c.n_qubits) if (qmask >> w) & 1]
    if any(w in written for w in A + B) or not A or not B:
        return None
    for idx, g in enumerate(gates):
        if kinds[idx] == "other" and any(q in A or q in B for q in g.qubits):
            return None
    for idx, g in enumerate(gates):   # A/B only as fan controls / and controls
        if kinds[idx] == "fan" and g.qubits[0] not in F and g.qubits[0] not in A + B:
            pass
    # blocks
    s_all = [s for _, _, _, s in comp]
    s0 = s_all[0]
    blocks = []
    cur_blk = None
    outside_other = False
    for idx, g in enumerate(gates):
        k = kinds[idx]
        if k == "compute":
            cur_blk = {"s": g.qubits[2], "gates": [g]}
            cur_blk["pf"] = next(pf for i, pf, _, _ in comp if i == idx)
            cur_blk["qf"] = next(qf for i, _, qf, _ in comp if i == idx)
        elif k == "uncompute":
            cur_blk["gates"].append(g)
            blocks.append(cur_blk)
            cur_blk = None
        elif k == "other":
            if cur_blk is None:
                outside_other = True
                blocks.append({"other": g})
            else:
                cur_blk["gates"].append(g)
    # rename s_r -> s0; require s_r private to its block
    rn = {}
    for b in blocks:
        if "s" in b and b["s"] != s0:
            rn[b["s"]] = s0
    for b in blocks:
        if "s" in b and b["s"] in rn:
            pass
    s_used_outside = set()
    for b in blocks:
        if "other" in b:
            s_used_outside.update(b["other"].qubits)
    if any(s in s_used_outside for s in rn) or s0 in s_used_outside:
        return None
    gb = [b for b in blocks if "s" in b]
    # reorder only when every non-gadget gate is a cx(s, y) inside a block
    reorderable = not outside_other and all(
        g.name in ("and_compute", "and_uncompute") or (g.name == "cx" and g.qubits[0] == b["s"])
        for b in gb for g in b["gates"])
    nA, nB = len(A), len(B)
    ia = {w: i for i, w in enumerate(A)}
    ib = {w: i for i, w in enumerate(B)}

    def to_idx(f, idxmap):
        m = 0
        for w, i in idxmap.items():
            if (f >> w) & 1:
                m |= 1 << i
        return m

    for b in gb:
        b["u"] = to_idx(b["pf"], ia)
        b["v"] = to_idx(b["qf"], ib)
    curA = [1 << i for i in range(nA)]
    curB = [1 << i for i in range(nB)]
    order = list(gb)
    if reorderable:
        rem = list(gb)
        order = []
        ca, cb = list(curA), list(curB)
        while rem:
            best = None
            for b in rem:
                ta, tb = list(ca), list(cb)
                ra, rb = _route(ta, b["u"]), _route(tb, b["v"])
                if ra is None or rb is None:
                    return None
                cost = len(ra) + len(rb)
                if best is None or cost < best[0]:
                    best = (cost, b, ta, tb)
            _, b, ca, cb = best
            order.append(b)
            rem.remove(b)
    seq = order if reorderable else [b for b in blocks]
    out = []
    G = dv.IRGate
    ra_all = []
    for b in seq:
        if "other" in b:
            out.append(b["other"])
            continue
        ra, rb = _route(curA, b["u"]), _route(curB, b["v"])
        if ra is None or rb is None:
            return None
        out += [G("cx", (A[i], A[j])) for i, j in ra]
        out += [G("cx", (B[i], B[j])) for i, j in rb]
        for g in b["gates"]:
            if g.name == "and_compute":
                out.append(G("and_compute", (A[0], B[0], s0)))
            elif g.name == "and_uncompute":
                out.append(G("and_uncompute", (A[0], B[0], s0)))
            else:
                out.append(G(g.name, tuple(s0 if q in rn or q == b["s"] else q for q in g.qubits)))
    ra, rb = _restore(curA), _restore(curB)
    if ra is None or rb is None:
        return None
    out += [G("cx", (A[i], A[j])) for i, j in ra]
    out += [G("cx", (B[i], B[j])) for i, j in rb]
    # drop dead wires and compact
    dead = set(F) | set(rn)
    if dead & reg:
        return None
    used = {q for g in out for q in g.qubits}
    if dead & used:
        return None
    keep = [q for q in range(c.n_qubits) if q not in dead]
    if len(keep) >= c.n_qubits:
        return None
    mp = {q: i for i, q in enumerate(keep)}
    out = [G(g.name, tuple(mp[q] for q in g.qubits), g.cbit, g.cond) for g in out]
    if sum(1 for g in out if g.name == "and_compute") != len(comp):
        return None
    res = dv.ir_with_gates(c, out, n_qubits=len(keep))
    res.registers = {k: [mp[q] for q in v] for k, v in c.registers.items()}
    return res


def find_matches(c):
    try:
        r = _analyse(c)
    except Exception:
        return []
    return [(len(c.gates), r.n_qubits)] if r is not None else []


def apply_match(c, m):
    r = _analyse(c)
    return c if r is None else r


RULE = Rule(
    name="in_place_affine_routing_for_and_gadget_fanin",
    domain="dv",
    kind="resource",
    contract="relaxed",
    source="Patel-Markov-Hayes 2008 (in-place CNOT synthesis); Kepley-Steinwandt 2015; Gidney 2018 (4-T AND)",
    idea="Instead of loading each AND gadget's two affine input forms onto dedicated fan-in ancillas and unloading "
         "them, apply the CNOT network that moves one chosen wire of each read-only register to the next form in "
         "place (Gaussian elimination between consecutive forms), run the unchanged AND gadget on those wires, and "
         "restore the registers at the end. T is unchanged; the fan-in ancillas and the load/unload CNOTs vanish.",
    trigger=find_matches,
    apply=apply_match,
)
