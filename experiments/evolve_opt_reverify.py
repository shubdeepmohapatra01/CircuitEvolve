"""Re-verify every program evaluated in an LLM evolution run under the current evaluator (ev-v3, spawn +
verify lock). Writes results/evolve_opt/<tag>_reverify.jsonl (new file; the run's own files are untouched).
Usage: .venv/bin/python experiments/evolve_opt_reverify.py evo_s0_120
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from circuitevolve.evolve_opt import evaluate as ev, split  # noqa: E402

tag = sys.argv[1]
run = REPO / "results" / "evolve_opt" / tag
out = REPO / "results" / "evolve_opt" / f"{tag}_reverify.jsonl"
assert not out.exists(), f"{out} exists"
fast, dev = split.fast(), split.dev()
ref = ev.baseline(dev)
done = set()
with open(out, "w") as f:
    for line in (run / "calls.jsonl").read_text().splitlines():
        d = json.loads(line)
        if d["kind"] == "seed":
            h, old_f, old_d, call = None, d["fast"], d["dev"], 0
            src = None
            from circuitevolve.evolve_opt.programs import SEED_PROGRAM
            src = SEED_PROGRAM
        elif d["kind"] == "proposer" and d.get("fast") and not d.get("duplicate"):
            src = (run / "programs" / f"{d['src_hash']}.py").read_text()
            old_f, old_d, call = d["fast"], d.get("dev"), d["call"]
        else:
            continue
        h = ev.source_hash(src)
        if h in done:
            continue
        done.add(h)
        nf = ev.evaluate_program(src, fast, ref, workers=4)["fitness"]
        rec = dict(call=call, hash=h[:16], old_fast_valid=old_f["valid"], old_fast=old_f["geomean"],
                   new_fast_valid=nf["valid"], new_fast=nf["geomean"], new_fast_failures=nf["failures"],
                   old_dev_valid=old_d["valid"] if old_d else None, old_dev=old_d["geomean"] if old_d else None)
        if old_d or (nf["valid"]):
            nd = ev.evaluate_program(src, dev, ref, workers=4)["fitness"]
            rec.update(new_dev_valid=nd["valid"], new_dev=nd["geomean"], new_dev_runtime=nd["runtime"],
                       new_dev_failures=nd["failures"], new_dev_t=nd["t"])
        f.write(json.dumps(rec) + "\n")
        f.flush()
