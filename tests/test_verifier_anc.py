"""Tests of verifier_anc. Run: .venv/bin/python tests/test_verifier_anc.py
1. Named cases on the Toffoli: Gidney's temporary AND (4 T) with measured or unitary uncompute must pass; planted bugs
   and every out-of-scope construction must be rejected.
2. The tensor simulator against qiskit Operator on random unitary circuits with ancillas.
3. Fuzz: random valid ancilla circuits (parity gadgets, uncomputed or measured out with Z fix-ups) and planted-bug
   copies; the verdict must match a NAIVE reference that runs every input and every measurement branch explicitly
   (no deferred measurement) and must match the planted label.
"""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "verifier")]
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import ClassicalRegister
from qiskit.quantum_info import Operator, Statevector
from pipeline import t_count
from verifier_anc import _apply, _deferred, verify

FAILED = []


def expect(name, v, ok):
    mark = "OK " if v["ok"] == ok else "BUG"
    if v["ok"] != ok: FAILED.append(name)
    d = "-" if v["distance"] is None else f"{v['distance']:.1e}"
    print(f"{mark} expect {'pass' if ok else 'fail'}: {'pass' if v['ok'] else 'fail'}  dist {d:>8s}  {name}: {v['reason']}")


# ---- 1. named cases: Toffoli (q0, q1 controls, q2 target), ancilla q3 -------------------------------------------
def qasm(body, nq=4, cregs="creg m0[1];"):
    return QuantumCircuit.from_qasm_str(f'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[{nq}];\n{cregs}\n{body}')


tof = QuantumCircuit(3); tof.ccx(0, 1, 2)
old = transpile(tof, basis_gates=["cx", "h", "rz"], optimization_level=0)          # the start circuit, 7 T
AND = "h q[3]; t q[3]; cx q[0],q[3]; cx q[1],q[3]; cx q[3],q[0]; cx q[3],q[1]; tdg q[0]; tdg q[1]; t q[3]; " \
      "cx q[3],q[1]; cx q[3],q[0]; h q[3]; s q[3];"                                 # |a b 0> -> |a b ab>, 4 T
AND_DG = "sdg q[3]; h q[3]; cx q[3],q[0]; cx q[3],q[1]; tdg q[3]; t q[1]; t q[0]; cx q[3],q[1]; cx q[3],q[0]; " \
         "cx q[1],q[3]; cx q[0],q[3]; tdg q[3]; h q[3];"
MEAS = "h q[3]; measure q[3] -> m0[0];"
TOF7 = " ".join(f"{g.operation.name}({g.operation.params[0]}) q[{old.find_bit(g.qubits[0]).index}];"
                if g.operation.params else
                f"{g.operation.name} " + ",".join(f"q[{old.find_bit(q).index}]" for q in g.qubits) + ";" for g in old.data)
cases = [
    ("Gidney AND + measured uncompute + CZ fix-up", qasm(f"{AND} cx q[3],q[2]; {MEAS} if (m0 == 1) cz q[0],q[1];"), True),
    ("Gidney AND + unitary uncompute (AND^dag)", qasm(f"{AND} cx q[3],q[2]; {AND_DG}"), True),
    ("ancilla ends in a fixed non-zero state |1>", qasm(f"{TOF7} cx q[0],q[3]; cx q[0],q[3]; x q[3];"), True),
    ("two ancillas, both measured out", qasm(f"{AND.replace('q[3]', 'q[4]')} cx q[4],q[2]; cx q[0],q[3]; cx q[0],q[3]; "
                                             f"h q[4]; measure q[4] -> m0[0]; if (m0 == 1) cz q[0],q[1]; "
                                             f"h q[3]; measure q[3] -> m1[0]; if (m1 == 1) z q[0];", 5,
                                             "creg m0[1]; creg m1[1];"), False),   # PLANTED: m1 fix-up z q[0] is wrong
    ("two ancillas, both measured out, no stray fix-up",
     qasm(f"{AND.replace('q[3]', 'q[4]')} cx q[4],q[2]; cx q[0],q[3]; h q[4]; measure q[4] -> m0[0]; "
          f"if (m0 == 1) cz q[0],q[1]; h q[3]; measure q[3] -> m1[0]; if (m1 == 1) z q[0];", 5,
          "creg m0[1]; creg m1[1];"), True),
    ("PLANTED missing CZ fix-up", qasm(f"{AND} cx q[3],q[2]; {MEAS}"), False),
    ("PLANTED fix-up on the wrong outcome (m0 == 0)", qasm(f"{AND} cx q[3],q[2]; {MEAS} if (m0 == 0) cz q[0],q[1];"), False),
    ("PLANTED ancilla left entangled (no uncompute)", qasm(f"{AND} cx q[3],q[2];"), False),
    ("PLANTED wrong data qubit (cx onto q0)", qasm(f"{AND} cx q[3],q[0]; {MEAS} if (m0 == 1) cz q[0],q[1];"), False),
    ("PLANTED approximate: t -> rz(pi/4 + 1e-6)",
     qasm(f"{AND.replace('t q[3]; cx', 'rz(pi/4+1e-6) q[3]; cx', 1)} cx q[3],q[2]; {MEAS} if (m0 == 1) cz q[0],q[1];"), False),
    ("OUT OF SCOPE non-Clifford under if", qasm(f"{AND} cx q[3],q[2]; {MEAS} if (m0 == 1) t q[0];"), False),
    ("OUT OF SCOPE measured ancilla reused", qasm(f"{AND} cx q[3],q[2]; {MEAS} if (m0 == 1) cz q[0],q[1]; x q[3];"), False),
    ("OUT OF SCOPE data qubit measured", qasm(f"{TOF7} cx q[0],q[3]; cx q[0],q[3]; measure q[0] -> m0[0];"), False),
    ("OUT OF SCOPE multi-bit creg", qasm(f"{AND} cx q[3],q[2]; h q[3]; measure q[3] -> m[0]; if (m == 1) cz q[0],q[1];",
                                         cregs="creg m[2];"), False),
    ("OUT OF SCOPE reset", qasm(f"{TOF7} cx q[0],q[3]; reset q[3];"), False),
    ("OUT OF SCOPE no ancilla (a = 0)", old, False),
    ("OUT OF SCOPE decorative ancilla (no cx)", qasm(f"{TOF7} x q[3]; x q[3];"), False),
    ("OUT OF SCOPE 7 ancillas", qasm(f"{TOF7} cx q[0],q[3]; cx q[0],q[3];", 10), False),
]
print(f"start circuit: Toffoli, T = {t_count(old)}")
for name, new, ok in cases:
    v = verify(old, new)
    expect(name, v, ok)
    if v["ok"]: print(f"      T = {t_count(new)}, ancillas {v['ancillas']}, measurements {v['measurements']}")
cond_t = qasm(f"{AND} cx q[3],q[2]; {MEAS} if (m0 == 1) t q[0];")
print(f"metric: a `t` under `if` is charged: T = {t_count(cond_t)} (4 + 1 expected)")
if t_count(cond_t) != 5: FAILED.append("t_count under if")

# ---- 2. tensor simulator vs qiskit Operator ---------------------------------------------------------------------
rng = np.random.default_rng(1)
GATES1, worst = ["h", "x", "z", "s", "sdg", "t", "tdg"], 0.0
for trial in range(60):
    N, n = int(rng.integers(2, 6)), 1
    n = int(rng.integers(1, N))
    c = QuantumCircuit(N)
    for _ in range(25):
        r = rng.random()
        if r < 0.4:
            a, b = rng.choice(N, 2, replace=False); c.cx(int(a), int(b))
        elif r < 0.6:
            c.rz(float(rng.uniform(0, 6.3)), int(rng.integers(N)))
        else:
            getattr(c, GATES1[rng.integers(len(GATES1))])(int(rng.integers(N)))
    psi = np.eye(2 ** N, 2 ** n, dtype=complex)
    for g in c.data:
        psi = _apply(psi, Operator(g.operation).data, [c.find_bit(q).index for q in g.qubits], N, g.operation.name)
    worst = max(worst, np.abs(psi - Operator(c).data[:, :2 ** n]).max())
print(f"\nsimulator vs qiskit Operator, 60 random circuits: max |difference| = {worst:.1e}")
if worst > 1e-10: FAILED.append("simulator")


# ---- 3. fuzz against a naive branch-by-branch reference ---------------------------------------------------------
def naive(old, new):
    """Run new on every data input, splitting into branches at each measurement (projectors, no deferral). Each
    branch r gives a 2^N x 2^n map E_r; require E_r = chi_r (x) U_old with chi_r the same for every input."""
    n, N = old.num_qubits, new.num_qubits
    U, branches = Operator(old).data, {}
    for x in range(2 ** n):
        states = [({}, Statevector.from_int(x, 2 ** N))]
        for g in new.data:
            op, qs = g.operation, [new.find_bit(q).index for q in g.qubits]
            nxt = []
            for bits, s in states:
                if op.name == "measure":
                    reg = new.find_bit(g.clbits[0]).registers[0][0].name
                    for o in (0, 1):
                        nxt.append((bits | {reg: o}, s.evolve(Operator(np.diag([1 - o, o]).astype(complex)), [qs[0]])))
                elif op.name == "if_else":
                    reg, val = op.condition
                    b = op.blocks[0].data[0]
                    hit = bits[reg.name] == val
                    nxt.append((bits, s.evolve(b.operation, [qs[op.blocks[0].find_bit(q).index] for q in b.qubits])
                                if hit else s))
                else:
                    nxt.append((bits, s.evolve(op, qs)))
            states = nxt
        for bits, s in states:
            branches.setdefault(tuple(sorted(bits.items())), np.zeros((2 ** N, 2 ** n), complex))[:, x] = s.data
    res = 0.0
    for E in branches.values():
        chi = np.array([np.vdot(U, E[m * 2 ** n:(m + 1) * 2 ** n]) for m in range(2 ** (N - n))]) / 2 ** n
        res = max(res, np.linalg.norm(E - np.kron(chi.reshape(-1, 1), U), 2))
    return res


def random_pair(rng):
    """(old on n data qubits, new with a ancillas, planted bug or None). Each ancilla holds a data parity, gets an rz,
    and is then uncomputed or measured out in the X basis with Z fix-ups; old does the same phase on the data."""
    n, a = int(rng.integers(2, 5)), int(rng.integers(1, 4))
    old, new = QuantumCircuit(n), QuantumCircuit(n + a)
    def layer():
        for _ in range(4):
            q = int(rng.integers(n)); r = rng.random()
            g = [("h", [q]), ("t", [q]), ("rz", [q]), ("cx", [q, (q + 1) % n])][int(rng.integers(4))]
            ang = float(rng.uniform(0, 6.3))
            for c in (old, new):
                getattr(c, g[0])(*([ang] if g[0] == "rz" else []), *g[1])
    bug = ["drop_fixup", "wrong_value", "skip_uncompute", "angle", None, None, None][int(rng.integers(7))]
    for k in range(a):
        layer()
        S = sorted(rng.choice(n, int(rng.integers(1, n + 1)), replace=False).tolist())
        th, anc, measure = float(rng.uniform(0.1, 6.2)), n + k, bool(rng.random() < 0.6)
        if k == 0 and not measure and bug in ("drop_fixup", "wrong_value"): bug = "skip_uncompute"
        if k == 0 and measure and bug == "skip_uncompute": bug = "drop_fixup"
        for q in S: new.cx(q, anc)
        new.rz(th, anc)
        for q in S[:-1]: old.cx(q, S[-1])                           # same phase on the data: parity into S[-1]
        old.rz(th + (1e-3 if bug == "angle" and k == 0 else 0), S[-1])
        for q in reversed(S[:-1]): old.cx(q, S[-1])
        if measure:
            cr = ClassicalRegister(1, f"m{k}"); new.add_register(cr)
            new.h(anc); new.measure(anc, cr[0])
            for j, q in enumerate(S):
                if bug == "drop_fixup" and k == 0 and j == 0: continue
                with new.if_test((cr, 0 if bug == "wrong_value" and k == 0 else 1)):
                    new.z(q)
        else:
            for j, q in enumerate(S):
                if bug == "skip_uncompute" and k == 0 and j == 0: continue
                new.cx(q, anc)
    layer()
    return old, new, bug


agree, label_ok, counts, t0 = 0, 0, {}, time.time()
N_FUZZ = 300
for i in range(N_FUZZ):
    o, nw, bug = random_pair(rng)
    v, ref = verify(o, nw), naive(o, nw)
    agree += v["ok"] == (ref <= 1e-8)
    label_ok += v["ok"] == (bug is None)
    counts[str(bug)] = counts.get(str(bug), 0) + 1
    if v["ok"] != (ref <= 1e-8) or v["ok"] != (bug is None):
        FAILED.append(f"fuzz {i}: bug={bug} verifier={v['ok']} ({v['reason']}) naive residual={ref:.1e}")
print(f"fuzz: {N_FUZZ} cases {counts}; verdict = naive reference on {agree}/{N_FUZZ}, "
      f"= planted label on {label_ok}/{N_FUZZ} ({time.time() - t0:.0f} s)")

print("\nALL PASS" if not FAILED else "\nFAILURES:\n" + "\n".join(FAILED[:20]))
