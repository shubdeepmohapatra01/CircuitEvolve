"""Run the current book (rules/accepted/) on every DV circuit at eps 1e-3 -> append to v3/results/p2/ours.jsonl.

    .venv/bin/python -m v3.report.ours --reason "<why>"

One row per circuit: T-count, qubits, CNOT, rotations, error bound, whether any accepted application used a
relaxed rule (hatched in figures), certified (all checks proofs), per-rule application counts. Hand-written P1
rules (rules/handwritten/) are NOT loaded.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter

from ..judge import dv as J
from ..paths import RESULTS
from ..runner import optimize
from ..tools.evaluate import accepted_book, suite

EPS = 1e-3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reason", default="")
    a = ap.parse_args()
    book = accepted_book()
    out = RESULTS / "p2"
    out.mkdir(parents=True, exist_ok=True)
    for c in suite("dv"):
        t0 = time.time()
        r = optimize(J.load(c["label"]), book, EPS, time_limit=300)
        contract = {x.name: x.contract for x in book}
        acc = [e for e in r.log if e["accepted"]]
        row = dict(time=time.time(), reason=a.reason, book=[x.name for x in book], label=c["label"], eps=EPS,
                   t_count=r.cost["t_count"], qubits=r.cost["qubits"], cx=r.cost["cx"],
                   rotations=r.cost.get("rotations", 0), err_bound=r.err_bound, err_rules=r.err_rules,
                   relaxed=any(contract[e["rule"]] == "relaxed" for e in acc),
                   certified=r.summary()["certified"], applications=dict(Counter(e["rule"] for e in acc)),
                   verify_failures=r.summary()["verify_failures"], timeout=any(e.get("timeout") for e in r.log),
                   seconds=round(time.time() - t0, 1))
        with open(out / "ours.jsonl", "a") as f:
            f.write(json.dumps(row) + "\n")
        print(json.dumps({k: row[k] for k in ("label", "t_count", "qubits", "relaxed", "applications")}), flush=True)


if __name__ == "__main__":
    main()
