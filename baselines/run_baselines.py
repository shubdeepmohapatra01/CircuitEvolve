"""The four baselines on a set of circuits: raw, tket(raw), pyzx(raw), bqskit_dpf(tket(raw)) with k=3.
Each output is verified against raw (tol 1e-8; DPF: tol = eps_used) and T-counted at total error 1e-3 (DPF already
spent eps_used, so gridsynth gets 1e-3 - eps_used). Failures and timeouts are rows with an `error`, never dropped.
    .venv/bin/python baselines/run_baselines.py [--workers 8] [--out NAME] [circuit ...]
With no circuit named, every row of benchmarks/MANIFEST.csv is run; named circuits are found by playbook.find_circuit
and need no manifest.  -> results/<NAME>/baselines.{csv,json}, summary.md   (NAME defaults to baselines_suite)
"""
import argparse, csv, json, math, os, subprocess, sys, time
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "verifier")]
import pipeline
import verifier_noanc as verifier
from playbook import find_circuit

OUT = os.path.join(pipeline.HERE, "results", "baselines_suite")
DPF_TIMEOUT = 900                                   # s per circuit; pipeline.bqskit_dpf itself allows 3600
BASELINES = ["raw", "tket", "pyzx", "bqskit_dpf"]
_run = subprocess.run
subprocess.run = lambda *a, **k: _run(*a, **{**k, "timeout": DPF_TIMEOUT})


def run_one(c):
    """All four baselines on one circuit (a manifest row, or one from find_circuit); one result row per baseline."""
    raw, rows, done = pipeline.load(os.path.join(pipeline.HERE, c["path"])), [], {}
    steps = [("raw", lambda: (raw, 0.0)), ("tket", lambda: (pipeline.tket(raw), 0.0)),
             ("pyzx", lambda: (pipeline.pyzx(raw), 0.0)), ("bqskit_dpf", lambda: pipeline.bqskit_dpf(done["tket"], k=3))]
    for b, f in steps:
        r = dict(name=c["name"], family=c["family"], qubits=int(c["qubits"]), baseline=b, T="", arbitrary_rz="", cx="",
                 gates="", seconds="", verified=False, distance="", eps_used="", error="")
        t0 = time.time()
        try:
            qc, eps = f()
            r["seconds"] = round(time.time() - t0, 2)
            done[b] = qc
            v = verifier.verify(raw, qc, tol=max(eps, 1e-8))
            s = pipeline.stats(qc)
            r.update(T=pipeline.t_count(qc, eps_total=pipeline.EPS_TOTAL - eps), arbitrary_rz=s["arbitrary_rz"],
                     cx=s["cx"], gates=s["gates"], verified=v["ok"], distance=v["distance"], eps_used=eps,
                     error="" if v["ok"] else "not verified: " + v["reason"])
        except Exception as e:
            r.update(seconds=r["seconds"] or round(time.time() - t0, 2), error=f"{type(e).__name__}: {str(e)[-300:]}")
        rows.append(r)
    print(c["name"], " ".join(f"{r['baseline']}={r['T']}{'' if r['verified'] else '!'}" for r in rows), flush=True)
    return rows


def summary(rows):
    """Markdown table: per family and baseline, sum of T, geometric-mean T / T_tket (over T > 0), verified count."""
    T = {(r["name"], r["baseline"]): r["T"] for r in rows if r["verified"]}
    fams = sorted({r["family"] for r in rows}) + ["ALL"]
    lines = ["| family | n | " + " | ".join(f"{b}: sum T / geomean T/T_tket / ok" for b in BASELINES) + " |",
             "|---" * (2 + len(BASELINES)) + "|"]
    for f in fams:
        names = sorted({r["name"] for r in rows if f in ("ALL", r["family"])})
        cells = []
        for b in BASELINES:
            ok = [n for n in names if (n, b) in T]
            rat = [T[n, b] / T[n, "tket"] for n in ok if T.get((n, "tket"))]
            pos = [x for x in rat if x > 0]
            g = math.exp(sum(map(math.log, pos)) / len(pos)) if pos else float("nan")
            cells.append(f"{sum(T[n, b] for n in ok)} / {g:.3f} / {len(ok)}" + (f" ({len(rat) - len(pos)} T=0)" if len(pos) < len(rat) else ""))
        lines.append(f"| {f} | {len(names)} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def circuit_rows(names):
    """Manifest rows for `names`, or every manifest row if none are named."""
    manifest = os.path.join(pipeline.HERE, "benchmarks", "MANIFEST.csv")
    if not names:
        return list(csv.DictReader(open(manifest)))
    rows = {r["name"]: r for r in csv.DictReader(open(manifest))} if os.path.exists(manifest) else {}
    out = []
    for n in names:                                                     # a named circuit need not be in the manifest
        if n in rows:
            out.append(rows[n]); continue
        p = find_circuit(n); qc = pipeline.load(p)
        out.append(dict(name=n, family="", qubits=qc.num_qubits, gates=qc.size(),
                        path=os.path.relpath(p, pipeline.HERE)))
    return out


def main(workers=8, names=(), out=OUT):
    global OUT
    OUT = out
    os.makedirs(OUT, exist_ok=True)
    circuits = sorted(circuit_rows(list(names)), key=lambda c: -int(c["gates"]))   # big first: better load balance
    t0, rows = time.time(), []
    with Pool(workers) as p:
        for rs in p.imap_unordered(run_one, circuits):
            rows += rs
    order = {c["name"]: i for i, c in enumerate(sorted(circuits, key=lambda c: (c["family"], c["name"])))}
    rows.sort(key=lambda r: (order[r["name"]], BASELINES.index(r["baseline"])))
    with open(os.path.join(OUT, "baselines.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    json.dump(rows, open(os.path.join(OUT, "baselines.json"), "w"), indent=1, default=str)
    open(os.path.join(OUT, "summary.md"), "w").write(
        f"# Baselines on {len(circuits)} circuits ({round(time.time() - t0)} s, {workers} workers)\n\n" + summary(rows)
        + "\nFailures:\n" + "".join(f"- {r['name']} {r['baseline']}: {r['error']}\n" for r in rows if r["error"]))
    print(open(os.path.join(OUT, "summary.md")).read())


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("circuits", nargs="*")
    a.add_argument("--workers", type=int, default=8)
    a.add_argument("--out", default="baselines_suite", help="results/<NAME>/")
    a = a.parse_args()
    main(a.workers, a.circuits, os.path.join(pipeline.HERE, "results", a.out))
