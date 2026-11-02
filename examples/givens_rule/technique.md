# Free-fermion (Gaussian) re-synthesis

Pull all Cliffords to the end, so the circuit becomes Clifford · (product of Pauli rotations). Absorb the π/2 part of
every rz into the Clifford so only the remainder angle stays as a rotation. If every remaining Pauli is quadratic in
Jordan-Wigner Majoranas (XX, YY, XY, single Z, Z..Z-strings between two sites), the product is a Gaussian unitary. It is
fully described by one orthogonal matrix R in SO(2n). Re-decompose R with Givens elimination into at most n(2n-1)
rotations in adjacent Majorana planes. Each one is a single Pauli rotation, so it costs one rz, and the remaining
Clifford is synthesized for free. The count of arbitrary rotations drops from the original (160) to ≤ n(2n-1) (66 for n=6).

**Applies when:** the circuit is a long Trotter/Floquet sequence of free-fermion terms (XX+YY / XY chains, TFIM-like
Hamiltonians that map to quadratic fermions, Z fields), with many more arbitrary rotations than n(2n-1) and few
qubits (dense 2^n checks, n ≤ 10). Check: the Lie algebra of the rotation generators is a subalgebra of so(2n).

**Does not apply when:** any rotation Pauli is not quadratic (ZZ-with-X interacting terms, 3-body, odd-weight
Majorana), when the circuit has t/tdg gates, or when the rotation count is already ≤ n(2n-1). The script then
copies the input. A further reduction (number-conserving u(n), ~n² params) was checked and did not hold here
because the rotation ordering breaks number conservation.

**Scripts:** `technique.py` (general, self-verifying; this is the one to reuse). The exploration scripts were
`opt.py` (Pauli-rotation extraction + merge), `gauss.py`/`gauss2.py` (the Givens decomposition on this circuit).
Result here: T-count 8560 -> 3354 (160 -> 66 arbitrary rotations).
