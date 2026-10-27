"""Reporting only (not used for acceptance): max probe infidelity of the compiled circuit vs EXACT e^{-iHt}, t = 1,
H = sum of the IR terms (same probes / cutoffs / ancilla rule as judge.verify.whole_check, which is reused with the
single-term spec [H]). Includes the one-step first-order Trotter error, identical for both compilers."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cvdv_fast import paths, bench
from cvdv import qasm
from cvdv_fast.judge import verify as V
lab, who = sys.argv[1], sys.argv[2]
Hs = bench.hamiltonians(lab)
Ht = Hs[0]
for H in Hs[1:]:
    Ht = Ht + H
if who == "ours":
    d = paths.RESULTS / "final"
    ops = qasm.read(d / f"{lab}.physical.cvdvqasm").ops
    fmap = {tuple(a): tuple(b) for a, b in json.loads((d / f"{lab}.final_map.json").read_text())}
else:
    j = next(json.loads(l) for l in open(paths.GENESIS_OUT / "judged.jsonl") if json.loads(l)["label"] == lab)
    d = paths.GENESIS_OUT / lab / f"seed{j['best_seed']}"
    ops = qasm.read(d / f"{lab}.cvdvqasm").ops
    fmap = {tuple(a): tuple(b) for a, b in json.loads((d / f"{lab}.cvdvqasm.mapping.json").read_text())["final_log_to_phys"]}
cut = paths.WHOLE_CUTOFFS.get(lab, V.WHOLE_CUTOFFS)
w = V.whole_check([Ht], ops, final_map=fmap, cutoffs=cut)
# ideal one-step Trotter product vs exact evolution (compiler-independent)
from cvdv_fast.judge.enr import Space, haar_block, probe_subspace
import numpy as np
qs = sorted({("q", q) for H in Hs for (pa, _b) in H.c for q, _ in pa}, key=lambda x: x[1])
ms = sorted({("qm", m) for H in Hs for (_p, bo) in H.c for m, _, _ in bo}, key=lambda x: x[1])
A = Space(qs, ms, V.N_PROBE if w["exact_sector"] else cut[-1])
cols = probe_subspace(A, qs, ms, V.N_PROBE); pr = haar_block(A, cols, V.N_HAAR, V.SEED)
tro = pr
for H in Hs:
    tro = A.apply_term(tro, A.term_generator(H))
ex = A.apply_term(pr, A.term_generator(Ht))
ov = np.abs(np.einsum("dqp,dqp->p", ex.conj(), tro)) ** 2
print(json.dumps(dict(label=lab, who=who, max_infid_vs_exact=w["max_infid"], mean_infid_vs_exact=w["mean_infid"],
                      cutoffs=w["cutoffs"], ideal_trotter_vs_exact_max=float((1 - ov).max()))))
