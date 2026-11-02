"""The no-ancilla verifier on hand-made edits of tfim_4, and on every baseline output (each must be equivalent)."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "verifier")]
from qiskit import QuantumCircuit
from pipeline import HERE, Log, load, pyzx, tket
from verifier_noanc import verify

log = Log("verifier_test")
c = load(os.path.join(HERE, "circuits", "tfim_4.qasm"))
gates = list(c.data)
rz = [i for i, g in enumerate(gates) if g.operation.name == "rz"]
cx = [i for i, g in enumerate(gates) if g.operation.name == "cx"]


def edited(fn):
    out = QuantumCircuit(c.num_qubits)
    for g in fn(list(gates)):
        out.append(g.operation, g.qubits)
    return out


def with_angle(g, theta):
    op = g.operation.copy(); op.params = [theta]
    return g.replace(operation=op)


i = rz[0]
cases = [  # (description, edited circuit, should it pass?)
    ("unchanged copy", edited(lambda G: G), True),
    ("insert a cancelling pair cx;cx after the first cx",
     edited(lambda G: G[:cx[0] + 1] + [G[cx[0]], G[cx[0]]] + G[cx[0] + 1:]), True),
    ("split the first rz(a) into rz(a/2) rz(a/2)",
     edited(lambda G: G[:i] + [with_angle(G[i], G[i].operation.params[0] / 2)] * 2 + G[i + 1:]), True),
    ("add 2*pi to the first rz angle (global phase -1 only)",
     edited(lambda G: G[:i] + [with_angle(G[i], G[i].operation.params[0] + 2 * 3.141592653589793)] + G[i + 1:]), True),
    ("delete the first cx", edited(lambda G: G[:cx[0]] + G[cx[0] + 1:]), False),
    ("change the first rz angle by 1e-3",
     edited(lambda G: G[:i] + [with_angle(G[i], G[i].operation.params[0] + 1e-3)] + G[i + 1:]), False),
    ("delete the first rz", edited(lambda G: G[:i] + G[i + 1:]), False),
]
print(f"{'expected':9s} {'verdict':8s} {'distance':>10s}  case")
for text, new, expect in cases:
    v = verify(c, new, log=log, label=text)
    mark = "OK " if v["ok"] == expect else "BUG"
    print(f"{mark} {'pass' if expect else 'fail':5s} {'pass' if v['ok'] else 'fail':8s} {v['distance']:10.2e}  {text}")
print("\nbaselines must be equivalent to the loaded circuit:")
for name in ["tfim_4", "tfim_6"]:
    raw = load(os.path.join(HERE, "circuits", f"{name}.qasm"))
    orig = QuantumCircuit.from_qasm_file(os.path.join(HERE, "circuits", f"{name}.qasm")); orig.remove_final_measurements()
    for label, qc, ref in [("raw vs original file", raw, orig), ("tket vs raw", tket(raw), raw), ("pyzx vs raw", pyzx(raw), raw)]:
        v = verify(ref, qc, log=log, label=f"{name} {label}")
        print(f"  {name} {label:22s} {'pass' if v['ok'] else 'FAIL'}  distance {v['distance']:.2e}")
