import time, numpy as np, inspect
from circuitevolve.blocks import verify_block as vb
from circuitevolve.core.circuit import Circuit
print("=== circuit_check: does it rebuild BOTH sides every call? ===")
print(inspect.getsource(vb.circuit_check)[:900])
c = Circuit.from_qasm(open('v3/suite/inputs/qpe_8.qasm').read()); ops=list(c.ops); n=c.n
def tt(f,k=5):
    t0=time.time()
    for _ in range(k): f()
    return 1000*(time.time()-t0)/k
one = tt(lambda: vb.unitary(ops, n))
both = tt(lambda: vb.circuit_check(ops, ops, n))
print(f"\nqpe_8 (8q,1034 ops): one unitary build {one:7.1f} ms | full circuit_check {both:7.1f} ms "
      f"-> ratio {both/one:.2f}x  (caching the reference saves ~{100*(1-one/both):.0f}%)")
print("\n=== is price()/gridsynth actually cheap (cache warm)? ===")
import sys; sys.path.insert(0,'.')
from v3.judge import dv as J
st=J.load('hhl_8')
t=tt(lambda: J.measure(st, 1e-3), 3)
print(f"J.measure(hhl_8, eps=1e-3) [1101 rotations, warm gridsynth cache]: {t:.1f} ms")
