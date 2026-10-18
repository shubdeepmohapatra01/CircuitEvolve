"""Simple selection loop: mutator -> verifier -> metric, with a small archive and a self-evolving playbook.

    start   TKET-pre-optimized input (circuit.load_input), ledger charged with its measured distance to the
            original qseed circuit;
    repeat  pick a parent (best with prob. p_best, else another archive member); partition it into windows;
            choose windows by T-cost (highest first, round-robin, skipping ones already tried on this parent);
            one LLM call per window (batched); every candidate -> verify_window at the ledger allowance ->
            splice -> metric; accept the best candidate per window if metric.improves over the parent and
            the ledger can pay its distance; whole-circuit check against the ORIGINAL (n <= 20) on accept;
    archive best + up to `archive_size - 1` other distinct circuits (ranked by cost_key);
    playbook A/B-tests candidate rules; evidence = prompts whose proposal was ACCEPTED AND reduced T
            (Playbook(evidence="improvement")); a reflector call every `reflect_every` proposal calls when
            there is new verifier evidence; reflector calls count against the LLM-call budget;
    log     one JSON line per LLM call (prompt, response, parsed candidates, verifier records, costs,
            decision) in results/window_runs/<tag>.jsonl, plus <tag>_summary.json, <tag>_best.qasm and a
            playbook snapshot (append-only: an existing tag is refused).
The verifier files are hashed at start and end (integrity.frozen_digest).
"""
from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..blocks import REPO
from ..blocks.cost_model import canonical_angle, cost_key, rz_angles
from ..blocks.circuit_io import classify_angle
from ..integrity import check_unchanged, frozen_digest
from ..search.playbook import Playbook
from .circuit import Circuit, splice, window_text, windows
from .ledger import Ledger
from .metric import BqskitTMetric, improves
from .mutator import DECLINED, WindowTask, build_prompt, extract_proposals
from .refit import refit
from .verifier import check_circuit, verify_window

RUNS = REPO / "results" / "window_runs"
TASK_TEXT = ("The proposer rewrites windows (<= 4 qubits, <= 40 gates) of a Clifford+Rz circuit to lower its "
             "T-count under gridsynth synthesis at eps_rz = eps_synth / N_Rz; an exact (Clifford+T) or "
             "operator-norm verifier with an error allowance decides acceptance. Gates: h s sdg x z t tdg cx cz "
             "rz(angle) on local qubits q0..q3.")


@dataclass
class Member:
    ops: list
    ledger: Ledger
    cost: dict
    digest: str
    born: int = 0
    tried: set = field(default_factory=set)      # window keys already proposed on this member
    _win: tuple | None = None


def _fmt_target(a: float) -> str:
    import math as _m
    m = round(a / (_m.pi / 8))
    return "0" if m == 0 else f"{m}*pi/8"


def _digest(ops) -> str:
    return hashlib.sha1(repr(ops).encode()).hexdigest()[:16]


def _wkey(w) -> str:
    return hashlib.sha1((repr(w.qubits) + window_text(w.ops)).encode()).hexdigest()[:12]


class WindowLoop:
    def __init__(self, circ: Circuit, original_ops, eps: float, complete, *, reflect_complete=None,
                 playbook: Playbook | None = None, tag: str | None = None, n_calls: int = 20, batch: int = 4,
                 reflect_every: int = 8, archive_size: int = 4, p_best: float = 0.7, seed: int = 0,
                 feedback_len: int = 6, runs_dir: Path | None = None, check_whole: bool = True,
                 window_fraction: float = 0.5, per_rewrite_fraction: float = 0.25, max_tokens_note: str = "",
                 ledger_rule: str = "v1", pool_fraction: float = 0.25, refit_multistarts: int = 8,
                 seeded_ties: bool = False):
        self.circ, self.n, self.original = circ, circ.n, original_ops
        self.eps, self.complete = float(eps), complete
        self.reflect_complete = reflect_complete or complete
        self.pb = playbook
        self.n_calls, self.batch, self.reflect_every = n_calls, batch, reflect_every
        self.archive_size, self.p_best, self.rng = archive_size, p_best, random.Random(seed)
        self.feedback_len, self.check_whole = feedback_len, check_whole
        # acceptance and reported T use eps_rz = ledger.eps_synth / N_Rz of the circuit's OWN ledger (v1: unspent
        # window budget returns to synthesis; v0: fixed eps/2)
        self.metric = BqskitTMetric(eps)
        self.ledger0 = Ledger(eps, rule=ledger_rule, window_fraction=window_fraction, pool_fraction=pool_fraction,
                              per_rewrite_fraction=per_rewrite_fraction)
        self.refit_multistarts = refit_multistarts
        # seeded_ties: windows of EQUAL T-cost are ordered by a seed-dependent hash of their content instead of
        # their position (default False = stage-1 behaviour). Consumes no RNG, so parent selection is unchanged.
        self.seed, self.seeded_ties = seed, seeded_ties
        self.tag = tag
        self.runs_dir = Path(runs_dir) if runs_dir else RUNS
        self.calls = 0
        self.stats = dict(proposal_calls=0, reflect_calls=0, llm_errors=0, declined=0, candidates=0, parse_errors=0,
                          verified=0, rejected_verifier=0, rejected_metric=0, rejected_ledger=0,
                          rejected_whole=0, accepted=0, accepted_t_reduced=0, exact_accepts=0, approx_accepts=0,
                          rules_added=0, reflect_skipped_no_evidence=0, window_proposals=0, fix_proposals=0,
                          refit_failed=0, accepted_window=0, accepted_fix=0, rotations_removed_window=0,
                          rotations_removed_fix=0)
        self.feedback: list = []
        self.improvements: list = []       # for the reflector: (parent T, child T, parent window, child window)
        self.failures: list = []           # (candidate window text, reason)
        self._new_evidence = 0
        self._log = None

    # ------------------------------------------------------------------ logging
    def _open_log(self):
        if self.tag is None:
            return
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        p = self.runs_dir / f"{self.tag}.jsonl"
        self._log = open(p, "x")           # append-only: refuse an existing tag

    def _write(self, rec: dict):
        if self._log:
            self._log.write(json.dumps(rec, default=str) + "\n")
            self._log.flush()

    # ------------------------------------------------------------------ archive
    def _cost(self, ops, ledger: Ledger) -> dict:
        n_rz = len(rz_angles(ops))
        c = self.metric.cost(ops, eps_rz=ledger.eps_synth / n_rz if n_rz else ledger.eps_synth)
        c["eps_synth"] = ledger.eps_synth
        return c

    def _member(self, ops, ledger, born=0) -> Member:
        return Member(ops=ops, ledger=ledger, cost=self._cost(ops, ledger), digest=_digest(ops), born=born)

    def _insert(self, m: Member):
        if any(x.digest == m.digest for x in self.archive):
            return
        self.archive.append(m)
        self.archive.sort(key=lambda x: (cost_key(x.cost), x.ledger.spent))
        del self.archive[self.archive_size:]

    def _windows(self, m: Member):
        if m._win is None:
            ws, flat = windows(Circuit(self.n, m.ops))
            m._win = (ws, flat)
        return m._win

    def _pick(self):
        if len(self.archive) == 1 or self.rng.random() < self.p_best:
            return self.archive[0]
        return self.rng.choice(self.archive[1:])

    def _window_cost(self, w, eps_rz: float) -> tuple:
        angs = [canonical_angle(a) for g, _, a in w.ops if g == "rz" and classify_angle(a) is None]
        t_rot = self.metric.rotation_t(angs, eps_rz)
        t_fixed = sum(1 for g, _, _ in w.ops if g in ("t", "tdg")) + \
            sum(classify_angle(a) % 2 for g, _, a in w.ops if g == "rz" and classify_angle(a) is not None)
        return t_rot, t_fixed

    def _choose_windows(self, m: Member, k: int) -> list:
        ws, _ = self._windows(m)
        e = m.cost["eps_rz"]
        scored = []
        for w in ws:
            t_rot, t_fixed = self._window_cost(w, e)
            if t_fixed + sum(t_rot) > 0:
                scored.append((t_fixed + sum(t_rot), w, t_rot, t_fixed))
        if self.seeded_ties:
            scored.sort(key=lambda s: (-s[0], hashlib.sha1(f"{self.seed}:{_wkey(s[1])}".encode()).hexdigest()))
        else:
            scored.sort(key=lambda s: (-s[0], s[1].index))
        fresh = [s for s in scored if _wkey(s[1]) not in m.tried]
        if not fresh:                       # round-robin: start over on this member
            m.tried.clear()
            fresh = scored
        return fresh[:k]

    # ------------------------------------------------------------------ main
    def run(self) -> dict:
        t0 = time.time()
        digest = frozen_digest()
        self._open_log()
        d_in = 0.0
        if self.check_whole and self.n <= 20:
            r = check_circuit(self.original, self.circ.ops, self.n, bound=self.ledger0.window_pool)
            if not r["ok"]:
                raise ValueError(f"input circuit is not equivalent to the original: {r}")
            d_in = float(r["dist"])
        ledger = self.ledger0.with_input(d_in)
        start = self._member(list(self.circ.ops), ledger)
        self.archive = [start]
        self.start_cost = dict(start.cost)
        self._write(dict(kind="start", tag=self.tag, n=self.n, eps=self.eps, input=self.circ.meta,
                         cost=start.cost, ledger=ledger.summary(start.cost["rz"]), verifier_digest=digest[:16]))
        while self.calls < self.n_calls:
            k = min(self.batch, self.n_calls - self.calls)
            self._proposal_batch(k)
            if (self.pb is not None and not self.pb.frozen and self.reflect_every and self.calls < self.n_calls
                    and self.stats["proposal_calls"] // self.reflect_every > self.stats.get("_reflected_at", 0)):
                self.stats["_reflected_at"] = self.stats["proposal_calls"] // self.reflect_every
                self._reflect()
        check_unchanged(digest)
        best = self.archive[0]
        summ = self._summary(best, time.time() - t0, digest)
        self._write(dict(kind="end", summary=summ))
        if self._log:
            self._log.close()
            self._save_outputs(best, summ)
        return summ

    def _proposal_batch(self, k: int):
        parent = self._pick()
        chosen = self._choose_windows(parent, k)
        if not chosen:
            self.calls = self.n_calls          # nothing left to optimize
            return
        allowance = parent.ledger.allowance()
        e = parent.cost["eps_rz"]
        prompts, metas = [], []
        for t_win, w, t_rot, t_fixed in chosen:
            parent.tried.add(_wkey(w))
            rules, shown, hidden = (self.pb.select(self.rng) if self.pb is not None else ([], [], []))
            task = WindowTask(local_ops=w.ops, k=w.k, eps_rz=e, allowance=allowance, t_rot=t_rot, t_fixed=t_fixed,
                              rules=rules, feedback=self.feedback[-self.feedback_len:])
            prompts.append(build_prompt(task))
            metas.append((w, t_win, shown, hidden))
        resp = self.complete(prompts)
        self.calls += len(prompts)
        self.stats["proposal_calls"] += len(prompts)
        _, flat = self._windows(parent)
        # evaluate windows in DESCENDING start order so splices never shift a window still to be evaluated
        order = sorted(range(len(prompts)), key=lambda i: -metas[i][0].start)
        cur_ops, cur_ledger, cur_cost = list(flat), parent.ledger, parent.cost
        changed = False
        for i in order:
            w, t_win, shown, hidden = metas[i]
            text = resp[i]
            rec = dict(kind="propose", call=self.calls - len(prompts) + i + 1, parent=parent.digest,
                       window=dict(index=w.index, qubits=list(w.qubits), n_ops=len(w.ops), t_cost=t_win),
                       allowance=allowance, eps_rz=e, rules_shown=shown, rules_hidden=hidden,
                       prompt=prompts[i], candidates=[])
            if isinstance(text, Exception):
                self.stats["llm_errors"] += 1
                rec["error"] = str(text)[:500]
                self._write(rec)
                if self.pb is not None:
                    self.pb.record(shown, hidden, 0, 0, False)
                continue
            rec["response"] = text
            props, perr = extract_proposals(text)
            if perr == [DECLINED]:
                rec["declined"] = True
                self.stats["declined"] += 1
                perr = []
            rec["parse_errors"] = perr
            self.stats["parse_errors"] += len(perr)
            best_c = None
            n_pass = 0
            cands = []
            for action, payload in props:
                self.stats["candidates"] += 1
                self.stats[f"{action}_proposals"] += 1
                if action == "fix":
                    fx = {int(i): float(a) for i, a in payload.items()}
                    label = "fix " + ", ".join(f"op {i}->{_fmt_target(a)}" for i, a in sorted(fx.items()))
                    rf = refit(w.ops, w.k, fx, multistarts=self.refit_multistarts, seed=rec["call"])
                    crec = dict(action="fix", fixes={str(i): a for i, a in fx.items()},
                                refit={kk: rf[kk] for kk in ("ok", "dist", "n_free", "reason")})
                    if not rf["ok"]:
                        self.stats["refit_failed"] += 1
                        crec["decision"] = f"rejected: refit ({rf['reason']})"
                        self._fail_text(label, crec["decision"])
                        rec["candidates"].append(crec)
                        continue
                    c = rf["ops"]
                    crec["window"] = window_text(c)
                else:
                    c = payload
                    label = None
                    crec = dict(action="window", window=window_text(c))
                cands.append(c)
                v = verify_window(w.ops, c, w.k, allowance)
                crec["verify"] = v
                if not v["ok"]:
                    self.stats["rejected_verifier"] += 1
                    crec["decision"] = "rejected: verifier"
                    self._fail_text(label or window_text(c), (label + ": " if label else "") + v["reason"])
                    rec["candidates"].append(crec)
                    continue
                n_pass += 1
                self.stats["verified"] += 1
                new_ops = splice(cur_ops, w, c)
                if not cur_ledger.can_charge(v["charge"]):
                    self.stats["rejected_ledger"] += 1
                    crec["decision"] = f"rejected: ledger (charge {v['charge']:.3e} > remaining {cur_ledger.remaining:.3e})"
                    self._fail_text(label or window_text(c), crec["decision"])
                    rec["candidates"].append(crec)
                    continue
                led_c = cur_ledger.charge(v["charge"], call=rec["call"], window=w.index, mode=f"{v['mode']}/{action}")
                cost = self._cost(new_ops, led_c)
                crec["cost"] = {kk: cost[kk] for kk in ("t", "t_fixed", "t_gs", "rz", "cx", "gates", "eps_rz")}
                if not improves(cost, cur_cost):
                    self.stats["rejected_metric"] += 1
                    crec["decision"] = f"rejected: no improvement (T {cur_cost['t']} -> {cost['t']}, rz {cur_cost['rz']} -> {cost['rz']})"
                    self._fail_text(label or window_text(c), (label + ": " if label else "") + crec["decision"])
                elif best_c is None or cost_key(cost) < cost_key(best_c[1]):
                    crec["decision"] = "best so far"
                    best_c = (c, cost, v, new_ops, led_c, action, label)
                rec["candidates"].append(crec)
            improved = False
            if best_c is not None:
                c, cost, v, new_ops, led, action, label = best_c
                whole = None
                if self.check_whole and self.n <= 20:
                    whole = check_circuit(self.original, new_ops, self.n, bound=led.d_input + led.spent)
                rec["whole_check"] = whole
                if whole is not None and not whole["ok"]:
                    self.stats["rejected_whole"] += 1
                    rec["accepted"] = False
                    self._fail_text(label or window_text(c),
                                    f"whole-circuit check failed: dist {whole['dist']:.3e} > bound {whole['bound']:.3e}")
                else:
                    self.stats["accepted"] += 1
                    self.stats["exact_accepts" if v["mode"] == "exact" else "approx_accepts"] += 1
                    self.stats[f"accepted_{action}"] += 1
                    self.stats[f"rotations_removed_{action}"] += cur_cost["rz"] - cost["rz"]
                    improved = cost["t"] < cur_cost["t"]
                    self.stats["accepted_t_reduced"] += int(improved)
                    rec.update(accepted=True, action=action, t_before=cur_cost["t"], t_after=cost["t"],
                               charge=v["charge"], rz_before=cur_cost["rz"], rz_after=cost["rz"])
                    self.improvements.append((cur_cost["t"], cost["t"], window_text(w.ops),
                                              (label + "\n" if label else "") + window_text(c)))
                    self.feedback.append(f"ACCEPTED {label or 'window rewrite'} ({v['mode']}, distance {v['dist']:.2e}): "
                                         f"T {cur_cost['t']} -> {cost['t']}, rotations {cur_cost['rz']} -> {cost['rz']}")
                    cur_ops, cur_ledger, cur_cost = new_ops, led, cost
                    changed = True
            rec.setdefault("accepted", False)
            self._new_evidence += len(props)
            if self.pb is not None:
                self.pb.record(shown, hidden, len(props), n_pass, improved)
            self._write(rec)
        if changed:
            child = self._member(cur_ops, cur_ledger, born=self.calls)
            child.tried = set(parent.tried)     # unchanged windows keep their 'tried' mark (key = content)
            self._insert(child)
        if self.pb is not None:
            ch = self.pb.update_status(self.calls)
            if ch:
                self._write(dict(kind="playbook_gate", call=self.calls, changes=ch))

    def _fail(self, c, why: str):
        self._fail_text(window_text(c), why)

    def _fail_text(self, what: str, why: str):
        self.failures.append((what, why))
        self.feedback.append(f"rejected: {why}")

    def _reflect(self):
        if self._new_evidence == 0:
            self.stats["reflect_skipped_no_evidence"] += 1
            return
        stats = {k: v for k, v in self.stats.items() if not k.startswith("_")}
        prompt = self.pb.reflect_prompt(TASK_TEXT, self.improvements[-4:], self.failures[-6:], stats)
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
        n_rz = best.cost["rz"]
        reclaimed = None
        if n_rz:
            reclaimed = BqskitTMetric(best.ledger.reclaimed_eps_synth).cost(best.ops)["t"]
        final = None
        if self.check_whole and self.n <= 20:
            final = check_circuit(self.original, best.ops, self.n, bound=best.ledger.d_input + best.ledger.spent,
                                  seed=12345)
            final = {kk: final.get(kk) for kk in ("ok", "verified", "method", "dist", "bound")}
        st = {k: v for k, v in self.stats.items() if not k.startswith("_")}
        backend = dict(getattr(self.complete, "stats", {}) or {})
        return dict(tag=self.tag, name=self.circ.meta.get("name"), input_source=self.circ.meta.get("source"),
                    n=self.n, eps=self.eps, calls=self.calls, stats=st, backend_stats=backend,
                    t_before=self.start_cost["t"], t_after=best.cost["t"],
                    before={kk: self.start_cost[kk] for kk in ("t", "t_fixed", "t_gs", "rz", "cx", "gates", "eps_rz")},
                    after={kk: best.cost[kk] for kk in ("t", "t_fixed", "t_gs", "rz", "cx", "gates", "eps_rz")},
                    t_after_reclaimed=reclaimed, ledger=best.ledger.summary(n_rz), final_check_vs_original=final,
                    archive=[dict(t=m.cost["t"], rz=m.cost["rz"], spent=m.ledger.spent, digest=m.digest) for m in self.archive],
                    seconds=round(seconds, 1), verifier_digest=digest[:16],
                    playbook=(dict(live=len(self.pb.live()), active=sum(r.status == "active" for r in self.pb.rules))
                              if self.pb is not None else None))

    def _save_outputs(self, best: Member, summ: dict):
        d = self.runs_dir
        (d / f"{self.tag}_summary.json").open("x").write(json.dumps(summ, indent=1, default=str))
        (d / f"{self.tag}_best.qasm").open("x").write(Circuit(self.n, best.ops).to_qasm())
        if self.pb is not None:
            self.pb.save(d / f"{self.tag}_playbook.json")
            (d / f"{self.tag}_playbook.md").open("x").write(self.pb.to_markdown())


def run(name: str, eps: float, complete, tag: str | None = None, playbook_path=None, **kw) -> dict:
    """Convenience entry: load the stage-1 input and original, run the loop, persist the playbook."""
    from .circuit import load_input, original_ops
    circ = load_input(name)
    orig, n = original_ops(name)
    assert n == circ.n
    pb = None
    if playbook_path is not None:
        p = Path(playbook_path)
        pb = Playbook.load(p) if p.exists() else Playbook(evidence="improvement")
    loop = WindowLoop(circ, orig, eps, complete, playbook=pb, tag=tag, **kw)
    out = loop.run()
    if pb is not None and not pb.frozen:
        pb.save(playbook_path)
    return out
