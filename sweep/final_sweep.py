"""All 76 benchmarks, final table. Per circuit: collect every verified candidate (Sonnet isolated/shared finals, Opus run
best.qasm or, for the 3 runs stopped by the user, their last accepted circuit), then the no-LLM sweep: the 18 new Opus
rules (playbook/opus/*_opus_*) greedily on (a) the TKET start and (b) the best candidate. Every candidate and the final
circuit are verified against the ORIGINAL benchmark file (tol 1e-8 via verifier.verify) and T is re-counted.
Usage: PRIOR_DIR=<dir> sweep/final_sweep.py OUT_DIR   (writes OUT_DIR/final_all.csv, OUT_DIR/circuits/<name>_final.qasm,
progress lines to stdout)

ARCHIVAL. This is the exact script that produced results/final_all_76.csv; it is kept so the final table's provenance
is readable, not because it reruns from a clean checkout. It reads the per-family intermediate tables that the campaign
wrote to a scratch directory outside the repo (all_families_final.csv, hamsim_final/, family_final/); point PRIOR_DIR
at a copy of those to run it again. The committed results in this folder are its output.
"""
import csv, glob, json, os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # this file lives in sweep/
PRIOR = os.environ.get("PRIOR_DIR", "")                              # scratch tables from the campaign, not in the repo
OUT = os.path.abspath(sys.argv[1]); sys.path[:0] = [ROOT, os.path.join(ROOT, "verifier")]; os.chdir(ROOT)
from qiskit import QuantumCircuit, qasm2
from pipeline import load, tket, t_count
from verifier_noanc import verify
from playbook import find_circuit, try_rule, valid_rules
PREV = {r["circuit"]: r for r in csv.DictReader(open(f"{PRIOR}/all_families_final.csv"))}
RULES = [r for r in valid_rules("playbook/opus") if "_opus_" in os.path.basename(r[0])]
STOPPED = ["basis_change_n3_opus_20261031_165053", "hubbard_4_opus_20261031_172525", "quantumwalks_n2_opus_20261031_165209"]
tmp = tempfile.mkdtemp()

def arm_file(name, arm):
    f = glob.glob(f"{PRIOR}/hamsim_final/circuits/{name}_{arm}.qasm") + glob.glob(f"{PRIOR}/family_final/*/circuits/{name}_{arm}.qasm")
    return f[0] if f else None

def opus_files(name):
    fs = [f for f in glob.glob(f"runs/{name}_opus_*/best.qasm")]
    for run in STOPPED:
        if run.startswith(name + "_opus_"):
            fs += glob.glob(f"playbook/opus/{run}_r*/after.qasm") + [f"runs/{run}/circuit.qasm"]
    return fs

def greedy(c, ref, tag):
    best, Tb, used = c, t_count(c), []
    for i, (entry, _) in enumerate(RULES):
        new, v = try_rule(os.path.join(entry, "technique.py"), best, ref, f"{tmp}/{tag}_{i}_in.qasm", f"{tmp}/{tag}_{i}_out.qasm", timeout=120)
        if new is not None and v["T"] < Tb: best, Tb, used = new, v["T"], used + [os.path.basename(entry)]
    return best, Tb, used

def job(name):
    p = PREV[name]; path = find_circuit(name); tk = tket(load(path))
    orig = QuantumCircuit.from_qasm_file(path); orig.remove_final_measurements()
    files = [("isolated", arm_file(name, "isolated")), ("shared", arm_file(name, "shared"))] + [("opus", f) for f in opus_files(name)]
    for ref in (orig, tk):          # verified vs the original; only if nothing passes (hhl_n7: TKET's own 7e-8 offset) vs TKET
        cands = {}                                                  # source -> (circuit, T)
        for src, f in files:
            if f and os.path.exists(f):
                c = QuantumCircuit.from_qasm_file(f)
                if c.num_qubits == orig.num_qubits and verify(ref, c)["ok"] and (src not in cands or t_count(c) < cands[src][1]):
                    cands[src] = (c, t_count(c))
        if cands: break
    ref_name = "original" if ref is orig else "tket"
    start_src = min(cands, key=lambda s: cands[s][1])
    c1, T1, u1 = greedy(tk, tk, f"{name}_tk")
    c2, T2, u2 = greedy(cands[start_src][0], tk, f"{name}_best")
    if u1: cands["sweep_from_tket"] = (c1, T1)
    if u2: cands[f"sweep_on_{start_src}"] = (c2, T2)
    src = min(cands, key=lambda s: cands[s][1]); final = cands[src][0]; v = verify(orig, final)
    qasm2.dump(final, f"{OUT}/circuits/{name}_final.qasm")
    row = dict(family=p["family"], circuit=name, qubits=p["qubits"], T_tket=p["T_tket"], T_pyzx=p["T_pyzx"], T_dpf=p["T_dpf"],
               T_isolated=cands.get("isolated", (0, ""))[1], T_shared=cands.get("shared", (0, ""))[1],
               opus_run=("stopped" if any(r.startswith(name + "_opus_") for r in STOPPED) else "full") if "opus" in cands else "not run",
               T_opus=cands.get("opus", (0, ""))[1], T_sweep_tket=T1, T_sweep_best=T2, sweep_rules_used="+".join(u1 + u2),
               T_final=t_count(final), final_source=src, final_verified_vs_file=v["ok"], final_distance=v["distance"], verified_against=ref_name,
               final_ok_vs_ref=verify(ref, final)["ok"])
    print(json.dumps(row), flush=True); return row

if __name__ == "__main__":
    from multiprocessing import Pool
    names = sys.argv[2:] or sorted(PREV, key=lambda n: -int(PREV[n]["T_tket"]))                 # largest first
    print(f"{len(names)} circuits, {len(RULES)} Opus rules", flush=True)
    with Pool(10) as pool: rows = pool.map(job, names, chunksize=1)
    with open(f"{OUT}/final_all{'_' + '_'.join(sys.argv[2:]) if sys.argv[2:] else ''}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print("SWEEP DONE", flush=True)
