"""Pick the best Genesis seed per CV-DV circuit (min total gates; tie -> lowest seed) and judge it.

    python v3/baselines/genesis_errors.py [label ...]       -> appends to v3/baselines/genesis/judged.jsonl

Gate counts at two levels (ours is compared at the same level as Genesis):
  routed  = Genesis' physical output (== Genesis --stats; checked here);
  logical = Genesis' logical_<label>.cvdvqasm before routing; for z2Higgs / heisenberg / electronicVibration it
            still holds unsynthesized multi-Pauli placeholders (Genesis synthesizes them only while routing), so its
            count is INCOMPLETE there (`complete` False, `unsynthesized` = #placeholders). Errors are
computed on the physical circuit with its final qumode mapping; if its dense register exceeds the judge limit
(kerr_small: 19 qubits + 20 qumodes) they are computed on Genesis' logical (pre-routing) circuit instead and the
row says error_level = "logical".
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

V3 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V3.parent))
from v3.judge import cvdv_judge as J  # noqa: E402
from v3.paths import MANIFEST  # noqa: E402

G = V3 / "baselines" / "genesis"


def stats(d: Path) -> dict:
    s = next(iter(json.loads((d / "stats.json").read_text()).values()))
    return dict(one_op=s["single op gate count"], two_op=s["multi op gate count"], total=s["total gate count"],
                duration=int(s["depth"]))


def main():
    m = json.loads(MANIFEST.read_text())
    metrics_only = "--metrics-only" in sys.argv     # gate counts only; errors skipped (user decision 2026-10-20)
    labels = [a for a in sys.argv[1:] if not a.startswith("--")] or [c["label"] for c in m["circuits"] if c["domain"] == "cvdv"]
    for c in m["circuits"]:
        if c["label"] not in labels:
            continue
        lab = c["label"]
        seeds = {s: stats(G / lab / f"seed{s}") for s in c["genesis_seeds"]}
        best = min(seeds, key=lambda s: (seeds[s]["total"], s))
        d = G / lab / f"seed{best}"
        t0 = time.time()
        phys = J.judge(lab, d / f"{lab}.cvdvqasm", mapping=d / f"{lab}.cvdvqasm.mapping.json",
                       what=("metrics",) if metrics_only else ("metrics", "errors"))
        if metrics_only:
            phys["errors"] = []
        assert {k: phys["metrics"][k] for k in seeds[best]} == seeds[best], (phys["metrics"], seeds[best])
        assert phys["metrics"]["complete"]
        logical = {s: J.judge(lab, G / lab / f"seed{s}" / f"logical_{lab}.cvdvqasm")["metrics"] for s in seeds}
        level, res = "physical", phys
        if metrics_only:
            level = "skipped (user decision 2026-10-20)"
        elif any(e["status"] == "too_large" for e in phys["errors"]):
            level = "logical"
            res = J.judge(lab, d / f"logical_{lab}.cvdvqasm", what=("errors",))
        row = dict(label=lab, method="Genesis", best_seed=best, seeds_total={s: v["total"] for s, v in seeds.items()},
                   **{k: phys["metrics"][k] for k in seeds[best]}, logical_best_seed=logical[best], logical_all_seeds=logical, error_level=level, err_trotter=res.get("err_trotter"),
                   err_exact=res.get("err_exact"), cutoffs_agree=res.get("cutoffs_agree"),
                   errors_detail=res["errors"], physical_errors_status=[e["status"] for e in phys["errors"]],
                   judge_s=round(time.time() - t0, 1))
        with open(G / "judged.jsonl", "a") as f:
            f.write(json.dumps(row) + "\n")
        print(json.dumps({k: row[k] for k in ("label", "best_seed", "total", "two_op", "error_level", "err_trotter",
                                              "err_exact", "cutoffs_agree")}), flush=True)


if __name__ == "__main__":
    main()
