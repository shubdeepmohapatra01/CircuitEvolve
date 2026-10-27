"""Reporting: full r-step Trotter circuit (step size t/r, t = 1) compiled by our book, routed once, vs EXACT e^{-iHt}.
Also the ideal r-step Trotter product vs exact (compiler-independent)."""
import json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cvdv_fast import paths, runner, bench
from cvdv import route as ROUTE, metrics as MET
from cvdv_fast.judge import verify as V
from cvdv_fast.judge.enr import Space, haar_block, probe_subspace
import numpy as np
lab, r = sys.argv[1], int(sys.argv[2])
src = (paths.V3_INPUTS / f"{lab}.ir.cvdvqasm").read_text()
sc = lambda m: f"({complex(m.group(1)) / r!r})".replace("(", "(", 1)
scaled = re.sub(r"\(([-+0-9.e]+j)\)", lambda m: "(" + repr(complex(m.group(1)) / r).strip("()") + ")", src)
scaled = re.sub(r"pauli\(([-+0-9.e]+j)\)", lambda m: "pauli(" + repr(complex(m.group(1)) / r).strip("()") + ")", scaled)
d = paths.RESULTS / "multistep"; d.mkdir(exist_ok=True)
(d / f"{lab}.ir.cvdvqasm").write_text(scaled)
Hfull = bench.hamiltonians(lab)                     # t = 1 terms (original IR)
paths.V3_INPUTS = d                                 # scaled IR for synthesis
t0 = time.time(); log = []
book = runner.load_book()
ops, rep = runner.synthesize(lab, book, paths.EPS / r, log)
assert ops is not None, rep
ops, _, _ = runner.rewrite_pass(ops, book, "logical", paths.EPS / 4, log)
full = ops * r
full, _, _ = runner.rewrite_pass(full, book, "logical", paths.EPS / 4, log)
best = None
for s in range(5):
    phys, info = ROUTE.route(full, seed=s); m = MET.metrics(phys)
    if best is None or m["total"] < best[1]["total"]: best = (phys, m, info)
phys, m, info = best
Ht = Hfull[0]
for H in Hfull[1:]: Ht = Ht + H
cut = paths.WHOLE_CUTOFFS.get(lab, V.WHOLE_CUTOFFS)
w = V.whole_check([Ht], phys, final_map=info["final_map"], cutoffs=cut)
Hs = bench.hamiltonians(lab)                        # scaled terms
qs = sorted({("q", q) for H in Hs for (pa, _b) in H.c for q, _ in pa}, key=lambda x: x[1])
ms = sorted({("qm", mm) for H in Hs for (_p, bo) in H.c for mm, _, _ in bo}, key=lambda x: x[1])
A = Space(qs, ms, V.N_PROBE if w["exact_sector"] else cut[-1])
cols = probe_subspace(A, qs, ms, V.N_PROBE); pr = haar_block(A, cols, V.N_HAAR, V.SEED)
tro = pr
for _ in range(r):
    for H in Hs: tro = A.apply_term(tro, A.term_generator(H))
ex = A.apply_term(pr, A.term_generator(Ht))
ideal = float((1 - np.abs(np.einsum("dqp,dqp->p", ex.conj(), tro)) ** 2).max())
row = dict(label=lab, r=r, ours_vs_exact=w["max_infid"], ideal_trotter_vs_exact=ideal, **m, ledger=rep["synth_err"] * r,
           cutoffs=w["cutoffs"], seconds=round(time.time() - t0, 1))
with open(d / "results.jsonl", "a") as f: f.write(json.dumps(row) + "\n")
print(json.dumps(row))
