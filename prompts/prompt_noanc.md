# Task: lower the T-count of a quantum circuit

You are working in a folder that contains:
- `circuit.qasm` - the circuit you should improve (OpenQASM 2.0, qelib1.inc). Edit this file.
- `start.qasm`   - a read-only copy of the starting circuit. Do not edit it.
- `check.py`     - run it with `python3 check.py` as often as you like.

## Goal
Make the final T-count reported by `python3 check.py` as low as you can, while `circuit.qasm` stays equivalent
to `start.qasm` (same unitary up to a global phase, operator-norm distance <= 1e-8).

## How the T-count is computed (this is exactly what check.py does)
- Clifford gates (h, x, z, s, sdg, cx, and rz at multiples of pi/2) cost 0 T.
- t, tdg, and rz at odd multiples of pi/4 cost 1 T each.
- Every other rz(theta) is an "arbitrary rotation". All of them are synthesized with gridsynth, sharing a total
  error budget of 1e-3 equally (eps = 1e-3 / N for N arbitrary rotations). Each costs roughly 50 T.

## Rules
- Allowed gates: h, x, z, s, sdg, t, tdg, cx, rz. Keep the same qubits; no extra qubits, no measurements.
- You can read files, edit or rewrite `circuit.qasm`, and run `python3 check.py`.
- You may write your own Python scripts in THIS folder and run them with `./py yourscript.py`
  (a Python with qiskit, numpy and scipy). Scripts must only read and write files inside this folder.
- Before you finish, make sure `python3 check.py` reports EQUIVALENT: yes. If an edit breaks equivalence and you
  cannot fix it, restore `circuit.qasm` from `start.qasm`.

- Run every command in the foreground and wait for it to finish (no background commands, no scheduled wake-ups);
  keep each script under about 10 minutes.

## When you are done
Reply with a short summary: what you changed, why it lowers the T-count, and the final output of `python3 check.py`.
