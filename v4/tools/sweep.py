"""Run the book over the whole DV suite and record it (the P0 gate, and the per-circuit "ours" row).

    .venv/bin/python -m v4.tools.sweep [--eps 1e-3] [--order best|min_all] [--out results/sweep_<tag>.json]
                                       [--only qft_8,qpe_8] [--no-memo] [--tag p0]

Prints one JSON line per circuit and a final total. The P0 gate compares these T-counts against v3's
(they must be identical) and the wall clock (>= 5x faster).
"""
from __future__ import annotations

import argparse
import json
import time

from .. import book as B
from ..judge import dv as J
from ..judge.frozen import check_frozen, frozen_state, recheck_frozen
from ..memo import optimize_memo, stats as memo_stats
from ..paths import MANIFEST, RESULTS
from ..runner import optimize


def dv_suite(only=None) -> list:
    cs = [c for c in json.loads(MANIFEST.read_text())["circuits"] if c["domain"] == "dv"]
    if only:
        cs = [c for c in cs if c["label"] in only]
    return cs


def sweep(eps=1e-3, order="best", only=None, memo=True, bk=None, **kw) -> dict:
    check_frozen()
    bk = B.book() if bk is None else bk
    rows, t_all = [], time.time()
    for c in dv_suite(only):
        t0 = time.time()
        if memo:
            res = optimize_memo(c["label"], bk, eps, order=order, **kw)
        else:
            start = J.load(c["label"])
            res = optimize(start, bk, eps, reference=start, order=order, **kw)
        rows.append(dict(label=c["label"], family=c["family"], t_count=res.cost["t_count"],
                         qubits=res.cost["qubits"], cx=res.cost.get("cx"), rotations=res.cost.get("rotations"),
                         err_rules=res.err_rules, err_bound=res.err_bound,
                         seconds=round(time.time() - t0, 2), **{k: v for k, v in res.summary().items()
                                                                if k in ("applications", "attempts",
                                                                         "priced_out", "verify_failures",
                                                                         "whole_checks", "certified")},
                         order_choice=res.order_choice, excluded=res.excluded, never_fired=res.never_fired))
        print(json.dumps(rows[-1], default=str), flush=True)
    return dict(eps=eps, order=order, book=[r.name for r in bk], book_digest=B.digest(bk),
                total_seconds=round(time.time() - t_all, 2), rows=rows,
                judge_cache=J.cache_stats(), memo=memo_stats(), frozen=frozen_state(),
                frozen_rechecked=recheck_frozen() if True else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eps", type=float, default=1e-3)
    ap.add_argument("--order", default="best")
    ap.add_argument("--only", default=None)
    ap.add_argument("--no-memo", action="store_true")
    ap.add_argument("--tag", default="sweep")
    ap.add_argument("--opcode-budget", type=int, default=None)
    a = ap.parse_args()
    out = sweep(a.eps, a.order, a.only.split(",") if a.only else None, memo=not a.no_memo,
                opcode_budget=a.opcode_budget)
    p = RESULTS / f"sweep_{a.tag}.json"
    p.write_text(json.dumps(out, default=str, indent=1) + "\n")
    print(json.dumps(dict(total_seconds=out["total_seconds"], t={r["label"]: r["t_count"] for r in out["rows"]},
                          wrote=str(p)), default=str), flush=True)


if __name__ == "__main__":
    main()
