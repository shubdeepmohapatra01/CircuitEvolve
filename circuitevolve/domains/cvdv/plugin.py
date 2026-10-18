"""CV-DV rule-evolution family: the cvdv certified compiler behind the engine loop (PLAN_P1 P1.3).

Wraps cvdv/src/cvdv/{evolve,compiler,certify,library,metrics,terms,target} UNCHANGED (the stack is
frozen via cvdv/FROZEN.sha256 and this module only imports it; see the package __init__ for the
sys.path shim). The evolve.py campaign semantics map onto the engine contract as:

    state      the rule library, represented as its SOURCE TEXT (exactly the object evolve.py
               reads from rulebook/rules.py, loads with library.load and appends accepted rules to)
    task       one term kind to attack, ranked by its share of the certified compile's duration
               on a fixed workload (a benchmark's Trotter terms, or synthetic terms in tests)
    candidate  one rule-function source string in the restricted DSL; parsing is regex-only
               (evolve.extract_code); the static check + restricted exec happen in materialize()
               through the FROZEN library.load path, exactly as evolve.run_campaign does — no new
               execution path for LLM text is introduced
    verify     the frozen per-instance certificate (certify.certify at n_max, ancilla back to
               vacuum), reached through Compiler.evaluate/best_r — called, never reimplemented;
               charge = sum of certified eps over the kind's instances, clamped to 0 for exact
               rules (eps <= compiler.EXACT_TOL)
    measure    compile the workload with Compiler.compile_step and score with the existing
               lexicographic metric (valid, duration, two_op, one_op) = metrics.key; improvement
               is strict lexicographic and never lets the primary (duration) worsen
    ledger     circuitevolve.core.ledger.Ledger unchanged; exact rules charge 0

Documented deviations where the existing code contradicts the plan mapping (followed the code):
  * the existing lexicographic metric (cvdv/src/cvdv/metrics.py key(), evolve.score_rule) is
    (valid, duration, 2-op, 1-op) — it has NO ancilla component, so none is added here.
  * global_check / final_check: the engine passes bound = d_input + ledger spend, but every cvdv
    compile re-certifies all parts from scratch, so the sound whole-problem statement is the
    compiler's own one: bound_valid AND eps_bound <= eps_total. The engine bound is ignored
    (it would double-count); the certified eps_bound is reported as `dist` against eps_total.
  * input_check returns 0.0: the start compile's certified bound is already budgeted by the
    compiler (eps_total) and is NOT an input distance in the DV sense — charging it to the
    ledger's window pool would both double-count and overflow the pool (eps_bound ~ eps_total
    when approximate rules are in play). The start compile is still required to certify
    (valid == 0) or input_check raises.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from cvdv import evolve as EV
from cvdv import isa as ISA
from cvdv import library as L
from cvdv import metrics as M
from cvdv import target as TG
from cvdv.compiler import EXACT_TOL, Compiler, part_hamiltonian
from cvdv.terms import classify, hamiltonian_of

from ...engine.plugin import DomainPlugin, Member

CVDV_ROOT = Path(__file__).resolve().parents[3] / "cvdv"

COST_KEYS = ("valid", "duration", "two_op", "one_op", "total", "eps_bound")

KIND_DOCS = {
    "n": "H = theta n on one qumode.",
    "n2": "H = theta n^2 on one qumode.",
    "hop": "H = theta (e^{i phi} a\u2020b + h.c.) on two qumodes.",
    "z_n": "H = theta Z n (one qubit, one qumode).",
    "pauli_n": "H = theta P n, P a Pauli string.",
    "z_hop": "H = theta Z (e^{i phi} a\u2020b + h.c.).",
    "pauli_hop": "H = theta P (e^{i phi} a\u2020b + h.c.).",
    "pauli": "H = theta P, P a Pauli string.",
    "disp": "H with exp(-iH) = D(alpha) on one qumode.",
    "pauli_disp": "H with exp(-iH) = exp(P (alpha a\u2020 - alpha* a)).",
}

_DEF_NAME = re.compile(r"^def (rule_\w+__\w+)\s*\(", re.M)


def _digest(src: str) -> str:
    return hashlib.sha1(src.encode()).hexdigest()[:16]


@dataclass
class KindTask:
    """Engine task: one term kind on the workload (key/order/index are engine-visible)."""
    kind: str
    share: int                 # this kind's certified-duration share in the parent's compile
    instances: list            # [(TermClass part, Poly H)] — the kind's instances in the workload
    src: str                   # parent library source (prompt context + rename policy)
    existing: set              # rule function names already defined in src
    index: int                 # stable kind index (recorded in ledger charges)
    key: str = field(init=False)

    def __post_init__(self):
        # content key: the kind becomes "fresh" again once its rules changed (round-robin by content)
        self.key = hashlib.sha1(
            (self.kind + "\n" + EV.kind_source(self.src, self.kind)).encode()).hexdigest()[:12]

    @property
    def order(self):
        return self.share


class CvdvRulesPlugin(DomainPlugin):
    name = "cvdv_rules"
    actions = ("rule",)
    primary = "duration"

    def __init__(self, terms, start_src: str, *, eps_total: float = 1e-3, n_max: int = 3,
                 r_max: int = 4096, isa=None, meta: dict | None = None):
        self.terms = list(terms)
        self._start_src = start_src
        self.eps_total = float(eps_total)
        self.n_max, self.r_max = int(n_max), int(r_max)
        self.isa = ISA.PS_BS if isa is None else isa
        ws = {w for t in self.terms for w in t.wires}
        self.n_sys_q = max([w[1] + 1 for w in ws if w[0] == "q"], default=0)
        self.n_sys_m = max([w[1] + 1 for w in ws if w[0] == "qm"], default=0)
        self.n = self.n_sys_q
        self.meta = dict(name="cvdv", source="cvdv")
        self.meta.update(meta or {})
        self.meta.update(n_terms=len(self.terms), eps_total=self.eps_total, n_max=self.n_max,
                         n_sys_q=self.n_sys_q, n_sys_m=self.n_sys_m, r_max=self.r_max)
        # the kind's certification instances: the distinct classified parts of the workload
        self._instances: dict[str, list] = {}
        for t in self.terms:
            for part in classify(hamiltonian_of(t)):
                lst = self._instances.setdefault(part.kind, [])
                if all(repr(part) != repr(p) for p, _ in lst):
                    lst.append((part, part_hamiltonian(part)))
        self._kinds = sorted(self._instances)
        self._certs: dict = {}      # frozen-certificate cache, shared by every Compiler below
        self._mcache: dict = {}     # state digest -> measure() dict
        self._scorer = self._compiler({})

    # ------------------------------------------------------------------ cvdv plumbing
    def _compiler(self, rules) -> Compiler:
        comp = Compiler(rules, n_max=self.n_max, n_sys_q=self.n_sys_q, n_sys_m=self.n_sys_m,
                        r_max=self.r_max, isa=self.isa)
        comp.cache = self._certs
        return comp

    def measure(self, src: str) -> dict:
        """The measure path: certified compile of the workload with the library `src`.

        -> dict(ops, report, parts_metrics, kind_share, cost); cached by library digest. Every
        part is (re-)certified by the frozen certificate inside Compiler.compile_step.
        """
        key = _digest(src)
        out = self._mcache.get(key)
        if out is None:
            out = self._mcache[key] = self._measure(src)
        return out

    def _measure(self, src: str) -> dict:
        try:
            ops, rep = self._compiler(L.load(src)).compile_step(self.terms, eps_total=self.eps_total)
        except Exception as e:  # noqa: BLE001 - a non-compiling candidate state is a metric reject
            inf = math.inf
            return dict(ops=None, report=None, parts_metrics=None, kind_share={},
                        error=f"{type(e).__name__}: {e}"[:300],
                        cost=dict(valid=1, duration=inf, two_op=inf, one_op=inf, total=inf,
                                  eps_bound=inf))
        m = M.metrics(ops)
        valid = 0 if (rep["bound_valid"] and rep["eps_bound"] <= self.eps_total) else 1
        parts_metrics, share, i0 = [], {}, 0
        for p in rep["parts"]:
            seg = ops[i0:i0 + p["n_ops"]]
            i0 += p["n_ops"]
            sm = M.metrics(seg)
            parts_metrics.append(dict(kind=p["kind"], rule=p["rule"], r=p["r"], **sm))
            share[p["kind"]] = share.get(p["kind"], 0) + sm["duration"]
        cost = dict(valid=valid, duration=m["duration"], two_op=m["two_op"], one_op=m["one_op"],
                    total=m["total"], eps_bound=rep["eps_bound"])
        return dict(ops=ops, report=rep, parts_metrics=parts_metrics, kind_share=share, cost=cost)

    # ------------------------------------------------------------------ state
    def start_state(self):
        return self._start_src

    def flat_state(self, m: Member):
        return m.state

    def digest(self, state) -> str:
        return _digest(state)

    # ------------------------------------------------------------------ select
    def select_tasks(self, m: Member, k: int, rng) -> list:
        share = self.measure(m.state)["kind_share"]
        scored = sorted(((share.get(kind, 0), kind) for kind in self._kinds),
                        key=lambda s: (-s[0], s[1]))
        tasks = [self._task(m.state, kind, s) for s, kind in scored]
        fresh = [t for t in tasks if t.key not in m.tried]
        if not fresh:                        # round-robin: start over on this member
            m.tried.clear()
            fresh = tasks
        return fresh[:k]

    def _task(self, src: str, kind: str, share: int) -> KindTask:
        return KindTask(kind=kind, share=share, instances=self._instances[kind], src=src,
                        existing=set(_DEF_NAME.findall(src)), index=self._kinds.index(kind))

    # ------------------------------------------------------------------ mutate
    def _score(self, fn, part, H, budget: float) -> dict:
        """evolve.score_rule semantics with the plugin's wire bases and the shared cert cache."""
        comp = self._scorer
        ev1 = comp.evaluate(part, H, fn, 1)
        if ev1 is None:
            try:
                comp.emit(part, fn, 1)
                why = "rejected (ISA/wire/unreliable certificate)"
            except Exception as e:  # noqa: BLE001 - feedback to the mutator
                why = f"{type(e).__name__}: {e}"[:200]
            return {"feasible": False, "why": why}
        out = {"eps_r1": ev1[1]["eps"], "cost_r1": ev1[2]}
        ev4 = comp.evaluate(part, H, fn, 4)
        if ev4 is not None:
            out["eps_r4"] = ev4[1]["eps"]
        res = comp.best_r(part, H, fn, budget)
        if res is None:
            out.update(feasible=False, why=f"no r <= {self.r_max} reaches eps {budget:g}")
        else:
            out.update(feasible=True, r=res[0], eps=res[1][1]["eps"], cost=res[1][2])
        return out

    def _best_table(self, task: KindTask, budget: float) -> list:
        rules = L.load(task.src).get(task.kind, [])
        table = []
        for part, H in task.instances:
            best, who, per = EV.INF, None, {}
            for name, fn in rules:
                s = self._score(fn, part, H, budget)
                per[name] = s
                if s.get("feasible") and tuple(s["cost"]) < best:
                    best, who = tuple(s["cost"]), name
            table.append({"theta": float(complex(part.params[0]).real), "n_max": self.n_max,
                          "best": best, "who": who, "per": per})
        return table

    def build_prompt(self, task: KindTask, rules, feedback, allowance) -> str:
        table = self._best_table(task, allowance)
        doc = KIND_DOCS.get(task.kind, f"term kind {task.kind}")
        playbook = "\n".join(rules) if rules else "(empty)"
        prompt = EV.build_prompt(task.kind, doc, EV.kind_source(task.src, task.kind), table,
                                 history=[], playbook=playbook, eps_share=allowance, k_idx=0)
        if feedback:
            prompt += "\n\nRECENT FEEDBACK (this run):\n" + "\n".join(feedback)
        return prompt

    def parse(self, text: str):
        """Regex-only (evolve.extract_code); no exec/eval — that happens in materialize()."""
        if text.strip() in ("NONE", "DECLINE"):
            return [], [], True
        code = EV.extract_code(text)
        if not code:
            return [], ["no ```python code block"], False
        return [("rule", code)], [], False

    def materialize(self, task: KindTask, action: str, payload, call_id: int) -> dict:
        code = payload
        mname = re.search(r"def (rule_(\w+?)__(\w+))\s*\(", code)
        crec = dict(action="rule", code=code)
        if not mname:
            return dict(ok=False, cand=None, crec=crec, label="rule <unnamed>",
                        fail_stat="bad_name",
                        fail_reason="rejected: no rule_<kind>__<name> function found")
        fname, kind, short = mname.group(1), mname.group(2), mname.group(3)
        crec["name"] = fname
        if kind != task.kind:
            return dict(ok=False, cand=None, crec=crec, label=fname, fail_stat="wrong_kind",
                        fail_reason=f"rejected: rule kind {kind!r} != task kind {task.kind!r}")
        if fname in task.existing:            # same rename policy as evolve.run_campaign
            renamed = f"{fname}_c{call_id}"
            code = code.replace(fname, renamed, 1)
            crec["renamed"] = renamed
            fname, short = renamed, f"{short}_c{call_id}"
        try:
            # the EXISTING restricted-DSL path (frozen library.py): static check + restricted exec
            fn = dict(L.load(code)[task.kind])[short]
        except Exception as e:  # noqa: BLE001 - static-check feedback to the mutator
            crec["error"] = str(e)[:300]
            return dict(ok=False, cand=None, crec=crec, label=fname,
                        fail_stat="static_check_failed",
                        fail_reason=f"rejected: static check ({e})"[:300])
        return dict(ok=True,
                    cand=dict(name=fname, short=short, kind=task.kind, code=code, fn=fn,
                              call=call_id),
                    crec=crec, label=fname)

    # ------------------------------------------------------------------ verify (FROZEN)
    def verify(self, task: KindTask, cand, allowance: float) -> dict:
        """Frozen certificate on every instance of the kind (certify at n_max, ancilla back to
        vacuum), via Compiler.evaluate/best_r. charge = sum of certified eps (0 for exact)."""
        feasible, why, charge, worst, exact = 0, [], 0.0, 0.0, True
        for part, H in task.instances:
            res = self._scorer.best_r(part, H, cand["fn"], allowance)
            if res is None:
                s = self._score(cand["fn"], part, H, allowance)
                why.append(f"{part!r}: {s.get('why', 'infeasible')}")
                continue
            eps = float(res[1][1]["eps"])
            feasible += 1
            worst = max(worst, eps)
            if eps > EXACT_TOL:
                exact = False
                charge += eps
        if feasible == 0:
            return dict(ok=False, mode="none", dist=math.inf, charge=math.inf,
                        reason=("; ".join(why)[:500] or "infeasible on every instance"))
        return dict(ok=True, mode="exact" if exact else "approx", dist=worst, charge=charge,
                    reason="")

    def global_check(self, state, bound: float):
        """Whole-problem statement: the recompile's certified eps_bound <= eps_total (the engine
        `bound` is ignored — see module docstring)."""
        c = self.measure(state)["cost"]
        ok = c["valid"] == 0
        return dict(ok=ok, verified=ok, method="frozen-certified-compile",
                    dist=float(c["eps_bound"]), bound=self.eps_total)

    def input_check(self, pool: float) -> float:
        c = self.measure(self._start_src)["cost"]
        if c["valid"] != 0:
            raise ValueError(f"start library does not certify within eps_total: {c}")
        return 0.0

    def frozen_digest(self) -> str:
        man = (CVDV_ROOT / "FROZEN.sha256").read_text()
        h = hashlib.sha256(man.encode())
        for line in man.strip().splitlines():
            rel = line.split("  ", 1)[1].strip()
            h.update(hashlib.sha256((CVDV_ROOT / rel).read_bytes()).digest())
        return h.hexdigest()

    # ------------------------------------------------------------------ apply / measure
    def apply(self, cur_state, task: KindTask, cand):
        code, name = cand["code"], cand["name"]
        if re.search(rf"^def {re.escape(name)}\s*\(", cur_state, re.M):
            # in-batch clash: an earlier accept this batch already defined the name
            renamed = f"{name}_b{cand['call']}"
            code = code.replace(name, renamed, 1)
        prov = f"# @provenance: engine-loop | call={cand['call']} | kind={task.kind}"
        return cur_state.rstrip() + f"\n\n\n{prov}\n" + code.rstrip() + "\n"

    def cost(self, state, ledger) -> dict:
        return dict(self.measure(state)["cost"])

    def cost_key(self, cost: dict) -> tuple:
        # the existing lexicographic order (cvdv metrics.key): valid, duration, 2-op, 1-op
        return (cost["valid"], cost["duration"], cost["two_op"], cost["one_op"])

    def improves(self, new: dict, old: dict) -> bool:
        return self.cost_key(new) < self.cost_key(old) and new["duration"] <= old["duration"]

    def cost_subset(self, cost: dict) -> dict:
        return {k: cost[k] for k in COST_KEYS}

    def cand_text(self, cand) -> str:
        return cand["code"] if isinstance(cand, dict) else repr(cand)

    # ------------------------------------------------------------------ reporting hooks
    def record_fields(self, task: KindTask) -> dict:
        # "kind" is taken by the log-record type ("propose"); the term kind gets its own key
        return dict(term_kind=task.kind, duration_share=task.share,
                    n_instances=len(task.instances))

    def reject_metric_text(self, old: dict, new: dict) -> str:
        return (f"rejected: no improvement (duration {old['duration']} -> {new['duration']}, "
                f"2-op {old['two_op']} -> {new['two_op']}, 1-op {old['one_op']} -> {new['one_op']})")

    def accept_record(self, old: dict, new: dict) -> dict:
        return dict(duration_before=old["duration"], duration_after=new["duration"],
                    two_op_before=old["two_op"], two_op_after=new["two_op"])

    def accept_feedback(self, label, v, old, new) -> str:
        return (f"ACCEPTED {label or 'rule'} ({v['mode']}, certified eps {v['dist']:.2e}): "
                f"duration {old['duration']} -> {new['duration']}, "
                f"2-op {old['two_op']} -> {new['two_op']}")

    def improvement_entry(self, task: KindTask, cand, label, old, new) -> tuple:
        return (old["duration"], new["duration"], task.kind, label or "")

    def stats_template(self) -> dict:
        return dict(bad_name=0, wrong_kind=0, static_check_failed=0)

    def ledger_summary(self, ledger, cost: dict) -> dict:
        return ledger.summary(0)

    def archive_entry(self, m: Member) -> dict:
        return dict(duration=m.cost["duration"], two_op=m.cost["two_op"], one_op=m.cost["one_op"],
                    eps_bound=m.cost["eps_bound"], spent=m.ledger.spent, digest=m.digest)

    def final_check(self, m: Member):
        c = self.measure(m.state)["cost"]
        ok = c["valid"] == 0
        return dict(ok=ok, verified=ok, method="frozen-certified-compile",
                    dist=float(c["eps_bound"]), bound=self.eps_total)

    def output_files(self, m: Member) -> dict:
        mm = self.measure(m.state)
        rep = json.dumps(mm["report"], indent=1, default=str) if mm["report"] else "{}"
        return {"_rules.py": m.state, "_compile.json": rep}


# ---------------------------------------------------------------------- factory
def read_benchmark_terms(name: str):
    """The benchmark's Trotter terms, resolved like cvdv/experiments/common.intermediate()."""
    for root in ("results/genesis_seeded_s0", "results/genesis_baseline"):
        p = CVDV_ROOT / root / name / f"intermediate_{name}.cvdvqasm"
        if p.exists():
            return TG.read_intermediate(str(p)), str(p)
    raise FileNotFoundError(f"no intermediate file for benchmark {name!r} under {CVDV_ROOT}/results")


def benchmark_plugin(name: str, *, eps_total: float = 1e-3, n_max: int = 3, r_max: int = 4096,
                     isa=None, rules_path=None) -> CvdvRulesPlugin:
    """Plugin over one Genesis benchmark with the current rulebook (default) as start library."""
    terms, src_path = read_benchmark_terms(name)
    rules_src = Path(rules_path or CVDV_ROOT / "rulebook" / "rules.py").read_text()
    return CvdvRulesPlugin(terms, rules_src, eps_total=eps_total, n_max=n_max, r_max=r_max,
                           isa=isa, meta=dict(name=name, source=src_path))
