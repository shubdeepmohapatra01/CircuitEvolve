import time, numpy as np
from circuitevolve.blocks import verify_block as vb
from circuitevolve.v2 import verify as V2
from v3.judge import dv as J

rng = np.random.default_rng(0)
blk = [(('rz',(int(rng.integers(4)),), float(rng.normal())) if i%2 else
        ('cx', tuple(rng.choice(4,2,replace=False).tolist()), None)) for i in range(40)]
a = (blk, 4); b = (list(blk), 4)

def tt(f, n=200):
    t0=time.time()
    for _ in range(n): f()
    return 1000*(time.time()-t0)/n

print(f"raw: 2x vb.unitary(4q,40ops)            {tt(lambda: (vb.unitary(blk,4), vb.unitary(blk,4))):7.3f} ms")
print(f"raw: vb.verify_instance (the actual cmp) {tt(lambda: vb.verify_instance(blk, blk, 4, eps=1e-8)):7.3f} ms")
print(f"ReferenceSpec.from_circuit alone         {tt(lambda: V2.ReferenceSpec.from_circuit(b)):7.3f} ms")
print(f"FULL J.verify(approx) as the runner calls{tt(lambda: J.verify(a, b, mode='approx', eps=1e-8), 100):7.3f} ms")
print(f"  of which check_frozen() (hash 8 files) {tt(lambda: __import__('v3.judge.frozen',fromlist=['x']).check_frozen(), 100):7.3f} ms")
