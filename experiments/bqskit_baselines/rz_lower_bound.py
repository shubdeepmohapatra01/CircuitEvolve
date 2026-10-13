"""Per-1q-gate minimal number of non-Clifford Z rotations (k in 0..3) via the Bloch rotation R:
k=0 iff R is a signed permutation; k<=1 iff some |R_ij|=1; k<=2 iff some R_ij=0; else 3.
(U = C1 RZ C2 iff U maps a stabilizer axis onto a stabilizer axis; U = C1 RZ C RZ C2 iff U maps
a stabilizer axis into a stabilizer plane.)"""
import sys, numpy as np
from bqskit import Circuit
from bqskit.passes import GroupSingleQuditGatePass, UnfoldPass
sys.path.insert(0, '.')
from serial_runtime import run_passes
P = [np.array([[0,1],[1,0]]), np.array([[0,-1j],[1j,0]]), np.array([[1,0],[0,-1]])]
def bloch(U):
    U = np.asarray(U, complex)
    return np.array([[0.5*np.real(np.trace(P[i] @ U @ P[j] @ U.conj().T)) for j in range(3)] for i in range(3)])
def kmin(U, tol=1e-8):
    R = np.abs(bloch(U))
    if np.all((np.abs(R-1) < tol) | (R < tol)): return 0
    if np.any(np.abs(R-1) < tol): return 1
    if np.any(R < tol): return 2
    return 3
def count(c):
    k = [kmin(op.get_unitary()) for op in c if op.num_qudits == 1]
    return sum(k), np.bincount(k, minlength=4).tolist()
if __name__ == '__main__':
    for name in sys.argv[1:]:
        c = Circuit.from_file(f'../../benchmarks/bqskit_qseed/qasm/{name}.qasm')
        a = count(c)
        g = c.copy(); run_passes(g, [GroupSingleQuditGatePass()])
        b = count(g)
        print(name, 'per-gate', a, 'merged', b)
