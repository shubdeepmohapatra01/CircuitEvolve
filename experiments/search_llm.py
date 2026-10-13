"""P4/P5: LLM-proposer search.

From a terminal where `claude` is logged in (CLI backend):
    .venv/bin/python experiments/search_llm.py --row cuccaro_B --arm evo --calls 120 --repair 300
    ... --cli-timeout 600 --cli-max-turns 1          # see docs/LLM_BACKENDS.md before long runs

From a platform python kernel (in-platform API backend; `host` exists only there):
    from experiments.search_llm import run
    from circuitevolve.search.llm import make_api_backend
    be = make_api_backend(host.llm, model=host.reasoning_model(), max_tokens=8000)   # thinking disabled
    run("cuccaro_B", backend=be, backend_tag="api", calls=60, repair=300, seed=0)

Arms: zeroshot (no feedback), evo (archive + verifier feedback); --blind renames all cue identifiers.
Self-evolving playbook (search/playbook.py):
    ... --playbook playbooks/dev.json --reflect-every 2      # learn rules (file updated in place)
    ... --playbook playbooks/dev.json --freeze-playbook      # evaluate learned rules, no updates
The CLI runs in an empty temp directory so it cannot read this repository (which contains the answer).
Writes results/llm_runs/<row>_<arm>[_blind][_repairN][_pb..][_p4prompt]_s<seed>_<calls>_<backend>.jsonl/.summary.json
(an existing tag is never overwritten: a suffix _r2, _r3, ... is added).
"""
import argparse, json, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from circuitevolve.search.llm import llm_search, make_cli_backend
from circuitevolve.search.slice import CUCCARO, TOFFOLI_CARRY, to_source

ROWS = {"cuccaro_A": (CUCCARO, "A"), "cuccaro_B": (CUCCARO, "B"), "toffoli_carry_B": (TOFFOLI_CARRY, "B")}
OUT = ROOT / "results" / "llm_runs"


def fresh_tag(tag: str) -> str:
    """results/ is append-only: never reuse a tag whose files exist."""
    t, r = tag, 1
    while (OUT / f"{t}.jsonl").exists() or (OUT / f"{t}.summary.json").exists():
        r += 1
        t = f"{tag}_r{r}"
    return t


def run(row, backend, backend_tag, arm="evo", blind=False, calls=24, k=4, batch=4, repair=0, seed=0,
        playbook=None, reflect_every=2, freeze_playbook=False, format_rules=True, verbose=True):
    seed_prog, tier = ROWS[row]
    pb = None
    if playbook:
        from circuitevolve.search.playbook import Playbook
        p = pathlib.Path(playbook)
        p.parent.mkdir(parents=True, exist_ok=True)
        pb = Playbook.load(p, frozen=freeze_playbook) if p.exists() else Playbook(blinded=blind, frozen=freeze_playbook)
    pb_tag = "" if pb is None else ("_pbfrozen" if freeze_playbook else f"_pb{reflect_every}")
    tag = fresh_tag(f"{row}_{arm}{'_blind' if blind else ''}{f'_repair{repair}' if repair else ''}{pb_tag}"
                    f"{'' if format_rules else '_p4prompt'}_s{seed}_{calls}_{backend_tag}")
    OUT.mkdir(parents=True, exist_ok=True)
    t = time.time()
    arch, traj, stats, best = llm_search(seed_prog, tier, backend, calls, k=k, batch=batch, blinded=blind,
                                         feedback=arm == "evo", rng_seed=seed, repair_budget=repair,
                                         log_path=OUT / f"{tag}.jsonl", playbook=pb,
                                         reflect_every=0 if freeze_playbook else reflect_every,
                                         format_rules=format_rules)
    if pb is not None and not freeze_playbook:
        pb.save(playbook)
        pathlib.Path(playbook).with_suffix(".md").write_text(pb.to_markdown())
    if pb is not None:   # append-only snapshot of the rules this run ended with (results/ is never edited)
        pb.save(OUT / f"{tag}.playbook.json")
    summary = {"tag": tag, "row": row, "arm": arm, "repair": repair, "seed": seed, "k": k, "batch": batch,
               "backend": backend_tag, "format_rules": format_rules, "stats": stats, "trajectory": traj,
               "best_source": to_source(best), "playbook": playbook, "playbook_frozen": freeze_playbook,
               "wall_seconds": round(time.time() - t, 1)}
    (OUT / f"{tag}.summary.json").write_text(json.dumps(summary, indent=1, default=str))
    if verbose:
        print(tag, f"{time.time() - t:.0f}s", stats)
        if stats.get("llm_error", 0) == stats["calls"]:
            print("every LLM call failed - see the .jsonl 'error' fields and docs/LLM_BACKENDS.md")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--row", choices=ROWS, required=True)
    ap.add_argument("--arm", choices=["zeroshot", "evo"], default="evo")
    ap.add_argument("--blind", action="store_true")
    ap.add_argument("--calls", type=int, default=24)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--repair", type=int, default=0)
    ap.add_argument("--model", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--playbook", default=None,
                    help="playbook JSON to load (created if missing); updated in place unless --freeze-playbook")
    ap.add_argument("--reflect-every", type=int, default=2, help="batches between reflector calls")
    ap.add_argument("--freeze-playbook", action="store_true", help="evaluation mode: show ACTIVE rules, change nothing")
    ap.add_argument("--p4-prompt", action="store_true", help="send the P4 prompt (no output-format rules)")
    ap.add_argument("--cli-timeout", type=int, default=300, help="seconds per `claude -p` call")
    ap.add_argument("--cli-retries", type=int, default=1, help="retries for transient CLI failures")
    ap.add_argument("--cli-retry-timeouts", action="store_true", help="also retry calls that timed out")
    ap.add_argument("--cli-workers", type=int, default=None, help="concurrent CLI processes (default: --batch)")
    ap.add_argument("--cli-max-turns", type=int, default=None, help="pass --max-turns N to claude -p")
    ap.add_argument("--cli-arg", action="append", default=[], help="extra argument for claude -p (repeatable)")
    a = ap.parse_args()
    extra = (["--max-turns", str(a.cli_max_turns)] if a.cli_max_turns else []) + a.cli_arg
    backend = make_cli_backend(a.model, timeout=a.cli_timeout, workers=a.cli_workers or a.batch,
                               retries=a.cli_retries, retry_timeouts=a.cli_retry_timeouts, extra_args=extra)
    s = run(a.row, backend, "cli", arm=a.arm, blind=a.blind, calls=a.calls, k=a.k, batch=a.batch, repair=a.repair,
            seed=a.seed, playbook=a.playbook, reflect_every=a.reflect_every, freeze_playbook=a.freeze_playbook,
            format_rules=not a.p4_prompt)
    print("backend stats:", dict(backend.stats))
