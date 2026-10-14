"""Compile the small benchmarks under both ISAs, route with Genesis' router (SWAP fixed), and
write one CSV per Python hash seed next to Genesis' numbers for the same hash seed.

Genesis' router iterates over Python sets of strings, so its output depends on PYTHONHASHSEED;
both compilers are therefore run under the same set of hash seeds (scripts/compare_isas_sweep.sh).

    PYTHONHASHSEED=3 python experiments/compare_isas.py results/isa_sweep/hs3.csv results/isa_sweep/genesis_hs3
"""
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as X  # noqa: E402
from cvdv import isa as ISA, metrics, qasm, route as RT  # noqa: E402

BENCH = ["kerr_small", "boseHubbard_small", "z2Higgs_small", "heisenberg_small", "electronicVibration_small"]
rules = X.load_rules(os.path.join(X.ROOT, "rulebook", "rules.py"))
rows = []
HS = os.environ.get("PYTHONHASHSEED", "random")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(X.RES, "compare_isas_small_nmax3.csv")
GDIR = sys.argv[2] if len(sys.argv) > 2 else None
for name in BENCH:
    if GDIR:
        g = metrics.metrics(qasm.read(f"{GDIR}/{name}/{name}.cvdvqasm"))
        rows.append(dict(benchmark=name, compiler="Genesis", isa="Genesis Table 2", **g, eps_bound=None, hashseed=HS))
    for label, isa in [("phase-space + BS", ISA.PS_BS), ("Genesis Table 2", ISA.GENESIS)]:
        t0 = time.time()
        tl, ops, rep, comp = X.compile_bench(name, rules, eps=1e-3, n_max=3, isa=isa)
        phys, info = RT.route(ops)
        m = metrics.metrics(phys)
        used = sorted({o.name for o in phys if len(o.wires) > 1})
        rows.append(dict(benchmark=name, compiler="ours", isa=label, **m, eps_bound=rep["eps_bound"],
                         two_op_gate_types=" ".join(used), seconds=round(time.time() - t0, 1), hashseed=HS))
        print(name, label, m, f"{rep['eps_bound']:.1e}", used, rows[-1]["seconds"], flush=True)
df = pd.DataFrame(rows)
df.to_csv(OUT, index=False)
