"""P0 gate check: the runner with an EMPTY book returns every suite input unchanged with error 0.

    .venv/bin/python -m v3.tools.empty_book        -> appends one line per (circuit, eps) to v3/results/events.jsonl

DV: output must be the same object and serialize identically (QASM digest), err_rules == 0; the cost of the
unchanged input (T-count under the BQSKit convention) is recorded for reference. CV-DV: our start circuit (the IR
terms) is returned unchanged, err 0.
"""
from __future__ import annotations

import hashlib
import json
import time

from ..api.cvdv import start_circuit
from ..judge import dv as J
from ..judge.frozen import check_frozen
from ..paths import MANIFEST, RESULTS
from ..runner import optimize


def digest(c) -> str:
    text = c.to_qasm() if hasattr(c, "to_qasm") else repr([(g.name, g.qubits, g.cond) for g in c.gates])
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def main():
    n_frozen = check_frozen()
    m = json.loads(MANIFEST.read_text())
    RESULTS.mkdir(parents=True, exist_ok=True)
    ok_all = True
    for c in m["circuits"]:
        for eps in c.get("eps", [None]):
            t0 = time.time()
            if c["domain"] == "dv":
                circ = J.load(c["label"])
                d0 = digest(circ)
                r = optimize(circ, [], eps)
                ok = r.circuit is circ and digest(r.circuit) == d0 and r.err_rules == 0.0 and not r.log
                row = dict(event="p0_empty_book", label=c["label"], eps=eps, ok=ok, digest_in=d0,
                           digest_out=digest(r.circuit), err_rules=r.err_rules, err_bound=r.err_bound,
                           **{f"cost_{k}": v for k, v in r.cost.items() if k in ("t_count", "rotations", "cx", "qubits")})
            else:
                start = start_circuit(c["label"])        # every IR term as a placeholder, in IR order
                r = optimize(start, [], eps or 0.0, domain="cvdv")
                ok = r.circuit is start and r.err_rules == 0.0
                row = dict(event="p0_empty_book", label=c["label"], eps=eps, ok=ok, err_rules=r.err_rules,
                           n_terms=len(start["ops"]))
            row.update(seconds=round(time.time() - t0, 1), frozen_files_checked=n_frozen, time=time.time())
            ok_all &= ok
            with open(RESULTS / "events.jsonl", "a") as f:
                f.write(json.dumps(row) + "\n")
            print(json.dumps(row), flush=True)
    print("EMPTY-BOOK GATE:", "PASS" if ok_all else "FAIL")


if __name__ == "__main__":
    main()
