"""Clifford+T exports and qiskit drawings for every method.

For tfim_4 and tfim_6 and every method (raw, TKET, pyzx, BQSKit DPF, agent, playbook rule):
    clifford_t(qc, eps)  every arbitrary rz -> its gridsynth word (h/s/t/x), T-like rz -> t/tdg/s/z: the final
                         Clifford+T circuit, written to results/clifford_t/<circuit>_<method>.qasm, T re-counted and
                         the whole thing re-verified against the original circuit within the total error 1e-3
    drawings             results/drawings/*.png (qiskit 'mpl' drawer)
    summary              results/summary.json (one row per circuit x method)
"""
import json, math, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [ROOT, os.path.join(ROOT, "verifier")]
import matplotlib
matplotlib.use("Agg")
import mpmath
from pygridsynth.gridsynth import gridsynth_gates
from qiskit import QuantumCircuit, qasm2
from pipeline import DPF_FRACTION, EPS_TOTAL, HERE, kind, load, pyzx, stats, t_count, tket
from verifier_noanc import verify

OUT = os.path.join(HERE, "results")
AGENT_BEST = {"tfim_4": "runs/tfim_4_20261030_122403/best.qasm", "tfim_6": "runs/tfim_6_20261030_112857/best.qasm"}
RULE = "examples/givens_rule/{}_out.qasm"        # the shipped Givens rule's output on each circuit


def methods(name):
    """[(label, circuit, error already spent before gridsynth)], skipping methods whose file is not on this
    machine: runs/ and the DPF outputs are per-machine artefacts, so only raw / TKET / pyzx are always there."""
    raw = load(os.path.join(HERE, "circuits", f"{name}.qasm"))

    def q(p):
        f = os.path.join(HERE, p)
        return QuantumCircuit.from_qasm_file(f) if os.path.exists(f) else None

    ms = [("raw", raw, 0.0), ("TKET", tket(raw), 0.0), ("pyzx", pyzx(raw), 0.0),
          ("BQSKit DPF", q(f"results/bqskit_dpf/{name}_raw_tket_bqskitdpf.qasm"), DPF_FRACTION * EPS_TOTAL),
          ("agent (direct)", q(AGENT_BEST[name]), 0.0), ("playbook rule", q(RULE.format(name)), 0.0)]
    return raw, [(l, c, e) for l, c, e in ms if c is not None]


_QUARTER = {0: [], 1: ["t"], 2: ["s"], 3: ["s", "t"], 4: ["z"], 5: ["z", "t"], 6: ["sdg"], 7: ["tdg"]}


def clifford_t(qc, eps_total):
    """Final Clifford+T circuit: arbitrary rz -> gridsynth at eps_total/N each (global phase dropped)."""
    mpmath.mp.dps = 128
    n_arb = stats(qc)["arbitrary_rz"]
    eps = eps_total / max(n_arb, 1)
    out, cache = QuantumCircuit(qc.num_qubits), {}
    for g in qc.data:
        q = [qc.find_bit(x).index for x in g.qubits]
        if g.operation.name != "rz":
            out.append(g.operation, q); continue
        th = float(g.operation.params[0])
        if kind(th) != "arbitrary":
            for name in _QUARTER[round(th / (math.pi / 4)) % 8]:
                getattr(out, name)(q[0])
            continue
        key = round(th % (2 * math.pi), 12)
        if key not in cache:
            cache[key] = str(gridsynth_gates(mpmath.mpf(key), mpmath.mpf(eps)))
        for ch in reversed(cache[key]):                         # gridsynth words are in matrix order
            if ch in "HSTX":
                getattr(out, ch.lower())(q[0])                  # 'W' (global phase) and 'I' are dropped
    return out


def draw(qc, path, fold, title):
    fig = qc.draw("mpl", fold=fold, idle_wires=False)
    fig.suptitle(title, fontsize=12, x=0.02, ha="left")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    matplotlib.pyplot.close(fig)


if __name__ == "__main__":
    os.makedirs(os.path.join(OUT, "clifford_t"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "drawings"), exist_ok=True)
    rows = []
    for name in ["tfim_4", "tfim_6"]:
        orig, ms = methods(name)
        for label, qc, spent in ms:
            ct = clifford_t(qc, EPS_TOTAL - spent)
            slug = label.lower().replace(" ", "_").replace("(", "").replace(")", "")
            qasm2.dump(ct, os.path.join(OUT, "clifford_t", f"{name}_{slug}.qasm"))
            v = verify(orig, ct, tol=EPS_TOTAL)                 # whole Clifford+T circuit vs the original
            ops = ct.count_ops()
            rows.append(dict(circuit=name, method=label, T=ops.get("t", 0) + ops.get("tdg", 0),
                             T_metric=t_count(qc, EPS_TOTAL - spent), arbitrary_rz=stats(qc)["arbitrary_rz"],
                             cx=ops.get("cx", 0), clifford_t_gates=ct.size(), distance_to_original=v["distance"],
                             within_total_error=v["ok"]))
            print(json.dumps(rows[-1]), flush=True)
        # drawings: a slice of the TKET circuit, the full optimized circuit, its first rotation in Clifford+T
        by_label = dict((l, c) for l, c, _ in ms)
        tk = by_label["TKET"]
        sl = QuantumCircuit(tk.num_qubits); [sl.append(g.operation, g.qubits) for g in tk.data[:90]]
        draw(sl, os.path.join(OUT, "drawings", f"{name}_tket_first90.png"), 45,
             f"{name}, TKET baseline: first 90 of {tk.size()} gates ({stats(tk)['arbitrary_rz']} arbitrary rz in total)")
        best = by_label.get("playbook rule")
        if best is not None:
            draw(best, os.path.join(OUT, "drawings", f"{name}_optimized_full.png"), 50,
                 f"{name}, after the Givens (free-fermion) rule: all {best.size()} gates, "
                 f"{stats(best)['arbitrary_rz']} arbitrary rz")
    one = QuantumCircuit(1); one.rz(0.5, 0)
    ct1 = clifford_t(one, EPS_TOTAL / 100)
    draw(ct1, os.path.join(OUT, "drawings", "one_rotation_clifford_t.png"), 60,
         f"rz(0.5) at eps = 1e-5 as Clifford+T (gridsynth): {ct1.count_ops().get('t', 0)} T gates, {ct1.size()} gates")
    json.dump(rows, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
