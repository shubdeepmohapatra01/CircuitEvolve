"""Classical control at matched program evaluations: random and greedy search over pass sequences and
parameters, using the SAME toolbox, sandbox, verifier, cascade and cache as the LLM loop (programs are
generated from genomes by programs.genome_source, so they are ordinary optimizer programs).

  random : n_evals genomes sampled independently (programs.random_genome);
  greedy : first-improvement hill climbing from the seed genome (= the seed program's pipeline):
           mutate the incumbent (programs.mutate_genome), accept if the FAST fitness key is lower.
Each FAST evaluation counts as one program evaluation (duplicates by source hash are re-drawn, up to 20
times, and do not count). Cascade to the full dev set exactly as in evolve.run_evolution.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

from . import split
from .evaluate import baseline, evaluate_program, fitness, source_hash
from .evolve import RESULTS, _slim
from .programs import SEED_GENOME, genome_source, mutate_genome, random_genome


def run_control(tag: str, mode: str, n_evals: int = 120, seed: int = 0, workers: int = 6, time_s: float = 300.0,
                cascade_tol: float = 0.02, fast_names=None, dev_names=None, out_root: Path = RESULTS,
                log=print) -> dict:
    from circuitevolve.integrity import check_unchanged, frozen_digest
    assert mode in ("random", "greedy")
    digest = frozen_digest()
    out = Path(out_root) / tag
    if out.exists():
        raise FileExistsError(f"{out} exists (results are append-only)")
    (out / "programs").mkdir(parents=True)
    fast_names = list(fast_names or split.fast())
    dev_names = list(dev_names or split.dev())
    ref = baseline(dev_names)
    rng = random.Random(seed)
    f = open(out / "evals.jsonl", "a")
    seen, entries = set(), []
    best_fast_gm = float("inf")
    t0 = time.time()

    def run(genome, i):
        nonlocal best_fast_gm
        src = genome_source(genome)
        seen.add(source_hash(src))
        (out / "programs" / f"{source_hash(src)[:16]}.py").write_text(src)
        fr = evaluate_program(src, fast_names, ref, workers=workers, time_s=time_s)
        e = dict(i=i, genome=genome, hash=source_hash(src), fast=fr["fitness"], dev=None, src=src,
                 fast_results={k: _slim(v) for k, v in fr["results"].items()})
        if fr["fitness"]["valid"] and fr["fitness"]["geomean"] <= min(best_fast_gm, fr["fitness"]["geomean"]) * (1 + cascade_tol):
            rest = [nm for nm in dev_names if nm not in fast_names]
            dr = evaluate_program(src, rest, ref, workers=workers, time_s=time_s)
            allres = dict(fr["results"], **dr["results"])
            e["dev"] = fitness(allres, dev_names, ref)
            e["dev_results"] = {k: _slim(v) for k, v in allres.items()}
        if fr["fitness"]["valid"]:
            best_fast_gm = min(best_fast_gm, fr["fitness"]["geomean"])
        f.write(json.dumps({k: v for k, v in e.items() if k != "src"}) + "\n")
        f.flush()
        entries.append(e)
        return e

    seed_e = run(SEED_GENOME, 0)
    inc = seed_e
    for i in range(1, n_evals + 1):
        for _ in range(20):
            g = random_genome(rng) if mode == "random" else mutate_genome(inc["genome"], rng)
            if source_hash(genome_source(g)) not in seen:
                break
        e = run(g, i)
        if mode == "greedy" and tuple(e["fast"]["key"]) < tuple(inc["fast"]["key"]):
            inc = e
        if i % 10 == 0:
            bd = min((x for x in entries if x["dev"] and x["dev"]["valid"]), key=lambda x: tuple(x["dev"]["key"]),
                     default=None)
            log(f"[{tag}] eval {i}/{n_evals}: best fast {best_fast_gm:.5f} best dev "
                f"{bd['dev']['geomean'] if bd else float('nan'):.5f}")
    f.close()
    check_unchanged(digest)
    devs = [x for x in entries if x["dev"] and x["dev"]["valid"]]
    best = min(devs, key=lambda x: tuple(x["dev"]["key"]))
    (out / "best_program.py").write_text(best["src"])
    summary = dict(tag=tag, mode=mode, seed=seed, n_evals=n_evals, fast=fast_names, dev=dev_names,
                   n_valid_fast=sum(x["fast"]["valid"] for x in entries), n_dev_evals=len([x for x in entries if x["dev"]]),
                   seed_program=dict(fast=seed_e["fast"], dev=seed_e["dev"]),
                   best=dict(i=best["i"], hash=best["hash"], genome=best["genome"], fast=best["fast"], dev=best["dev"],
                             dev_results=best.get("dev_results")),
                   frozen_digest=digest, seconds=round(time.time() - t0, 1))
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    return summary
