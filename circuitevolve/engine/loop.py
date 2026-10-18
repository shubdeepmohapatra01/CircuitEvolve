"""Generic selection loop over a DomainPlugin (PLAN_P1 phase P1.1).

Extracted from core/loop.py with the DV specifics moved behind the plugin interface; control
flow, acceptance semantics, ledger protocol, playbook credit, log record shapes and stats keys
are IDENTICAL to the stage-1 window loop (gate: tests/engine/test_golden_dv.py).

Engine-owned and not plugin-overridable (CLAUDE.md invariants 3-5, 7):
    accept iff verdict.ok AND the ledger can pay AND plugin.improves AND the global check
    passes; archive = best + up to archive_size-1 distinct members (plugin.cost_key, ties by
    ledger spend); playbook credit only for prompts whose candidate was ACCEPTED and reduced
    the primary metric; reflector cadence and budget accounting; append-only JSONL logs
    (existing tag refused); plugin frozen digest checked at start and end.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

from .plugin import DomainPlugin, Member
from .reflector import build_reflector_input, render_anatomy

BASE_STATS = ("proposal_calls", "reflect_calls", "llm_errors", "declined", "candidates", "parse_errors",
              "verified", "rejected_verifier", "rejected_metric", "rejected_ledger", "rejected_whole",
              "accepted", "accepted_t_reduced", "exact_accepts", "approx_accepts", "rules_added",
              "reflect_skipped_no_evidence")


class EvolveLoop:
    def __init__(self, plugin: DomainPlugin, eps: float, complete, ledger0, *, reflect_complete=None,
                 playbook=None, tag: str | None = None, n_calls: int = 20, batch: int = 4,
                 reflect_every: int = 8, archive_size: int = 4, p_best: float = 0.7, seed: int = 0,
                 feedback_len: int = 6, runs_dir: Path | None = None, task_text: str = ""):
        self.plugin = plugin
        self.eps, self.complete = float(eps), complete
        self.reflect_complete = reflect_complete or complete
        self.pb = playbook
        self.ledger0 = ledger0
        self.n_calls, self.batch, self.reflect_every = n_calls, batch, reflect_every
        self.archive_size, self.p_best, self.rng = archive_size, p_best, random.Random(seed)
        self.feedback_len = feedback_len
        self.tag, self.task_text = tag, task_text
        self.runs_dir = Path(runs_dir) if runs_dir else None
        self.calls = 0
        self.stats = {k: 0 for k in BASE_STATS}
        for a in plugin.actions:
            self.stats[f"{a}_proposals"] = 0
            self.stats[f"accepted_{a}"] = 0
        self.stats.update(plugin.stats_template())
        self.feedback: list = []
        self.improvements: list = []       # for the reflector: plugin.improvement_entry tuples + anatomy
        self.failures: list = []           # (candidate text, reason)
        self.anatomy: list = []            # AcceptAnatomy per accept (P2.1)
        self._fail_mark = 0                # failures consumed by the last reflection
        self._new_evidence = 0
        self._log = None

    # ------------------------------------------------------------------ logging
    def _open_log(self):
        if self.tag is None:
            return
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._log = open(self.runs_dir / f"{self.tag}.jsonl", "x")      # append-only: refuse an existing tag

    def _write(self, rec: dict):
        if self._log:
            self._log.write(json.dumps(rec, default=str) + "\n")
            self._log.flush()

    # ------------------------------------------------------------------ archive
    def _member(self, state, ledger, born=0) -> Member:
        return Member(state=state, ledger=ledger, cost=self.plugin.cost(state, ledger),
                      digest=self.plugin.digest(state), born=born)

    def _insert(self, m: Member):
        if any(x.digest == m.digest for x in self.archive):
            return
        self.archive.append(m)
        self.archive.sort(key=lambda x: (self.plugin.cost_key(x.cost), x.ledger.spent))
        del self.archive[self.archive_size:]

    def _pick(self):
        if len(self.archive) == 1 or self.rng.random() < self.p_best:
            return self.archive[0]
        return self.rng.choice(self.archive[1:])

    # ------------------------------------------------------------------ main
    def run(self) -> dict:
        t0 = time.time()
        digest = self.plugin.frozen_digest()
        self._open_log()
        d_in = self.plugin.input_check(self.ledger0.window_pool)
        ledger = self.ledger0.with_input(d_in)
        start = self._member(self.plugin.start_state(), ledger)
        self.archive = [start]
        self.start_cost = dict(start.cost)
        self._write(dict(kind="start", tag=self.tag, n=self.plugin.n, eps=self.eps, input=self.plugin.meta,
                         cost=start.cost, ledger=self.plugin.ledger_summary(ledger, start.cost),
                         verifier_digest=digest[:16]))
        while self.calls < self.n_calls:
            k = min(self.batch, self.n_calls - self.calls)
            self._proposal_batch(k)
            if (self.pb is not None and not self.pb.frozen and self.reflect_every and self.calls < self.n_calls
                    and self.stats["proposal_calls"] // self.reflect_every > self.stats.get("_reflected_at", 0)):
                self.stats["_reflected_at"] = self.stats["proposal_calls"] // self.reflect_every
                self._reflect()
        self.plugin.check_unchanged(digest)
        best = self.archive[0]
        summ = self._summary(best, time.time() - t0, digest)
        self._write(dict(kind="end", summary=summ))
        if self._log:
            self._log.close()
            self._save_outputs(best, summ)
        return summ

    def _proposal_batch(self, k: int):
        parent = self._pick()
        chosen = self.plugin.select_tasks(parent, k, self.rng)
        if not chosen:
            self.calls = self.n_calls          # nothing left to optimize
            return
        allowance = parent.ledger.allowance()
        prompts, metas = [], []
        for task in chosen:
            parent.tried.add(task.key)
            rules, shown, hidden = (self.pb.select(self.rng) if self.pb is not None else ([], [], []))
            prompts.append(self.plugin.build_prompt(task, rules, self.feedback[-self.feedback_len:], allowance))
            metas.append((task, shown, hidden))
        resp = self.complete(prompts)
        self.calls += len(prompts)
        self.stats["proposal_calls"] += len(prompts)
        # evaluate tasks in DESCENDING order so applications never shift a task still to be evaluated
        order = sorted(range(len(prompts)), key=lambda i: -metas[i][0].order)
        cur_state = self.plugin.flat_state(parent)
        cur_ledger, cur_cost = parent.ledger, parent.cost
        changed = False
        for i in order:
            task, shown, hidden = metas[i]
            text = resp[i]
            rec = dict(kind="propose", call=self.calls - len(prompts) + i + 1, parent=parent.digest,
                       **self.plugin.record_fields(task),
                       allowance=allowance, rules_shown=shown, rules_hidden=hidden,
                       prompt=prompts[i], candidates=[])
            if isinstance(text, Exception):
                self.stats["llm_errors"] += 1
                rec["error"] = str(text)[:500]
                self._write(rec)
                if self.pb is not None:
                    self.pb.record(shown, hidden, 0, 0, False)
                continue
            rec["response"] = text
            props, perr, declined = self.plugin.parse(text)
            if declined:
                rec["declined"] = True
                self.stats["declined"] += 1
            rec["parse_errors"] = perr
            self.stats["parse_errors"] += len(perr)
            best_c = None
            n_pass = 0
            for action, payload in props:
                self.stats["candidates"] += 1
                self.stats[f"{action}_proposals"] += 1
                m = self.plugin.materialize(task, action, payload, rec["call"])
                crec, label = m["crec"], m["label"]
                if not m["ok"]:
                    self.stats[m["fail_stat"]] += 1
                    crec["decision"] = m["fail_reason"]
                    self._fail_text(label, crec["decision"])
                    rec["candidates"].append(crec)
                    continue
                c = m["cand"]
                v = self.plugin.verify(task, c, allowance)
                crec["verify"] = v
                if not v["ok"]:
                    self.stats["rejected_verifier"] += 1
                    crec["decision"] = "rejected: verifier"
                    self._fail_text(label or self.plugin.cand_text(c), (label + ": " if label else "") + v["reason"])
                    rec["candidates"].append(crec)
                    continue
                n_pass += 1
                self.stats["verified"] += 1
                new_state = self.plugin.apply(cur_state, task, c)
                if not cur_ledger.can_charge(v["charge"]):
                    self.stats["rejected_ledger"] += 1
                    crec["decision"] = f"rejected: ledger (charge {v['charge']:.3e} > remaining {cur_ledger.remaining:.3e})"
                    self._fail_text(label or self.plugin.cand_text(c), crec["decision"])
                    rec["candidates"].append(crec)
                    continue
                led_c = cur_ledger.charge(v["charge"], call=rec["call"], window=task.index, mode=f"{v['mode']}/{action}")
                cost = self.plugin.cost(new_state, led_c)
                crec["cost"] = self.plugin.cost_subset(cost)
                if not self.plugin.improves(cost, cur_cost):
                    self.stats["rejected_metric"] += 1
                    crec["decision"] = self.plugin.reject_metric_text(cur_cost, cost)
                    self._fail_text(label or self.plugin.cand_text(c), (label + ": " if label else "") + crec["decision"])
                elif best_c is None or self.plugin.cost_key(cost) < self.plugin.cost_key(best_c[1]):
                    crec["decision"] = "best so far"
                    best_c = (c, cost, v, new_state, led_c, action, label)
                rec["candidates"].append(crec)
            improved = False
            if best_c is not None:
                c, cost, v, new_state, led, action, label = best_c
                whole = self.plugin.global_check(new_state, bound=led.d_input + led.spent)
                rec["whole_check"] = whole
                if whole is not None and not whole["ok"]:
                    self.stats["rejected_whole"] += 1
                    rec["accepted"] = False
                    self._fail_text(label or self.plugin.cand_text(c),
                                    f"whole-circuit check failed: dist {whole['dist']:.3e} > bound {whole['bound']:.3e}")
                else:
                    self.stats["accepted"] += 1
                    self.stats["exact_accepts" if v["mode"] == "exact" else "approx_accepts"] += 1
                    self.stats[f"accepted_{action}"] += 1
                    self.plugin.on_accept_stats(self.stats, action, cur_cost, cost)
                    improved = cost[self.plugin.primary] < cur_cost[self.plugin.primary]
                    self.stats["accepted_t_reduced"] += int(improved)
                    rec.update(accepted=True, action=action, charge=v["charge"],
                               **self.plugin.accept_record(cur_cost, cost))
                    anatomy = self.plugin.accept_anatomy(task, c, label, v, cur_cost, cost, shown)
                    anatomy.call = rec["call"]
                    self.anatomy.append(anatomy)
                    pf, cf, ps, cs = self.plugin.improvement_entry(task, c, label, cur_cost, cost)
                    self.improvements.append((pf, cf, ps, cs + "\n" + render_anatomy(anatomy)))
                    self.feedback.append(self.plugin.accept_feedback(label, v, cur_cost, cost))
                    cur_state, cur_ledger, cur_cost = new_state, led, cost
                    changed = True
            rec.setdefault("accepted", False)
            self._new_evidence += len(props)
            if self.pb is not None:
                self.pb.record(shown, hidden, len(props), n_pass, improved)
            self._write(rec)
        if changed:
            child = self._member(cur_state, cur_ledger, born=self.calls)
            child.tried = set(parent.tried)     # unchanged tasks keep their 'tried' mark (key = content)
            self._insert(child)
        if self.pb is not None:
            ch = self.pb.update_status(self.calls)
            if ch:
                self._write(dict(kind="playbook_gate", call=self.calls, changes=ch))

    def _fail_text(self, what: str, why: str):
        self.failures.append((what, why))
        self.feedback.append(f"rejected: {why}")

    def _reflect(self):
        if self._new_evidence == 0:
            self.stats["reflect_skipped_no_evidence"] += 1
            return
        stats = {k: v for k, v in self.stats.items() if not k.startswith("_")}
        imp, fails, stats = build_reflector_input(self.improvements, self.failures[self._fail_mark:], stats)
        self._fail_mark = len(self.failures)
        prompt = self.pb.reflect_prompt(self.task_text, imp[-4:], fails, stats)
        (resp,) = self.reflect_complete([prompt])
        self.calls += 1
        self.stats["reflect_calls"] += 1
        rec = dict(kind="reflect", call=self.calls, prompt=prompt)
        if isinstance(resp, Exception):
            rec["error"] = str(resp)[:500]
            self.stats["llm_errors"] += 1
        else:
            applied, errors = self.pb.apply_deltas(resp, self.calls)
            self.stats["rules_added"] += sum(1 for op, _ in applied if op in ("add", "edit"))
            rec.update(response=resp, applied=applied, errors=errors)
        self._new_evidence = 0
        self._write(rec)

    # ------------------------------------------------------------------ outputs
    def _summary(self, best: Member, seconds: float, digest: str) -> dict:
        p = self.plugin
        st = {k: v for k, v in self.stats.items() if not k.startswith("_")}
        backend = dict(getattr(self.complete, "stats", {}) or {})
        return dict(tag=self.tag, name=p.meta.get("name"), input_source=p.meta.get("source"),
                    n=p.n, eps=self.eps, calls=self.calls, stats=st, backend_stats=backend,
                    t_before=self.start_cost[p.primary], t_after=best.cost[p.primary],
                    before=p.cost_subset(self.start_cost), after=p.cost_subset(best.cost),
                    t_after_reclaimed=p.reclaimed(best), ledger=p.ledger_summary(best.ledger, best.cost),
                    final_check_vs_original=p.final_check(best),
                    archive=[p.archive_entry(m) for m in self.archive],
                    seconds=round(seconds, 1), verifier_digest=digest[:16],
                    playbook=(dict(live=len(self.pb.live()), active=sum(r.status == "active" for r in self.pb.rules))
                              if self.pb is not None else None))

    def _save_outputs(self, best: Member, summ: dict):
        d = self.runs_dir
        (d / f"{self.tag}_summary.json").open("x").write(json.dumps(summ, indent=1, default=str))
        for suffix, content in self.plugin.output_files(best).items():
            (d / f"{self.tag}{suffix}").open("x").write(content)
        if self.pb is not None:
            self.pb.save(d / f"{self.tag}_playbook.json")
            (d / f"{self.tag}_playbook.md").open("x").write(self.pb.to_markdown())
