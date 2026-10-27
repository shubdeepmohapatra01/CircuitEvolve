"""X-frame normalisation of CCZ spans, then one temporary-AND ancilla per span (Toffoli-level circuits only)."""
from itertools import combinations

from v3.api import Rule
from v3.api import dv

G = dv.IRGate


def _status(g, a, b):
    """'free' (touches neither a nor b), 'ok' (frame-compatible) or 'bad'."""
    t = [q for q in g.qubits if q in (a, b)]
    if not t:
        return "free"
    if g.cond is not None:
        return "bad"
    n = g.name
    if n == "x" or n in ("z", "cz", "ccz"):
        return "ok"
    if n in ("cx", "ccx") and g.qubits[-1] not in t:
        return "ok"
    return "bad"


def _corr(qs, flipped, xt=None):
    """Clifford corrections for X_flipped conjugating a diagonal gate on qs (H-conjugated on xt if given)."""
    F = [q for q in qs if q in flipped]
    out = []
    for r in range(1, len(F) + 1):
        for S in combinations(F, r):
            mono = [q for q in qs if q not in S]
            if len(mono) == 2:
                if xt is not None and xt in mono:
                    out.append(G("cx", (mono[0] if mono[1] == xt else mono[1], xt)))
                else:
                    out.append(G("cz", tuple(mono)))
            elif len(mono) == 1:
                out.append(G("x" if mono[0] == xt else "z", (mono[0],)))
    return out


def _sweep(gates, lo, hi, a, b, mem):
    """Emit gates[lo..hi] with the X frame on (a, b) propagated; returns (ops, flipped set)."""
    fl = set()
    out = []
    for k in range(lo, hi + 1):
        g = gates[k]
        if k in mem:
            act = mem[k]
            qs = g.qubits
            xt = qs[2] if g.name == "ccx" else None
            if act[0] == "and":
                t = act[1]
                if g.name == "ccx":
                    out += [G("h", (xt,)), G("cz", (t, xt)), G("h", (xt,))]
                else:
                    c = [q for q in qs if q not in (a, b)][0]
                    out.append(G("cz", (t, c)))
            out += _corr(qs, fl, xt)
            continue
        if g.name == "x" and g.cond is None and g.qubits[0] in (a, b):
            fl ^= {g.qubits[0]}
            continue
        out.append(g)
        t = [q for q in g.qubits if q in fl]
        if t and g.name in ("z", "cz", "ccz", "cx", "ccx"):
            xt = g.qubits[-1] if g.name in ("cx", "ccx") else None
            out += _corr(g.qubits, fl, xt)
    return out, fl


def _members(gates):
    """pair -> list of (idx, target, is_ccx)."""
    groups = {}
    for i, g in enumerate(gates):
        if g.cond is not None:
            continue
        if g.name == "ccz":
            for tgt in g.qubits:
                pr = tuple(sorted(q for q in g.qubits if q != tgt))
                groups.setdefault(pr, []).append((i, tgt, False))
        elif g.name == "ccx":
            pr = tuple(sorted(g.qubits[:2]))
            groups.setdefault(pr, []).append((i, g.qubits[2], True))
    return groups


def _legal_between(gates, i, j, a, b):
    return all(_status(gates[k], a, b) != "bad" for k in range(i + 1, j))


def _cancel_ok(gates, i, j, a, b, c, is_ccx):
    for k in range(i + 1, j):
        g = gates[k]
        if _status(g, a, b) == "bad":
            return False
        if c in g.qubits and a not in g.qubits and b not in g.qubits or (c in g.qubits):
            if is_ccx:
                return False
            if g.cond is not None:
                return False
            if g.name in ("z", "cz", "ccz"):
                continue
            if g.name in ("cx", "ccx") and g.qubits[-1] != c:
                continue
            return False
    return True


def find_matches(c):
    if not dv.is_ir_circuit(c):
        return []
    gates = c.gates
    groups = _members(gates)
    cancels, spans = [], []
    # identical-triple cancellations
    last = {}
    for i, g in enumerate(gates):
        if g.cond is not None or g.name not in ("ccz", "ccx"):
            continue
        key = (g.name, frozenset(g.qubits[:2]) | {g.qubits[2]}) if g.name == "ccz" else \
              ("ccx", frozenset(g.qubits[:2]), g.qubits[2])
        if key in last:
            j0 = last[key]
            done = False
            for tgt in sorted(g.qubits):
                if done:
                    break
                a, b = sorted(q for q in g.qubits if q != tgt)
                if g.name == "ccx" and tgt != g.qubits[2]:
                    continue
                if _cancel_ok(gates, j0, i, a, b, tgt, g.name == "ccx"):
                    cancels.append(("cancel", a, b, (j0, i)))
                    done = True
        last[key] = i
    # sharing spans
    for (a, b), mem in sorted(groups.items()):
        mem = sorted(set(mem))
        chain = []
        chains = []
        seen = set()
        for m in mem:
            if m[0] in seen:
                continue
            seen.add(m[0])
            if chain and not _legal_between(gates, chain[-1][0], m[0], a, b):
                chains.append(chain)
                chain = []
            chain.append(m)
        chains.append(chain)
        for ch in chains:
            if len(ch) >= 2:
                spans.append(("and", a, b, tuple(m[0] for m in ch)))
    spans.sort(key=lambda m: (-len(m[3]), m[3][-1] - m[3][0], m[3]))
    # leftover singletons get the plain 4-T lowering (the book rule's job in the card's totals), after every span
    singles = [("and", g.qubits[0], g.qubits[1], (i,)) for i, g in enumerate(gates)
               if g.cond is None and g.name in ("ccz", "ccx")]
    return cancels + spans + singles


def _free_ancilla(c, lo, hi):
    gates = c.gates
    for q in c.ancillas():
        idx = [k for k, g in enumerate(gates) if q in g.qubits]
        ands = [k for k in idx if gates[k].name in ("and_compute", "and_uncompute")]
        if not ands:
            continue
        if any(not ((gates[k].name in ("and_compute", "and_uncompute") and gates[k].qubits[2] == q)
                    or (gates[k].name == "cz" and gates[k].cond is None)) for k in idx):
            continue
        if any(lo <= k <= hi for k in idx):
            continue
        before = [k for k in ands if k < lo]
        after = [k for k in ands if k > hi]
        if before and gates[before[-1]].name != "and_uncompute":
            continue
        if after and gates[after[0]].name != "and_compute":
            continue
        return q
    return None


def apply_match(c, m):
    kind, a, b, idx = m
    if not dv.is_ir_circuit(c):
        return c
    gates = list(c.gates)
    lo, hi = idx[0], idx[-1]
    if hi >= len(gates):
        return c
    if kind == "cancel":
        mem = {k: ("drop",) for k in idx}
        body, fl = _sweep(gates, lo, hi, a, b, mem)
        new = gates[:lo] + body + [G("x", (q,)) for q in sorted(fl)] + gates[hi + 1:]
        return dv.ir_with_gates(c, new)
    t = _free_ancilla(c, lo, hi)
    nq = c.n_qubits
    if t is None:
        t = nq
        nq += 1
    mem = {k: ("and", t) for k in idx}
    body, fl = _sweep(gates, lo, hi, a, b, mem)
    new = (gates[:lo] + [G("and_compute", (a, b, t))] + body + [G("and_uncompute", (a, b, t))]
           + [G("x", (q,)) for q in sorted(fl)] + gates[hi + 1:])
    return dv.ir_with_gates(c, new, n_qubits=nq)


RULE = Rule(
    name="x_frame_normalized_and_sharing_span",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney 2018 (temporary logical AND); Jones 2013; Pauli-frame propagation through diagonal gates "
           "(Amy-Maslov-Mosca 2014; Nam et al. 2018)",
    idea="X on a control of a CCZ propagates as X_a CCZ(a,b,c) = CCZ CZ(b,c) X_a (Clifford corrections only). "
         "Deleting the x gates on a pair {a,b} inside a span of CCZ sharing that pair and carrying them as a frame "
         "makes a,b read-only, so one AND ancilla (4 T) serves every CCZ in the span (CZ(t,c_i), 0 T); two CCZ "
         "on an identical triple cancel outright after normalisation.",
    trigger=find_matches,
    apply=apply_match,
)
