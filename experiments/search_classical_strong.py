"""Stronger classical arm on the rows the P3 search left flat -> results/classical_search_strong.csv

Same representation, verifier and fitness as P3; adds crossover (rate 0.3) and a 1e6-evaluation
budget. Progress snapshots: results/runs_strong/<config>_s<seed>.progress.json
"""
import argparse, datetime, json, pathlib
from multiprocessing import Pool

from circuitevolve.ir import TIER_A, TIER_B
from circuitevolve.search.evolve import map_elites
from circuitevolve.search.slice import CUCCARO, TOFFOLI_CARRY, build, to_source
from circuitevolve.spec import AdderSpec
from circuitevolve.verify import verify

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "runs_strong"
CONFIGS = {"cuccaro_A": (CUCCARO, "A"), "cuccaro_B": (CUCCARO, "B"), "toffoli_carry_B": (TOFFOLI_CARRY, "B")}


def run(job):
    name, rng_seed, budget, xo = job
    seed, tier = CONFIGS[name]
    OUT.mkdir(parents=True, exist_ok=True)
    archive, traj, stats = map_elites(seed, tier, budget, 1000 + rng_seed, crossover_rate=xo,
                                      progress_path=OUT / f"{name}_s{rng_seed}.progress.json")
    fit, best = min(archive.values(), key=lambda x: x[0])
    final = verify(lambda n: build(best, n), AdderSpec(), list(range(1, 17)), TIER_A if tier == "A" else TIER_B)
    rec = {"config": name, "tier": tier, "rng_seed": 1000 + rng_seed, "budget": budget, "crossover": xo, **stats,
           "t_per_bit": (final.costs[16]["t_count"] - final.costs[8]["t_count"]) / 8 if final.ok else None,
           "final_verify_n1_16": final.ok, "best_source": to_source(best), "trajectory": traj}
    (OUT / f"{name}_s{rng_seed}.json").write_text(json.dumps(rec, indent=1, default=str))
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=1_000_000)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--crossover", type=float, default=0.3)
    ap.add_argument("--procs", type=int, default=9)
    a = ap.parse_args()
    jobs = [(c, s, a.budget, a.crossover) for c in CONFIGS for s in range(a.seeds)]
    with Pool(a.procs) as pool:
        recs = pool.map(run, jobs)
    csv = ROOT / "results" / "classical_search_strong.csv"
    new = not csv.exists()
    with csv.open("a") as f:
        if new:
            f.write("timestamp,config,tier,rng_seed,budget,crossover,evals,seconds,t_per_bit,final_verify_n1_16,archive_cells\n")
        for r in recs:
            f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')},{r['config']},{r['tier']},{r['rng_seed']},"
                    f"{r['budget']},{r['crossover']},{r['evals']},{r['seconds']},{r['t_per_bit']},"
                    f"{r['final_verify_n1_16']},{r['archive_cells']}\n")
    for r in recs:
        print(r["config"], r["rng_seed"], "T/bit", r["t_per_bit"], r["seconds"], "s")
