"""Run: python3 check.py   (ancilla arm) Reports whether circuit.qasm, with its ancilla qubits, is a valid replacement for
start.qasm (verifier_anc: the cases listed in the task prompt), and its final T-count."""
import os, sys

VENV = "__VENV_PYTHON__"                                   # filled in by agent.py
if os.environ.get("CHECK_IN_VENV") != "1":                 # re-run with the interpreter that has qiskit/gridsynth
    os.environ["CHECK_IN_VENV"] = "1"
    os.execv(VENV, [VENV] + sys.argv)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from qiskit import QuantumCircuit                          # noqa: E402
from pipeline import stats, t_count                        # noqa: E402  (frozen copy in this folder)
from verifier_anc import verify                            # noqa: E402

ref = QuantumCircuit.from_qasm_file(os.path.join(HERE, "tket_start.qasm"))   # the reference: no ancillas
start = QuantumCircuit.from_qasm_file(os.path.join(HERE, "start.qasm"))       # where this run started (may have some)
try:
    new = QuantumCircuit.from_qasm_file(os.path.join(HERE, "circuit.qasm"))
except Exception as e:
    sys.exit(f"PARSE ERROR in circuit.qasm: {e}")
v = verify(ref, new)
s0, s1 = stats(start), stats(new)
print(f"VALID: {'yes' if v['ok'] else 'NO'}  ({v['reason']})")
print(f"qubits: {ref.num_qubits} original + {new.num_qubits - ref.num_qubits} ancillas   "
      f"measurements: {v['measurements'] if v['measurements'] is not None else 'n/a'}")
print(f"gates: {s0['gates']} -> {s1['gates']}   cx: {s0['cx']} -> {s1['cx']}")
print(f"arbitrary rotations: {s0['arbitrary_rz']} -> {s1['arbitrary_rz']}   T/Tdg gates: {s0['t_gates']} -> {s1['t_gates']}")
print(f"final T-count: {t_count(start)} -> {t_count(new)}" + ("" if v["ok"] else "   (not valid, see the first line)"))
