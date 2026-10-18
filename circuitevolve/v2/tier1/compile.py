"""Tier 1, part 3: execute a compilation plan deterministically, then verify against the LOGICAL circuit.

    compile_plan(lc, summary, plan) -> Compiled      (raises plan.PlanError on structurally invalid plans)
    evaluate(lc, summary, plan, original=None) -> dict   compile + verify + metric (never raises on bad plans)

Gadgets reuse the frozen IR: Gidney temporary AND = ir `and_compute` (4 T, needs a |0> target) / `and_uncompute`
(H, measure, classically controlled CZ + X; needs target = a.b); the frozen simulator checks both preconditions.
RCCX (Maslov relative-phase Toffoli) = qiskit's rccx definition over {h, t, tdg, cx}.

Verification (circuitevolve.v2.verify): mode 'exact' if the compiled circuit has no measurement, no extra qubit and
needs no zero-init promise; otherwise 'relaxed' with zero_qubits = the declared zero-init qubits the plan's routes
rely on (direct temporary_and / clean_and targets). The reference is the normalized logical circuit (ccx form), which
the runner checks against the original QASM once per circuit.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from ...ir import Circuit as IRCircuit, Gate
from .plan import Decision, Plan, PlanError
from .recognize import LogicalCircuit, Summary

# qiskit RCCXGate definition (controls a, b; target c): 4 T, 3 CX; Toffoli up to a diagonal; self-inverse.
RCCX = [("h", 2), ("t", 2), ("cx", 1, 2), ("tdg", 2), ("cx", 0, 2), ("t", 2), ("cx", 1, 2), ("tdg", 2), ("h", 2)]
PRIMS = {"x", "z", "h", "s", "sdg", "t", "tdg", "cx", "cz"}
# verification limits used by evaluate(): exhaustive branches up to 2^17 (inputs x branches), 240 s per check
DEFAULT_LIMITS = dict(branch_budget=1 << 17, time_limit_s=240.0)


@dataclass
class Compiled:
    circuit: IRCircuit                 # routed + global-passed candidate (data qubits 0..n-1, ancillas n..)
    routed: IRCircuit                  # before the global pass (gadget level)
    zero_qubits: tuple                 # declared zero-init qubits the routes rely on
    mode: str                          # 'exact' | 'relaxed'
    routes: dict                       # T id -> route label
    n_data: int
    ancillas: int
    measurements: int
    global_pass: str
    pass_log: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def digest(self) -> str:
        s = "|".join(f"{g.name}:{g.qubits}:{g.cbit}:{g.cond}" for g in self.circuit.gates)
        return hashlib.sha256(f"{self.circuit.n_qubits}/{self.zero_qubits}/{s}".encode()).hexdigest()[:16]


class _Pool:
    def __init__(self, n):
        self.n, self.free, self.top = n, [], n

    def alloc(self) -> int:
        if self.free:
            self.free.sort()
            return self.free.pop(0)
        q = self.top
        self.top += 1
        return q

    def release(self, q):
        self.free.append(q)


# ============================================================================================ plan -> actions
def _resolve(summary: Summary, plan: Plan) -> tuple[dict, list]:
    """gate index -> (role, decision, info). Raises PlanError on unknown/overlapping elements."""
    tof = {t["id"]: t for t in summary.toffolis}
    pairs = {p["id"]: p for p in summary.pairs}
    mcx = {m["id"]: m for m in summary.mcx}
    acts, warn = {}, []

    def claim(t, role, dec, info=None):
        if t["gate"] in acts:
            raise PlanError(f"{t['id']} is named by two decisions ({acts[t['gate']][1].element} and {dec.element})")
        acts[t["gate"]] = (role, dec, info or {})

    def pair_of(el):
        if el in pairs:
            p = pairs[el]
            return tof[p["first"]], tof[p["second"]], p
        a, b = el.split("+")
        if a not in tof or b not in tof:
            raise PlanError(f"unknown Toffoli in {el}")
        ta, tb = sorted((tof[a], tof[b]), key=lambda t: t["gate"])
        if ta["kind"] != tb["kind"] or ta["target"] != tb["target"] or set(ta["controls"]) != set(tb["controls"]):
            raise PlanError(f"{el}: not a matching pair (kind/controls/target differ)")
        return ta, tb, None

    def apply_pair(dec, ta, tb, route, via=False):
        info = dict(partner=None, via=via, key=f"{ta['id']}+{tb['id']}")
        claim(ta, f"{route}:first", dec, info)
        claim(tb, f"{route}:second", dec, info)

    for dec in plan.decisions:
        el, r = dec.element, dec.route
        if el.startswith("M"):
            if el not in mcx:
                raise PlanError(f"unknown element {el}")
            m = mcx[el]
            for pid in m["pairs"]:
                ta, tb, p = pair_of(pid)
                if r == "ancilla_mcx":
                    apply_pair(dec, ta, tb, "temporary_and", via=(p["cls"] != "clean"))
                else:
                    apply_pair(dec, ta, tb, "relative_phase_toffoli")
            mid = tof[m["middle"]]
            if r == "ancilla_mcx" and dec.middle == "jones":
                claim(mid, "jones_toffoli", dec)
            else:
                claim(mid, "toffoli_7T", dec)
            continue
        if el.startswith("P") or "+" in el:
            if el.startswith("P") and el not in pairs:
                raise PlanError(f"unknown element {el}")
            ta, tb, p = pair_of(el)
            if r == "custom":
                apply_pair(dec, ta, tb, "custom")
            elif r == "relative_phase_toffoli":
                if ta["kind"] != "ccx":
                    raise PlanError(f"{el}: relative_phase_toffoli applies to ccx pairs only")
                apply_pair(dec, ta, tb, r)
            elif r == "temporary_and":
                if ta["kind"] != "ccx" and not dec.via_ancilla:
                    raise PlanError(f"{el}: direct temporary_and needs a ccx pair (use via_ancilla for ccz)")
                apply_pair(dec, ta, tb, r, via=dec.via_ancilla)
            else:
                raise PlanError(f"route {r} does not apply to pair {el}")
            continue
        if el not in tof:
            raise PlanError(f"unknown element {el}")
        t = tof[el]
        if r in ("clean_and",) and t["kind"] != "ccx":
            raise PlanError(f"{el}: clean_and applies to ccx only")
        if r in ("relative_phase_toffoli", "temporary_and"):
            raise PlanError(f"{el}: {r} needs a pair element (P<k> or Ti+Tj); a lone Toffoli has no cancelling "
                            "partner")
        claim(t, r, dec)
    return acts, warn


# ============================================================================================ emission
def _emit_dsl(out: IRCircuit, gates, qmap: dict, cmap: dict, pool: _Pool, local_anc: dict):
    for g in gates:
        qs = []
        for kind, i in g.qubits:
            if kind == "q":
                if not 0 <= i < qmap["n"]:
                    raise PlanError(f"custom gate uses q{i}, circuit has {qmap['n']} qubits")
                qs.append(i)
            else:
                if i not in local_anc:
                    local_anc[i] = pool.alloc()
                qs.append(local_anc[i])
        if g.name == "measure":
            cmap[g.cbit] = out.measure(qs[0])
            continue
        cond = None
        if g.cond is not None:
            if g.cond not in cmap:
                raise PlanError(f"if(c{g.cond}) before c{g.cond} was measured")
            cond = cmap[g.cond]
        out.gates.append(Gate(g.name, tuple(qs), None, cond))


def compile_plan(lc: LogicalCircuit, summary: Summary, plan: Plan, pass_cache: dict | None = None) -> Compiled:
    acts, warn = _resolve(summary, plan)
    n = lc.n
    out = IRCircuit(n)
    pool = _Pool(n)
    live: dict = {}            # pair key -> ancilla / local maps
    zero, routes = set(), {}
    tof_by_gate = {t["gate"]: t for t in summary.toffolis}
    for gi, g in enumerate(lc.gates):
        if gi not in acts:
            if g.name == "swap":
                a, b = g.qubits
                out.add("cx", a, b).add("cx", b, a).add("cx", a, b)
            else:
                out.add(g.name, *g.qubits)
            if gi in tof_by_gate:
                routes[tof_by_gate[gi]["id"]] = "toffoli_7T"
            continue
        role, dec, info = acts[gi]
        t = tof_by_gate[gi]
        a, b = t["controls"]
        tq = t["target"]
        kind = t["kind"]
        routes[t["id"]] = role.split(":")[0] + ("(via_ancilla)" if info.get("via") else "")
        if role == "toffoli_7T":
            out.add(kind, a, b, tq)
        elif role == "jones_toffoli":
            anc = pool.alloc()
            out.add("and_compute", a, b, anc)
            out.add("cx" if kind == "ccx" else "cz", anc, tq)
            out.add("and_uncompute", a, b, anc)
            pool.release(anc)
        elif role == "clean_and":
            out.add("and_compute", a, b, tq)
            if tq in summary.declared_zero:
                zero.add(tq)
        elif role.startswith("relative_phase_toffoli"):
            for name, *loc in RCCX:
                out.add(name, *[(a, b, tq)[i] for i in loc])
        elif role.startswith("temporary_and"):
            first = role.endswith(":first")
            if info.get("via"):
                if first:
                    anc = pool.alloc()
                    live[info["key"]] = anc
                    out.add("and_compute", a, b, anc)
                    out.add("cx" if kind == "ccx" else "cz", anc, tq)
                else:
                    anc = live.pop(info["key"])
                    out.add("cx" if kind == "ccx" else "cz", anc, tq)
                    out.add("and_uncompute", a, b, anc)
                    pool.release(anc)
            else:
                if first:
                    out.add("and_compute", a, b, tq)
                    if tq in summary.declared_zero:
                        zero.add(tq)
                else:
                    out.add("and_uncompute", a, b, tq)
        elif role == "custom":
            local = {}
            _emit_dsl(out, dec.gates, {"n": n}, {}, pool, local)
            for q in local.values():
                pool.release(q)
        elif role.startswith("custom"):
            key = info["key"]
            if role.endswith(":first"):
                st = live.setdefault(key, {"anc": {}, "c": {}})
                _emit_dsl(out, dec.first, {"n": n}, st["c"], pool, st["anc"])
            else:
                st = live.pop(key, {"anc": {}, "c": {}})
                _emit_dsl(out, dec.second, {"n": n}, st["c"], pool, st["anc"])
                for q in st["anc"].values():
                    pool.release(q)
        else:
            raise PlanError(f"internal: unknown role {role}")
    out.n_qubits = max(pool.top, n)
    out.registers = {}
    routed = out
    final, plog = global_pass(routed, plan.global_pass, pass_cache)
    from ...sim import n_measurements
    M = n_measurements(final)
    gad = any(g.name in ("and_compute", "and_uncompute") or g.cond is not None for g in final.gates)
    mode = "relaxed" if (M or final.n_qubits > n or zero or gad) else "exact"
    return Compiled(final, routed, tuple(sorted(zero)), mode, routes, n, final.n_qubits - n, M, plan.global_pass,
                    plog, warn)


# ============================================================================================ global passes
def _segments(c: IRCircuit):
    """Split a primitive-level circuit into maximal runs of unconditioned unitary gates (separated by measure /
    classically controlled gates)."""
    segs, cur = [], []
    for g in c.gates:
        if g.name == "measure" or g.cond is not None:
            if cur:
                segs.append(("seg", cur))
                cur = []
            segs.append(("fixed", [g]))
        else:
            cur.append(g)
    if cur:
        segs.append(("seg", cur))
    return segs


def _t(gates) -> int:
    return sum(g.name in ("t", "tdg") for g in gates)


def _run_pass(name: str, gates, n: int, cache: dict | None):
    ops = [(g.name, tuple(g.qubits), None) for g in gates]
    key = (name, n, tuple(ops))
    if cache is not None and key in cache:
        return cache[key]
    from ..verify import NotExact, ops_to_ir
    res = None
    try:
        if name == "pyzx":
            from ...blocks.classical import pyzx_optimise
            new = pyzx_optimise(ops, n)
        elif name == "tket":
            from experiments.v2_bench_common import tket_arm
            new = tket_arm(ops, n)["ops"]
        else:
            raise ValueError(name)
        res = list(ops_to_ir(new, n).gates)
    except NotExact:
        res = None                 # e.g. TKET left a non-pi/4 rotation: segment kept as is
    except Exception as e:         # pass crashed: keep segment, log
        res = ("error", f"{type(e).__name__}: {e}")
    if cache is not None:
        cache[key] = res
    return res


def global_pass(routed: IRCircuit, name: str, cache: dict | None = None):
    if name == "none":
        return routed, []
    seq = ["pyzx", "tket"] if name == "pyzx_then_tket" else [name]
    c = routed.expand("clifford_t")
    log = []
    for pname in seq:
        new_gates = []
        for kind, gs in _segments(c):
            if kind == "fixed" or not any(g.name in ("t", "tdg") for g in gs):
                new_gates += gs
                continue
            r = _run_pass(pname, gs, c.n_qubits, cache)
            if isinstance(r, tuple):
                log.append(dict(pass_=pname, seg_T=_t(gs), result=r[1][:200]))
                new_gates += gs
            elif r is None:
                log.append(dict(pass_=pname, seg_T=_t(gs), result="non-exact output (kept segment)"))
                new_gates += gs
            elif _t(r) < _t(gs) or (_t(r) == _t(gs) and len(r) < len(gs)):
                log.append(dict(pass_=pname, seg_T=_t(gs), new_T=_t(r)))
                new_gates += r
            else:
                new_gates += gs
        c = IRCircuit(c.n_qubits, c.n_cbits, new_gates, {})
    return c, log


# ============================================================================================ evaluate
def reference_for(lc: LogicalCircuit, zero_qubits=()):
    from ..verify import ReferenceSpec
    return ReferenceSpec.from_circuit(lc.to_ir(), zero_qubits=tuple(zero_qubits), name=lc.name, registers={})


def evaluate(lc: LogicalCircuit, summary: Summary, plan_or_text, pass_cache: dict | None = None,
             verify_cache: dict | None = None, limits=None) -> dict:
    """Parse (if text) + compile + verify + measure. Returns a flat record; ok=False with a reason on any failure."""
    from ..metric import measure
    from ..verify import Limits, verify
    from .plan import parse_plan
    t0 = time.time()
    rec = dict(ok=False, stage="parse", reason="", mode=None, certified=False)
    try:
        plan = plan_or_text if isinstance(plan_or_text, Plan) else parse_plan(plan_or_text)
    except PlanError as e:
        rec["reason"] = f"plan rejected: {e}"
        return rec
    rec["plan"] = plan.to_dict()
    rec["stage"] = "compile"
    try:
        comp = compile_plan(lc, summary, plan, pass_cache)
    except PlanError as e:
        rec["reason"] = f"plan rejected: {e}"
        return rec
    rec.update(stage="verify", mode=comp.mode, zero_qubits=list(comp.zero_qubits), routes=comp.routes,
               global_pass=comp.global_pass, pass_log=comp.pass_log[:20], digest=comp.digest())
    key = comp.digest()
    if verify_cache is not None and key in verify_cache:
        v = verify_cache[key]
    else:
        ref = reference_for(lc, comp.zero_qubits)
        v = verify(comp.circuit, ref, comp.mode, data_map=list(range(lc.n)),
                   limits=limits or Limits(**DEFAULT_LIMITS)).to_dict()
        v.pop("details", None)
        if verify_cache is not None:
            verify_cache[key] = v
    m = measure(comp.circuit, data_qubits=lc.n)
    rec.update(ok=bool(v["ok"]), verdict_mode=v["mode"], certified=bool(v["certified"]), method=v["method"],
               reason=v["reason"], unitary_preserving=bool(v["unitary_preserving"]),
               t_count=m["t_count"], t_depth=m["t_depth"], qubits=m["qubits"], ancillas=m["ancillas"],
               measurements=m["measurements"], cx=m["cx"], gates=m["gates"], seconds=round(time.time() - t0, 2))
    rec["_compiled"] = comp
    return rec
