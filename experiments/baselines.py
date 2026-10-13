"""P2: baseline table for the adder test -> results/baselines.csv

Every row is produced by our own cost model on a circuit that passed our verifier at that n
(column `verified`). pyzx outputs are dense, so exact verification is limited to n <= PYZX_VERIFY_MAX;
beyond that the row reports T-count only and says so.
"""
import pathlib, time

import pandas as pd

from circuitevolve.baselines import cuccaro, gidney, pyzx_opt
from circuitevolve.ir import TIER_A, TIER_B
from circuitevolve.spec import AdderSpec
from circuitevolve.verify import verify

N = list(range(1, 17))
PYZX_VERIFY_MAX = 5
spec = AdderSpec()
methods = {
    "naive Cuccaro": (cuccaro.construct, TIER_A | TIER_B, N),
    "pyzx full_reduce": (lambda n: pyzx_opt.optimize(cuccaro.construct(n)), TIER_B, N),
    "Gidney temporary AND": (gidney.construct_tier_b, TIER_B, N),
}
rows = []
for name, (fn, vocab, ns) in methods.items():
    for n in ns:
        t = time.time()
        do_verify = not (name.startswith("pyzx") and n > PYZX_VERIFY_MAX)
        if do_verify:
            r = verify(fn, spec, [n], vocab)
            assert r.ok, (name, n, r.level, r.reason)
            c = r.costs[n]
        else:
            from circuitevolve.cost import cost
            c = cost(fn(n))
        rows.append({"method": name, "n": n, **c, "verified": do_verify, "seconds": round(time.time() - t, 2)})
        print(name, n, c["t_count"], do_verify, flush=True)
out = pathlib.Path(__file__).resolve().parents[1] / "results" / "baselines.csv"
pd.DataFrame(rows).to_csv(out, index=False)
print("wrote", out)
