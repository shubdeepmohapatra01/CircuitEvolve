"""P3: classical search (no LLM) -> results/classical_search.csv (append-only) + results/runs/*.json

Configurations
  sanity_padded_A   Cuccaro padded with a cancelling Toffoli pair (28n), tier A. Expect 14n:
                    checks that the search machinery can remove waste at all.
  cuccaro_A         Cuccaro seed, tier A (AND gadgets available). Does search get below 8n?
  toffoli_carry_A   Gidney's carry structure with Toffolis (14n), tier A. Gadget substitution only.
  cuccaro_B         Cuccaro seed, tier B (primitives only).
  toffoli_carry_B   Toffoli-carry seed, tier B: the 4-T AND must be built from primitives.
"""
import argparse, datetime, json, pathlib
from multiprocessing import Pool

from circuitevolve.ir import TIER_A, TIER_B
from circuitevolve.search.evolve import map_elites
from circuitevolve.search.slice import CUCCARO, TOFFOLI_CARRY, G, SliceProgram, build, to_source
from circuitevolve.spec import AdderSpec
from circuitevolve.verify import verify

ROOT = pathlib.Path(__file__).resolve().parents[1]
PADDED = SliceProgram(CUCCARO.fwd + (G("ccx", "pa", "b", "a"), G("ccx", "pa", "b", "a")), CUCCARO.top, CUCCARO.bwd)
CONFIGS = {
    "sanity_padded_A": (PADDED, "A"),
    "cuccaro_A": (CUCCARO, "A"),
    "toffoli_carry_A": (TOFFOLI_CARRY, "A"),
    "cuccaro_B": (CUCCARO, "B"),
    "toffoli_carry_B": (TOFFOLI_CARRY, "B"),
}


def run(job):
    name, rng_seed, budget = job
    seed, tier = CONFIGS[name]
    archive, traj, stats = map_elites(seed, tier, budget, rng_seed)
    fit, best = min(archive.values(), key=lambda x: x[0])
    final = verify(lambda n: build(best, n), AdderSpec(), list(range(1, 17)), TIER_A if tier == "A" else TIER_B)
    t16 = final.costs[16]["t_count"] if final.ok else None
    t8 = final.costs[8]["t_count"] if final.ok else None
    rec = {"config": name, "tier": tier, "rng_seed": rng_seed, "budget": budget, **stats,
           "best_t8": fit[1], "best_t_per_bit_search": fit[0], "t_per_bit": (t16 - t8) / 8 if final.ok else None,
           "final_verify_n1_16": final.ok, "best_source": to_source(best), "trajectory": traj}
    out = ROOT / "results" / "runs" / f"{name}_s{rng_seed}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1, default=str))
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=30000)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--procs", type=int, default=10)
    args = ap.parse_args()
    jobs = [(c, s, args.budget) for c in CONFIGS for s in range(args.seeds)]
    with Pool(args.procs) as pool:
        recs = pool.map(run, jobs)
    csv = ROOT / "results" / "classical_search.csv"
    new = not csv.exists()
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    with csv.open("a") as f:
        if new:
            f.write("timestamp,config,tier,rng_seed,budget,evals,seconds,best_t8,t_per_bit,final_verify_n1_16,"
                    "fail_L0,fail_L1,fail_L2,archive_cells\n")
        for r in recs:
            fl = r["failures"]
            f.write(f"{stamp},{r['config']},{r['tier']},{r['rng_seed']},{r['budget']},{r['evals']},{r['seconds']},"
                    f"{r['best_t8']},{r['t_per_bit']},{r['final_verify_n1_16']},{fl.get('L0', 0)},{fl.get('L1', 0)},"
                    f"{fl.get('L2', 0)},{r['archive_cells']}\n")
    for r in recs:
        print(f"{r['config']:18s} s{r['rng_seed']}  T/bit={r['t_per_bit']}  best_t8={r['best_t8']}  "
              f"verified1-16={r['final_verify_n1_16']}  {r['seconds']}s")
