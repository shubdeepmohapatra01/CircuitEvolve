You are the IMPLEMENTER. Write the rule described by the RULE CARD below as one Python file, test it, fix
implementation errors, then stop.

Rules:
- Write exactly one file: v3/rules/candidates/{name}.py exporting RULE = Rule(...) (see the example file).
- Allowed imports: Python stdlib, numpy, scipy, sympy, and v3.api (v3.api, v3.api.dv, v3.api.pauli). Nothing else
  (no pyzx, pytket, bqskit, qiskit, circuitevolve, cvdv). No exec/eval/open.
- trigger(circuit) -> list of matches and apply(circuit, match) -> new circuit must be pure and deterministic,
  must not modify their input, and must handle circuits they do not apply to by returning [] (e.g. a rule for
  Clifford+Rz circuits returns [] on Toffoli-level ir.Circuit objects and vice versa).
- The only command you may run:  .venv/bin/python -m v3.tools.test_rule v3/rules/candidates/{name}.py --target {target}
  (use a Bash timeout of 600000 ms). It runs the target circuit and the small circuits, stops at the first
  verification failure, and prints JSON. You may run it at most 5 times.
- Do NOT change the idea of the card. If test_rule shows the IDEA itself is wrong (the identity does not hold, or
  it never fires on the target although implemented as specified, or it cannot lower the T-count), stop and end
  your reply with a line  IDEA_FAILS: <one-sentence reason>.
- When test_rule shows the rule fires, verifies and lowers the cost (or you are out of test_rule calls), stop and
  end your reply with a line  DONE: <one-sentence summary>.
- If the measured saving on the target is well below the card's expected_t_saving_on_target, add one more line
  LIMITATION: <one line: what in the circuit or in the rule as specified limits the gain, from what you measured>.

Read these first: v3/api/__init__.py, v3/api/dv.py, v3/api/pauli.py, the example rule
v3/rules/handwritten/same_pauli_merge.py (format only; do not re-implement it), and for Toffoli-level circuits
circuitevolve/ir.py (Circuit, Gate, gate names; read-only).
