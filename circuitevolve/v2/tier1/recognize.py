"""Tier 1, part 1: deterministic subroutine recognition on a LOGICAL circuit.

    load_logical(path_or_text) -> (original ir.Circuit, normalized LogicalCircuit)
    normalize(ir_circuit)      -> LogicalCircuit   (h . ccz . h on the same target fused to ccx)
    summarize(lc, declared_zero=(), name="") -> Summary   (Summary.text() is what the LLM reads)

Everything here is a deterministic heuristic that only DESCRIBES the circuit; it never decides correctness. Every
compilation built from a summary is checked against the logical circuit by `circuitevolve.v2.verify`.

Elements (ids the compilation plan refers to)
--------------------------------------------
T<k>   the k-th Toffoli-type gate (ccx or ccz) of the normalized circuit, in gate order.
P<k>   a Toffoli PAIR (Ti, Tj), i < j: same kind, same controls, same target, no gate between them changes a control
       (the second gate undoes the first). Each Toffoli is in at most one pair (nearest partner). Pair classes:
         'clean'          target is a declared zero-init qubit, |0> just before Ti on every sampled input, and not
                          written between Ti and Tj -> Gidney temporary AND directly on the target;
         'mirror'         target is not written between Ti and Tj (only read, e.g. as a control) -> candidate for a
                          relative-phase Toffoli pair (Maslov), exact;
         'controls_fixed' target IS written in between (e.g. Cuccaro MAJ/UMA) -> temporary AND on a FRESH ancilla
                          (and_compute into the ancilla, cx(ancilla, target) at both ends), relaxed.
M<k>   a multi-controlled-X cascade: an unpaired Toffoli whose controls are targets of pairs enclosing it
       (recursively): X^{AND(leaf controls)} on its target, the pairs' targets being work qubits.

Qubit roles: 'declared_zero' comes from the benchmark manifest (the circuit's documented contract); 'first_touch' and
'restored' are measured here: restored = the qubit is |0> at the end on every sampled input in which all declared
zero-init qubits start in |0> (classical bit simulation; only for classical circuits over x/cx/ccx/swap + diagonal
gates; exhaustive when 2^(free qubits) <= samples).
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ...ir import Circuit as IRCircuit

TOFFOLI = ("ccx", "ccz")
DIAGONAL = {"z", "s", "sdg", "t", "tdg", "cz", "ccz"}
CLASSICAL = {"x", "cx", "ccx", "swap"} | DIAGONAL


@dataclass
class LGate:
    name: str
    qubits: tuple

    def writes(self) -> tuple:
        """Qubits whose computational-basis value this gate can change."""
        if self.name in DIAGONAL:
            return ()
        if self.name in ("cx", "ccx"):
            return (self.qubits[-1],)
        return tuple(self.qubits)        # x, h, swap, ...

    def controls(self) -> tuple:
        if self.name in ("cx", "ccx"):
            return tuple(self.qubits[:-1])
        if self.name in ("cz", "ccz"):
            return tuple(self.qubits)
        return ()

    def text(self) -> str:
        if self.name in ("cx", "ccx", "cz", "ccz"):
            return f"{self.name} " + " ".join(f"q{q}" for q in self.qubits[:-1]) + f" -> q{self.qubits[-1]}"
        return f"{self.name} " + " ".join(f"q{q}" for q in self.qubits)


@dataclass
class LogicalCircuit:
    n: int
    gates: list                       # [LGate]
    name: str = ""

    def to_ir(self) -> IRCircuit:
        c = IRCircuit(self.n)
        for g in self.gates:
            if g.name == "swap":
                a, b = g.qubits
                c.add("cx", a, b).add("cx", b, a).add("cx", a, b)
            else:
                c.add(g.name, *g.qubits)
        return c

    @property
    def classical(self) -> bool:
        return all(g.name in CLASSICAL for g in self.gates)

    def digest(self) -> str:
        s = ";".join(f"{g.name}:{','.join(map(str, g.qubits))}" for g in self.gates)
        return hashlib.sha256(f"{self.n}|{s}".encode()).hexdigest()[:16]


# ============================================================================================ loading
def _strip_gate_defs(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.strip().startswith("gate "))


def load_logical(src, name: str = ""):
    """QASM path or text -> (original ir.Circuit, normalized LogicalCircuit). Literal parsing only (no eval)."""
    from ..verify import parse_qasm_ir
    s = str(src)
    is_text = s.lstrip().startswith("OPENQASM")
    text = s if is_text else Path(s).read_text()
    orig = parse_qasm_ir(_strip_gate_defs(text))
    lc = normalize(orig, name=name or ("" if is_text else Path(s).stem))
    return orig, lc


def normalize(c: IRCircuit, name: str = "") -> LogicalCircuit:
    """Fuse `h t ; ccz(..t..) ... ; h t` into ccx gates targeting t when, between the two h, the only gates on t are
    ccz. Local rewrite of H_t CCZ(a,b,t) H_t = CCX(a,b->t); the runner verifies the result against the original."""
    gates = [LGate(g.name, tuple(g.qubits)) for g in c.gates]
    drop = set()
    for i, g in enumerate(gates):
        if i in drop or g.name != "h":
            continue
        t = g.qubits[0]
        j, inner, close = i + 1, [], None
        while j < len(gates):
            gj = gates[j]
            if j in drop or t not in gj.qubits:
                j += 1
                continue
            if gj.name == "h":
                close = j if inner else None
                break
            if gj.name == "ccz":
                inner.append(j)
                j += 1
                continue
            break
        if close is not None:
            for k in inner:
                a, b = [q for q in gates[k].qubits if q != t]
                gates[k] = LGate("ccx", (a, b, t))
            drop.update((i, close))
    return LogicalCircuit(c.n_qubits, [g for i, g in enumerate(gates) if i not in drop], name)


# ============================================================================================ analysis
def _bit_trace(lc: LogicalCircuit, zero: set, k: int = 1024, seed: int = 0):
    """Classical bit simulation on k sampled inputs (exhaustive if 2^free <= k) with `zero` qubits fixed to 0.
    Returns (before, final): before[i] = bool array (inputs, n) just before gate i. None if not classical."""
    if not lc.classical:
        return None
    n = lc.n
    free = [q for q in range(n) if q not in zero]
    rng = np.random.default_rng(seed)
    if (1 << len(free)) <= k:
        idx = np.arange(1 << len(free))
        X = np.zeros((len(idx), n), dtype=bool)
        for b, q in enumerate(free):
            X[:, q] = (idx >> b) & 1
    else:
        X = np.zeros((k, n), dtype=bool)
        X[:, free] = rng.integers(0, 2, size=(k, len(free))).astype(bool)
        X[0, free] = False
        X[1, free] = True
    before = []
    for g in lc.gates:
        before.append(X.copy())
        q = g.qubits
        if g.name == "x":
            X[:, q[0]] ^= True
        elif g.name == "cx":
            X[:, q[1]] ^= X[:, q[0]]
        elif g.name == "ccx":
            X[:, q[2]] ^= X[:, q[0]] & X[:, q[1]]
        elif g.name == "swap":
            X[:, [q[0], q[1]]] = X[:, [q[1], q[0]]]
    return before, X


@dataclass
class Summary:
    name: str
    n: int
    n_gates: int
    gate_counts: dict
    classical: bool
    toffolis: list            # [{id, gate, kind, controls, target}]
    pairs: list               # [{id, first, second, gates, target, controls, cls, ...}]
    unpaired: list            # [T ids]
    mcx: list                 # [{id, middle, pairs, controls, target, work, work_clean}]
    qubits: list              # [{q, declared_zero, first_touch, restored, role}]
    repeated: list            # [{pattern, count, at, k}]
    rotations: dict
    declared_zero: tuple
    digest: str
    hints: list = field(default_factory=list)

    def element(self, eid: str) -> dict | None:
        for coll in (self.toffolis, self.pairs, self.mcx):
            for e in coll:
                if e["id"] == eid:
                    return e
        return None

    def toffoli(self, tid: str) -> dict:
        return next(t for t in self.toffolis if t["id"] == tid)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("name", "n", "n_gates", "gate_counts", "classical", "toffolis",
                                               "pairs", "unpaired", "mcx", "qubits", "repeated", "rotations",
                                               "declared_zero", "digest", "hints")}

    def text(self, lc: LogicalCircuit | None = None, max_gates: int = 120) -> str:
        """Compact summary for the LLM prompt."""
        L = [f"CIRCUIT {self.name}: {self.n} qubits, {self.n_gates} gates "
             f"({', '.join(f'{k}:{v}' for k, v in sorted(self.gate_counts.items()))}); "
             f"{'classical reversible (x/cx/ccx + diagonal)' if self.classical else 'not purely classical'}."]
        L.append(f"Naive cost: {7 * len(self.toffolis)} T (7 per Toffoli, {len(self.toffolis)} Toffolis).")
        dz = list(self.declared_zero)
        L.append(f"Declared zero-init qubits (benchmark contract, start in |0>): "
                 f"{['q%d' % q for q in dz] if dz else 'none'}.")
        L.append("QUBITS (q: Z=declared zero-init / first touch / R=restored to |0> at end / guessed role):")
        L.append("  " + "; ".join(f"q{r['q']}:{'Z' if r['declared_zero'] else '-'}/{r['first_touch']}/"
                                  f"{'R' if r['restored'] else ('notR' if r['restored'] is False else '-')}/"
                                  f"{r['role']}" for r in self.qubits))
        L.append("TOFFOLIS (id: gate index, kind, controls -> target):")
        L.append("  " + "; ".join(f"{t['id']}:g{t['gate']} {t['kind']} q{t['controls'][0]} q{t['controls'][1]}"
                                  f"->q{t['target']}" for t in self.toffolis))
        if self.pairs:
            L.append("PAIRS (same Toffoli repeated, controls unchanged in between; class: clean = declared-zero "
                     "target, |0> before, not written between; mirror = target only read between; controls_fixed "
                     "= target written between):")
            for p in self.pairs:
                L.append(f"  {p['id']} = {p['first']}+{p['second']} (g{p['gates'][0]}..g{p['gates'][1]}) target "
                         f"q{p['target']} controls q{p['controls'][0]} q{p['controls'][1]}: {p['cls']}")
        L.append(f"UNPAIRED TOFFOLIS: {', '.join(self.unpaired) if self.unpaired else 'none'}")
        if self.mcx:
            L.append("MULTI-CONTROLLED-X CASCADES (middle Toffoli + enclosing pairs):")
            for m in self.mcx:
                L.append(f"  {m['id']}: C{len(m['controls'])}X controls {['q%d' % q for q in m['controls']]} -> "
                         f"q{m['target']}, middle {m['middle']}, pairs {m['pairs']}, work qubits "
                         f"{['q%d' % q for q in m['work']]} ({'clean' if m['work_clean'] else 'dirty/borrowed'})")
        if self.repeated:
            L.append("REPEATED BLOCKS (gate pattern with relabelled qubits, count):")
            for r in self.repeated[:4]:
                L.append(f"  [{r['pattern']}] x{r['count']} at gates {r['at'][:8]}")
        L.append(f"ROTATIONS (non-Toffoli phase gates): {self.rotations}")
        if self.hints:
            L.append("SUBROUTINE GUESSES: " + "; ".join(self.hints))
        if lc is not None and len(lc.gates) <= max_gates:
            L.append("NORMALIZED LOGICAL GATES (g<index>):")
            L.append("  " + "; ".join(f"g{i} {g.text()}" for i, g in enumerate(lc.gates)))
        return "\n".join(L)


def _repeated_blocks(lc: LogicalCircuit, kmin: int = 3, kmax: int = 8) -> list:
    """Repeated gate windows (containing a Toffoli) up to qubit relabelling; non-overlapping greedy count."""
    out = []
    G = lc.gates
    for k in range(kmax, kmin - 1, -1):
        sig_at: dict = {}
        for i in range(len(G) - k + 1):
            if not any(G[j].name in TOFFOLI for j in range(i, i + k)):
                continue
            m, parts = {}, []
            for g in G[i:i + k]:
                parts.append(g.name + "(" + ",".join(str(m.setdefault(q, len(m))) for q in g.qubits) + ")")
            sig_at.setdefault(" ".join(parts), []).append(i)
        for sig, at in sig_at.items():
            sel, last = [], -10 ** 9
            for i in at:
                if i >= last + k:
                    sel.append(i)
                    last = i
            if len(sel) >= 2 and not any(sig in r["pattern"] for r in out):
                out.append(dict(pattern=sig, count=len(sel), at=sel, k=k))
    out.sort(key=lambda r: (-r["count"] * r["k"], -r["k"]))
    return out[:6]


def summarize(lc: LogicalCircuit, declared_zero=(), name: str = "", samples: int = 1024, seed: int = 0) -> Summary:
    n, G = lc.n, lc.gates
    dz = tuple(sorted(set(int(q) for q in declared_zero)))
    tr = _bit_trace(lc, set(dz), k=samples, seed=seed)
    # ---------------------------------------------------------------- Toffolis
    tofs = []
    for i, g in enumerate(G):
        if g.name in TOFFOLI:
            tofs.append(dict(id=f"T{len(tofs)}", gate=i, kind=g.name, controls=tuple(g.qubits[:2]),
                             target=g.qubits[2]))
    # ---------------------------------------------------------------- pairs (nearest partner, controls unchanged)
    in_pair, pairs = set(), []
    for a_idx, ta in enumerate(tofs):
        if ta["id"] in in_pair:
            continue
        ctrl, tgt = set(ta["controls"]), ta["target"]
        for tb in tofs[a_idx + 1:]:
            i, j = ta["gate"], tb["gate"]
            between = G[i + 1:j]
            if any(set(g.writes()) & ctrl for g in between):
                break                          # a control changed: no later Toffoli undoes Ti
            if ta["kind"] == "ccz":
                same = tb["kind"] == "ccz" and set(G[j].qubits) == set(G[i].qubits)
            else:
                same = tb["kind"] == "ccx" and set(tb["controls"]) == ctrl and tb["target"] == tgt
            if not same:
                continue
            if tb["id"] in in_pair:
                break
            t_written = any(tgt in g.writes() for g in between)
            cb = ca = None
            if tr is not None:
                cb = bool(not tr[0][i][:, tgt].any())
                after = tr[0][j + 1] if j + 1 < len(G) else tr[1]
                ca = bool(not after[:, tgt].any())
            if not t_written and cb and tgt in dz:
                cls = "clean"
            elif not t_written:
                cls = "mirror"
            else:
                cls = "controls_fixed"
            pairs.append(dict(id=f"P{len(pairs)}", first=ta["id"], second=tb["id"], gates=(i, j), kind=ta["kind"],
                              target=tgt, controls=ta["controls"], cls=cls, target_written_between=t_written,
                              target_clean_before=cb, target_clean_after=ca, target_declared_zero=tgt in dz))
            in_pair.update((ta["id"], tb["id"]))
            break
    unpaired = [t["id"] for t in tofs if t["id"] not in in_pair]
    # ---------------------------------------------------------------- multi-controlled-X cascades
    tof_by_id = {t["id"]: t for t in tofs}
    mcx = []
    for tid in unpaired:
        t = tof_by_id[tid]
        if t["kind"] != "ccx":
            continue
        used_pairs, work, leaves = [], [], []

        def expand(ctrls, pos):
            for q in ctrls:
                enc = [p for p in pairs if p["target"] == q and p["gates"][0] < pos < p["gates"][1]
                       and p["kind"] == "ccx" and p["id"] not in used_pairs]
                if enc:
                    p = max(enc, key=lambda p: p["gates"][0])       # innermost enclosing pair
                    used_pairs.append(p["id"])
                    work.append(q)
                    expand(p["controls"], p["gates"][0])
                else:
                    leaves.append(q)
        expand(t["controls"], t["gate"])
        if used_pairs:
            wc = all(next(p for p in pairs if p["id"] == pid)["cls"] == "clean" for pid in used_pairs)
            mcx.append(dict(id=f"M{len(mcx)}", middle=tid, pairs=used_pairs, controls=sorted(set(leaves)),
                            target=t["target"], work=work, work_clean=wc))
    # ---------------------------------------------------------------- qubit roles
    qinfo = []
    final = tr[1] if tr is not None else None
    for q in range(n):
        ft = "untouched"
        for g in G:
            if q in g.qubits:
                if g.name in ("cx", "ccx") and g.qubits[-1] == q:
                    ft = f"{g.name}-target"
                elif q in g.controls():
                    ft = f"{g.name}-control"
                else:
                    ft = g.name
                break
        restored = None if final is None or q not in dz else bool(not final[:, q].any())
        role = ("ancilla(clean)" if restored else "output(starts |0>)") if q in dz else "data"
        qinfo.append(dict(q=q, declared_zero=q in dz, first_touch=ft, restored=restored, role=role))
    # ---------------------------------------------------------------- rotations / hints
    cnt = Counter(g.name for g in G)
    rot = dict(t_like=sum(cnt.get(k, 0) for k in ("t", "tdg")), s_like=sum(cnt.get(k, 0) for k in ("s", "sdg")),
               z=cnt.get("z", 0))
    rep = _repeated_blocks(lc)
    hints = []
    n_cf = sum(p["cls"] == "controls_fixed" for p in pairs)
    if n_cf >= 2:
        hints.append(f"ripple-carry-like: {n_cf} Toffoli pairs whose target is modified in between "
                     "(MAJ/UMA-style compute ... uncompute)")
    for m in mcx:
        hints.append(f"{m['id']} is a C{len(m['controls'])}X built from an AND ladder on "
                     f"{'clean' if m['work_clean'] else 'borrowed (dirty)'} work qubits")
    tz = [t for t in tofs if t["target"] in dz and t["id"] in unpaired]
    if tz:
        hints.append(f"{len(tz)} unpaired Toffolis write into declared zero-init qubits "
                     "(accumulation into an output register, multiplier-like)")
    return Summary(name=name or lc.name, n=n, n_gates=len(G), gate_counts=dict(cnt), classical=lc.classical,
                   toffolis=tofs, pairs=pairs, unpaired=unpaired, mcx=mcx, qubits=qinfo, repeated=rep,
                   rotations=rot, declared_zero=dz, digest=lc.digest(), hints=hints)


def first_toffoli_on_clean(lc: LogicalCircuit, s: Summary) -> dict:
    """{T id: bool} - target is a declared zero-init qubit and |0> just before this Toffoli on every sampled input
    (where a 4-T compute-only AND, route 'clean_and', can replace it)."""
    tr = _bit_trace(lc, set(s.declared_zero))
    out = {}
    for t in s.toffolis:
        ok = t["kind"] == "ccx" and t["target"] in s.declared_zero and tr is not None
        out[t["id"]] = bool(ok and not tr[0][t["gate"]][:, t["target"]].any())
    return out
