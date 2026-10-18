"""Tier 1 loop: LLM arm (plans from the model) and NO-LLM control arm, same number of compile+verify evaluations.

run_llm_arm(lc, s, complete, calls, log_path, classical) -> ArmResult
run_control_arm(lc, s, budget, log_path) -> ArmResult

`complete` is a backend callable list[str] -> list[str | Exception] (circuitevolve.llm_backends.make_api_backend);
its `stats` Counter gives tokens. One JSON line per evaluation in `log_path` (prompt, reply, verdict, metrics).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field

from ..metric import fitness_key
from .compile import evaluate
from .control import NAMES, control_plans
from .prompt import build_prompt, compact_plan, select_cards


@dataclass
class ArmResult:
    arm: str
    best: dict = field(default_factory=dict)        # mode -> record (with 'plan', '_compiled')
    evaluations: int = 0
    records: list = field(default_factory=list)
    tokens: dict = field(default_factory=dict)


def _public(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if not k.startswith("_")}


def _update_best(best: dict, rec: dict, extra: dict):
    if not rec.get("ok"):
        return False
    mode = "exact" if rec["verdict_mode"] == "exact" else "relaxed"
    m = dict(t_count=rec["t_count"], qubits=rec["qubits"], t_depth=rec["t_depth"])
    cur = best.get(mode)
    if cur is None or fitness_key(m) < fitness_key(cur):
        r = dict(rec)
        r.update(extra)
        r["plan_compact"] = compact_plan(rec["plan"])
        best[mode] = r
        return True
    return False


def _feedback_text(rec: dict) -> str:
    if rec.get("ok"):
        return (f"VERIFIED {rec['verdict_mode']} ({'certified' if rec['certified'] else 'sampled, not certified'}): "
                f"T={rec['t_count']} qubits={rec['qubits']} meas={rec['measurements']} T-depth={rec['t_depth']} "
                f"plan={json.dumps(compact_plan(rec['plan']))}")
    p = rec.get("plan")
    return f"REJECTED ({rec.get('stage')}): {rec.get('reason', '')[:300]}" + \
        (f" plan={json.dumps(compact_plan(p))}" if p else "")


def run_llm_arm(lc, s, complete, calls: int, log_path, classical: str, pass_cache=None, verify_cache=None,
                schedule=("relaxed", "exact"), tag: str = "llm") -> ArmResult:
    res = ArmResult(tag)
    feedback, requested = [], []
    stats = getattr(complete, "stats", None)
    tok0 = dict(stats) if stats is not None else {}
    with open(log_path, "a") as fh:
        for k in range(calls):
            target = schedule[k % len(schedule)]
            cards = select_cards(s, requested)
            prompt = build_prompt(s, lc, target, res.best, feedback, cards, classical)
            before = dict(stats) if stats is not None else {}
            t0 = time.time()
            reply = complete([prompt])[0]
            dt = time.time() - t0
            after = dict(stats) if stats is not None else {}
            usage = {key: after.get(key, 0) - before.get(key, 0) for key in ("input_tokens", "output_tokens")}
            if isinstance(reply, Exception):
                rec = dict(ok=False, stage="llm", reason=f"llm error: {reply}")
                text = ""
            else:
                text = reply
                rec = evaluate(lc, s, text, pass_cache, verify_cache)
            res.evaluations += 1
            improved = _update_best(res.best, rec, dict(call=k, arm=tag))
            requested = list(rec.get("plan", {}).get("request_cards", []) or [])
            feedback.append(dict(call=k, target=target, text=_feedback_text(rec) + (" [NEW BEST]" if improved else "")))
            line = dict(circuit=s.name, arm=tag, call=k, target=target, cards=cards,
                        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(), prompt_chars=len(prompt),
                        prompt=prompt, reply=text, usage=usage, llm_seconds=round(dt, 1), improved=improved,
                        **_public(rec))
            fh.write(json.dumps(line, default=str) + "\n")
            fh.flush()
            res.records.append(_public(rec))
    after = dict(stats) if stats is not None else {}
    res.tokens = {key: after.get(key, 0) - tok0.get(key, 0) for key in ("input_tokens", "output_tokens", "calls")}
    return res


def run_control_arm(lc, s, budget: int, log_path, pass_cache=None, verify_cache=None) -> ArmResult:
    res = ArmResult("control")
    with open(log_path, "a") as fh:
        for k, (v, gp, plan) in enumerate(control_plans(lc, s, budget)):
            rec = evaluate(lc, s, plan, pass_cache, verify_cache)
            res.evaluations += 1
            improved = _update_best(res.best, rec, dict(call=k, arm="control", variant=v, variant_name=NAMES[v]))
            fh.write(json.dumps(dict(circuit=s.name, arm="control", call=k, variant=v, variant_name=NAMES[v],
                                     improved=improved, **_public(rec)), default=str) + "\n")
            res.records.append(dict(_public(rec), variant=v))
    return res
