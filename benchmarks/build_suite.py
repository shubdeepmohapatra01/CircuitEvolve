"""Build benchmarks/<family>/<name>.qasm from the repo's own benchmark sets, then filter and write
MANIFEST.csv and DROPPED.csv.  Run from the repo root:  .venv/bin/python benchmarks/build_suite.py

Kept: <= 8 qubits (9-10 for arithmetic only, there is little small arithmetic), loads through pipeline.load, no
mid-circuit measurement / reset / classical control, and T > 0 after tket + t_count (some non-Clifford content).
Copies are normalized (see normalize): one qreg q, no barriers; the gates are exactly the source's.
"""
import csv, glob, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from qiskit import QuantumCircuit, qasm2
from qiskit.transpiler.passes import RemoveBarriers
import pipeline

# ARCHIVAL: the four upstream benchmark repositories below are NOT vendored here -- only the filtered copies this
# script produced (benchmarks/<family>/*.qasm) and their provenance in MANIFEST.csv are committed. To rebuild the
# suite, clone the sources at the commits recorded below and point SOURCE_DIR at the directory holding them.
B = os.environ.get("SOURCE_DIR", os.path.join(HERE, "sources"))
QB = ("QASMBench", "https://github.com/pnnl/QASMBench @ 357b942396d5c2b7cbc1c229c585a6ef5ccaebac",
      "BSD-style (Battelle Memorial Institute / PNNL QASMBench)")
SM = ("SupermarQ generator (instance)", "supermarq 0.5.70 (https://github.com/Infleqtion/client-superstaq)",
      "Apache-2.0 (Infleqtion Supermarq)")
NAM = ("Nam et al. 2018 arithmetic (Quartz copy)",
       "https://github.com/quantum-compiler/quartz @ ce31db1c91f502f6ef2b9af655855f17f78caf17 circuit/nam-benchmarks",
       "Apache-2.0 (Quartz copy); upstream T-par/Feynman BSD-3-Clause")
QS = ("BQSKit qseed (Weiden)", "https://github.com/mtweiden/qseed @ eb9ccab7a0736ba9c8793899b155dd4c20c5ccb1 qasm/",
      "none declared (research-use copy)")
MINI = ("circuits/ (= BQSKit qseed copy)", QS[1], QS[2])

FAMILY = {  # name prefix -> family directory; everything else is "other"
    "adder": "arithmetic", "toffoli": "arithmetic", "fredkin": "arithmetic", "tof_": "arithmetic",
    "barenco_tof": "arithmetic", "mod5": "arithmetic", "mod_mult": "arithmetic", "vbe_adder": "arithmetic",
    "hwb": "arithmetic", "mult_": "arithmetic",
    "tfim": "hamsim", "heisenberg": "hamsim", "hubbard": "hamsim", "hamsim": "hamsim", "basis_trotter": "hamsim",
    "ising": "hamsim",
    "qft": "qft_qpe", "qpe": "qft_qpe", "pea": "qft_qpe", "hhl": "qft_qpe",
    "qaoa": "variational", "vqe": "variational", "variational": "variational", "dnn": "variational",
    "qml": "variational",
}


def family(name):
    return next((f for p, f in FAMILY.items() if name.startswith(p)), "other")


def candidates():
    """(name, path, source tuple, file within source, qubits) for every circuit in the three repo sets."""
    for r in csv.DictReader(open(os.path.join(B, "train_v2", "MANIFEST.csv"))):
        name = r["name"].replace("qasmbench_small_", "").replace("qasmbench_medium_", "").replace("supermarq_", "")
        path = glob.glob(os.path.join(B, "train_v2", "*", r["name"] + ".qasm"))[0]
        yield name, path, SM if r["name"].startswith("supermarq") else QB, r["source"], int(r["qubits"])
    for r in csv.DictReader(open(os.path.join(B, "nam_arith", "MANIFEST.csv"))):
        if r["logical_path"].startswith("generated/"):
            yield r["name"], None, ("project code", "", ""), r["source"], int(r["qubits"])
            continue
        name = "nam_" + r["name"] if r["name"] == "grover_5" else r["name"]
        yield name, os.path.join(B, "nam_arith", r["logical_path"]), NAM, r["logical_path"], int(r["qubits"])
    for r in csv.DictReader(open(os.path.join(B, "bqskit_qseed", "MANIFEST.csv"))):
        src = MINI if r["circuit"] in ("tfim_4", "tfim_6") else QS
        path = os.path.join(os.path.dirname(HERE), "circuits", r["circuit"] + ".qasm") if src is MINI else \
            os.path.join(B, "bqskit_qseed", r["source_path"])
        yield r["circuit"], path, src, r["source_path"], int(r["qubits"])


def normalize(path):
    """Source QASM -> same gates on one qreg q, barriers removed. pytket re-emits several qregs in its own order, so
    pipeline.tket would return a qubit-permuted circuit; BQSKit DPF cannot partition barriers."""
    qc = QuantumCircuit.from_qasm_file(path)
    flat = QuantumCircuit(qc.num_qubits, qc.num_clbits)
    flat.compose(RemoveBarriers()(qc), qubits=range(qc.num_qubits), clbits=range(qc.num_clbits), inplace=True)
    return qasm2.dumps(flat)


def why_not(name, path, n):
    """None if the circuit is kept, else the drop reason."""
    if path is None:
        return "project-generated construction, not a published benchmark file"
    if n > 10 or (n > 8 and family(name) != "arithmetic"):
        return "more than 8 qubits (9-10 allowed for arithmetic only)"
    qc = QuantumCircuit.from_qasm_file(path)
    qc.remove_final_measurements()
    bad = {g.operation.name for g in qc.data} & {"measure", "reset", "if_else", "while_loop", "for_loop", "switch_case"}
    if bad:
        return "mid-circuit measurement / reset / classical control"
    try:
        raw = pipeline.load(path)
    except Exception as e:
        return f"pipeline.load failed: {type(e).__name__}"
    if pipeline.t_count(pipeline.tket(raw)) == 0:
        return "T = 0 after tket + t_count (Clifford only)"
    return None


def main():
    kept, dropped = [], []
    for name, path, src, where, n in candidates():
        try:
            reason = why_not(name, path, n)
        except Exception as e:                       # e.g. qiskit cannot parse the file at all
            reason = f"parse failed: {type(e).__name__}"
        if reason:
            dropped.append(dict(name=name, source=f"{src[0]}: {where}", qubits=n, reason=reason)); continue
        dst = os.path.join(HERE, family(name), name + ".qasm")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "w").write(normalize(path))
        ops = QuantumCircuit.from_qasm_file(path).count_ops()
        s = pipeline.stats(pipeline.load(dst))
        kept.append(dict(name=name, family=family(name), source=f"{src[0]}: {where}", commit_url=src[1], license=src[2],
                         qubits=n, qregs_in_source=len(QuantumCircuit.from_qasm_file(path).qregs),
                         barriers_removed=ops.get("barrier", 0), gates=s["gates"], cx=s["cx"],
                         ccx_in_source=ops.get("ccx", 0) + ops.get("ccz", 0),
                         arbitrary_rz=s["arbitrary_rz"], path=os.path.relpath(dst, os.path.dirname(HERE))))
        print(f"kept {name:28s} {family(name):12s} {n:3d}q {s['gates']:6d} gates {s['arbitrary_rz']:5d} arb rz", flush=True)
    for r in csv.DictReader(open(os.path.join(B, "train_v2", "DROPPED.csv"))):   # dropped upstream, before train_v2
        n = re.search(r"_n(\d+)$", r["name"])
        if n and int(n.group(1)) <= 10:
            dropped.append(dict(name=r["name"].replace("qasmbench_small_", "").replace("qasmbench_medium_", ""),
                                source=f"{QB[0]}: (train_v2/DROPPED.csv)", qubits=int(n.group(1)),
                                reason="train_v2: " + r["reason"]))
    for fn, rows in [("MANIFEST.csv", kept), ("DROPPED.csv", dropped)]:
        with open(os.path.join(HERE, fn), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(len(kept), "kept,", len(dropped), "dropped")


if __name__ == "__main__":
    main()
