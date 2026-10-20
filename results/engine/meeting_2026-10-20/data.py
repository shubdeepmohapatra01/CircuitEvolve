"""Group-meeting data assembly: reads ONLY committed CircuitEvolve result files (no new runs)."""
import csv, glob, json
from pathlib import Path
import pandas as pd

CE = Path("/Users/shubdeepmohapatra/Documents/CircuitEvolve")
RC = CE / "results/engine/recon_campaign1"
AC = CE / "results/engine/angle_campaign1"

# ---------------- reconstruction (recon_campaign1): numbers as tabulated in DEV/HELDOUT/SWEEP reports
base = {}
for r in csv.DictReader(open(CE / "results/engine/recon_bench/baselines.csv")):
    if r["t_count"].strip():
        base.setdefault(r["circuit"], {})[r["arm"]] = int(r["t_count"])
recon_rows = [  # circuit, split, naive, control_exact, control_relaxed, llm_relaxed
    ("cuccaro_4", "dev", 56, 32, 16, 16), ("cuccaro_8", "dev", 112, 64, 32, 32),
    ("barenco_tof_5", "dev", 84, 40, 36, 16), ("tof_5", "dev", 49, 31, 16, 16),
    ("rc_adder_6", "dev", 77, 47, 40, 24),
    ("cuccaro_16", "held-out", 224, 128, 64, 64), ("adder_8", "held-out", 399, 173, 180, 160),
    ("barenco_tof_10", "held-out", 224, 100, 96, 96), ("mod_adder_1024", "held-out", 1995, 1011, 660, 628),
    ("gf2^4_mult", "held-out", 112, 68, 64, 36),
    ("ham15-med", "reserved", 574, 212, 220, 208), ("gf2^6_mult", "reserved", 252, 150, 144, 144),
    ("hwb6", "reserved", 105, 75, 56, 52), ("mod_red_21", "reserved", 119, 73, 56, 44)]
rec = pd.DataFrame(recon_rows, columns=["circuit", "split", "naive_T", "control_exact", "control_relaxed", "llm_relaxed"])
rec["B0_tket"] = [base.get(c, {}).get("B0_tket") for c in rec.circuit]
rec["B1_pyzx"] = [base.get(c, {}).get("B1_pyzx") for c in rec.circuit]

# cross-checks against the run files
dv = {c["circuit"]: c for c in json.load(open(RC / "dev_results.json"))["circuits"]}
ho = {c["circuit"]: c for c in json.load(open(RC / "heldout_results.json"))["circuits"]}
for _, r in rec.iterrows():
    if r.circuit in dv:
        assert dv[r.circuit]["t_after"] == r.llm_relaxed, r.circuit
    elif r.circuit in ho and r.circuit != "gf2^4_mult":
        assert ho[r.circuit]["t_after"] == r.llm_relaxed, r.circuit
    if "control_relaxed" in base.get(r.circuit, {}):
        assert base[r.circuit]["control_relaxed"] == r.control_relaxed, r.circuit
        assert base[r.circuit]["naive_T"] == r.naive_T, r.circuit
assert json.load(open(RC / "runs/recon_c1_held2_gf2^4_mult_summary.json"))["t_after"] == 36
reserved_files = {c: sorted(Path(f).name for f in glob.glob(str(RC / f"runs/*{c}_summary.json")))
                  for c in ["ham15-med", "gf2^6_mult", "hwb6", "mod_red_21"]}

# ---------------- angle (stage-1 baselines + angle_campaign1)
bl = {}
for r in csv.DictReader(open(CE / "results/bqskit_baselines/stage1/stage1_baselines_v2.csv")):
    k = (r["circuit"], float(r["eps_total"]))
    bl.setdefault(k, {}).setdefault(r["arm"], dict(t=int(r["t_count_canon"]), valid=r["measured_within_eps"] == "True"))
zero = {(z["circuit"], z["eps"]): z for z in json.load(open(AC / "zero_llm.json"))["rows"]}
runs = {}
for l in open(AC / "results.jsonl"):
    r = json.loads(l)
    if r.get("valid"):
        runs[(r["phase"], r["circuit"], r["arm"])] = r
DEV = ["qft_8", "heisenberg_6", "hubbard_8", "qml_13", "hhl_8"]
HELD = ["qpe_8", "qae_13", "tfim_6"]
ang = []
for c in DEV + HELD:
    b = bl[(c, 1e-3)]
    z = zero[(c, 1e-3)]
    row = dict(circuit=c, split=("dev" if c in DEV else "held-out"),
               B0_tket=b["B0"]["t"], B1_pyzx=b["B1"]["t"], B2_bqskit_ft=b["B2"]["t"],
               B3_bqskit_dpf_published=b["B3"]["t"], B3g_bqskit_dpf_gridsynth=b["B3g"]["t"],
               G1_pass=z["t_after_g1"])
    assert z["t_input_no_pass"] == b["B0"]["t"], c
    for a in "ABC":
        rr = runs.get(("dev" if c in DEV else "held", c, a))
        row[f"llm_arm_{a}"] = rr["t_after"] if rr else None
        if rr:
            assert rr["t_before"] == z["t_after_g1"], (c, a)
    ang.append(row)
ang = pd.DataFrame(ang)

# ---------------- rule counts
def counts(path):
    d = json.load(open(path))
    out = {}
    for r in d["rules"]:
        out[(r["origin"], r["status"])] = out.get((r["origin"], r["status"]), 0) + 1
    return d, out
