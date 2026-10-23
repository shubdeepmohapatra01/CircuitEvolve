# What a rule program can use (v3.api)

A rule is one Python file exporting RULE = Rule(name, domain="dv", kind, contract, source, idea, trigger, apply).
trigger(circuit) -> list of matches; apply(circuit, match) -> new circuit. Pure, deterministic. The runner applies
matches one at a time, verifies every application with the frozen judge (exact D[omega] check on the changed
window when both sides are Clifford+T; numerical operator distance otherwise; relaxed specification check for
ancilla / measurement constructions), and keeps it only if the T-count (then qubits, then CNOT) drops.

Imports allowed: stdlib, numpy, scipy, sympy, v3.api.
- v3.api.dv: Circuit(n, ops) for Clifford+Rz circuits, ops = (name, qubits, angle) over h s sdg x z t tdg cx cz rz;
  rotation(op) -> Z-angle of t/tdg/rz else None; with_ops(c, ops) builds the result (rz at pi/4 multiples become
  Clifford/T gates). IRCircuit / IRGate for Toffoli-level circuits (x z h s sdg t tdg cx cz ccx ccz, measure,
  classically controlled gates, and_compute / and_uncompute gadgets); ir_with_gates(c, gates, n_qubits=...)
  builds the result, extra ancillas appended as qubits n, n+1, ...
- v3.api.pauli: z_on(q), conjugate(P, gate, qubits) (P -> C P C^dag for Cliffords), commutes_with_z(P, q), is_z(P, q).
Rules may not import pyzx, pytket, bqskit, qiskit or the judge.
