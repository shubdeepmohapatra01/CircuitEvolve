"""Paper-convention By-Gate reference (arXiv:2409.00433 Table 3 row, reproduced in results/bqskit_baselines) for the
held-out adder family. Calls experiments/bqskit_baselines/run_bygate_exact.run_one(method='paramzsx') unchanged,
with its scratch output redirected to .cache (results/bqskit_baselines is not touched).
add_17 is included as a cross-check against results/bqskit_baselines/table3_bygate.csv (23,520 T / 251 RZ).
Writes results/evolve_opt/eval/bygate_adders.json (new file)."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments" / "bqskit_baselines"))
import run_bygate_exact as rb  # noqa: E402

rb.OUT = REPO / ".cache" / "eval_bygate"


def main():
    out = REPO / "results" / "evolve_opt" / "eval" / "bygate_adders.json"
    assert not out.exists(), out
    cache: dict = {}
    res = {}
    for nm in ["add/add_17", "add/add_41", "add/add_65"]:
        r = rb.run_one(nm, 1e-9, cache, method="paramzsx")
        res[r["circuit"]] = {k: r[k] for k in ("pipeline", "qubits", "cx", "rz_count", "t_fixed", "t_gridsynth", "t_count",
                                               "eps_total_bound", "rounded_angles", "max_gridsynth_dist")}
        print(r["circuit"], r["rz_count"], r["t_count"], flush=True)
    out.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":   # gridsynth uses a spawn Pool: the guard is required
    main()
