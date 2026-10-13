"""Re-evaluate the best program of each given run on the full dev set under the current evaluator (ev-v3).
Writes results/evolve_opt/bests_reverified_<label>.json (new file). Usage: ... <label> <tag> [<tag> ...]"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from circuitevolve.evolve_opt import evaluate as ev, split  # noqa: E402
from circuitevolve.evolve_opt.programs import BEST_CLASSICAL_PROGRAM, SEED_PROGRAM  # noqa: E402

label, tags = sys.argv[1], sys.argv[2:]
out = REPO / "results" / "evolve_opt" / f"bests_reverified_{label}.json"
assert not out.exists(), out
dev = split.dev()
ref = ev.baseline(dev)
res = {"_eval_version": ev.EVAL_VERSION}
progs = {"seed_program": SEED_PROGRAM, "best_classical_program": BEST_CLASSICAL_PROGRAM}
for t in tags:
    progs[t] = (REPO / "results" / "evolve_opt" / t / "best_program.py").read_text()
for name, src in progs.items():
    r = ev.evaluate_program(src, dev, ref, workers=2)
    f = r["fitness"]
    res[name] = dict(hash=ev.source_hash(src), valid=f["valid"], geomean=f["geomean"], runtime=f["runtime"], t=f["t"],
                     failures=f["failures"],
                     bound={k: v.get("bound") for k, v in r["results"].items()},
                     check={k: (v.get("check") or {}).get("dist") for k, v in r["results"].items()},
                     method={k: (v.get("check") or {}).get("method") for k, v in r["results"].items()})
    out.write_text(json.dumps(res, indent=1))
