"""Genesis baseline: best-of-5-seed physical circuit (v3/baselines, Genesis @996d5d30), metrics + whole-circuit error."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cvdv_fast import paths, bench
from cvdv import qasm, metrics
from cvdv_fast.judge import verify as V

label = sys.argv[1]; cut = tuple(int(x) for x in sys.argv[2].split(",")) if len(sys.argv) > 2 else paths.WHOLE_CUTOFFS.get(label, V.WHOLE_CUTOFFS)
j = next(json.loads(l) for l in open(paths.GENESIS_OUT / "judged.jsonl") if json.loads(l)["label"] == label)
d = paths.GENESIS_OUT / label / f"seed{j['best_seed']}"
c = qasm.read(d / f"{label}.cvdvqasm")
mp = json.loads((d / f"{label}.cvdvqasm.mapping.json").read_text())["final_log_to_phys"]
fmap = {tuple(a): tuple(b) for a, b in mp}
m = metrics.metrics(c)
assert (m["one_op"], m["two_op"], m["total"], m["duration"]) == (j["one_op"], j["two_op"], j["total"], j["duration"]), (m, j)
t0 = time.time()
w = V.whole_check(bench.hamiltonians(label), c.ops, final_map=fmap, cutoffs=cut)
row = dict(label=label, method="Genesis", seed=j["best_seed"], **m, n_qubits=len({x for o in c.ops for x in o.wires if x[0]=='q'}),
           n_qumodes=len({x for o in c.ops for x in o.wires if x[0]=='qm'}), cutoffs=w["cutoffs"], exact_sector=w["exact_sector"], max_infid=w["max_infid"],
           mean_infid=w["mean_infid"], cutoff_gap=w["cutoff_gap"], per_K=w["per_K"], seconds=round(time.time()-t0,1))
print(json.dumps(row))
