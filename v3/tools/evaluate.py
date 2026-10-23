"""Shared evaluation core of tools/admit.py (harness) and tools/test_rule.py (agent, read-only).

evaluate(path) runs the candidate, added to the current accepted book, on EVERY suite circuit of its domain at
every eps of the manifest (or one eps), and returns one report per (circuit, eps) plus a decision:

  1. static: the file imports only stdlib, numpy, scipy, sympy, v3.api*, and defines a valid RULE;
  2. verification: every application of the candidate anywhere verifies (one failure = reject, with circuit and
     location); checked BEFORE the improvement test, so a wrong rule is rejected for being wrong;
  3. never fires: if the trigger matches on no suite circuit the rule is NOT rejected; it is reported as
     "never_fires" (kept in rules/never_fires/, can be re-tested when the suite or book changes);
  4. runtime per circuit below the limit (default 120 s);
  5. improvement: adding it lowers the primary metric (DV T-count, CV-DV unsynthesized terms then total gates)
     on at least one circuit beyond the current book.
  6. superseding (admitted rules only): see superseded(); replaced rules are moved to rules/retired/ by admit.py.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
import time
from pathlib import Path

from ..api import Rule, cvdv as api_cvdv
from ..judge import dv as J
from ..judge.frozen import check_frozen
from ..paths import MANIFEST, RULES
from ..runner import optimize

ALLOWED_ROOTS = {"numpy", "scipy", "sympy"}
FORBIDDEN_ROOTS = {"pyzx", "pytket", "bqskit", "qiskit", "circuitevolve", "cvdv", "src"}
TIME_LIMIT = 120.0


def static_check(path: Path) -> str:
    """'' if the file only imports allowed modules, else the reason."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError as e:
        return f"syntax error: {e}"
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                return "relative import"
            names = [node.module or ""]
        for n in names:
            root = n.split(".")[0]
            if n == "v3.api" or n.startswith("v3.api."):
                continue
            if root in FORBIDDEN_ROOTS or root == "v3" or (root not in ALLOWED_ROOTS and
                                                           root not in sys.stdlib_module_names):
                return f"forbidden import {n!r}"
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("exec", "eval", "__import__", "open"):
            return f"forbidden call {node.func.id}()"
    return ""


def load_rule(path: Path) -> Rule:
    spec = importlib.util.spec_from_file_location(f"v3_rule_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    r = getattr(mod, "RULE", None)
    if not isinstance(r, Rule):
        raise TypeError("file does not define RULE = Rule(...)")
    if r.name != path.stem:
        raise ValueError(f"RULE.name {r.name!r} != file name {path.stem!r}")
    return r


def accepted_book() -> list:
    return [load_rule(p) for p in sorted((RULES / "accepted").glob("*.py"))]


def suite(domain: str) -> list:
    return [c for c in json.loads(MANIFEST.read_text())["circuits"] if c["domain"] == domain]


def _start(c):
    return J.load(c["label"]) if c["domain"] == "dv" else api_cvdv.start_circuit(c["label"])


def _primary(c, cost):
    return cost["t_count"] if c["domain"] == "dv" else (cost["unsynthesized"], cost["total"])


SMALL = ("qft_8", "adder_6", "mult_4", "modred_21")   # quick circuits test_rule runs after the target


def plan(domain: str, eps=None, target=None, small_only=False) -> list:
    """[(manifest entry, eps)] in run order. target first; small_only = target + SMALL (test_rule)."""
    cs = suite(domain)
    if small_only:
        names = ([target] if target else []) + [n for n in SMALL if n != target]
        cs = [next(c for c in cs if c["label"] == n) for n in names if any(c["label"] == n for c in cs)]
    elif target:
        cs = sorted(cs, key=lambda c: c["label"] != target)
    return [(c, e) for c in cs for e in (c.get("eps") or [None]) if eps is None or e is None or e == eps]


def evaluate(path, time_limit: float = TIME_LIMIT, book=None, eps=None, target=None, small_only=False,
             stop_at_first_failure=False) -> dict:
    check_frozen()
    path = Path(path)
    out = dict(candidate=str(path), static="", circuits=[], decision=None, reason="")
    bad = static_check(path)
    if bad:
        out.update(static=bad, decision="reject", reason=f"static check: {bad}")
        return out
    try:
        rule = load_rule(path)
    except Exception as e:  # noqa: BLE001  (any failure to define a valid RULE is a static reject)
        out.update(static=f"{type(e).__name__}: {e}", decision="reject", reason=f"invalid RULE: {e}")
        return out
    book = accepted_book() if book is None else book
    out["rule"] = dict(name=rule.name, domain=rule.domain, kind=rule.kind, contract=rule.contract)
    for c, eps_c in plan(rule.domain, eps, target, small_only):
        for eps in (eps_c,):
            t0 = time.time()
            start = _start(c)
            n_match = len(rule.trigger(start))
            row = dict(label=c["label"], eps=eps, matches_on_input=n_match)
            base = optimize(start, book, eps or 0.0, domain=c["domain"], label=c["label"])
            with_r = optimize(start, book + [rule], eps or 0.0, domain=c["domain"], label=c["label"],
                              time_limit=time_limit)
            mine = [e for e in with_r.log if e["rule"] == rule.name]
            fails = [e for e in mine if not e.get("verified", True)]
            if any(e.get("timeout") for e in mine):
                row["timeout"] = True
            row.update(fired=bool(mine), applications_tried=len(mine), verified=sum(e.get("verified", False)
                                                                                    for e in mine),
                       accepted=sum(e["accepted"] for e in mine), timeout=any(e.get("timeout") for e in mine),
                       seconds=round(time.time() - t0, 1),
                       certified=all(e.get("certified", False) for e in mine if e.get("verified")),
                       verify_methods=sorted({e.get("method") for e in mine if e.get("method")}))
            if fails:
                f = fails[0]
                row["first_failure"] = dict(match=f["match"], mode=f.get("mode"), method=f.get("method"),
                                            distance=f.get("distance"), reason=f.get("reason"))
            if mine and c["domain"] == "dv":
                row.update(cost_before=_primary(c, base.cost), cost_after=_primary(c, with_r.cost),
                           qubits_before=base.cost["qubits"], qubits_after=with_r.cost["qubits"],
                           err_bound=with_r.err_bound, err_rules=with_r.err_rules)
            elif mine:
                row.update(cost_before=_primary(c, base.cost) if base.cost else None,
                           cost_after=_primary(c, with_r.cost) if with_r.cost else None)
            out["circuits"].append(row)
            if stop_at_first_failure and "first_failure" in row:
                out["stopped_early"] = f"first verification failure on {c['label']}"
                break
        if out.get("stopped_early"):
            break
    rows = out["circuits"]
    failed = [r for r in rows if "first_failure" in r]
    if failed:
        r = failed[0]
        out.update(decision="reject", reason=f"verification failed on {r['label']} (eps {r['eps']}): "
                                             f"{r['first_failure']}")
    elif not any(r["fired"] for r in rows):
        out.update(decision="never_fires", reason=f"trigger matched on none of the {len(rows)} suite runs of "
                                                  f"domain {rule.domain}")
    elif any(r["timeout"] or r["seconds"] > time_limit for r in rows):
        r = next(r for r in rows if r["timeout"] or r["seconds"] > time_limit)
        out.update(decision="reject", reason=f"runtime limit {time_limit}s exceeded on {r['label']}")
    else:
        helped = [r for r in rows if r.get("cost_after") is not None and r["cost_after"] < r["cost_before"]]
        if helped:
            out.update(decision="admit", reason="lowers the primary metric on " +
                       ", ".join(f"{r['label']}@{r['eps']}: {r['cost_before']} -> {r['cost_after']}" for r in helped),
                       helped=[dict(label=r["label"], eps=r["eps"], before=r["cost_before"], after=r["cost_after"])
                               for r in helped])
        else:
            out.update(decision="reject", reason="fires and verifies, but lowers the primary metric on no circuit "
                                                 "beyond the current book")
    if out["decision"] == "admit" and book:
        out["supersedes"] = superseded(rule, book, eps, time_limit)
    return out


def superseded(new, book, eps=None, time_limit: float = TIME_LIMIT) -> list:
    """Accepted rules the new one replaces. Operational test on the suite (each rule run ALONE, at the admission
    eps): the new rule fires on every circuit where the old one fires (its matches cover the old one's), its T-count
    is <= the old one's on every circuit, and strictly lower on at least one."""
    out = []
    for old in book:
        if old.domain != new.domain:
            continue
        ev, ok, strict = [], True, False
        for c, e in plan(new.domain, eps):
            start = _start(c)
            ro = optimize(start, [old], e or 0.0, domain=c["domain"], label=c["label"], time_limit=time_limit)
            rn = optimize(start, [new], e or 0.0, domain=c["domain"], label=c["label"], time_limit=time_limit)
            fo = any(x["accepted"] for x in ro.log)
            fn = any(x["accepted"] for x in rn.log)
            to, tn = _primary(c, ro.cost), _primary(c, rn.cost)
            ev.append(dict(label=c["label"], eps=e, old_fires=fo, new_fires=fn, old=to, new=tn))
            if (fo and not fn) or tn > to:
                ok = False
                break
            strict |= tn < to
        if ok and strict:
            out.append(dict(rule=old.name, evidence=ev))
    return out
