"""Stage-1 runs of the window core: 8 qseed circuits x eps {1e-3, 1e-5}, one persistent playbook.

Protocol (docs/CORE.md "Stage-1 runs"):
  * input: results/bqskit_baselines/stage1/inputs/<c>_tket.qasm (TKET FullPeepholeOptimise, shared with B0-B3);
  * ledger v1 (core/ledger.py): window pool cap eps/4, unspent budget returns to synthesis, acceptance and
    reported T at eps_rz = (eps - d_input - ceil_q(sum d_w)) / N_Rz;
  * actions: exact rewrite (```window) and fix-and-refit (```fix, core/refit.py);
  * 40 proposer calls per run in batches of 5, reflector every 10 proposer calls (4 per run, counted as LLM
    calls, n_calls = 44), in-platform backend host.llm with the reasoning model, thinking disabled;
  * ONE playbook playbooks/stage1.json carried across runs in a fixed order (all 1e-3 runs in STAGE1 order,
    then 1e-5); the loop snapshots it after every run into results/window_runs/stage1/<tag>_playbook.{json,md};
  * every run's best circuit is checked against the ORIGINAL qseed circuit (summary.final_check_vs_original).

Usage from a platform kernel (env circuitevolve-dev, where `host` exists):
    from experiments.window_stage1 import run_stage1
    run_stage1(host, [("qft_8", 1e-3), ...])
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from circuitevolve.core.circuit import STAGE1  # noqa: E402
from circuitevolve.core.loop import run  # noqa: E402

PLAYBOOK = REPO / "playbooks" / "stage1.json"
OUT = REPO / "results" / "window_runs" / "stage1"
ORDER = [(c, 1e-3) for c in STAGE1] + [(c, 1e-5) for c in STAGE1]


def tag_for(name: str, eps: float, prefix: str = "stage1") -> str:
    return f"{prefix}_{name}_e{round(-__import__('math').log10(eps))}"


def run_stage1(host, jobs=ORDER, calls: int = 44, batch: int = 5, reflect_every: int = 10, max_tokens: int = 2000,
               playbook=PLAYBOOK, out_dir=OUT, prefix: str = "stage1", seed: int = 0, model=None,
               progress=None) -> list:
    from circuitevolve.llm_backends import make_api_backend
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    progress = Path(progress) if progress else out_dir / f"_{prefix}_progress.jsonl"
    res = []
    for name, eps in jobs:
        tag = tag_for(name, eps, prefix)
        be = make_api_backend(host.llm, model=model or host.reasoning_model(), max_tokens=max_tokens,
                              max_concurrency=batch)
        t0 = time.time()
        s = run(name, eps, be, tag=tag, playbook_path=playbook, runs_dir=out_dir, n_calls=calls, batch=batch,
                reflect_every=reflect_every, seed=seed)
        rec = dict(tag=tag, name=name, eps=eps, t_before=s["t_before"], t_after=s["t_after"],
                   rz=(s["before"]["rz"], s["after"]["rz"]), calls=s["calls"], stats=s["stats"],
                   tokens=dict(input=s["backend_stats"].get("input_tokens", 0),
                               output=s["backend_stats"].get("output_tokens", 0)),
                   final_check=s["final_check_vs_original"], bound=s["ledger"]["bound"],
                   seconds=round(time.time() - t0, 1))
        with progress.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        res.append(rec)
    return res
