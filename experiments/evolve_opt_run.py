"""Run one seed of optimizer-program evolution, or one classical-control run.

From a Claude Science python kernel in the `circuitevolve-dev` environment (host.llm exists only there):

    import sys; sys.path.insert(0, "/Users/shubdeepmohapatra/Documents/CircuitEvolve")
    from experiments.evolve_opt_run import run_seed
    summary = run_seed(seed=0, llm=host.llm, model=host.reasoning_model(), n_calls=120)

Classical control (no LLM; from a terminal):
    .venv/bin/python experiments/evolve_opt_run.py control --mode random --seed 0 --evals 120
Outputs: results/evolve_opt/<tag>/ (calls.jsonl or evals.jsonl, programs/, summary.json, best_program.py,
playbook.json/md). Tags never overwrite existing results.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def run_seed(seed: int, llm, model, n_calls: int = 120, tag: str | None = None, batch: int = 4,
             max_tokens: int = 6000, workers: int = 4, reflect_every: int = 16, log_path: str | None = None,
             **kw) -> dict:
    from circuitevolve.evolve_opt.evolve import run_evolution
    from circuitevolve.search.llm import make_api_backend
    from circuitevolve.search.playbook import Playbook
    tag = tag or f"evo_s{seed}_{n_calls}"
    be = make_api_backend(llm, model=model, max_tokens=max_tokens, max_concurrency=batch)
    logf = open(log_path or (REPO / "results" / "evolve_opt" / f"{tag}.log"), "a")

    def log(msg):
        logf.write(time.strftime("%H:%M:%S ") + msg + "\n")
        logf.flush()

    try:
        return run_evolution(tag, be, n_calls=n_calls, seed=seed, batch=batch, workers=workers,
                             reflect_every=reflect_every, playbook=Playbook(evidence="improvement"), log=log, **kw)
    finally:
        logf.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("control")
    c.add_argument("--mode", choices=["random", "greedy"], required=True)
    c.add_argument("--seed", type=int, default=0)
    c.add_argument("--evals", type=int, default=120)
    c.add_argument("--workers", type=int, default=4)
    c.add_argument("--tag")
    a = ap.parse_args(argv)
    from circuitevolve.evolve_opt.control import run_control
    tag = a.tag or f"control_{a.mode}_s{a.seed}_{a.evals}"
    logf = open(REPO / "results" / "evolve_opt" / f"{tag}.log", "a")

    def log(msg):
        logf.write(time.strftime("%H:%M:%S ") + msg + "\n")
        logf.flush()

    s = run_control(tag, a.mode, n_evals=a.evals, seed=a.seed, workers=a.workers, log=log)
    log(f"done: best dev {s['best']['dev']['geomean']:.5f}")


if __name__ == "__main__":
    main()
