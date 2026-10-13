"""Build results/evolve_opt/dev_table.csv and the data block of DEV_REPORT.md from run summaries.

Every number is read from results/evolve_opt/<tag>/summary.json, calls.jsonl / evals.jsonl and
baseline_dev.json; nothing is recomputed here.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
R = REPO / "results" / "evolve_opt"


def load(tag):
    p = R / tag / "summary.json"
    return json.loads(p.read_text()) if p.exists() else None


def llm_trajectory(tag):
    """Best FAST / dev geomean after each proposer call (from calls.jsonl)."""
    best_dev, best_fast, out = math.inf, math.inf, []
    for line in (R / tag / "calls.jsonl").read_text().splitlines():
        d = json.loads(line)
        if d["kind"] == "seed":
            best_fast = d["fast"]["geomean"]
            best_dev = d["dev"]["geomean"] if d.get("dev") else math.inf
            continue
        if d["kind"] != "proposer":
            continue
        f, v = d.get("fast"), d.get("dev")
        if f and f["valid"]:
            best_fast = min(best_fast, f["geomean"])
        if v and v["valid"]:
            best_dev = min(best_dev, v["geomean"])
        out.append((d["call"], best_fast, best_dev))
    return out


def control_trajectory(tag):
    best_dev, out = math.inf, []
    for line in (R / tag / "evals.jsonl").read_text().splitlines():
        d = json.loads(line)
        if d.get("dev") and d["dev"]["valid"]:
            best_dev = min(best_dev, d["dev"]["geomean"])
        out.append((d["i"], best_dev))
    return out


def llm_cost(tag):
    tok_in = tok_out = n = refl = 0
    s = load(tag)
    be = s.get("backend", {}) if s else {}
    return dict(calls=be.get("calls", 0), ok=be.get("ok", 0), input_tokens=be.get("input_tokens", 0),
                output_tokens=be.get("output_tokens", 0), proposer=s["stats"]["proposer_calls"] if s else 0,
                reflector=s["stats"]["reflector_calls"] if s else 0)


def main(llm_tags, control_tags, out_csv=R / "dev_table.csv"):
    ref = json.loads((R / "baseline_dev.json").read_text())
    runs = {}
    for t in llm_tags + control_tags:
        s = load(t)
        if s:
            runs[t] = s
    first = runs[next(iter(runs))]
    dev = first["dev"]
    seed_res = first["seed_program"]["dev"]
    cols = ["circuit", "n", "best_classical_pipeline", "best_classical_T", "seed_program_T"] + \
           [f"{t}_T" for t in runs]
    rows = []
    for nm in dev:
        row = dict(circuit=nm, n=ref[nm]["n"], best_classical_pipeline=ref[nm]["best"], best_classical_T=ref[nm]["t"],
                   seed_program_T=seed_res["t"][nm])
        for t, s in runs.items():
            row[f"{t}_T"] = s["best"]["dev"]["t"][nm]
        rows.append(row)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    summ = {t: dict(dev_geomean=s["best"]["dev"]["geomean"], fast_geomean=s["best"]["fast"]["geomean"],
                    runtime=s["best"]["dev"]["runtime"], hash=s["best"]["hash"][:16],
                    found_at=s["best"].get("call", s["best"].get("i")),
                    total_T=sum(s["best"]["dev"]["t"].values())) for t, s in runs.items()}
    summ["_seed_program"] = dict(dev_geomean=seed_res["geomean"], runtime=seed_res["runtime"],
                                 total_T=sum(seed_res["t"].values()))
    summ["_best_classical"] = dict(dev_geomean=1.0, total_T=sum(ref[nm]["t"] for nm in dev))
    return dict(rows=rows, summary=summ, cost={t: llm_cost(t) for t in llm_tags if t in runs},
                traj={t: llm_trajectory(t) for t in llm_tags if t in runs},
                ctraj={t: control_trajectory(t) for t in control_tags if t in runs})


if __name__ == "__main__":
    llm = [a for a in sys.argv[1:] if a.startswith("evo_")]
    ctl = [a for a in sys.argv[1:] if a.startswith("control_")]
    print(json.dumps(main(llm, ctl)["summary"], indent=1))
