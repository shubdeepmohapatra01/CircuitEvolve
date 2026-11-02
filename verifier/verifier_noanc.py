"""The no-ancilla verifier. Does `new` do exactly what `old` does?

Build both full unitaries (2^n x 2^n) and compare them, ignoring global phase:
    distance = || U_new - e^{i phi} U_old ||   (operator norm; phi taken from the overlap tr(U_old^dag U_new))
Accept if distance <= tol (1e-8 for exact edits, or the allowed error eps for approximate ones).
No ancillas, no measurements.
"""
import numpy as np
from qiskit.quantum_info import Operator

MAX_QUBITS = 12         # the two full unitaries cost 4^n in memory: 16M complex entries each at 12 qubits


def verify(old, new, tol=1e-8, log=None, label=""):
    if new.num_qubits != old.num_qubits:
        v = dict(ok=False, distance=None, reason=f"qubit count changed {old.num_qubits} -> {new.num_qubits}")
    elif old.num_qubits > MAX_QUBITS:
        v = dict(ok=False, distance=None, reason=f"{old.num_qubits} qubits: too large for a full unitary")
    else:
        A, B = Operator(old).data, Operator(new).data
        # Divide out the single best-fitting global phase (the one maximising |tr(A^dag B)|); what is left is the
        # true deviation. Operator norm, not Frobenius: the largest error on ANY input state, not an average.
        ov = np.vdot(A, B)                                    # tr(A^dag B)
        phase = ov / abs(ov) if abs(ov) > 1e-12 else 1.0
        d = float(np.linalg.norm(B - phase * A, 2))
        v = dict(ok=d <= tol, distance=d, reason="equivalent" if d <= tol else f"distance {d:.3e} > tol {tol:.0e}")
    if log: log("verify " + label, **v)
    return v
