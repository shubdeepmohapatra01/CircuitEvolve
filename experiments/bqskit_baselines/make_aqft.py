"""Diagnostic inputs: textbook (approximate) QFT-n, cp gates kept only for distance d <= dmax,
written in two gate sets: cp-level lowered by qiskit to {u3,cx} (opt 0), and {h, rz, cx}+swap."""
import math, sys
from pathlib import Path
from qiskit import QuantumCircuit, transpile
from qiskit.qasm2 import dumps
def aqft(n, dmax):
    qc = QuantumCircuit(n)
    for j in reversed(range(n)):          # same orientation as qseed (h on top qubit first)
        qc.h(j)
        for k in reversed(range(j)):
            d = j - k
            if d <= dmax:
                qc.cp(math.pi / 2**d, j, k)
    for i in range(n // 2):
        qc.swap(i, n - 1 - i)
    return qc
if __name__ == '__main__':
    n, dmax = int(sys.argv[1]), int(sys.argv[2])
    out = Path('../../results/bqskit_baselines/work'); out.mkdir(parents=True, exist_ok=True)
    qc = aqft(n, dmax)
    print('cp gates', qc.count_ops().get('cp', 0))
    (out / f'aqft{n}_d{dmax}_u3cx.qasm').write_text(dumps(transpile(qc, basis_gates=['u3', 'cx'], optimization_level=0)))
    (out / f'aqft{n}_d{dmax}_hrzcx.qasm').write_text(dumps(transpile(qc, basis_gates=['h', 'rz', 'cx'], optimization_level=0)))
