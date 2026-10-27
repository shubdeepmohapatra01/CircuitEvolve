"""Run the current book (seeds + accepted) on benchmarks; one JSON line per benchmark to results/<tag>.jsonl."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cvdv_fast import paths, runner
from cvdv import qasm

tag = sys.argv[1]; labels = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] != "all" else paths.BENCH
folders = tuple(sys.argv[3].split(",")) if len(sys.argv) > 3 else ("handwritten_seeds", "accepted")
book = runner.load_book(folders)
outdir = paths.RESULTS / tag; outdir.mkdir(parents=True, exist_ok=True)
for lab in labels:
    try:
        r = runner.compile_benchmark(lab, book, whole_cutoffs=paths.WHOLE_CUTOFFS.get(lab))
    except Exception as e:
        import traceback; r = dict(label=lab, valid=False, reason="exception", err=traceback.format_exc()[-1500:])
    ops = r.pop("_phys_ops", None); fm = r.pop("_final_map", None)
    if ops is not None:
        qasm.write(qasm.Circuit(ops=ops), outdir / f"{lab}.physical.cvdvqasm")
        (outdir / f"{lab}.final_map.json").write_text(json.dumps([[list(k), list(v)] for k, v in fm.items()]))
    r["book"] = [x.name for x in book]
    with open(outdir / "results.jsonl", "a") as f:
        f.write(json.dumps(r, default=str) + "\n")
    print(lab, r.get("valid"), r.get("total"), r.get("two_op"), r.get("duration"), "ledger", r.get("err_ledger"),
          "infid", r.get("max_infid"), r.get("seconds"), "s", r.get("reason", ""), flush=True)
