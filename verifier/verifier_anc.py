"""The ancilla verifier. Does `new`, run with fresh ancilla qubits, do exactly what `old` does on the original qubits?

old: the start circuit, a unitary on n qubits (gate set h x z s sdg t tdg cx rz, no measurements).
new: the same n qubits first (DATA, same order), then a ANCILLAS, 1 <= a <= MAX_ANCILLAS.

The cases it accepts (anything else is rejected with a reason):
  1. clean ancillas   every ancilla starts in |0>.
  2. uncompute        an ancilla ends in |0> (or in any fixed state), unentangled from the data; it is then dropped.
  3. measure out      `measure q[k] -> m[0];` on an ANCILLA, into its own 1-bit creg, once; after that the ancilla is
                      never used again.
  4. fix-up           `if (m == 0 or 1) G;` with m a 1-bit creg measured earlier and G ONE Clifford gate in IF_GATES
                      on data qubits or unmeasured ancillas.
  and at least one ancilla takes part in a cx (otherwise it is a no-ancilla rewrite: use verifier_noanc).
Rejected: a = 0 or a > MAX_ANCILLAS, measuring a data qubit, reset, reusing a measured qubit, non-Clifford gates or
multi-bit conditions under `if`, any gate outside GATES. Dirty ancillas need no tag here or anywhere: borrowing an
EXISTING qubit is a no-ancilla rewrite (verifier_noanc checks existing qubits on every input).

Check (deferred measurement). Drop each measurement and replace `if (m == v) G` by G controlled on the measured
ancilla (control state v); exact because that ancilla is never touched after its measurement. The result W is a
unitary on n + a qubits; on |x>|0..0> it gives  W|x>|0> = sum_m |m> (x) K_m|x>  (m = ancilla basis state).
Accept iff  W|x>|0> = e^{i phi} (U_old|x>) (x) |anc>  for ONE ancilla state |anc> on every input x, i.e. every block
K_m is anc_m * U_old: the data end exactly as in old, unentangled, on every input and every measurement branch.
distance = || W[:, anc=0] - U_old (x) |anc> ||  (operator norm; anc_m = tr(U_old^dag K_m) / 2^n, normalised)
         = the worst-case error of the output state over all inputs. Accept if distance <= tol (1e-8).
Cost: simulates 2^n inputs on n + a qubits at once; refused above MAX_WORK = 2^26 amplitudes (n = 10, a = 6).
"""
import numpy as np
from qiskit.circuit import ClassicalRegister
from qiskit.quantum_info import Operator

# MAX_WORK bounds the simulation below: 2^(N+n) complex numbers, i.e. ~1 GiB at 2^26. Measured cost at the limit:
# ~60 s and 3.1 GiB for 10 data + 6 ancillas.
MAX_ANCILLAS, MAX_WORK, TOL = 6, 2 ** 26, 1e-8
GATES = {"h", "x", "z", "s", "sdg", "t", "tdg", "cx", "rz"}
IF_GATES = {"x", "z", "s", "sdg", "h", "cx", "cz"}   # Clifford only: a conditional T would be a T the metric cannot see


def _deferred(new, n):
    """new -> ([(matrix, qubits)] of the deferred unitary W, number of measurements), or raise ValueError(reason)."""
    ops, creg_qubit, measured, uses_cx = [], {}, set(), False
    for g in new.data:
        op, qs = g.operation, [new.find_bit(q).index for q in g.qubits]
        # Rejecting reuse of a measured qubit is what makes deferred measurement exact: if nothing touches the
        # ancilla after its measurement, the measurement commutes to the end of the circuit.
        if any(q in measured for q in qs):
            raise ValueError(f"q[{[q for q in qs if q in measured][0]}] is used after its measurement")
        if op.name == "measure":
            regs = new.find_bit(g.clbits[0]).registers
            if qs[0] < n:
                raise ValueError(f"measures data qubit q[{qs[0]}] (only ancillas may be measured)")
            if len(regs) != 1 or regs[0][0].size != 1 or regs[0][0].name in creg_qubit:
                raise ValueError("each measurement needs its own 1-bit creg, written once")
            creg_qubit[regs[0][0].name] = qs[0]
            measured.add(qs[0])
        elif op.name == "if_else":
            reg, val = op.condition if isinstance(op.condition, tuple) else (None, None)
            body = op.blocks[0]
            if not isinstance(reg, ClassicalRegister) or reg.size != 1 or reg.name not in creg_qubit:
                raise ValueError("an `if` must test a 1-bit creg that was measured earlier")
            if len(op.blocks) > 1 and op.blocks[1] is not None or len(body.data) != 1:
                raise ValueError("an `if` must hold exactly one gate")
            b = body.data[0]
            if b.operation.name not in IF_GATES:
                raise ValueError(f"`{b.operation.name}` under `if` (allowed: {sorted(IF_GATES)})")
            bq = [qs[body.find_bit(q).index] for q in b.qubits]
            ops.append((Operator(b.operation.control(1, ctrl_state=int(val))).data, [creg_qubit[reg.name]] + bq, "if"))
        elif op.name in GATES:
            uses_cx |= op.name == "cx" and any(q >= n for q in qs)
            ops.append((Operator(op).data, qs, op.name))
        else:
            raise ValueError(f"gate `{op.name}` not allowed (allowed: {sorted(GATES)}, measure, if)")
    # An "ancilla" that never interacts with the data is an idle qubit: that is a no-ancilla rewrite, and the
    # stricter no-ancilla verifier must judge it.
    if not uses_cx:
        raise ValueError("no ancilla takes part in a cx: this is a no-ancilla rewrite (use verifier_noanc)")
    return ops, len(measured)


def _apply(psi, mat, qs, N, name=""):
    """Apply a k-qubit gate (qiskit little-endian matrix on qubits qs) to the columns of psi (2^N x cols).
    1-qubit gates and cx work in place on views (qubit q = axis N-1-q); anything else goes through tensordot.
    Hand-written rather than building the 2^N x 2^N gate matrix, which would not fit at N = 16."""
    if len(qs) == 1:
        v = psi.reshape(2 ** (N - 1 - qs[0]), 2, -1)
        if mat[0, 1] == 0 and mat[1, 0] == 0:                     # diagonal: rz, t, s, z, ...
            if mat[0, 0] != 1: v[:, 0] *= mat[0, 0]
            v[:, 1] *= mat[1, 1]
        else:
            a0 = v[:, 0].copy()
            v[:, 0] *= mat[0, 0]; v[:, 0] += mat[0, 1] * v[:, 1]
            v[:, 1] *= mat[1, 1]; v[:, 1] += mat[1, 0] * a0
        return psi
    if name == "cx":
        v, i10 = psi.reshape([2] * N + [-1]), [slice(None)] * (N + 1)
        i10[N - 1 - qs[0]], i10[N - 1 - qs[1]] = 1, 0
        i11 = list(i10); i11[N - 1 - qs[1]] = 1
        tmp = v[tuple(i10)].copy(); v[tuple(i10)] = v[tuple(i11)]; v[tuple(i11)] = tmp
        return psi
    k = len(qs)
    axes = [N - 1 - qs[k - 1 - j] for j in range(k)]            # tensor axis of each matrix index bit
    psi = np.tensordot(mat.reshape([2] * (2 * k)), psi.reshape([2] * N + [-1]), axes=(list(range(k, 2 * k)), axes))
    return np.moveaxis(psi, list(range(k)), axes).reshape(2 ** N, -1)


def verify(old, new, tol=TOL, log=None, label=""):
    n, N = old.num_qubits, new.num_qubits
    v = dict(ok=False, distance=None, ancillas=N - n, measurements=None)
    try:
        if not 1 <= N - n <= MAX_ANCILLAS:
            raise ValueError(f"{N - n} ancillas (need 1 to {MAX_ANCILLAS} extra qubits after the {n} data qubits)")
        if 2 ** (N + n) > MAX_WORK:
            raise ValueError(f"too large to check: {n} data + {N - n} ancilla qubits (limit 2^(N+n) <= 2^26)")
        ops, v["measurements"] = _deferred(new, n)
        # All 2^n basis inputs at once as the columns of one matrix, so one pass over the gates checks every input.
        psi = np.eye(2 ** N, 2 ** n, dtype=complex)                # columns |x>|0..0>, ancillas are the high bits
        for mat, qs, name in ops:
            psi = _apply(psi, mat, qs, N, name)
        U = Operator(old).data
        # Row block m of psi is K_m: what the data undergoes when the ancillas end in basis state m. Correct iff
        # every K_m is a multiple of U; anc holds those multipliers as the overlap tr(U^dag K_m) / 2^n.
        anc = np.array([np.vdot(U, psi[m * 2 ** n:(m + 1) * 2 ** n]) for m in range(2 ** (N - n))]) / 2 ** n
        if np.linalg.norm(anc) < 1e-6:
            raise ValueError("no ancilla outcome gives the start circuit's action on the data")
        # Residual against the ideal product form |anc> (x) U; its operator norm (sqrt of the top eigenvalue of
        # R^dag R) is the worst-case output error over all inputs and all measurement branches at once.
        R = psi - np.kron((anc / np.linalg.norm(anc)).reshape(-1, 1), U)
        d = float(np.sqrt(max(np.linalg.eigvalsh(R.conj().T @ R)[-1], 0.0)))
        v |= dict(ok=d <= tol, distance=d, reason="equivalent" if d <= tol else f"distance {d:.3e} > tol {tol:.0e}")
    except ValueError as e:
        v["reason"] = str(e)
    if log: log("verify_anc " + label, **v)
    return v
