"""Structure lifting (PLAN_P3 P3.4): recover Toffolis from decomposed Clifford+T circuits.

Deterministic core, no LLM. Matches the standard 7-T Toffoli network and the Maslov
relative-phase Toffoli (RCCX) over {h,s,sdg,x,z,t,tdg,cx,cz}, tolerant of commuting-gate
interleaving: candidate spans are PER-QUBIT PROJECTED subsequences on a 3-qubit support
(ops on other qubits pass through untouched; an op straddling the support boundary ends the
candidate window), and the minimal matching op span is taken. EVERY claimed span is verified
EXACTLY before substitution — its 8 basis columns are computed in the D[omega] ring (the
frozen sparse simulator, circuitevolve/sim.py) and compared to the CCX / RCCX reference
columns up to one GLOBAL unit phase omega^j (global phase is unobservable; the phase is
recorded per claim). Anything that does not match exactly is dropped — a false structure is
worse than a missed one.

Wiring (engine/router.py): pre-recognition fires only when the input has toffolis == 0 AND
t+tdg >= 7 (never on inputs that already carry structure). ccx claims are substituted; RCCX
claims are REPORTED but not substituted by default (a lone relative-phase Toffoli is not a
ccx, and the downstream exact-IR pipeline has no rccx gate; substitute_rccx=True opts in,
e.g. for analysis).

The LLM spotter (candidate span proposals from a model, each still exactly verified here) is
budget-gated and NOT implemented: llm_spot_candidates is the call-site stub behind
lift_llm=False, raising NotImplementedError.
"""
from __future__ import annotations

from pathlib import Path

from ..ir import Circuit as IRCircuit
from ..ring import D, ONE
from ..sim import run

LIFT_GATES = frozenset({"h", "s", "sdg", "x", "z", "t", "tdg", "cx", "cz"})
_UNITS = [D.omega_pow(j) for j in range(8)]
_WINDOW_CAP = 30            # max projected ops per candidate span
_T_CAP = 11                 # max t/tdg inside a span (7-T network + slack)


def _cols(ops3) -> list[dict]:
    c = IRCircuit(3)
    for g, qs in ops3:
        c.add(g, *qs)
    return [run(c, i)[()] for i in range(8)]


def _ccx_ref(target: int) -> list[dict]:
    cs = [q for q in range(3) if q != target]
    return [{i ^ ((1 << target) if (i >> cs[0]) & 1 and (i >> cs[1]) & 1 else 0): ONE}
            for i in range(8)]


def _rccx_ref(target: int) -> list[dict]:
    a, b = [q for q in range(3) if q != target]
    t = target
    tpl = [("h", (t,)), ("t", (t,)), ("cx", (b, t)), ("tdg", (t,)), ("cx", (a, t)),
           ("t", (t,)), ("cx", (b, t)), ("tdg", (t,)), ("h", (t,))]
    return _cols(tpl)


_CCX_REFS = {t: _ccx_ref(t) for t in range(3)}
_RCCX_REFS = {t: _rccx_ref(t) for t in range(3)}


def _match(states: list[dict]) -> tuple[str, int, int] | None:
    """states[i] = span columns. -> (kind, local_target, phase_j) on an exact match."""
    for refs, kind in ((_CCX_REFS, "ccx"), (_RCCX_REFS, "rccx")):
        for t, ref in refs.items():
            amp0 = states[0].get(0)
            if amp0 is None or len(states[0]) != 1:
                break                                   # column 0 is {0: unit} for both kinds
            for j, u in enumerate(_UNITS):
                if amp0 != u * ref[0][0]:
                    continue
                if all(len(states[i]) == len(ref[i]) and
                       all(states[i].get(k) == u * v for k, v in ref[i].items())
                       for i in range(8)):
                    return kind, t, j
                break                                   # phase fixed by column 0: one try
    return None


class _Apply:
    """Incremental 8-column exact simulation of a projected span (local 3-qubit ops)."""

    def __init__(self):
        self.states = [{i: ONE} for i in range(8)]

    def add(self, g: str, qs: tuple):
        from ..ir import Gate
        from ..sim import _apply
        gate = Gate(g, qs, None, None)
        self.states = [_apply(s, gate) for s in self.states]


def lift_toffolis(ops: list, n: int, substitute_rccx: bool = False) -> tuple[list, dict]:
    """-> (lifted ops, report). Claims are exactly verified, non-overlapping, scanned
    left-to-right; unverified candidates are dropped silently (counted in the report)."""
    claimed: set[int] = set()                           # op indices consumed by substitutions
    claims: list[dict] = []                             # every verified claim (incl. reported-only)
    i = 0
    while i < len(ops):
        if ops[i][0] != "h" or i in claimed:
            i += 1
            continue
        claim = _try_anchor(ops, i, claimed)
        if claim is None:
            i += 1
            continue
        claim["substituted"] = claim["kind"] == "ccx" or substitute_rccx
        claims.append(claim)
        if not claim["substituted"]:                    # rccx reported only (default)
            i += 1
            continue
        claimed.update(claim["indices"])
        i += 1          # resume at the NEXT op, not past the span end: ops interleaved inside
        # a macro span (e.g. inner recursions on other qubits) may anchor their own claims
    out = []
    starts = {c["indices"][0]: c for c in claims if c["substituted"]}
    for idx, op in enumerate(ops):
        c = starts.get(idx)
        if c is not None:
            out.append((c["kind"], c["qubits"], None))
        elif idx not in claimed:
            out.append(op)
    report = dict(
        ccx=sum(1 for c in claims if c["kind"] == "ccx"),
        rccx_spotted=sum(1 for c in claims if c["kind"] == "rccx"),
        rccx_substituted=sum(1 for c in claims if c["kind"] == "rccx" and c["substituted"]),
        phase_adjusted=sum(1 for c in claims if c["phase_j"] != 0 and c["substituted"]),
        t_absorbed=sum(c["t_in_span"] for c in claims if c["substituted"]),
        claims=[{k: c[k] for k in ("kind", "qubits", "span", "phase_j", "t_in_span",
                                   "substituted")} for c in claims],
    )
    return out, report


def _try_anchor(ops: list, i: int, claimed: set) -> dict | None:
    """Grow a 3-qubit support from the h at ops[i]; test every projected prefix exactly."""
    tq = ops[i][1][0]
    support = {tq}
    proj: list[int] = []
    sim = None
    pending: list[tuple] = []                           # local ops awaiting |support| == 3
    qmap: dict[int, int] = {}
    t_seen = 0
    bystanders: set[int] = set()                        # qubits of skipped ops inside the span:
    j = i                                               # the support may NEVER grow onto one —
    while j < len(ops) and len(proj) < _WINDOW_CAP and t_seen <= _T_CAP:
        g, qs, _a = ops[j]                              # a skipped op on q does not commute with
        if j in claimed or g not in LIFT_GATES:         # later span ops once q joins the support
            if set(qs) & support:
                return None
            bystanders.update(qs)
            j += 1
            continue
        inside = set(qs) & support
        if not inside:
            bystanders.update(qs)
            j += 1
            continue
        if len(inside) < len(qs):                       # op straddles / grows the support
            new = set(qs) - support
            if len(support) + len(new) > 3:
                return None                             # boundary crossing: window ends
            if new & bystanders:
                return None                             # stale bystander: substitution at the
            support.update(qs)                          # span start would reorder non-commuting ops
        proj.append(j)
        t_seen += g in ("t", "tdg")
        pending.append((g, qs))
        if len(support) == 3 and qmap == {}:
            qmap = {q: k for k, q in enumerate(sorted(support))}
        if qmap:
            if sim is None:
                sim = _Apply()
                for pg, pqs in pending:
                    sim.add(pg, tuple(qmap[q] for q in pqs))
                pending = []
            else:
                sim.add(g, tuple(qmap[q] for q in qs))
            m = _match(sim.states) if t_seen >= 4 else None
            if m is not None:
                kind, lt, phase_j = m
                inv = {v: k for k, v in qmap.items()}
                target = inv[lt]
                controls = tuple(sorted(q for q in support if q != target))
                return dict(kind=kind, qubits=(*controls, target),
                            indices=list(proj), span=(proj[0], proj[-1]),
                            phase_j=phase_j, t_in_span=t_seen)
        j += 1
    return None


# ---------------------------------------------------------------------- macro expansion
_QELIB_CCX = [("h", "c"), ("cx", "bc"), ("tdg", "c"), ("cx", "ac"), ("t", "c"), ("cx", "bc"),
              ("tdg", "c"), ("cx", "ac"), ("t", "b"), ("t", "c"), ("h", "c"), ("cx", "ab"),
              ("t", "a"), ("tdg", "b"), ("cx", "ab")]


def expand_toffolis(ops: list) -> list:
    """Macro-expand ccx/ccz with the standard qelib 7-T network (deterministic splice, no
    optimization) — the BASE lifting target: what a toolchain emits when it expands gate
    macros without re-optimizing globally."""
    out = []
    for g, qs, a in ops:
        if g in ("ccx", "ccz"):
            m = dict(zip("abc", qs))
            if g == "ccz":
                out.append(("h", (m["c"],), None))
            out += [(tg, tuple(m[x] for x in tqs), None) for tg, tqs in _QELIB_CCX]
            if g == "ccz":
                out.append(("h", (m["c"],), None))
        else:
            out.append((g, qs, a))
    return out


# ---------------------------------------------------------------------- routing front door
def pre_recognize(source, lift_llm: bool = False) -> tuple[str | None, dict]:
    """QASM path/text -> (lifted QASM text | None, report). Fires only on Toffoli-free
    Clifford+T input with >= 7 t/tdg; never raises on unparseable input (reports a skip)."""
    from .tketpass import _emit_qasm, read_qasm_ops
    s = str(source)
    try:
        text = s if s.lstrip().startswith("OPENQASM") else Path(s).read_text()
        n, ops = read_qasm_ops(text)
    except (OSError, ValueError) as e:
        return None, dict(skipped=f"unreadable for lifting ({e})")
    if any(g in ("ccx", "ccz") for g, _q, _a in ops):
        return None, dict(skipped="toffolis already present: lifting never fires")
    t_like = sum(1 for g, _q, _a in ops if g in ("t", "tdg"))
    if t_like < 7:
        return None, dict(skipped=f"only {t_like} t/tdg (< 7): no 7-T network can hide here")
    if any(g == "rz" for g, _q, _a in ops):
        return None, dict(skipped="general-angle rotations present: lifting is Clifford+T only")
    if lift_llm:
        llm_spot_candidates(ops, n, None)
    lifted, report = lift_toffolis(ops, n)
    if report["ccx"] == 0:
        return None, report
    return _emit_qasm(lifted, n), report


def llm_spot_candidates(ops: list, n: int, complete):
    """LLM lifting spotter (budget-gated, PLAN_P3 P3.4): proposes candidate spans that the
    EXACT matcher above must still verify one by one. Interface defined; execution requires
    explicit user approval of LLM budget — not implemented in P3."""
    raise NotImplementedError(
        "LLM lifting spotter is budget-gated and lands outside P3.4's deterministic core; "
        "run with lift_llm=False (candidate proposals would still face the exact verifier)")
