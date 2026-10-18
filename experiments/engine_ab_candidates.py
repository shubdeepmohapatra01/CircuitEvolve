"""P3.5 — A/B harness: candidates-per-call 3 vs 5 on the P2 campaign dev circuits.

*** BUDGET-GATED: REAL-LLM EXECUTION REQUIRES EXPLICIT USER APPROVAL. ***
This script is committed NOT RUN (PLAN_P3: all real-LLM work is excluded from P3 execution).
Running it spends proposer-model tokens: 2 arms x 5 circuits x >= 12 calls = >= 120 LLM calls
plus reflector calls. Do not run without the user's go-ahead on model + spend.

Design (follows docs/P2_CAMPAIGN.md conventions):
  arms        max_candidates = 3 (today's default) vs 5; FIXED within each arm (the knob is
              proposal-side only — invariant 7: acceptance untouched)
  circuits    the P2 campaign DEV set: qft_8, heisenberg_6, hubbard_8, qml_13, hhl_8 @ 1e-3
  controls    same seeds across arms (seed = per-circuit constant), same n_calls, same batch,
              graduated pre-opt ON for both, playbook FROZEN for both (no learning during the
              A/B: the comparison isolates the knob, not rule evolution)
  report      paired per-circuit deltas (final T, accepted, candidates parsed, declined,
              tokens), appended under results/engine/ab_candidates/ (append-only)

Usage (after explicit approval):
    .venv/bin/python experiments/engine_ab_candidates.py --model <id> [--calls 12]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEV = ["qft_8", "heisenberg_6", "hubbard_8", "qml_13", "hhl_8"]
EPS = 1e-3
OUT = ROOT / "results" / "engine" / "ab_candidates"


def run_arm(name: str, max_candidates: int, complete, calls: int, seed: int, tag: str) -> dict:
    from circuitevolve.core.circuit import load_input, original_ops
    from circuitevolve.core.loop import WindowLoop
    from circuitevolve.search.playbook import Playbook
    circ = load_input(name)
    orig, n = original_ops(name)
    pb = Playbook.load(ROOT / "playbooks" / "families" / "dv.windows.json")
    pb.frozen = True                                    # no learning inside the A/B
    loop = WindowLoop(circ, orig, EPS, complete, playbook=pb, tag=tag, n_calls=calls,
                      batch=1, seed=seed, max_candidates=max_candidates,
                      runs_dir=OUT / "runs")
    s = loop.run()
    keep = ("t_before", "t_after")
    out = {k: s[k] for k in keep}
    out.update(accepted=s["stats"]["accepted"], candidates=s["stats"]["candidates"],
               declined=s["stats"]["declined"], parse_errors=s["stats"]["parse_errors"],
               proposal_calls=s["stats"]["proposal_calls"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True, help="proposer model id (explicit, no default)")
    ap.add_argument("--calls", type=int, default=12, help=">= 12 calls/circuit/arm (plan floor)")
    ap.add_argument("--yes-i-have-approval", action="store_true",
                    help="acknowledge the user approved this LLM spend")
    args = ap.parse_args()
    if not args.yes_i_have_approval:
        raise SystemExit("REFUSING: real-LLM execution is budget-gated. Re-run with "
                         "--yes-i-have-approval after the user explicitly approves the spend.")
    if args.calls < 12:
        raise SystemExit("plan floor is >= 12 calls/circuit/arm")
    from circuitevolve.llm_backends import make_api_backend
    complete = make_api_backend(args.model)
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    rows = []
    for name in DEV:
        seed = abs(hash(name)) % (2 ** 31)              # fixed per circuit, shared across arms
        per = dict(circuit=name, seed=seed)
        for arm in (3, 5):
            per[f"arm{arm}"] = run_arm(name, arm, complete, args.calls, seed,
                                       tag=f"ab_cand{arm}_{name}_{stamp}")
        per["delta_t_after"] = per["arm5"]["t_after"] - per["arm3"]["t_after"]
        rows.append(per)
        print(name, "d(t_after) 5-3 =", per["delta_t_after"])
    report = dict(format="circuitevolve.ab_candidates/1", model=args.model, eps=EPS,
                  calls_per_circuit_per_arm=args.calls, stamp=stamp,
                  note="paired per-circuit deltas; playbook frozen; graduated ON both arms; "
                       "same seeds across arms; knob is proposal-side only",
                  circuits=rows)
    p = OUT / f"report_{stamp}.json"
    p.write_text(json.dumps(report, indent=1))
    print("wrote", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
