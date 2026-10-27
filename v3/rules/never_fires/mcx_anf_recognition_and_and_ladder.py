"""Recognize a whole-circuit multi-controlled X (via exact GF(2) ANF) and rebuild it as a Gidney AND ladder."""
from v3.api import Rule
from v3.api import dv

_ALLOWED = {"ccz", "ccx", "cx", "x", "h"}
_MAX_WIRE = 512
_MAX_TOTAL = 4096
_MAX_PAIRS = 4096
_ONE = frozenset()


def _prefilter(c):
    if not dv.is_ir_circuit(c):
        return False
    n_tof = 0
    for g in c.gates:
        if g.name not in _ALLOWED or g.cond is not None:
            return False
        if g.name in ("ccz", "ccx"):
            n_tof += 1
    return n_tof >= 4


def _normalize(c):
    """-> list of (name, qubits) over ccx/cx/x only, or None."""
    gates = c.gates
    target = {}                 # gate index -> target qubit for a ccz leg
    drop = set()
    state = {}                  # qubit -> ('h', i) | ('g', i, j)
    for idx, g in enumerate(gates):
        if g.name == "h":
            q = g.qubits[0]
            st = state.get(q)
            if st is None:
                state[q] = ("h", idx)
            elif st[0] == "g":
                drop.add(st[1])
                drop.add(idx)
                del state[q]
            else:
                return None
            continue
        for q in g.qubits:
            st = state.get(q)
            if st is None:
                continue
            if g.name != "ccz" or idx in target:
                return None
            target[idx] = q
            state[q] = ("g", st[1])
        if g.name == "ccz" and idx not in target:
            return None
    if state:
        return None
    out = []
    for idx, g in enumerate(gates):
        if idx in drop:
            continue
        if g.name == "ccz":
            t = target[idx]
            out.append(("ccx", tuple(q for q in g.qubits if q != t) + (t,)))
        else:
            out.append((g.name, tuple(g.qubits)))
    return out


def _anf(n, net):
    f = [{frozenset((i,))} for i in range(n)]
    total = n
    for name, qs in net:
        if name == "x":
            a = qs[0]
            total -= len(f[a])
            f[a] = f[a] ^ {_ONE}
            total += len(f[a])
        elif name == "cx":
            a, b = qs
            total -= len(f[b])
            f[b] = f[b] ^ f[a]
            total += len(f[b])
        else:
            a, b, t = qs
            if len(f[a]) * len(f[b]) > _MAX_PAIRS:
                return None
            prod = set()
            for u in f[a]:
                for v in f[b]:
                    prod ^= {u | v}
            total -= len(f[t])
            f[t] = f[t] ^ prod
            total += len(f[t])
        if len(f[qs[-1]]) > _MAX_WIRE or total > _MAX_TOTAL:
            return None
    return f


def find_matches(c):
    if not _prefilter(c):
        return []
    net = _normalize(c)
    if net is None:
        return []
    n = c.n_qubits
    f = _anf(n, net)
    if f is None:
        return []
    bad = [q for q in range(n) if f[q] != {frozenset((q,))}]
    if len(bad) != 1:
        return []
    t = bad[0]
    diff = f[t] ^ {frozenset((t,))}
    if len(diff) != 1:
        return []
    (mono,) = diff
    if len(mono) < 4 or t in mono:
        return []
    return [(t, tuple(sorted(mono)))]


def apply_match(c, m):
    t, S = m
    k = len(S)
    n = c.n_qubits
    need = k - 1
    free = [q for q in range(n) if q != t and q not in S]
    extra = max(0, need - len(free))
    anc = free[:need] + list(range(n, n + extra))
    IG = dv.IRGate
    gates = []
    ctrl = [S[0]] + anc[:-1]
    for i in range(need):
        gates.append(IG("and_compute", (ctrl[i], S[i + 1], anc[i])))
    gates.append(IG("cx", (anc[-1], t)))
    for i in reversed(range(need)):
        gates.append(IG("and_uncompute", (ctrl[i], S[i + 1], anc[i])))
    return dv.ir_with_gates(c, gates, n_qubits=n + extra)


RULE = Rule(
    name="mcx_anf_recognition_and_and_ladder",
    domain="dv",
    kind="reconstruction",
    contract="relaxed",
    source="Gidney 2018 (arXiv:1709.06648) temporary AND; Barenco et al. 1995 Lemma 7.2; Jones 2013; Maslov 2016",
    idea="Exact GF(2) ANF with a hard monomial budget certifies that a whole Toffoli-level circuit is "
         "t ^= AND(S) with all other wires restored; rebuild it as a clean-ancilla temporary-AND ladder "
         "(4 T per AND, measurement-based 0-T uncompute). Cheap linear prefilter declines non-reversible circuits.",
    trigger=find_matches,
    apply=apply_match,
)
