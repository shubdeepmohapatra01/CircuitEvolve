import time, collections, sys
import v3.runner as R
from v3.tools.evaluate import accepted_book
from v3.judge import dv as J
from circuitevolve.v2 import verify as V2

book = accepted_book()
label = sys.argv[1] if len(sys.argv)>1 else "qft_8"

stats = collections.defaultdict(lambda: [0, 0.0])
def size_of(x):
    if isinstance(x, tuple) and len(x)==2 and isinstance(x[0], list): return x[1], len(x[0])
    if hasattr(x, "ops"): return x.n, len(x.ops)
    if hasattr(x, "gates"): return x.n_qubits, len(x.gates)
    return -1, -1

_ver = J.verify
def ver(c, ref, *a, **kw):
    nq, nops = size_of(c)
    nqr, nopsr = size_of(ref)
    t=time.time(); r=_ver(c,ref,*a,**kw); dt=time.time()-t
    key=(kw.get("mode","exact"), r.method, nq)
    stats[key][0]+=1; stats[key][1]+=dt
    return r
J.verify = ver

start = J.load(label)
t0=time.time(); res = R.optimize(start, book, 1e-3, domain="dv", label=label); el=time.time()-t0
print(f"== {label}: optimize total {el:.1f} s, T={res.cost['t_count']}, accepted={sum(e['accepted'] for e in res.log)}")
print(f"{'mode':10s} {'method':34s} {'nq':>3s} {'calls':>6s} {'sec':>8s} {'ms/call':>8s} {'%':>5s}")
tot=0
for (mode,method,nq),(n,s) in sorted(stats.items(), key=lambda x:-x[1][1]):
    tot+=s
    print(f"{mode:10s} {str(method)[:34]:34s} {nq:3d} {n:6d} {s:8.2f} {1000*s/n:8.1f} {100*s/el:5.1f}")
print(f"{'TOTAL verify':46s} {sum(n for n,_ in stats.values()):10d} {tot:8.2f} {'':8s} {100*tot/el:5.1f}")
