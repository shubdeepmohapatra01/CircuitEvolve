"""Evaluate one candidate rule. Shared by `admit` (harness) and `test_rule` (agent, read-only).

V4_README sections 5 and 5.1. The order of the checks is the point:

    1. static        the file imports only stdlib / numpy / scipy / sympy / v4.api, and defines a RULE
    2. precondition  circuits the rule DECLARES it cannot apply to are skipped. Free, and NOT a rejection
                     (v3 had no such declaration, so every rule was run on every circuit)
    3. trigger       a trigger-only pass over the remaining circuits. If it matches nowhere the decision
                     is `never_fires` with NO optimize call at all. In v3, `evaluate()` computed n_match
                     and then ran both optimize calls anyway: `never_fires` cost 20.86 h of the P2 run to
                     discover nothing, where the trigger pass over the whole suite x 6 rules costs 0.48 s
    4. residual      `optimize_memo(label, book, eps)` - the book's own result, computed ONCE EVER per
                     (book digest, circuit, eps) and shared by every candidate and every attempt
    5. on target     the candidate is applied to that cached residual, so only ITS OWN applications are
                     verified. The reference stays the ORIGINAL circuit, so the whole-circuit check is
                     unchanged; the ledger continues from where the book left it
    6. admission     improvement, and (for the final decision) the order-safe re-run of section 5.2

Classification of a failure follows V4_README 5.3: a trigger that matches nowhere is an IDEA-level
failure; a trigger that matches and then fails to rewrite is an IMPLEMENTATION-level failure ("narrow the
guard, keep the idea"); an exception or an exhausted opcode budget is implementation-level.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .. import book as B
from ..api import Rule, describe
from ..caps import DEFAULT_BUDGET
from ..judge import dv as J
from ..judge.frozen import check_frozen
from ..memo import optimize_memo, residual
from ..paths import MANIFEST
from ..runner import dv_key, optimize

EPS = 1e-3
SMALL = ("qft_8", "adder_6", "mult_4", "modred_21")     # quick circuits test_rule runs after the target

IDEA = "idea"
IMPL = "implementation"


def suite(domain: str = "dv") -> list:
    return [c for c in json.loads(MANIFEST.read_text())["circuits"] if c["domain"] == domain]


def plan(domain: str = "dv", target=None, small_only: bool = False) -> list:
    cs = suite(domain)
    if small_only:
        names = ([target] if target else []) + [n for n in SMALL if n != target]
        return [next(c for c in cs if c["label"] == n) for n in names if any(c["label"] == n for c in cs)]
    if target:
        cs = sorted(cs, key=lambda c: c["label"] != target)
    return cs


def check_on_target(rule: Rule, label: str, bk, eps: float, opcode_budget=None) -> dict:
    """Run ONLY `rule` on the book's cached residual for `label`, verified against the ORIGINAL circuit.

    This is mechanism 2 of V4_README 5.1: v3 re-ran the whole book plus the candidate over 5 circuits,
    139 times."""
    original = J.load(label)
    cur, cost_before, led = residual(label, bk, eps)
    res = optimize(cur, [rule], eps, reference=original, order="book", ledger=led,
                   opcode_budget=opcode_budget)
    mine = [e for e in res.log if e["rule"] == rule.name]
    fails = [e for e in mine if e.get("verified") is False]
    return dict(label=label, eps=eps, t_before=cost_before["t_count"], t_after=res.cost["t_count"],
                qubits_before=cost_before["qubits"], qubits_after=res.cost["qubits"],
                cost_before=cost_before["t_count"], cost_after=res.cost["t_count"],
                improves=dv_key(res.cost) < dv_key(cost_before),
                fired=any(e["accepted"] for e in mine), attempts=len(mine),
                accepted=sum(e["accepted"] for e in mine),
                priced_out=sum(1 for e in mine if e.get("priced_out")),
                verified=sum(1 for e in mine if e.get("verified")),
                certified=all(e.get("certified", False) for e in mine if e.get("verified")),
                verify_methods=sorted({e.get("method") for e in mine if e.get("method")}),
                err_rules=res.err_rules, err_bound=res.err_bound,
                ledger=res.ledger.report() if res.ledger else None,
                unverifiable=sum(1 for e in mine if e.get("unverifiable")),
                first_failure=(dict(match=fails[0]["match"], mode=fails[0].get("mode"),
                                    method=fails[0].get("method"), distance=fails[0].get("distance"),
                                    unverifiable=bool(fails[0].get("unverifiable")),
                                    reason=fails[0].get("reason"))) if fails else None,
                opcodes=res.opcodes, seconds=round(res.seconds, 2), result=res)


def evaluate(path, bk=None, eps: float = EPS, target=None, small_only: bool = False,
             stop_at_first_failure: bool = False, opcode_budget: int | None = DEFAULT_BUDGET) -> dict:
    check_frozen()
    path = Path(path)
    out = dict(candidate=str(path), static="", circuits=[], excluded={}, decision=None, reason="",
               level=None, t0=time.time())
    bad = B.static_check(path)
    if bad:
        out.update(static=bad, decision="reject", reason=f"static check: {bad}", level=IMPL)
        return _done(out)
    try:
        rule = B.load_rule(path, tier="accepted")
    except Exception as e:                                           # noqa: BLE001 (any invalid RULE)
        out.update(static=f"{type(e).__name__}: {e}", decision="reject", reason=f"invalid RULE: {e}",
                   level=IMPL)
        return _done(out)
    bk = B.book() if bk is None else bk
    out["rule"] = rule.tags() | dict(name=rule.name, domain=rule.domain)
    out["book_digest"] = B.digest(bk)

    # ---- 2 + 3: preconditions, then a trigger-only pass. No optimize call yet.
    live, triggers = [], {}
    for c in plan(rule.domain, target, small_only):
        why = rule.precondition.excludes(describe(J.load(c["label"])))
        if why:
            out["excluded"][c["label"]] = why
            continue
        try:
            n = len(rule.trigger(J.load(c["label"])))
        except Exception as e:                                       # noqa: BLE001 (rule code)
            out.update(decision="reject", level=IMPL,
                       reason=f"exception in trigger on {c['label']}: {type(e).__name__}: {e}")
            return _done(out)
        triggers[c["label"]] = n
        if n:
            live.append(c)
    out["triggers_on_input"] = triggers
    if not live:
        out.update(decision="never_fires", level=IDEA,
                   reason=f"the trigger matched on none of the {len(triggers)} circuits it is not "
                          f"excluded from (precondition excluded {len(out['excluded'])})")
        return _done(out)

    # ---- 4 + 5: the book's cached residual, then the candidate alone on it
    for c in live:
        row = check_on_target(rule, c["label"], bk, eps, opcode_budget)
        res = row.pop("result")
        row["matches_on_input"] = triggers[c["label"]]
        out["circuits"].append(row)
        if stop_at_first_failure and row["first_failure"]:
            out["stopped_early"] = f"first verification failure on {c['label']}"
            break
        del res

    rows = out["circuits"]
    failed = [r for r in rows if r["first_failure"]]
    if failed and all(r["first_failure"]["unverifiable"] for r in failed):
        # the check could not RUN. Not a rejection: the rule is neither admitted nor branded wrong, and
        # the actionable feedback is "make the construction narrower", not "the identity is false".
        r = failed[0]
        out.update(decision="not_verifiable", level=IMPL,
                   reason=f"NOT VERIFIABLE on {r['label']} (eps {r['eps']}), so nothing was accepted: "
                          f"{r['first_failure']['reason']}")
    elif failed:
        r = next(x for x in failed if not x["first_failure"]["unverifiable"])
        out.update(decision="reject", level=IMPL,
                   reason=f"verification failed on {r['label']} (eps {r['eps']}): {r['first_failure']}")
    elif not any(r["fired"] for r in rows):
        # trigger matched but no application survived: the GUARD is too broad (V4_README 5.3 row 3)
        out.update(decision="reject", level=IMPL,
                   reason="the trigger matches but no application was kept: narrow the guard so it only "
                          "matches where the rewrite is both valid and an improvement. Keep the idea.")
    else:
        helped = [r for r in rows if r["cost_after"] < r["cost_before"]]
        if helped:
            out.update(decision="admit", level=None,
                       reason="lowers the primary metric on " +
                              ", ".join(f"{r['label']}@{r['eps']}: {r['cost_before']} -> {r['cost_after']}"
                                        for r in helped),
                       helped=[dict(label=r["label"], eps=r["eps"], before=r["cost_before"],
                                    after=r["cost_after"]) for r in helped])
        else:
            out.update(decision="reject", level=IDEA,
                       reason="fires and verifies, but lowers the primary metric on no circuit beyond "
                              "the current book")
    return _done(out)


def _done(out: dict) -> dict:
    out["seconds"] = round(time.time() - out.pop("t0"), 2)
    return out
