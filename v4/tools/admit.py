"""Harness-side admission (V4_README 5.2; never run by the agent).

    .venv/bin/python -m v4.tools.admit <rules/candidates/name.py> [--origin "..."] [--eps 1e-3]
    .venv/bin/python -m v4.tools.admit --from-reevaluate results/reevaluate_p6.json   # batch

Runs `evaluate`, and on `admit` runs the ORDER-SAFE re-run of V4_README 5.2 before touching the book:
the whole suite is re-measured under `min(book_order, gain_order, best_single_rule)` and the rule is
refused if it raises T on any circuit or lowers it on none. Only then is the file moved to
`rules/accepted/`.

Where the file lands:
    admit         -> rules/accepted/           (+ BOOK.md regenerated)
    reject        -> rules/rejected/           (+ <name>.reason.json)
    never_fires   -> rules/never_fires/        (+ <name>.reason.json)  - NOT a rejection; it can be
                                               re-tested whenever the suite or the book changes
    not_evaluated -> stays in candidates/      - the harness ran out of wall clock. Never a rejection.

Everything is appended to `results/events.jsonl`.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from .. import book as B
from ..loop import LoopConfig, admit as order_safe_admit
from ..paths import RESULTS, RULES
from .evaluate import evaluate

FOLDER = dict(admit="accepted", reject="rejected", never_fires="never_fires")


def admit_one(path: Path, origin: str = "harness", eps: float = 1e-3, cfg: LoopConfig | None = None,
              dry: bool = False) -> dict:
    cfg = cfg or LoopConfig(eps=eps)
    t0 = time.time()
    rep = evaluate(path, eps=eps)
    rep.update(event="admission", origin=origin, candidate=str(path), time=time.time())
    if rep["decision"] == "admit":
        rule = B.load_rule(path, "accepted")
        bk, rec = order_safe_admit(rule, B.book(), cfg)
        rep["admission"] = rec
        if rec.get("refused"):
            rep.update(decision="reject", level="idea", reason=rec["refused"])
    rep["seconds"] = round(time.time() - t0, 1)
    if dry:
        return rep
    dest_dir = RULES / FOLDER.get(rep["decision"], "candidates")
    dest_dir.mkdir(parents=True, exist_ok=True)
    if rep["decision"] != "admit":
        (dest_dir / f"{path.stem}.reason.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    if dest_dir != path.parent:
        shutil.move(str(path), dest_dir / path.name)
        rep["moved_to"] = str((dest_dir / path.name).relative_to(RULES.parent))
    if rep["decision"] == "admit":
        B.write_book_md()
    with open(RESULTS / "events.jsonl", "a") as f:
        f.write(json.dumps(rep, default=str) + "\n")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate", nargs="?")
    ap.add_argument("--from-reevaluate", default=None,
                    help="a results/reevaluate_*.json: admit every rule it decided `admit`, in the order "
                         "it found them (so each admission sees the book the previous one left)")
    ap.add_argument("--origin", default="harness")
    ap.add_argument("--eps", type=float, default=1e-3)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.from_reevaluate:
        data = json.loads(Path(a.from_reevaluate).read_text())
        names = [r["candidate"] for r in data["rows"] if r.get("decision") == "admit"]
        print(json.dumps(dict(to_admit=[Path(n).stem for n in names])))
        for n in names:
            p = Path(n)
            if not p.is_file():
                print(json.dumps(dict(skipped=str(p), why="not in candidates/ any more")))
                continue
            rep = admit_one(p, f"re-evaluated v3 rule ({a.origin})", a.eps, dry=a.dry)
            print(json.dumps(dict(rule=p.stem, decision=rep["decision"],
                                  helped=rep.get("admission", {}).get("helped"),
                                  reason=rep["reason"][:200], seconds=rep["seconds"])))
        return
    if not a.candidate:
        ap.error("pass a candidate file or --from-reevaluate")
    rep = admit_one(Path(a.candidate).resolve(), a.origin, a.eps, dry=a.dry)
    print(json.dumps(dict(rule=Path(a.candidate).stem, decision=rep["decision"],
                          reason=rep["reason"][:300], helped=rep.get("admission", {}).get("helped"),
                          moved_to=rep.get("moved_to"), seconds=rep["seconds"]), indent=1))


if __name__ == "__main__":
    main()
