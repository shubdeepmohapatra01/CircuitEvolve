import time, json
import v3.runner as R
from v3.tools.evaluate import accepted_book, suite
from v3.judge import dv as J
book = accepted_book()
base = json.load(open("prof3_out.json"))
print(f"{'circuit':11s} {'best(s)':>8s} {'book(s)':>8s} {'speedup':>8s} {'T_best':>7s} {'T_book':>7s} {'dT':>5s}")
tb=tk=0
for c in suite("dv"):
    lab=c["label"]; start=J.load(lab)
    t0=time.time(); res=R.optimize(start, book, 1e-3, domain="dv", label=lab, order="book"); el=time.time()-t0
    b=base[lab]["seconds"]; tb+=b; tk+=el
    print(f"{lab:11s} {b:8.1f} {el:8.1f} {b/el:7.1f}x {base[lab]['t']:7d} {res.cost['t_count']:7d} {res.cost['t_count']-base[lab]['t']:5d}", flush=True)
print(f"{'TOTAL':11s} {tb:8.1f} {tk:8.1f} {tb/tk:7.1f}x")
