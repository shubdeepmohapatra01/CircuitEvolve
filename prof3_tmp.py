import time, json, sys
import v3.runner as R
from v3.tools.evaluate import accepted_book, suite
from v3.judge import dv as J
book = accepted_book()
out={}
for c in suite("dv"):
    lab=c["label"]
    start=J.load(lab)
    t0=time.time()
    try:
        res=R.optimize(start, book, 1e-3, domain="dv", label=lab)
        el=time.time()-t0
        out[lab]=dict(seconds=round(el,1), t=res.cost["t_count"], acc=sum(e["accepted"] for e in res.log),
                      attempts=len(res.log), whole=len(res.whole_checks))
    except Exception as e:
        out[lab]=dict(error=f"{type(e).__name__}: {e}", seconds=round(time.time()-t0,1))
    print(lab, out[lab], flush=True)
print("\nTOTAL base-book optimize over suite:", round(sum(v.get("seconds",0) for v in out.values()),1), "s")
json.dump(out, open("prof3_out.json","w"), indent=1)
