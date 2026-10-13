"""Subprocess entry: python -m circuitevolve.legacy.evolve_opt.child job.json out.json

Reads {source, n, orig (ops json), budget, cache}; runs optimize(circ, tools, budget) under the restricted
exec; writes {ok, ops, ledger, charged_s, cpu_s, calls, error}. The parent re-verifies everything it reports.
"""
from __future__ import annotations

import json
import sys
import time
import traceback


def main(job_path: str, out_path: str) -> None:
    from .sandbox import restricted_exec
    from .toolbox import Circ, Toolbox, ops_from_json, ops_to_json, _is_clifford_rz
    job = json.loads(open(job_path).read())
    t0, c0 = time.time(), time.process_time()
    res = dict(ok=False)
    try:
        ns = restricted_exec(job["source"])
        n = int(job["n"])
        budget = dict(job["budget"])
        tools = Toolbox(n, time_s=float(budget.get("time_s", 120.0)), cache=bool(job.get("cache", True)))
        circ = Circ(ops_from_json(job["orig"]), n)
        out = ns["optimize"](circ, tools, budget)
        if not isinstance(out, Circ):
            raise TypeError(f"optimize returned {type(out).__name__}, not a circuit handle")
        if out is circ or not _is_clifford_rz(out._ops):
            raise TypeError("optimize must return a Clifford+Rz tool output (e.g. tools.lower(circ))")
        res = dict(ok=True, ops=ops_to_json(out._ops), ledger=tools._ledger, charged_s=tools._charged,
                   calls=tools._calls, approx=tools._approx_log)
    except BaseException as e:                      # noqa: BLE001 - report everything to the parent
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"line {f.lineno}" for f in reversed(tb) if f.filename == "<program>"), "")
        res = dict(ok=False, error=f"{type(e).__name__}: {str(e)[:300]} {where}".strip())
    res["cpu_s"] = time.process_time() - c0
    res["child_wall_s"] = time.time() - t0
    with open(out_path + ".tmp", "w") as f:
        json.dump(res, f)
    import os
    os.replace(out_path + ".tmp", out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
