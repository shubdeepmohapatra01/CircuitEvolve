"""No-LLM pass for the ANCILLA arm: every valid rule of one or more playbook folders x every circuit's TKET start.
Ancilla rules read logical.qasm (the source's Toffoli-level form) and output n + a qubits, so they are NOT chained:
each rule runs alone on the TKET start (logical.qasm next to its input), is verified with verifier_anc against the
TKET start, and the circuit's result is the lowest-T valid output (TKET start if none).
    python sweep/sweep_anc.py TAG PLAYBOOK_DIR[,DIR2...] [circuit ... | --family F]   (default: all of MANIFEST.csv)
-> results/sweep_anc_<TAG>.csv (one row per circuit x rule + one BEST row per circuit), best circuits in
   results/sweep_anc_<TAG>/<circuit>_best.qasm; columns T_pyzx / T_noanc_final come from results/final_all_76.csv
   or final_all_76.csv when one exists (the no-ancilla campaign's output), and are left empty otherwise."""
import csv, glob, os, shutil, sys, tempfile, time
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "verifier")]
from qiskit import QuantumCircuit, qasm2
import verifier_anc
from pipeline import HERE, load, logical, t_count, tket
from playbook import find_circuit, try_rule, valid_rules

WORKERS = 4                     # verifier_anc peaks at ~3 GiB on 10 data + 6 ancilla qubits
# The no-ancilla final table, for the comparison columns only; empty until final_sweep.py has written one.
_prev = [p for p in (os.path.join(HERE, "results", f) for f in ("final_all.csv", "final_all_76.csv"))
         if os.path.exists(p)]
PREV = {r["circuit"]: r for r in csv.DictReader(open(_prev[0]))} if _prev else {}


def job(args):
    name, rules, tmp, outdir = args
    p = find_circuit(name); tk = tket(load(p)); T0 = t_count(tk)
    d = os.path.join(tmp, name); os.makedirs(d)
    lg = os.path.join(d, "logical_src.qasm")
    try:
        qasm2.dump(logical(p), lg)
    except Exception:
        shutil.copy(p, lg)
    prev = PREV.get(name, {})
    base = dict(circuit=name, family=prev.get("family", ""), qubits=tk.num_qubits, T_tket=T0,
                T_pyzx=prev.get("T_pyzx", ""), T_noanc_final=prev.get("T_final", ""))
    rows, best, t0 = [], dict(T=T0, rule="none (TKET start)", ancillas=0, measurements=0), time.time()
    for i, (entry, _) in enumerate(rules):
        new, v = try_rule(os.path.join(entry, "technique.py"), tk, tk, os.path.join(d, f"r{i}_in.qasm"),
                          os.path.join(d, f"r{i}_out.qasm"), verify_fn=verifier_anc.verify, logical_path=lg)
        rule = os.path.basename(entry)
        rows.append(base | dict(rule=rule, valid=v["equivalent"], T=v["T"], ancillas=v.get("ancillas"),
                                measurements=v.get("measurements"), reason=(v.get("reason") or "")[:120]))
        if new is not None and v["T"] < best["T"]:
            best = dict(T=v["T"], rule=rule, ancillas=v.get("ancillas"), measurements=v.get("measurements"), c=new)
    for f in sorted(glob.glob(os.path.join(HERE, "runs", f"{name}_anc_*", "best.qasm"))):   # the agents' own results
        c = QuantumCircuit.from_qasm_file(f)
        if c.num_qubits == tk.num_qubits:
            continue                                            # no accepted round: TKET start
        v = verifier_anc.verify(tk, c)
        run = "run:" + os.path.basename(os.path.dirname(f))
        rows.append(base | dict(rule=run, valid=v["ok"], T=t_count(c) if v["ok"] else None, ancillas=v["ancillas"],
                                measurements=v["measurements"], reason=v["reason"][:120]))
        if v["ok"] and rows[-1]["T"] < best["T"]:
            best = dict(T=rows[-1]["T"], rule=run, ancillas=v["ancillas"], measurements=v["measurements"], c=c)
    vf = dict(ok=None, distance=None)
    if "c" in best:                                             # final check against the ORIGINAL benchmark file
        qasm2.dump(best["c"], os.path.join(outdir, f"{name}_best.qasm"))
        vf = verifier_anc.verify(logical(p), best["c"])
    rows.append(base | dict(rule="BEST", valid=True, T=best["T"], ancillas=best["ancillas"],
                            measurements=best["measurements"], reason=f"from {best['rule']}; vs original file: "
                            f"{vf['ok']} ({vf['distance']})"))
    print(f"{name:18s} TKET {T0:6d}  pyzx {base['T_pyzx']:>7s}  noanc {base['T_noanc_final']:>6s}  ->  ancilla "
          f"{best['T']:6d} ({best['ancillas']} anc)  {round(time.time() - t0)} s", flush=True)
    return rows


if __name__ == "__main__":
    tag, folders, rest = sys.argv[1], sys.argv[2].split(","), sys.argv[3:]
    if rest and rest[0] != "--family":                          # named circuits: no manifest needed
        names = rest
    else:                                                       # a family, or the whole suite
        manifest = list(csv.DictReader(open(os.path.join(HERE, "benchmarks", "MANIFEST.csv"))))
        names = [c["name"] for c in manifest if rest[:1] != ["--family"] or c["family"] == rest[1]]
    rules = [r for f in folders for r in valid_rules(f)]
    outdir = os.path.join(HERE, "results", f"sweep_anc_{tag}"); os.makedirs(outdir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="sweep_anc_", dir=outdir)
    print(f"{len(rules)} rules x {len(names)} circuits, {WORKERS} workers", flush=True)
    with Pool(WORKERS) as pool:
        rows = [r for rs in pool.imap_unordered(job, [(n, rules, tmp, outdir) for n in names]) for r in rs]
    shutil.rmtree(tmp, ignore_errors=True)
    rows.sort(key=lambda r: (r["family"], r["circuit"], r["rule"] == "BEST"))
    with open(os.path.join(HERE, "results", f"sweep_anc_{tag}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print("SWEEP DONE ->", os.path.relpath(os.path.join(HERE, "results", f"sweep_anc_{tag}.csv"), HERE))
