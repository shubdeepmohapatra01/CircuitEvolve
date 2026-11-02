"""Circuits, baselines, T-count: the measurement layer. Every arm is scored by t_count, defined here.

Every circuit in this harness is a qiskit QuantumCircuit over the gate set {h, x, z, s, sdg, t, tdg, cx, rz}.
    load(path)           QASM file -> circuit, rebased to {cx, h, rz} (no optimization)
    tket(qc)             pytket FullPeepholeOptimise
    pyzx(qc)             pyzx full_reduce (ZX phase folding)
    t_count(qc)          T gates after synthesizing every arbitrary rz with gridsynth, total error 1e-3
Every function writes one line to the log, in the order it is called.
"""
import json, math, os, re, sys, time

os.environ.setdefault("XDG_CONFIG_HOME", os.path.join(os.path.dirname(__file__), ".cache"))  # pytket writes config here
from qiskit import QuantumCircuit, qasm2, transpile

# Error budget for the WHOLE circuit, split evenly over its arbitrary rotations (t_count below). A total rather than
# a per-rotation figure, so circuits with different rotation counts stay comparable.
EPS_TOTAL = 1e-3
HERE = os.path.dirname(os.path.abspath(__file__))


# ---- log: one JSON line per event, plus a readable markdown line -------------------------------------------------
class Log:
    def __init__(self, name):
        os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
        self.jsonl = open(os.path.join(HERE, "logs", f"{name}.jsonl"), "a")
        self.md = open(os.path.join(HERE, "logs", f"{name}.md"), "a")
        self.n = 0

    def __call__(self, stage, text="", **data):
        self.n += 1
        t = time.strftime("%H:%M:%S")
        self.jsonl.write(json.dumps(dict(step=self.n, time=t, stage=stage, text=text, **data), default=str) + "\n")
        self.md.write(f"\n### {self.n}. [{t}] {stage}\n" + (f"{text}\n" if text else "")
                      + "".join(f"- **{k}**: {v}\n" for k, v in data.items() if not isinstance(v, str) or len(v) < 300))
        self.jsonl.flush(); self.md.flush()


# ---- circuit summary ---------------------------------------------------------------------------------------------
def kind(theta):
    """'clifford' (multiple of pi/2, free), 't' (odd multiple of pi/4, one T) or 'arbitrary' (needs gridsynth).
    The 1e-9 tolerance absorbs the float error a transpiler accumulates when it adds angles together."""
    k = theta / (math.pi / 4)
    if abs(k - round(k)) > 1e-9:
        return "arbitrary"
    return "clifford" if round(k) % 2 == 0 else "t"


def flat_ops(qc):
    """Every operation, including the gates under an `if`: a conditional gate is charged as if it always runs, so a
    rule cannot look cheap by hiding gates behind a measurement."""
    for g in qc.data:
        if g.operation.name == "if_else":
            for block in g.operation.blocks:
                if block is not None:
                    yield from flat_ops(block)
        else:
            yield g.operation


def stats(qc):
    ops = list(flat_ops(qc))
    rz = [op.params[0] for op in ops if op.name == "rz"]
    arb = [float(a) for a in rz if kind(float(a)) == "arbitrary"]
    ops = {k: sum(op.name == k for op in ops) for k in ("cx", "t", "tdg")}
    return dict(gates=qc.size(), cx=ops.get("cx", 0), t_gates=ops.get("t", 0) + ops.get("tdg", 0)
                + sum(kind(float(a)) == "t" for a in rz), arbitrary_rz=len(arb),
                distinct_angles_mod_pi2=len({round(abs((a + math.pi / 4) % (math.pi / 2) - math.pi / 4), 6) for a in arb}))


# ---- load and baselines ------------------------------------------------------------------------------------------
# One fixed, universal basis for every circuit entering the harness.
BASIS = ["cx", "h", "rz"]


def load(path, log=None):
    qc = QuantumCircuit.from_qasm_file(path)
    qc.remove_final_measurements()                       # T-count concerns the unitary
    qc = transpile(qc, basis_gates=BASIS, optimization_level=0)   # "raw": rebase only, optimize nothing
    flat = QuantumCircuit(qc.num_qubits)                 # one register q[0..n-1]: TKET reorders multi-register input
    for g in qc.data:
        flat.append(g.operation, [qc.find_bit(q).index for q in g.qubits])
    qc = flat
    if log: log("load", path=os.path.relpath(path, HERE), **stats(qc))
    return qc


def logical(path):
    """The source file as written (ccx, ccz, custom gates kept; final measurements and barriers removed) on one
    register q[0..n-1] in the same qubit order as load(path). A read-only view for the ancilla arm, equivalent to load."""
    qc = QuantumCircuit.from_qasm_file(path)
    qc.remove_final_measurements()
    flat = QuantumCircuit(qc.num_qubits)
    for g in qc.data:
        if g.operation.name != "barrier":
            flat.append(g.operation, [qc.find_bit(q).index for q in g.qubits])
    return flat


def tket(qc, log=None):
    from pytket.passes import FullPeepholeOptimise
    from pytket.qasm import circuit_from_qasm_str, circuit_to_qasm_str
    tk = circuit_from_qasm_str(qasm2.dumps(qc))
    FullPeepholeOptimise(allow_swaps=False).apply(tk)
    out = transpile(QuantumCircuit.from_qasm_str(circuit_to_qasm_str(tk)), basis_gates=BASIS, optimization_level=0)
    if log: log("baseline tket", "pytket FullPeepholeOptimise(allow_swaps=False)", **stats(out))
    return out


def pyzx(qc, log=None):
    import pyzx as zx
    txt = re.sub(r"^creg .*;\n", "", qasm2.dumps(qc), flags=re.M)   # pyzx would turn a creg into extra qubit wires
    g = zx.Circuit.from_qasm(txt).to_graph()
    zx.full_reduce(g)
    ex = zx.basic_optimization(zx.extract_circuit(g.copy()).to_basic_gates())
    out = transpile(QuantumCircuit.from_qasm_str(ex.to_qasm()), basis_gates=BASIS, optimization_level=0)
    if log: log("baseline pyzx", "pyzx full_reduce -> extract -> basic_optimization", **stats(out))
    return out


DPF_FRACTION = 0.4      # share of EPS_TOTAL that BQSKit's DPF may spend; gridsynth gets the rest


def bqskit_dpf(qc, k=3, seed=0, log=None, label="bqskit dpf"):
    """BQSKit-FT Dyadic Phase Fixing (Kalloor et al. 2026) via the repo's driver in its own venv: CliffordRZ retarget
    -> 4-qubit partition -> GreedyNTRO -> PKAC -> unfold. k=3: fixed angles become T/Clifford, no phase-gradient
    ancillas. Approximate: spends eps_used = DPF_FRACTION * EPS_TOTAL. Returns (circuit, eps_used).

    A SUBPROCESS (QASM on stdin, one JSON line on stdout), not an import: the driver monkey-patches bqskit before
    importing bqskit.ft and that must not leak into the interpreter scoring every other arm. Needs bqskit-ft."""
    import subprocess
    eps_used = DPF_FRACTION * EPS_TOTAL
    txt = re.sub(r"^creg .*;\n", "", qasm2.dumps(qc), flags=re.M)
    t0 = time.time()
    p = subprocess.run([sys.executable,
                        os.path.join(HERE, "baselines/dpf/pk/dpf_pre_gridsynth.py"),
                        "--k", str(k), "--seed", str(seed), "--eps", str(eps_used)],
                       input=txt, capture_output=True, text=True, timeout=3600)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-2000:])
    payload = json.loads(p.stdout.strip().splitlines()[-1])
    assert not payload["unlowered"], payload["unlowered"]
    out = transpile(QuantumCircuit.from_qasm_str(payload["qasm"]), basis_gates=BASIS + ["s", "sdg", "t", "tdg", "x", "z"],
                    optimization_level=0)
    if log: log("baseline " + label, f"BQSKit-FT DPF k={k}, seed {seed}, spends eps {eps_used:g}",
                seconds=round(time.time() - t0), **stats(out))
    return out, eps_used


# ---- metric ------------------------------------------------------------------------------------------------------
_GS = {}        # (angle, eps) -> T gates; gridsynth costs ~0.1-1 s per angle, and circuits repeat few angles


def t_count(qc, eps_total=EPS_TOTAL, log=None, label=""):
    """T-count of the Clifford+T circuit: T-like rz count 1, arbitrary rz count their gridsynth T-count at eps_total/N."""
    import mpmath
    from pygridsynth.gridsynth import gridsynth_gates
    mpmath.mp.dps = 128
    s = stats(qc)
    eps = eps_total / max(s["arbitrary_rz"], 1)
    total, per = s["t_gates"], []
    for op in flat_ops(qc):
        if op.name == "rz" and kind(float(op.params[0])) == "arbitrary":
            key = (round(float(op.params[0]) % (2 * math.pi), 12), eps)
            if key not in _GS:
                _GS[key] = str(gridsynth_gates(mpmath.mpf(key[0]), mpmath.mpf(eps))).count("T")
            per.append(_GS[key]); total += _GS[key]
    if log: log("t_count " + label, f"gridsynth each arbitrary rz at eps {eps:.2e} (= {eps_total:g} / {s['arbitrary_rz']})",
                T=total, arbitrary_rz=s["arbitrary_rz"], T_per_rotation_mean=round(sum(per) / max(len(per), 1), 1))
    return total


if __name__ == "__main__":
    rows = []
    for name in ["tfim_4", "tfim_6"]:
        log = Log(f"baselines_{name}")
        raw = load(os.path.join(HERE, "circuits", f"{name}.qasm"), log)
        for label, qc in [("raw", raw), ("tket", tket(raw, log)), ("pyzx", pyzx(raw, log))]:
            rows.append(dict(circuit=name, baseline=label, **stats(qc), T=t_count(qc, log=log, label=label)))
    print(f"{'circuit':8s} {'baseline':8s} {'gates':>6s} {'cx':>5s} {'arb rz':>7s} {'angles':>7s} {'T':>6s}")
    for r in rows:
        print(f"{r['circuit']:8s} {r['baseline']:8s} {r['gates']:6d} {r['cx']:5d} {r['arbitrary_rz']:7d} "
              f"{r['distinct_angles_mod_pi2']:7d} {r['T']:6d}")
    json.dump(rows, open(os.path.join(HERE, "logs", "baselines.json"), "w"), indent=1)
