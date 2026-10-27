"""Harness-side admission (SPEC section 7; never run by the agent).

    .venv/bin/python -m v3.tools.admit <rules/candidates/name.py> [--origin "hand-written (P1)"] [--limit 120] [--eps 1e-3]

Runs tools/evaluate.evaluate and moves the file: admit -> rules/accepted/ (+ BOOK.md row); reject ->
rules/rejected/ with <name>.reason.json; never_fires -> rules/never_fires/ with <name>.reason.json (not a reject).
Appends the full report to v3/results/events.jsonl.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from ..paths import RESULTS, RULES
from .evaluate import evaluate

FOLDER = {"admit": "accepted", "reject": "rejected", "never_fires": "never_fires"}


def book_row(rep: dict, idea: str, origin: str) -> str:
    r = rep["rule"]
    helped = "; ".join(f"{h['label']}@{h['eps']}: {h['before']} -> {h['after']}" for h in rep.get("helped", []))
    idea = idea.replace("|", "/").replace("\n", " ")
    return f"| {r['name']} | accepted ({origin}) | {r['kind']} | {r['contract']} | {idea} | {helped} |"


def retire_in_book(old: str, new: str):
    book = RULES / "BOOK.md"
    lines = book.read_text().splitlines()
    row = next((l for l in lines if l.startswith(f"| {old} | accepted")), None)
    if row is None:
        return
    lines.remove(row)
    text = "\n".join(lines) + "\n"
    if "\n## Retired" not in text:
        text += "\n## Retired (superseded; rules/retired/)\n\n| name | replaced by | former row |\n|---|---|---|\n"
    text += f"| {old} | {new} | {row.replace('|', '/')} |\n"
    book.write_text(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--origin", default="LLM")
    ap.add_argument("--limit", type=float, default=120.0)
    ap.add_argument("--eps", type=float, default=None, help="only this eps (P2: 1e-3)")
    a = ap.parse_args()
    src = Path(a.candidate).resolve()
    t0 = time.time()
    rep = evaluate(src, time_limit=a.limit, eps=a.eps)
    rep.update(event="admission", origin=a.origin, seconds=round(time.time() - t0, 1), time=time.time())
    dest_dir = RULES / FOLDER[rep["decision"]]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if rep["decision"] == "admit":
        from .evaluate import load_rule
        idea = load_rule(src).idea
        book = RULES / "BOOK.md"
        text = book.read_text().replace("\n_Empty: no rules admitted yet (P0)._\n", "\n")
        head, sep, tail = text.partition("\n## Hand-written")     # rows go into the main (first) table
        book.write_text(head.rstrip("\n") + "\n" + book_row(rep, idea, a.origin) + "\n" + (sep + tail if sep else ""))
        for sup in rep.get("supersedes", []):
            old = RULES / "accepted" / f"{sup['rule']}.py"
            if old.exists():
                (RULES / "retired").mkdir(exist_ok=True)
                shutil.move(str(old), RULES / "retired" / old.name)
                (RULES / "retired" / f"{sup['rule']}.reason.json").write_text(json.dumps(
                    dict(rule=sup["rule"], status="retired", replaced_by=rep["rule"]["name"], evidence=sup["evidence"],
                         time=time.time()), indent=1) + "\n")
                retire_in_book(sup["rule"], rep["rule"]["name"])
    else:
        (dest_dir / f"{src.stem}.reason.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    shutil.move(str(src), dest)
    rep["moved_to"] = str(dest)
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "events.jsonl", "a") as f:
        f.write(json.dumps(rep, default=str) + "\n")
    print(json.dumps(dict(rule=rep.get("rule", {}).get("name", src.stem), decision=rep["decision"],
                          reason=rep["reason"], supersedes=[x["rule"] for x in rep.get("supersedes", [])], moved_to=str(dest.relative_to(RULES.parent)),
                          seconds=rep["seconds"])))


if __name__ == "__main__":
    main()
