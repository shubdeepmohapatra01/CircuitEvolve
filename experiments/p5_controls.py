"""P5 non-LLM control arms at matched evaluation budgets (no LLM calls).

    .venv/bin/python experiments/p5_controls.py --arm classical   --row cuccaro_B --seed 0 --evals 31234
    .venv/bin/python experiments/p5_controls.py --arm repair_only --row cuccaro_B --seed 0 --evals 31234

classical    MAP-Elites (search/evolve.py map_elites, unchanged) for `--evals` unique evaluations.
repair_only  The LLM+repair loop with the LLM replaced by random proposals: each proposal is a
             multi-step random mutation (2..8 edits, same operator set as the classical arm) of an
             archive member chosen like llm_search chooses parents (50% best, 50% uniform). A proposal
             that fails verification gets exactly the llm_search repair: up to `--repair` local mutants
             (1 edit, plus a second with prob. 0.5), first verifying one kept. Proposals are issued in
             groups of k (= one simulated "call") until `--evals` unique evaluations are spent.
`--evals` should be the final `evals` of the matching LLM+repair run.
Writes results/llm_runs/<row>_<arm>[_repairN]_s<seed>_ev<evals>.summary.json (never overwritten).
"""
import argparse, json, pathlib, random, sys, time
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from circuitevolve.integrity import check_unchanged, frozen_digest
from circuitevolve.search.evolve import TIERS, Evaluator, map_elites, mutate
from circuitevolve.search.slice import CUCCARO, TOFFOLI_CARRY, to_source

ROWS = {"cuccaro_A": (CUCCARO, "A"), "cuccaro_B": (CUCCARO, "B"), "toffoli_carry_B": (TOFFOLI_CARRY, "B")}
OUT = ROOT / "results" / "llm_runs"


def repair_only_search(seed, tier, eval_budget, rng_seed=0, repair_budget=300, k=4, min_steps=2, max_steps=8):
    digest = frozen_digest()
    rng = random.Random(rng_seed)
    vocab = TIERS[tier]
    ev = Evaluator(tier)
    ok, fit, _ = ev(seed)
    assert ok
    archive = {(fit[0], fit[4] // 4): (fit, seed)}
    best, best_prog = fit, seed
    counts = Counter()
    traj = [(0, ev.calls, best[0])]
    pseudo_calls = 0
    t0 = time.time()
    while ev.calls < eval_budget:
        pseudo_calls += 1
        for _ in range(k):
            if ev.calls >= eval_budget:
                break
            elites = list(archive.values())
            pf, parent = min(elites, key=lambda e: e[0]) if rng.random() < 0.5 else rng.choice(elites)
            p = parent
            for _ in range(rng.randint(min_steps, max_steps)):
                p = mutate(p, vocab, rng)
            if ev.seen(p):
                counts["duplicate"] += 1
                continue
            counts["proposals"] += 1
            okp, fp, rep = ev(p)
            if okp:
                counts["raw_pass"] += 1
            else:
                counts[f"fail_{rep.level}"] += 1
                fixed = None
                for _ in range(repair_budget):
                    if ev.calls >= eval_budget:
                        break
                    q = mutate(p, vocab, rng)
                    if rng.random() < 0.5:
                        q = mutate(q, vocab, rng)
                    okq, fq, _ = ev(q)
                    if okq:
                        fixed = (q, fq)
                        break
                if fixed is None:
                    continue
                counts["repaired"] += 1
                p, fp = fixed
            counts["accepted"] += 1
            cell = (fp[0], fp[4] // 4)
            if cell not in archive or fp <= archive[cell][0]:
                archive[cell] = (fp, p)
            if fp < best:
                best, best_prog = fp, p
                traj.append((pseudo_calls, ev.calls, best[0]))
    traj.append((pseudo_calls, ev.calls, best[0]))
    check_unchanged(digest)
    stats = {"pseudo_calls": pseudo_calls, "evals": ev.calls, "seconds": round(time.time() - t0, 1), "best": best,
             "archive_cells": len(archive), "verifier_digest": digest[:16], **counts}
    return archive, traj, stats, best_prog


def _fresh(path: pathlib.Path) -> pathlib.Path:
    r, p = 1, path
    while p.exists():
        r += 1
        p = path.with_name(path.name.replace(".summary.json", f"_r{r}.summary.json"))
    return p


def main(arm, row, seed, evals, repair=300, k=4, matched_to=None):
    seed_prog, tier = ROWS[row]
    t = time.time()
    if arm == "classical":
        digest = frozen_digest()
        arch, traj, stats = map_elites(seed_prog, tier, evals, rng_seed=seed)
        check_unchanged(digest)
        stats["verifier_digest"] = digest[:16]
        best_prog = min(arch.values(), key=lambda e: e[0])[1]
        tag = f"{row}_classical_s{seed}_ev{evals}"
    else:
        arch, traj, stats, best_prog = repair_only_search(seed_prog, tier, evals, rng_seed=seed, repair_budget=repair, k=k)
        tag = f"{row}_repair_only_repair{repair}_s{seed}_ev{evals}"
    OUT.mkdir(parents=True, exist_ok=True)
    path = _fresh(OUT / f"{tag}.summary.json")
    summary = {"tag": path.name.replace(".summary.json", ""), "row": row, "arm": arm, "seed": seed,
               "eval_budget": evals, "repair": repair if arm != "classical" else 0, "matched_to": matched_to,
               "stats": stats, "trajectory": traj, "best_source": to_source(best_prog),
               "wall_seconds": round(time.time() - t, 1)}
    path.write_text(json.dumps(summary, indent=1, default=str))
    print(summary["tag"], stats)
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["classical", "repair_only"], required=True)
    ap.add_argument("--row", choices=ROWS, default="cuccaro_B")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--evals", type=int, required=True)
    ap.add_argument("--repair", type=int, default=300)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--matched-to", default=None, help="tag of the LLM run whose evals this matches")
    a = ap.parse_args()
    main(a.arm, a.row, a.seed, a.evals, a.repair, a.k, a.matched_to)
