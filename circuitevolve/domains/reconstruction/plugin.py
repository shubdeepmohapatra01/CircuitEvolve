"""Reconstruction method plugin (PLAN_P3 P3.3): v2/tier1 behind the DomainPlugin contract.

Wraps circuitevolve/v2/tier1 UNCHANGED — recognize (elements), plan (literal parser, toolbox),
compile (compile_plan), and the FROZEN v2 relaxed verifier (v2/verify.py, same frozen digest as
the DV stack; check_integrity is called, never reimplemented). Mapping onto the engine contract:

    state      the current best verified compilation: {plan, rec, compiled}; start = the input
               LogicalCircuit with NO plan (its naive Clifford+T cost via the frozen cost path)
    task       ONE whole-circuit planning problem: the recognizer element menu (T/P/M ids)
               ranked by naive-T share — reconstruction decides per element, so a single task
               carries the full menu (key = parent digest: a new best re-opens it)
    candidate  one compilation plan (JSON, parsed by v2.tier1.plan.parse_plan — literal, no
               exec/eval); the deterministic control route (v2/tier1/control.py) is the no-LLM
               arm: its plans fed through the SAME path as scripted completions
    verify     v2.compile.evaluate -> frozen v2 relaxed verifier; charge 0 (exact-relaxed
               constructions are exact branch-wise — v2 conventions; ledger untouched)
    measure    (t_count, qubits, t_depth) in the RELAXED column (v2.metric.measure, frozen
               cost path); fitness lexicographic, never a blend

Contract notes (PLAN_P3 §1.5): results live in the relaxed column; verdict_mode is recorded
per accept so exact-mode plans remain distinguishable. global_check returns None because every
plan is verified WHOLE-CIRCUIT against the logical reference by the frozen verifier — there is
no incremental rewrite to re-check. cascade_payload() hands the angle stage the largest
measurement-free Clifford+T segment plus the fixed remainder (per-stage attribution stays
whole-circuit)."""
from __future__ import annotations

import json

from ...engine.plugin import DomainPlugin, Member
from ...v2.metric import measure
from ...v2.tier1.compile import evaluate
from ...v2.tier1.plan import PlanError, parse_plan
from ...v2.tier1.prompt import build_prompt as v2_prompt
from ...v2.tier1.prompt import select_cards

COST_KEYS = ("t_count", "qubits", "t_depth", "measurements")


class PlanTask:
    """The single whole-circuit planning task (engine-visible key/order/index)."""

    def __init__(self, parent_digest: str):
        self.key = parent_digest
        self.order = 0
        self.index = 0


class ReconstructionPlugin(DomainPlugin):
    name = "reconstruction"
    actions = ("plan",)
    primary = "t_count"

    def __init__(self, lc, summary, *, classical: str = "", meta: dict | None = None):
        from ...v2.verify import check_integrity
        check_integrity()                              # frozen verifier, checked at construction
        self.lc, self.s = lc, summary
        self.classical = classical
        self.n = lc.n
        self.meta = dict(name=summary.name or lc.name, source="reconstruction",
                         elements=dict(toffolis=len(summary.toffolis), pairs=len(summary.pairs),
                                       mcx=len(summary.mcx)),
                         declared_zero=list(summary.declared_zero))
        self.meta.update(meta or {})
        self._pass_cache: dict = {}
        self._verify_cache: dict = {}
        m0 = measure(lc.to_ir())
        self._m0 = {k: m0[k] for k in COST_KEYS}
        self._m0["mode"] = "input"

    # ------------------------------------------------------------------ state
    def start_state(self):
        return dict(plan=None, rec=None, compiled=None)

    def flat_state(self, m: Member):
        return dict(m.state)

    def digest(self, state) -> str:
        if state["compiled"] is None:
            return "input:" + self.lc.digest()
        return state["compiled"].digest()

    # ------------------------------------------------------------------ select / prompt
    def select_tasks(self, m: Member, k: int, rng) -> list:
        t = PlanTask(m.digest)
        if t.key in m.tried:                           # round-robin on the single task
            m.tried.clear()
        return [t]

    def build_prompt(self, task: PlanTask, rules, feedback, allowance) -> str:
        cards = select_cards(self.s)
        p = v2_prompt(self.s, self.lc, "relaxed", {}, [], cards, self.classical)
        if rules:
            p += "\n\nPLAYBOOK RULES (apply where relevant):\n" + "\n".join(f"- {r}" for r in rules)
        if feedback:
            p += "\n\nRECENT FEEDBACK (this run):\n" + "\n".join(str(f) for f in feedback)
        return p

    # ------------------------------------------------------------------ propose / verify
    def parse(self, text: str):
        t = (text or "").strip()
        if t in ("NONE", "DECLINE"):
            return [], [], True
        try:
            parse_plan(t)                              # literal syntax check (json + regex)
        except PlanError as e:
            return [], [f"plan rejected: {e}"], False
        return [("plan", t)], [], False

    def materialize(self, task: PlanTask, action: str, payload, call_id: int) -> dict:
        rec = evaluate(self.lc, self.s, payload, self._pass_cache, self._verify_cache)
        crec = dict(action="plan", plan=rec.get("plan"),
                    stage=rec.get("stage"), routes=rec.get("routes"))
        if rec.get("stage") in ("parse", "compile"):
            return dict(ok=False, cand=None, crec=crec, label="plan",
                        fail_stat="parse_errors" if rec["stage"] == "parse" else "rejected_verifier",
                        fail_reason=rec.get("reason", "rejected"))
        return dict(ok=True, cand=rec, crec=crec, label=self._label(rec))

    @staticmethod
    def _label(rec: dict) -> str:
        routes = rec.get("routes") or {}
        return "plan[" + ", ".join(f"{r}x{len(v)}" for r, v in sorted(routes.items())) + "]"

    def verify(self, task: PlanTask, cand: dict, allowance: float) -> dict:
        return dict(ok=bool(cand.get("ok")),
                    mode=("exact" if cand.get("verdict_mode") == "exact" else "relaxed"),
                    dist=0.0, charge=0.0,              # exact branch-wise: v2 conventions
                    reason=str(cand.get("reason", "")),
                    certified=bool(cand.get("certified")))

    def global_check(self, state, bound: float):
        return None                                    # every plan verified whole-circuit (frozen)

    def input_check(self, pool: float) -> float:
        return 0.0                                     # the logical input is exact

    # ------------------------------------------------------------------ apply / cost
    def apply(self, cur_state, task: PlanTask, cand: dict):
        return dict(plan=cand.get("plan"), compiled=cand["_compiled"],
                    rec={k: v for k, v in cand.items() if not k.startswith("_")})

    def cost(self, state, ledger) -> dict:
        if state["rec"] is None:
            return dict(self._m0)
        r = state["rec"]
        return dict(t_count=r["t_count"], qubits=r["qubits"], t_depth=r["t_depth"],
                    measurements=r["measurements"], mode=r["verdict_mode"])

    def cost_key(self, cost: dict) -> tuple:
        return (cost["t_count"], cost["qubits"], cost["t_depth"])   # lexicographic, never a blend

    def improves(self, new: dict, old: dict) -> bool:
        return self.cost_key(new) < self.cost_key(old)

    def cost_subset(self, cost: dict) -> dict:
        return {k: cost[k] for k in (*COST_KEYS, "mode") if k in cost}

    # ------------------------------------------------------------------ frozen digest
    def frozen_digest(self) -> str:
        from ...integrity import frozen_digest
        from ...v2.verify import check_integrity
        check_integrity()                              # v2 shares the DV frozen digest
        return frozen_digest()

    # ------------------------------------------------------------------ reporting
    def record_fields(self, task: PlanTask) -> dict:
        return dict(elements=self.meta["elements"])

    def cand_text(self, cand) -> str:
        return self._label(cand) if isinstance(cand, dict) else repr(cand)

    def accept_feedback(self, label, v, old, new) -> str:
        return (f"ACCEPTED {label} ({new.get('mode')}, "
                f"{'certified' if v.get('certified') else 'sampled'}): "
                f"T {old['t_count']} -> {new['t_count']}, qubits {old['qubits']} -> {new['qubits']}")

    def final_check(self, m: Member) -> dict | None:
        if m.state["rec"] is None:
            return dict(ok=True, mode="input", reason="no plan accepted: input returned unchanged")
        r = m.state["rec"]
        return dict(ok=bool(r["ok"]), mode=r["verdict_mode"], certified=bool(r["certified"]),
                    reason=str(r.get("reason", "")), unitary_preserving=bool(r["unitary_preserving"]))

    def ledger_summary(self, ledger, cost: dict) -> dict:
        s = ledger.summary(0)
        s["note"] = "reconstruction charges 0 (exact branch-wise constructions, v2 conventions)"
        return s

    def archive_entry(self, m: Member) -> dict:
        return dict(t_count=m.cost["t_count"], qubits=m.cost["qubits"],
                    mode=m.cost.get("mode"), digest=m.digest)

    def output_files(self, m: Member) -> dict:
        if m.state["plan"] is None:
            return {}
        return {"_plan.json": json.dumps(m.state["plan"], indent=1)}

    # ------------------------------------------------------------------ cascade handoff
    def cascade_payload(self, m: Member) -> dict | None:
        """Largest measurement-free Clifford+T segment for the angle stage + fixed remainder.
        None when no plan was accepted (the cascade threads the raw input onward)."""
        if m.state["compiled"] is None:
            return None
        c = m.state["compiled"].circuit.expand("clifford_t")
        segs, cur = [], []
        for g in c.gates:
            if g.name == "measure" or g.cond is not None:
                if cur:
                    segs.append(cur)
                    cur = []
            else:
                cur.append((g.name, tuple(g.qubits), None))
        if cur:
            segs.append(cur)
        if not segs:
            return None

        def t_of(seg):
            return sum(1 for g, _, _ in seg if g in ("t", "tdg"))

        best = max(range(len(segs)), key=lambda i: t_of(segs[i]))
        total_t = m.cost["t_count"]
        seg_t = t_of(segs[best])
        return dict(ops=list(segs[best]), n=c.n_qubits,
                    name=f"{self.meta['name']}+recon",
                    segment=best, segments=len(segs), segment_t=seg_t,
                    fixed_t=total_t - seg_t, total_t_before=total_t)
