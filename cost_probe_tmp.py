import time, numpy as np
from circuitevolve.blocks import verify_block as vb
from circuitevolve.core.circuit import Circuit

def tt(f, n=5):
    t0=time.time()
    for _ in range(n): f()
    return (time.time()-t0)/n

for lab in ['qft_8','qpe_8','hhl_8','qae_13']:
    c = Circuit.from_qasm(open(f'v3/suite/inputs/{lab}.qasm').read(), name=lab)
    ops = list(c.ops); n = c.n
    t = tt(lambda: vb.unitary(ops, n), 3)
    print(f"{lab:8s} n={n:2d} ops={len(ops):5d}  dense unitary build: {1000*t:8.1f} ms   "
          f"({2**n}x{2**n} matrix, {len(ops)} gate applications)")

# a 4-qubit, 40-op block -- what BQSKit actually compares
rng = np.random.default_rng(0)
blk = []
for i in range(40):
    if i % 3 == 0: blk.append(('cx', (int(rng.integers(4)), ), None))
for i in range(40):
    q = int(rng.integers(4))
    blk.append(('rz', (q,), float(rng.normal())))
blk = [('rz',(int(rng.integers(4)),), float(rng.normal())) if i%2 else
       ('cx', tuple(rng.choice(4, 2, replace=False).tolist()), None) for i in range(40)]
t = tt(lambda: vb.unitary(blk, 4), 50)
print(f"\n4-qubit 40-op block (BQSKit's unit): {1000*t:8.3f} ms  (16x16 matrix)")
print(f"ratio hhl_8-whole / 4q-block = {tt(lambda: vb.unitary(list(Circuit.from_qasm(open('v3/suite/inputs/hhl_8.qasm').read()).ops), 8),1)/t:,.0f}x")
