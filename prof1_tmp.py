import time, collections, sys
import v3.runner as R
from v3.tools.evaluate import accepted_book
from v3.judge import dv as J

book = accepted_book()
print("book:", [r.name for r in book], "size", len(book))

# instrument: count optimize invocations and J.measure / verify calls
counts = collections.Counter(); timers = collections.defaultdict(float)
_opt = R.optimize
depth = [0]
def opt(circuit, bk, eps, *a, **kw):
    counts[f"optimize(order={kw.get('order','best' if len(a)<7 else a[6])},|book|={len(list(bk))})"] += 1
    counts["optimize_total"] += 1
    return _opt(circuit, bk, eps, *a, **kw)
R.optimize = opt

_meas = J.measure
def meas(c, *a, **kw):
    counts["J.measure"] += 1
    t=time.time(); r=_meas(c,*a,**kw); timers["J.measure"]+=time.time()-t
    return r
J.measure = meas

_ver = J.verify
def ver(c, ref, *a, **kw):
    counts["J.verify(whole)"] += 1
    t=time.time(); r=_ver(c,ref,*a,**kw); timers["J.verify(whole)"]+=time.time()-t
    return r
J.verify = ver

label = sys.argv[1] if len(sys.argv)>1 else "qft_8"
start = J.load(label)
t0=time.time()
res = opt(start, book, 1e-3, domain="dv", label=label)
el=time.time()-t0
print(f"\n== one optimize({label}, full book of {len(book)}) : {el:.1f} s ==")
print("  result T:", res.cost["t_count"], " applications:", sum(e["accepted"] for e in res.log))
print("\ncall counts:")
for k,v in counts.most_common(): print(f"   {k:46s} {v}")
print("\ntimers:")
for k,v in timers.items(): print(f"   {k:20s} {v:8.1f} s  ({100*v/el:.0f}% of run)")
