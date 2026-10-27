"""The FLOOR GUARANTEE check (V4_README section 4): the floor tier ALONE vs the best baseline.

    .venv/bin/python -m v4.tools.floor_gate [--eps 1e-3] [--order min_all] [--tag p2]

> On every circuit, the floor tier alone must reach the best of every baseline - pyzx, or DPF at any k,
> whichever is lower on that circuit - using only Python over `v4.api`.

So the LLM's worst case is "ties the best baseline", and every attempt is scored against that rather than
against zero. The report prints, per circuit: the floor's T, the best baseline's T and method, and whether
the guarantee holds. `--order min_all` is the admission ordering of section 5.2
(`min(book_order, gain_order, best_single_rule)`), so the floor can never score worse than one of its own
rules.
"""
from __future__ import annotations

import argparse
import csv
import json
import time

from .. import book as B
from ..baselines import best_baseline
from ..judge.frozen import check_frozen
from ..memo import optimize_memo
from ..paths import RESULTS
from .evaluate import suite


def floor_gate(eps: float = 1e-3, order: str = "min_all", only=None) -> dict:
    check_frozen()
    bk = B.floor_tier()
    rows = []
    for c in suite("dv"):
        if only and c["label"] not in only:
            continue
        if c["family"] != "dv_angle":
            continue                         # the floor is the ANGLE baselines (pyzx / DPF)
        t0 = time.time()
        res = optimize_memo(c["label"], bk, eps, order=order)
        bb = best_baseline(c["label"], eps)
        rows.append(dict(label=c["label"], floor_t=res.cost["t_count"], floor_qubits=res.cost["qubits"],
                         best_baseline_t=bb["t_count"], best_baseline=bb["method"],
                         gap=res.cost["t_count"] - bb["t_count"],
                         meets=res.cost["t_count"] <= bb["t_count"],
                         err_bound=res.err_bound, order_choice=res.order_choice,
                         seconds=round(time.time() - t0, 2)))
        print(json.dumps(rows[-1], default=str), flush=True)
    return dict(eps=eps, order=order, floor=[r.name for r in bk], rows=rows,
                guarantee_met=all(r["meets"] for r in rows),
                met_on=[r["label"] for r in rows if r["meets"]],
                missing=[dict(label=r["label"], floor=r["floor_t"], target=r["best_baseline_t"],
                              method=r["best_baseline"], gap=r["gap"]) for r in rows if not r["meets"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eps", type=float, default=1e-3)
    ap.add_argument("--order", default="min_all")
    ap.add_argument("--only", default=None)
    ap.add_argument("--tag", default="floor")
    a = ap.parse_args()
    out = floor_gate(a.eps, a.order, a.only.split(",") if a.only else None)
    p = RESULTS / f"floor_gate_{a.tag}.json"
    p.write_text(json.dumps(out, default=str, indent=1) + "\n")
    print(json.dumps(dict(guarantee_met=out["guarantee_met"], missing=out["missing"], wrote=str(p)),
                     default=str))


if __name__ == "__main__":
    main()
