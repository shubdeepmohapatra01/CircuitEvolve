"""Comparison table + figures + summary for cvdv_fast (Genesis vs ours)."""
import json, sys
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
BENCH = ["kerr_small", "boseHubbard_small", "z2Higgs_small", "heisenberg_small", "electronicVibration_small"]
SHORT = {"kerr_small": "Kerr", "boseHubbard_small": "Bose-Hubbard", "z2Higgs_small": "Z2-Higgs",
         "heisenberg_small": "Heisenberg", "electronicVibration_small": "Electron-vib."}
tag = sys.argv[1] if len(sys.argv) > 1 else "final"
ours = {}
for t in (tag, "final_ev2"):
    f = ROOT / "results" / t / "results.jsonl"
    if f.exists():
        for l in open(f):
            d = json.loads(l); ours.setdefault(d["label"], d)
exact = {}
ef = ROOT / "report" / "exact_evolution.jsonl"
if ef.exists():
    for l in open(ef):
        d = json.loads(l); exact[(d["label"], d["who"])] = d
v3 = {json.loads(l)["label"]: json.loads(l) for l in open(ROOT.parent / "v3/baselines/genesis/judged.jsonl")}
rows = []
for b in BENCH:
    gp = ROOT / "baselines" / f"genesis_{b}.json"
    g = json.loads(gp.read_text()) if gp.exists() and gp.stat().st_size else None
    if g is None:  # kerr: physical circuit too large (19 q + 19 qm); v3 logical-level error
        j = v3[b]
        g = dict(one_op=j["one_op"], two_op=j["two_op"], total=j["total"], duration=j["duration"],
                 max_infid=j["err_exact"], err_note="logical circuit, v3 judge (per-mode cutoffs 16/22)")
    o = ours.get(b, {})
    rows.append(dict(benchmark=b, genesis_total=g["total"], genesis_2op=g["two_op"], genesis_duration=g["duration"],
                     genesis_max_infid=g["max_infid"], genesis_err_note=g.get("err_note", "physical circuit, cvdv_fast judge"),
                     ours_valid=o.get("valid"), ours_total=o.get("total"), ours_2op=o.get("two_op"),
                     ours_duration=o.get("duration"), ours_max_infid=o.get("max_infid"), ours_err_ledger=o.get("err_ledger"),
                     ours_cutoff_gap=o.get("cutoff_gap"), ours_reason=o.get("reason", ""),
                     ideal_trotter_vs_exact=exact.get((b, "ours"), {}).get("ideal_trotter_vs_exact_max"),
                     ours_vs_exact=exact.get((b, "ours"), {}).get("max_infid_vs_exact"),
                     genesis_vs_exact=exact.get((b, "genesis"), {}).get("max_infid_vs_exact"),
                     ours_rules=sorted({p["rule"] for p in o.get("parts", [])} | {x["rule"] for x in o.get("rewrites", [])})))
import csv
with open(ROOT / "report" / "comparison.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader()
    for r in rows: w.writerow({k: (";".join(v) if isinstance(v, list) else v) for k, v in r.items()})
for r in rows:
    print(r["benchmark"], r["genesis_total"], r["genesis_2op"], r["genesis_duration"], f'{r["genesis_max_infid"]:.3g}', '|',
          r["ours_valid"], r["ours_total"], r["ours_2op"], r["ours_duration"], r["ours_max_infid"], '| exact:', r["ideal_trotter_vs_exact"], r["ours_vs_exact"], r["genesis_vs_exact"])
