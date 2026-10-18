"""Run the window core (circuitevolve/core) on a stage-1 circuit.

From a Claude Science python kernel in the repo venv (environment `circuitevolve-dev`; `host` exists only
there):

    import sys; sys.path.insert(0, "/Users/shubdeepmohapatra/Documents/CircuitEvolve")
    from experiments.window_run import run_api
    summary = run_api(host, "heisenberg_6", 1e-3, tag="smoke_heisenberg_6_e3", calls=20, batch=4)

From a terminal (claude CLI backend, see docs/LLM_BACKENDS.md):

    .venv/bin/python experiments/window_run.py heisenberg_6 1e-3 --tag smoke_cli --calls 20

Outputs (append-only; an existing tag is refused): results/window_runs/<tag>.jsonl (one line per LLM
call), <tag>_summary.json, <tag>_best.qasm, <tag>_playbook.{json,md}. The mutable playbook is
playbooks/window_v0.json (created empty on first use); pass playbook=None to run without one.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from circuitevolve.core.loop import run  # noqa: E402

PLAYBOOK = REPO / "playbooks" / "window_v0.json"


def run_api(host, name: str, eps: float, tag: str, calls: int = 20, batch: int = 4, reflect_every: int = 8,
            max_tokens: int = 3000, playbook=PLAYBOOK, seed: int = 0, model=None) -> dict:
    """In-platform backend: host.llm, the reasoning model, thinking disabled."""
    from circuitevolve.llm_backends import make_api_backend
    be = make_api_backend(host.llm, model=model or host.reasoning_model(), max_tokens=max_tokens,
                          max_concurrency=batch)
    return run(name, eps, be, tag=tag, playbook_path=playbook, n_calls=calls, batch=batch,
               reflect_every=reflect_every, seed=seed)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("eps", type=float)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--calls", type=int, default=20)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--reflect-every", type=int, default=8)
    ap.add_argument("--no-playbook", action="store_true")
    ap.add_argument("--cli-timeout", type=int, default=600)
    a = ap.parse_args(argv)
    from circuitevolve.llm_backends import make_cli_backend
    be = make_cli_backend(timeout=a.cli_timeout, workers=a.batch, extra_args=("--max-turns", "1"))
    s = run(a.name, a.eps, be, tag=a.tag, playbook_path=None if a.no_playbook else PLAYBOOK, n_calls=a.calls,
            batch=a.batch, reflect_every=a.reflect_every)
    print(json.dumps({k: s[k] for k in ("tag", "t_before", "t_after", "t_after_reclaimed", "calls")}, indent=1))


if __name__ == "__main__":
    main()
