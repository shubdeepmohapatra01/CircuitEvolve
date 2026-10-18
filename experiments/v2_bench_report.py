"""Aggregate the v2 benchmark baselines into results/v2/baselines_new.csv (schema: circuit, source, arm, eps,
t_count, qubits, notes), results/v2/baselines_new_detail.csv (one row per circuit x arm with CNOT count,
verification record, runtime) and results/v2/baselines_consistency.json (cross-checks).

    .venv/bin/python experiments/v2_bench_report.py results/v2 results/v2/bench_runs/run2 [results/v2/bench_runs/run3_large ...]
(first argument = output directory; for a circuit present in several run dirs the FIRST listed run is used)
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
V2 = os.path.join(ROOT, "results", "v2")
PUB_BASE = ("/Users/shubdeepmohapatra/.claude-science/orgs/4f2e4147-ba5e-4b44-8499-c19c4f626162/artifacts/"
            "proj_a726946937e5/cc62703b-e9c7-4b16-a586-4294a304148f/vd35f54a0_published_baselines.csv")
ARM_DESC = {
    "given_cliffordt": "Clifford+T as given (Quartz nam_circs; 7 T per CCZ)",
    "pyzx_fr": "pyzx 0.10.7 full_reduce -> extract_circuit -> to_basic_gates -> basic_optimization (Clifford+T input)",
    "tket_fpo": "TKET FullPeepholeOptimise + AutoRebase{CX,H,Rz} + RemoveRedundancies (Clifford+T input)",
    "tket_fpo_logical": "TKET FullPeepholeOptimise ... on the logical input (ccx native, ccz as h-ccx-h)",
    "nam_light_file": "Nam et al. Light output file (njross/optimizer), T counted by us",
    "nam_heavy_file": "Nam et al. Heavy output file (njross/optimizer), T counted by us",
}


def vstr(v):
    if not v:
        return ""
    s = f"{v['method']} ok={v.get('ok')} dist={v.get('dist', float('nan')):.1e}"
    if "zx_identity" in v:
        s += f" zx_identity={v['zx_identity']}"
    if "qcec" in v:
        s += f" qcec={v['qcec']}"
    s += f" -> verified={v.get('verified')}"
    return s


def main(out_dir, *run_dirs):
    runs, run_of = {}, {}
    for rd in run_dirs:
        for p in sorted(glob.glob(os.path.join(rd, "*.json"))):
            r = json.load(open(p))
            if r["circuit"] not in runs:
                runs[r["circuit"]] = r
                run_of[r["circuit"]] = os.path.basename(os.path.normpath(rd))
    tag = "+".join(os.path.basename(os.path.normpath(rd)) for rd in run_dirs)
    pub = list(csv.DictReader(open(os.path.join(V2, "published_arith.csv"))))
    gs = {}
    for p in glob.glob(os.path.join(V2, "rotations_gridsynth_*_eps0.001.json")):
        gs.update(json.load(open(p)))
    rows, detail, cons = [], [], dict(run=tag, problems=[], checks={}, run_of=run_of)
    for name, r in sorted(runs.items()):
        n = r["qubits"]
        tag = run_of[name]
        for arm, a in r["arms"].items():
            v = a.get("verify")
            src = "given" if arm == "given_cliffordt" else ("nam_authors_file" if arm.startswith("nam_") else f"run:{tag}")
            note = ARM_DESC[arm]
            t_rep, eps = a["t_count"], 0
            if a.get("rz_other"):
                g = gs.get(f"{name}__{arm}")
                if g is None:
                    note += f"; {a['rz_other']} non-pi/4 rotations remain, NOT costed (t_count counts pi/4 T only)"
                    cons["problems"].append(f"{name}/{arm}: rotations not costed")
                else:
                    t_rep, eps = g["t"], g["eps_total"]
                    note += (f"; {g['rz']} non-pi/4 rotations remain -> BQSKit convention (core/metric.BqskitTMetric): "
                             f"{g['t_fixed']} T fixed + {g['t_gs']} T gridsynth at eps_rz={g['eps_rz']:.3g}")
            if v:
                note += "; verify " + vstr(v)
                if v.get("verified") is not True:
                    cons["problems"].append(f"{name}/{arm}: verification not passed: {vstr(v)}")
            if arm == "pyzx_fr":
                note += f"; graph T after full_reduce {a['t_graph']}"
            rows.append(dict(circuit=name, source=src, arm=arm, eps=eps, t_count=t_rep, qubits=n, notes=note))
            detail.append(dict(circuit=name, arm=arm, qubits=n, t_count=t_rep, eps=eps, t_pi4_only=a["t_count"],
                               cx=a.get("cx"),
                               gates=a.get("gates"), rz_other=a.get("rz_other", 0), t_graph=a.get("t_graph"),
                               verify_method=(v or {}).get("method"), verify_ok=(v or {}).get("ok"),
                               verify_dist=(v or {}).get("dist"), zx_identity=(v or {}).get("zx_identity"),
                               qcec=(v or {}).get("qcec"), verified=(v or {}).get("verified"),
                               runtime_s=a.get("pipeline_s"), run=tag))
        # consistency checks
        prov = r["provenance"]
        c = {k: v.get("verified") for k, v in prov.items() if isinstance(v, dict) and "method" in v}
        c["planted_bug_rejected"] = r["planted_bug_check"]["verified"] is False
        if not c["planted_bug_rejected"]:
            cons["problems"].append(f"{name}: planted bug NOT rejected")
        for k, ok in list(c.items())[:-1]:
            if ok is not True:
                cons["problems"].append(f"{name}: provenance {k} not passed")
        P = {(p["paper"], p["arm"]): int(p["t_count"]) for p in pub if p["circuit"] == name}
        g = r["arms"]["given_cliffordt"]["t_count"]
        for key, ours in ((("Nam2018", "nam2018_pre"), g), (("Nam2018", "nam2018_light"),
                          r["arms"].get("nam_light_file", {}).get("t_count")),
                          (("Nam2018", "nam2018_heavy"), r["arms"].get("nam_heavy_file", {}).get("t_count")),
                          (("KvdW2020", "kvdw2020_original"), g),
                          (("KvdW2020", "kvdw2020_pyzx"), r["arms"]["pyzx_fr"]["t_count"])):
            if key in P and ours is not None:
                c[f"{key[1]}: published {P[key]} vs ours {ours}"] = P[key] == ours
        cons["checks"][name] = c
    man = {m["name"]: m for m in csv.DictReader(open(os.path.join(ROOT, "benchmarks", "nam_arith", "MANIFEST.csv")))}
    for name, m in man.items():
        if name not in runs and m["family"] != "shor":
            rows.append(dict(circuit=name, source="given", arm="given_cliffordt", eps=0, t_count=m["t_count_given"],
                             qubits=m["qubits"], notes=ARM_DESC["given_cliffordt"] + "; from MANIFEST.csv"))
            rows.append(dict(circuit=name, source="none", arm="pyzx_fr/tket_fpo/tket_fpo_logical/nam_files",
                             eps="", t_count="", qubits=m["qubits"],
                             notes="baseline not computed (run3_large stopped at 01:57 after ~110 min; 5400 s / 7200 s timeouts in "
                                   "run1 / run2); MANIFEST split = large_optional"))
            cons["problems"].append(f"{name}: baseline not computed (timeout)")
    for p in pub:
        rows.append(dict(circuit=p["circuit"], source=f"published:{p['paper']}", arm=p["arm"], eps=0,
                         t_count=p["t_count"], qubits=man.get(p["circuit"], {}).get("qubits"),
                         notes="; ".join(x for x in (p["location"], f"CNOT {p['cnot']}" if p["cnot"] else "", p["notes"]) if x)))
    for p in csv.DictReader(open(PUB_BASE)):
        if p["paper"].startswith("2603.25101"):
            rows.append(dict(circuit=p["circuit"], source="published:TRbO (via published_baselines.csv)",
                             arm=f"{p['their_method']} vs {p['reference_method']}", eps="", t_count="", qubits="",
                             notes=f"RZ count (not T): reference {p['reference']}, TRbO {p['theirs']}; "
                                   f"{p['setting']}; {p['source_location']}; circuit NOT in the v2 suite "
                                   "(QFT-based adder, Nam et al. 2018 Table 1)"))
    for fn, data in (("baselines_new.csv", rows), ("baselines_new_detail.csv", detail)):
        path = os.path.join(out_dir, fn)
        if os.path.exists(path):
            raise SystemExit(f"{path} exists (append-only); write under a new name")
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    json.dump(cons, open(os.path.join(out_dir, "baselines_consistency.json"), "w"), indent=1)
    # markdown summary (T-counts; eps = 0 unless marked)
    piv = {}
    for r in rows:
        piv.setdefault(r["circuit"], {})[r["arm"]] = (r["t_count"], r["eps"])
    cols = [("given_cliffordt", "given"), ("pyzx_fr", "pyzx"), ("tket_fpo", "TKET (C+T in)"),
            ("tket_fpo_logical", "TKET (logical in)"), ("nam_light_file", "Nam L file"), ("nam_heavy_file", "Nam H file"),
            ("tpar_as_reported_by_nam2018", "T-par (Nam T4)"), ("kvdw2020_pyzx", "PyZX (KvdW T1)"),
            ("kvdw2020_pyzx_todd", "PyZX+TODD (KvdW T1)"), ("best_prev_as_reported_by_kvdw2020", "best prev (KvdW T1)")]
    lines = ["| circuit | split | n | " + " | ".join(c[1] for c in cols) + " |", "|" + "---|" * (len(cols) + 3)]
    for name in sorted(man, key=lambda x: (man[x]["split"], man[x]["family"], int(man[x]["qubits"]), x)):
        if man[name]["family"] == "shor":
            continue
        cells = []
        for k, _ in cols:
            t, e = piv.get(name, {}).get(k, ("", ""))
            v = "" if t in ("", None) else str(t)
            if v and e not in (0, "0", "", None):
                v += f" (eps {e})"
            if v and k.endswith("_file") and runs.get(name, {}).get("arms", {}).get(k, {}).get("verify", {}).get("verified") is False:
                v += " **NOT EQUIV**"
            cells.append(v or "-")
        lines.append(f"| {name} | {man[name]['split']} | {man[name]['qubits']} | " + " | ".join(cells) + " |")
    open(os.path.join(out_dir, "baselines_new_summary.md"), "w").write("\n".join(lines) + "\n")
    print(len(runs), "circuits", len(rows), "rows;", len(cons["problems"]), "problems")
    for k in cons["problems"]:
        print(" ", k)
    mism = [(n, k) for n, c in cons["checks"].items() for k, v in c.items() if k.startswith(("nam", "kvdw")) and v is False]
    print("published mismatches:", mism)


if __name__ == "__main__":
    main(*sys.argv[1:])
