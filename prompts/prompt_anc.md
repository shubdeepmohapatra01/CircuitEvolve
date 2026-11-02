# Task: lower the T-count of a quantum circuit using ancilla qubits

You are working in a folder that contains:
- `circuit.qasm` - the circuit you should improve (OpenQASM 2.0, qelib1.inc). Edit this file.
- `start.qasm`   - a read-only copy of the starting circuit. Do not edit it. (It may already use ancillas.)
- `tket_start.qasm` - read-only: the same circuit without ancillas. check.py compares circuit.qasm against it.
- `logical.qasm` - a read-only copy of the original benchmark file before it was compiled to tket_start.qasm: the same
                   qubits in the same order and the same unitary, but it may use other gates (ccx, ccz, custom gate
                   definitions). Read it to see the circuit's structure; its gates are not allowed in circuit.qasm.
- `check.py`     - run it with `python3 check.py` as often as you like.

## Goal
Make the final T-count reported by `python3 check.py` as low as you can by adding ancilla qubits, while `circuit.qasm`
does exactly what `tket_start.qasm` does on the original qubits (the cases below; distance <= 1e-8).
A circuit without ancillas (such as tket_start.qasm) is reported as not valid for this task.

## How the T-count is computed (this is exactly what check.py does)
- Clifford gates (h, x, z, s, sdg, cx, cz under `if`, and rz at multiples of pi/2) cost 0 T. Measurements cost 0 T.
- t, tdg, and rz at odd multiples of pi/4 cost 1 T each.
- Every other rz(theta) is an "arbitrary rotation". All of them are synthesized with gridsynth, sharing a total
  error budget of 1e-3 equally (eps = 1e-3 / N for N arbitrary rotations). Each costs roughly 50 T.
- A gate inside an `if` is counted as if it always runs.

## Ancillas: the only cases check.py accepts
1. Qubits: keep the original n qubits first, in the same order, and add 1 to 6 ancilla qubits after them (enlarge
   `qreg q[...]`, or declare a second `qreg` after it). Every ancilla starts in |0>.
2. Uncompute: an ancilla may end in |0>, or in any other fixed state that does not depend on the input, as long as it
   is not entangled with the original qubits.
3. Measure out: `measure q[k] -> mk[0];` with its own 1-bit register `creg mk[1];`. Only ancillas may be measured, each
   at most once, and a measured ancilla is never used again (no gate on it, no second measurement).
4. Fix-up: after a measurement, `if (mk == 1) G;` (or `mk == 0`) where `mk` is a 1-bit register measured earlier and G
   is ONE Clifford gate: x, z, s, sdg, h, cx or cz, on original qubits or ancillas not measured yet.
- check.py requires: for every input state of the original qubits and every measurement outcome, the original qubits
  end exactly as tket_start.qasm leaves them (up to a global phase), unentangled from the ancillas.
- At least one ancilla must take part in a cx. Rewrites that need no ancilla are handled in a separate task and are
  not accepted here.

## Rules
- Allowed gates: h, x, z, s, sdg, t, tdg, cx, rz; plus measure and `if` as in cases 3 and 4.
- Not accepted: removing or reordering original qubits, more than 6 ancillas, measuring an original qubit, reset,
  reusing a measured ancilla, a non-Clifford gate or more than one gate under an `if`, conditions on multi-bit
  registers, barriers.
- You can read files, edit or rewrite `circuit.qasm`, and run `python3 check.py`.
- You may write your own Python scripts in THIS folder and run them with `./py yourscript.py`
  (a Python with qiskit, numpy and scipy). Scripts must only read and write files inside this folder.
- Before you finish, make sure `python3 check.py` reports VALID: yes. If an edit breaks validity and you cannot fix
  it, restore `circuit.qasm` from `start.qasm` (the harness then keeps the best valid circuit so far).

- Run every command in the foreground and wait for it to finish (no background commands, no scheduled wake-ups);
  keep each script under about 10 minutes. check.py itself can take up to a minute on 10 original qubits plus 6
  ancillas.

## When you are done
Reply with a short summary: what you changed, why it lowers the T-count, how many ancillas and measurements it uses,
and the final output of `python3 check.py`.
