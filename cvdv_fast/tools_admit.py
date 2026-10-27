"""Harness-side admission (never run by the LLM).

    python -m cvdv_fast.tools_admit rules/candidates/<name>.py --origin "LLM (attempt k)"

1. static check (AST): imports only cvdv_fast.api / math / cmath; no exec/eval/open/compile/__import__/globals,
   no dunder attributes, no os/sys/subprocess names.
2. load RULE; well-formedness (kind, contract, callables).
3. per-instance window checks (synth: every benchmark part of a matching kind, r = 1,2,4..; recorded).
4. book + candidate compiled on all 5 benchmarks (whole-circuit check skipped here), vs book alone (cached in
   results/book_state.json). Decision:
     never_fires  rule never chosen / never applied on any benchmark
     reject       any benchmark gets worse (cost key or validity), exception, or verification failure on use
     admit        >= 1 benchmark strictly better, none worse, AND every improved benchmark passes the frozen
                  whole-circuit check (max probe infidelity <= eps at both cutoffs)
5. file moved to rules/{accepted,rejected,never_fires}/, reason JSON written, BOOK.md row on admit.
Prints one JSON line (the report).
"""
from __future__ import annotations

import argparse
import ast
import json
import shutil
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cvdv_fast import paths, runner  # noqa: E402
from cvdv_fast.judge import verify as V  # noqa: E402

BANNED = {"exec", "eval", "open", "compile", "__import__", "globals", "locals", "vars", "getattr", "setattr",
          "delattr", "os", "sys", "subprocess", "input", "breakpoint", "importlib", "builtins"}
DEFER_WHOLE = {"electronicVibration_small"}  # 9 qumodes: whole check only in the final evaluation
ALLOWED_IMPORTS = {"cvdv_fast.api", "math", "cmath", "itertools", "functools"}


def static_check(src):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name not in ALLOWED_IMPORTS:
                    raise ValueError(f"import {a.name} not allowed")
        if isinstance(node, ast.ImportFrom) and node.module not in ALLOWED_IMPORTS:
            raise ValueError(f"from {node.module} import not allowed")
        if isinstance(node, ast.Name) and node.id in BANNED:
            raise ValueError(f"name {node.id} not allowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError(f"dunder attribute {node.attr}")


def key(r):
    if not r.get("valid", False) and r.get("reason"):
        return (1, 10 ** 9, 10 ** 9, 10 ** 9)
    return (0 if r.get("valid") else 1, r["duration"], r["two_op"], r["one_op"])


def compile_all(rules):
    out = {}
    for lab in paths.BENCH:
        try:
            r = runner.compile_benchmark(lab, rules, whole=False)
        except Exception:  # noqa: BLE001
            r = dict(label=lab, valid=False, reason="exception", err=traceback.format_exc()[-800:])
        r.pop("_phys_ops", None); r.pop("_final_map", None)
        out[lab] = r
    return out


def book_state(book):
    names = sorted(r.name for r in book)
    p = paths.RESULTS / "book_state.json"
    if p.exists():
        d = json.loads(p.read_text())
        if d.get("book") == names:
            return d["results"]
    res = compile_all(book)
    p.write_text(json.dumps(dict(book=names, results=res), default=str))
    return res


def instance_checks(rule):
    rows = []
    if rule.kind != "synth":
        return rows
    for lab in paths.BENCH:
        items = runner._parts(lab)
        nq, nm = runner._sys_sizes(items)
        seen = set()
        for k, part, H in items:
            if part.kind not in rule.term_kinds or (part.kind, part.label, len(part.wires)) in seen:
                continue
            seen.add((part.kind, part.label, len(part.wires)))
            for r in (1, 4, 16) if rule.contract == "approx" else (1,):
                try:
                    ops = runner._emit(rule, part, nq, nm, r)
                except Exception as e:  # noqa: BLE001
                    rows.append(dict(label=lab, part=repr(part), r=r, error=repr(e)[:200])); continue
                if ops is None:
                    rows.append(dict(label=lab, part=repr(part), r=r, declined=True)); continue
                d = V.window_check(H, ops)["dist"]
                m = runner.key_of(ops)[1]
                rows.append(dict(label=lab, part=repr(part), r=r, dist=d, **m))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--origin", default="LLM")
    ap.add_argument("--mechanism", default="")
    a = ap.parse_args()
    t0 = time.time()
    path = Path(a.candidate)
    rep = dict(file=str(path), origin=a.origin, mechanism=a.mechanism)
    try:
        static_check(path.read_text())
        rule = runner.load_rule(path)
        assert rule.kind in ("synth", "rewrite") and rule.contract in ("exact", "approx"), "bad kind/contract"
        if rule.kind == "synth":
            assert callable(rule.synth) and rule.term_kinds, "synth rule needs synth() and term_kinds"
        else:
            assert callable(rule.trigger) and callable(rule.apply), "rewrite rule needs trigger() and apply()"
        rep["rule"] = dict(name=rule.name, kind=rule.kind, contract=rule.contract, idea=rule.idea,
                           term_kinds=list(rule.term_kinds), stage=rule.stage)
    except Exception as e:  # noqa: BLE001
        rep.update(decision="reject", reason=f"static/load: {e!r}"[:600])
        return finish(path, rep, t0)
    rep["instances"] = instance_checks(rule)
    book = runner.load_book()
    base = book_state(book)
    new = compile_all(book + [rule])
    used = False
    better, worse, rows = [], [], []
    for lab in paths.BENCH:
        b, n = base[lab], new[lab]
        if rule.kind == "synth":
            u = any(p.get("rule") == rule.name for p in n.get("parts", []))
        else:
            u = any(x.get("rule") == rule.name for x in n.get("rewrites", []))
        used |= u
        kb, kn = key(b), key(n)
        rows.append(dict(label=lab, used=u, before=dict(valid=b.get("valid"), total=b.get("total"), two_op=b.get("two_op"),
                                                         duration=b.get("duration"), reason=b.get("reason")),
                         after=dict(valid=n.get("valid"), total=n.get("total"), two_op=n.get("two_op"),
                                    duration=n.get("duration"), reason=n.get("reason"), err_ledger=n.get("err_ledger"))))
        if u and kn < kb:
            better.append(lab)
        elif u and kn > kb:
            worse.append(lab)
    rep["per_benchmark"] = rows
    fails = [x for lab in paths.BENCH for x in new[lab].get("log", []) if x.get("rule") == rule.name]
    rep["rule_failures"] = fails[:10]
    if not used:
        rep.update(decision="never_fires", reason="rule never chosen/applied on any benchmark "
                   + (f"(failures: {fails[:3]})" if fails else ""))
        return finish(path, rep, t0)
    if worse:
        rep.update(decision="reject", reason=f"worse on {worse}")
        return finish(path, rep, t0)
    if not better:
        rep.update(decision="reject", reason="no improvement on any benchmark (fires but not cheaper)")
        return finish(path, rep, t0)
    whole = {}
    for lab in [x for x in better if x not in DEFER_WHOLE]:
        r = runner.compile_benchmark(lab, book + [rule], whole=True, whole_cutoffs=paths.WHOLE_CUTOFFS.get(lab))
        whole[lab] = dict(max_infid=r.get("max_infid"), cutoff_gap=r.get("cutoff_gap"), valid=r.get("valid"))
    rep["whole_check"] = whole
    rep["whole_check_deferred"] = [x for x in better if x in DEFER_WHOLE]
    if not all(w["valid"] for w in whole.values()):
        rep.update(decision="reject", reason=f"whole-circuit check failed: {whole}")
        return finish(path, rep, t0)
    rep.update(decision="admit", improved=better)
    return finish(path, rep, t0)


def finish(path, rep, t0):
    folder = {"admit": "accepted", "reject": "rejected", "never_fires": "never_fires"}[rep["decision"]]
    dest = paths.RULES / folder / path.name
    if path.resolve() != dest.resolve():
        shutil.move(str(path), dest)
    rep["moved_to"] = str(dest.relative_to(paths.ROOT))
    rep["seconds"] = round(time.time() - t0, 1)
    (paths.RULES / folder / (path.stem + ".reason.json")).write_text(json.dumps(rep, indent=1, default=str))
    if rep["decision"] == "admit":
        r = rep["rule"]
        helped = "; ".join(f"{x['label']}: {x['before']['total']}/{x['before']['duration']} -> "
                           f"{x['after']['total']}/{x['after']['duration']}" for x in rep["per_benchmark"]
                           if x["label"] in rep["improved"])
        row = f"| {r['name']} | {rep['origin']} | {r['kind']} | {r['contract']} | {rep['mechanism']} | " \
              f"{r['idea'].replace('|', '/')} | {helped} |\n"
        book = paths.RULES / "BOOK.md"
        if not book.exists():
            book.write_text("# cvdv_fast rule book (written by tools_admit.py)\n\n| name | origin | kind | contract | "
                            "mechanism | idea | helped (gates/duration before -> after) |\n|---|---|---|---|---|---|---|\n")
        with open(book, "a") as f:
            f.write(row)
        (paths.RESULTS / "book_state.json").unlink(missing_ok=True)
    with open(paths.RESULTS / "events.jsonl", "a") as f:
        f.write(json.dumps(rep, default=str) + "\n")
    print(json.dumps(rep, default=str))


if __name__ == "__main__":
    main()
