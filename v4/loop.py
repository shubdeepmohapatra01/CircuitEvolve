"""The training loop - V4_README section 5.

    book = floor_tier()                      # pyzx-class + DPF-class, never retired
    while global_budget_remains():           # ONE global budget, not per-circuit quotas
      for A in CIRCUIT_ORDER:                # fixed, recorded as configuration
        cur_A, cost_A = optimize_memo(A, book, eps)        # keyed on (hash(book), A, eps)
        card = scout(residual=summary(cur_A), fingerprint[A], book_digest, baselines[A], log[A])
        if prefilter(card): continue                       # deterministic, zero compute
        for attempt in (1, 2, 3):
            rule = implementer(card, feedback)
            if precondition_excludes(rule, A): feedback = IDEA;  continue   # free
            if not rule.trigger(cur_A):        feedback = IDEA;  continue   # ~ms
            res = check_on_target(rule, A, cur_A, cost_A, ledger, OpcodeBudget)
            if res.verified and res.improves:
                book = admit(rule, book, res); break
            feedback = classify(res)        # fire-and-fail => NARROW THE GUARD, keep the idea
      retire(book)                          # no accepted application in 2 global loops

One global loop = one pass over `CIRCUIT_ORDER`. The playbook is a SINGLE MUTABLE OBJECT handed along
the chain: circuit A either updates it or leaves it, and B receives whatever it now is. A circuit's
second turn is where transfer happens - in loop 1 the first circuit only ever sees the floor.

What is different from v3, and why it is cheap (V4_README 5.1):

1. `optimize_memo` keyed on `(hash(book), circuit, eps)`: a (book-state, circuit) pair is verified ONCE,
   EVER. v3 re-ran the book on 5 circuits for each of 139 `test_rule` calls - about 23 h of its 53.9 h.
2. a candidate is applied to the CACHED RESIDUAL, so only its own applications are verified.
3. the full order-optimised re-run happens ONLY on admission (8 times in v3's P2, not 139), and the
   admission re-run keeps `min(book_order, gain_order, best_single_rule)` and REFUSES any admission that
   raises T on any circuit (5.2) - because the P2 six-rule book was 6 T worse on qft_8 than one of its
   own rules.

`LoopConfig` is written into the results directory before anything runs, because the round-robin result
depends on `CIRCUIT_ORDER` and that is configuration, not a finding.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import baselines as Ba, book as B, fingerprint as FP
from .api import Rule, describe
from .caps import DEFAULT_BUDGET
from .judge import dv as J
from .judge.frozen import check_frozen, recheck_frozen
from .ledger import Ledger
from .memo import optimize_memo, residual
from .paths import RESULTS
from .runner import dv_key, optimize
from .tools.evaluate import check_on_target

IDEA = "idea"
IMPL = "implementation"

# Fixed, and recorded as configuration. Ordered by where the fingerprint says the headroom is: the two
# circuits whose only remaining lever is (c) algebraic structure come first, because that is the lever no
# baseline owns and the one the project has already won on.
CIRCUIT_ORDER = ("tfim_6", "hhl_8", "qpe_8", "qae_13", "qft_8", "adder_8", "mult_4", "mcx_10",
                 "adder_6", "modred_21")


@dataclass
class LoopConfig:
    eps: float = 1e-3
    circuit_order: tuple = CIRCUIT_ORDER
    max_attempts_per_circuit: int = 3          # the `attempt in (1, 2, 3)` of section 5
    global_budget_attempts: int = 60           # ONE global budget, not per-circuit quotas
    global_budget_usd: float | None = None
    max_loops: int = 4
    retire_after_loops: int = 2
    opcode_budget: int = DEFAULT_BUDGET
    subprocess_limit_s: float = 1800.0         # LLM / candidate wall clock: infrastructure, not science
    order_on_admission: str = "min_all"        # section 5.2
    tag: str = "p7"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Outcome:
    """What one attempt produced, classified per V4_README 5.3."""
    kind: str                 # 'admitted' | 'excluded' | 'no_trigger' | 'fire_and_fail' | 'no_gain'
                              # | 'exception' | 'opcode' | 'prefiltered' | 'scout_failed'
    level: str | None         # IDEA | IMPL | None
    feedback: dict = field(default_factory=dict)
    report: dict = field(default_factory=dict)

    @property
    def admitted(self) -> bool:
        return self.kind == "admitted"


FEEDBACK = {
    "excluded": ("The rule's declared precondition excludes this circuit, so it was never run. That is "
                 "not a rejection - but the card described a circuit this is not. Propose an idea whose "
                 "precondition this circuit satisfies.", IDEA),
    "no_trigger": ("The trigger matched NOWHERE on this circuit. The precondition does not describe it: "
                   "the structure the idea needs is absent. Propose a different idea.", IDEA),
    "fire_and_fail": ("The trigger MATCHED but no application was kept. The idea may be right and the "
                      "GUARD is too broad: narrow it so it matches only where the rewrite is both valid "
                      "and an improvement. Keep the idea.", IMPL),
    "no_gain": ("The rule fires and verifies, but lowers no circuit's T-count beyond the current book. "
                "The idea does not pay here. Propose a different idea.", IDEA),
    "exception": ("The rule raised. Fix the implementation, not the idea.", IMPL),
    "opcode": ("The rule exhausted its opcode budget - it looped or scaled badly. Fix the "
               "implementation, not the idea.", IMPL),
}


def classify(rep: dict, target: str | None = None) -> Outcome:
    """Map an `evaluate` report onto V4_README 5.3's five outcomes.

    `target` is the circuit the card was written FOR, and it is what distinguishes the first two rows of
    5.3. A rule whose precondition excludes the target was never run there, which is not a rejection -
    but the card did describe a circuit this is not. A rule that was RUN on the target and matched
    nowhere is a different message: the structure the idea needs is absent."""
    dec, lvl = rep.get("decision"), rep.get("level")
    if dec == "admit":
        return Outcome("admitted", None, report=rep)
    reason = rep.get("reason") or ""
    if dec == "never_fires":
        excluded_here = target is not None and target in (rep.get("excluded") or {})
        kind = "excluded" if (excluded_here or not rep.get("triggers_on_input")) else "no_trigger"
    elif "opcode budget" in reason:
        kind = "opcode"
    elif "exception" in reason:
        kind = "exception"
    elif "the trigger matches but no application was kept" in reason:
        kind = "fire_and_fail"
    elif lvl == IMPL:
        kind = "exception"
    else:
        kind = "no_gain"
    text, level = FEEDBACK[kind]
    return Outcome(kind, level, feedback=dict(summary=text, harness_reason=reason,
                                              circuits=rep.get("circuits", [])[:4],
                                              excluded=rep.get("excluded"),
                                              triggers=rep.get("triggers_on_input")), report=rep)


# ------------------------------------------------------------------------------------------ admission
def admit(rule: Rule, bk: list, cfg: LoopConfig) -> tuple:
    """(new book, record). V4_README 5.2: the admission re-run keeps
    `min(book_order, gain_order, best_single_rule)` per circuit and REFUSES any admission that raises T
    on any circuit. The solo results are computed once inside `order='min_all'` and shared."""
    before = {}
    for lab in cfg.circuit_order:
        before[lab] = optimize_memo(lab, bk, cfg.eps, order=cfg.order_on_admission).cost
    cand = bk + [rule]
    after, worse = {}, []
    for lab in cfg.circuit_order:
        after[lab] = optimize_memo(lab, cand, cfg.eps, order=cfg.order_on_admission).cost
        if dv_key(after[lab]) > dv_key(before[lab]):
            worse.append(dict(label=lab, before=before[lab]["t_count"], after=after[lab]["t_count"]))
    rec = dict(rule=rule.name, tags=rule.tags(),
               before={k: v["t_count"] for k, v in before.items()},
               after={k: v["t_count"] for k, v in after.items()},
               helped=[dict(label=k, before=before[k]["t_count"], after=after[k]["t_count"])
                       for k in cfg.circuit_order if after[k]["t_count"] < before[k]["t_count"]],
               regressed=worse, order=cfg.order_on_admission)
    if worse:
        rec["refused"] = ("admission refused: it raises T on " +
                          ", ".join(f"{w['label']} {w['before']}->{w['after']}" for w in worse) +
                          ". A book must never score worse than it did without the rule (V4_README 5.2).")
        return bk, rec
    if not rec["helped"]:
        # `evaluate` measured the improvement on the book's cached RESIDUAL, in book order. The admission
        # re-run measures it under `min(book_order, gain_order, best_single_rule)`, and a rule can improve
        # the residual while improving none of those - it only helped an ordering the book would not
        # choose. That is not an improvement to the book, so it is refused.
        rec["refused"] = (f"admission refused: under order={cfg.order_on_admission} the rule lowers T on "
                          f"no circuit. It improved the cached residual (book order) but not the book's "
                          f"own best ordering, so the book is no better with it than without "
                          f"(V4_README 5.2).")
        return bk, rec
    return cand, rec


# ------------------------------------------------------------------------------------------ the loop
class Loop:
    """The loop, with the LLM calls behind two injectable callables so it can be driven by the agent, by
    a replay of recorded cards, or by a stub in tests.

        scout(ctx)            -> card dict (or None)
        implement(card, ctx)  -> Path to a candidate .py (or None)
    """

    def __init__(self, cfg: LoopConfig, scout, implement, out_dir: Path | None = None):
        self.cfg = cfg
        self.scout = scout
        self.implement = implement
        self.dir = Path(out_dir or (RESULTS / cfg.tag))
        self.dir.mkdir(parents=True, exist_ok=True)
        self.book = B.floor_tier()
        self.attempts_used = 0
        self.loop = 0
        self.history: dict = {lab: [] for lab in cfg.circuit_order}
        (self.dir / "config.json").write_text(json.dumps(cfg.to_dict(), default=str, indent=1) + "\n")

    # ---------------------------------------------------------------- bookkeeping
    def _append(self, name: str, row: dict) -> None:
        with open(self.dir / name, "a") as f:
            f.write(json.dumps(row, default=str) + "\n")

    def budget_remains(self) -> bool:
        return self.attempts_used < self.cfg.global_budget_attempts

    def context(self, label: str) -> dict:
        """What the scout is shown: the circuit AFTER the book, its fingerprint, the baselines, the book
        digest and this circuit's own history."""
        cur, cost, led = residual(label, self.book, self.cfg.eps)
        rep = FP.report(label, self.cfg.eps, self.book, circuit=cur, cost=cost)
        return dict(label=label, eps=self.cfg.eps, loop=self.loop,
                    book=[r.name for r in self.book], book_digest=B.digest(self.book),
                    current_t=cost["t_count"], current_qubits=cost["qubits"],
                    fingerprint=rep.to_dict(), baselines=Ba.baselines(label, self.cfg.eps),
                    best_baseline=rep.best_baseline, best_baseline_t=rep.best_baseline_t,
                    history=self.history[label], descriptor=describe(cur).__dict__,
                    ledger=led.report() if led else None, circuit=cur, cost=cost)

    # ---------------------------------------------------------------- one attempt
    def attempt(self, label: str, k: int) -> Outcome:
        ctx = self.context(label)
        t0 = time.time()
        card = self.scout(ctx)
        if not card:
            o = Outcome("scout_failed", IDEA, feedback=dict(summary="the scout produced no card"))
            self._record(label, k, None, o, t0, ctx)
            return o
        why = FP.prefilter(card, FP.LeverReport(**{kk: vv for kk, vv in ctx["fingerprint"].items()
                                                   if kk in FP.LeverReport.__dataclass_fields__}))
        if why:
            o = Outcome("prefiltered", IDEA, feedback=dict(summary=why), report=dict(card=card))
            self._record(label, k, card, o, t0, ctx)
            return o
        feedback = None
        for tries in range(1, self.cfg.max_attempts_per_circuit + 1):
            path = self.implement(card, dict(ctx, feedback=feedback, try_=tries))
            if path is None:
                o = Outcome("exception", IMPL, feedback=dict(summary="no candidate file was written"))
                self._record(label, k, card, o, t0, ctx, tries)
                return o
            rep = self._evaluate(Path(path), label)
            o = classify(rep, label)
            o.report["card"], o.report["try"] = card, tries
            if o.admitted:
                self.book, rec = admit(B.load_rule(Path(path), "accepted"), self.book, self.cfg)
                o.report["admission"] = rec
                if rec.get("refused"):
                    o = Outcome("no_gain", IDEA, feedback=dict(summary=rec["refused"]), report=o.report)
                else:
                    self._record(label, k, card, o, t0, ctx, tries)
                    return o
            self._record(label, k, card, o, t0, ctx, tries)
            if o.level == IDEA:
                return o                     # the idea is wrong: back to the scout, not the implementer
            feedback = o.feedback            # implementation-level: same card, narrow the guard
        return o

    def _evaluate(self, path: Path, label: str) -> dict:
        from .tools.evaluate import evaluate
        return evaluate(path, bk=self.book, eps=self.cfg.eps, target=label,
                        opcode_budget=self.cfg.opcode_budget)

    def _record(self, label, k, card, o: Outcome, t0, ctx, tries=0) -> None:
        self.attempts_used += 1
        row = dict(time=time.time(), seconds=round(time.time() - t0, 1), loop=self.loop, label=label,
                   attempt=k, implementer_tries=tries, kind=o.kind, level=o.level,
                   card=card, feedback=o.feedback,
                   book_after=[r.name for r in self.book], book_digest=B.digest(self.book),
                   current_t=ctx["current_t"], best_baseline_t=ctx["best_baseline_t"],
                   headroom=ctx["fingerprint"].get("headroom"),
                   admission=o.report.get("admission"), harness=o.report.get("reason"))
        self.history[label].append(dict(attempt=k, kind=o.kind, level=o.level, card=card,
                                        summary=o.feedback.get("summary"),
                                        estimate=(card or {}).get("expected_t_saving_on_target"),
                                        measured=o.report.get("admission", {}).get("helped")))
        self._append("attempts.jsonl", row)
        B.write_book_md(self.book)

    # ---------------------------------------------------------------- the global loop
    def run(self) -> dict:
        check_frozen()
        t0 = time.time()
        while self.budget_remains() and self.loop < self.cfg.max_loops:
            self.loop += 1
            used_names = set()
            for label in self.cfg.circuit_order:
                if not self.budget_remains():
                    break
                o = self.attempt(label, len(self.history[label]) + 1)
                if o.admitted:
                    used_names.add(o.report["admission"]["rule"])
            B.credit(used_names | {r.name for r in self.book if r.tier == "floor"}, self.loop)
            kept, gone = B.retire(self.book, self.loop, self.cfg.retire_after_loops)
            if gone:
                self._append("retired.jsonl", dict(loop=self.loop, retired=gone))
                self.book = kept
            self._append("loops.jsonl", dict(loop=self.loop, book=[r.name for r in self.book],
                                             attempts_used=self.attempts_used,
                                             seconds=round(time.time() - t0, 1)))
        recheck_frozen()
        out = dict(loops=self.loop, attempts_used=self.attempts_used,
                   book=[r.name for r in self.book], book_digest=B.digest(self.book),
                   seconds=round(time.time() - t0, 1),
                   final={lab: optimize_memo(lab, self.book, self.cfg.eps,
                                             order=self.cfg.order_on_admission).cost["t_count"]
                          for lab in self.cfg.circuit_order})
        (self.dir / "summary.json").write_text(json.dumps(out, default=str, indent=1) + "\n")
        return out
