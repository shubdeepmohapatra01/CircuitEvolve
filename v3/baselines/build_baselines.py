"""Assemble v3/baselines/baselines.csv: one row per circuit x method x eps (frozen after P0).

    .venv/bin/python -m v3.baselines.build_baselines         # refuses to overwrite an existing baselines.csv

Sources (no reruns except the two new ones):
  dv_angle  results/bqskit_baselines/stage1/stage1_baselines_v2.csv, column t_count_canon;
            TKET = B0, pyzx = B1, BQSKit-FT = B2, BQSKit-DPF = B3g (B3 exceeds its eps by code accounting).
  dv_recon  TKET = tket_fpo_logical, pyzx = pyzx_fr from results/v2/baselines_new.csv (exact, eps 0);
            BQSKit-FT (B2) / BQSKit-DPF (B3g) = NEW runs v3/baselines/bqskit_recon/runs/*.json (input: the Nam
            Clifford+T file, since BQSKit passes ccx through undecomposed).
  cvdv      Genesis best of 5 seeds by routed total gates, judged: v3/baselines/genesis/judged.jsonl; two rows per
            circuit, level = routed (physical output) and logical (before routing; may be incomplete). Ours is
            compared at the same level. Errors sit on the row of the level they were measured at.
"""
from __future__ import annotations

import csv
import json
import sys

from ..paths import BASELINES, BASELINES_CSV, MANIFEST, REPO

STAGE1 = REPO / "results/bqskit_baselines/stage1/stage1_baselines_v2.csv"
V2 = REPO / "results/v2/baselines_new.csv"
ANGLE_ARMS = [("TKET", "B0"), ("pyzx", "B1"), ("BQSKit-FT", "B2"), ("BQSKit-DPF", "B3g")]
RECON_V2 = [("TKET", "tket_fpo_logical"), ("pyzx", "pyzx_fr")]
RECON_NEW = [("BQSKit-FT", "B2"), ("BQSKit-DPF", "B3g")]
COLS = ["label", "family", "eps", "method", "arm", "level", "complete", "unsynthesized", "t_count", "qubits", "cx", "err_bound", "one_op", "two_op",
        "total", "duration", "err_trotter", "err_exact", "error_level", "cutoffs_agree", "best_seed",
        "source", "note"]


def main():
    if BASELINES_CSV.exists() and "--force" not in sys.argv:
        sys.exit(f"{BASELINES_CSV} exists (frozen); refusing to overwrite")
    man = json.loads(MANIFEST.read_text())["circuits"]
    s1 = list(csv.DictReader(open(STAGE1)))
    v2 = list(csv.DictReader(open(V2)))
    judged = {}
    for line in open(BASELINES / "genesis" / "judged.jsonl"):
        r = json.loads(line)
        judged[r["label"]] = r                     # last line per label wins (append-only log)
    rows = []
    for c in man:
        lab = c["label"]
        if c["family"] == "dv_angle":
            for eps in c["eps"]:
                for meth, arm in ANGLE_ARMS:
                    hit = [r for r in s1 if r["circuit"] == lab and r["arm"] == arm and float(r["eps_total"]) == eps]
                    assert len(hit) == 1, (lab, arm, eps, len(hit))
                    r = hit[0]
                    rows.append(dict(label=lab, family="dv_angle", eps=eps, method=meth, arm=arm,
                                     t_count=int(r["t_count_canon"]), qubits=int(r["qubits"]), cx=int(r["cx"]),
                                     err_bound=float(r["err_bound_total"]), source=str(STAGE1.relative_to(REPO)),
                                     note=r["arm_desc"]))
        elif c["family"] == "dv_recon":
            src = c["source"].split("/")[-1][:-5]
            for meth, arm in RECON_V2:
                hit = [r for r in v2 if r["circuit"] == src and r["arm"] == arm]
                assert len(hit) == 1, (lab, arm, len(hit))
                r = hit[0]
                rows.append(dict(label=lab, family="dv_recon", eps=float(r["eps"]), method=meth, arm=arm,
                                 t_count=int(r["t_count"]), qubits=int(r["qubits"]), err_bound=float(r["eps"]),
                                 source=str(V2.relative_to(REPO)), note=r["notes"][:200]))
            for meth, arm in RECON_NEW:
                for eps in c["eps"]:
                    f = BASELINES / "bqskit_recon" / "runs" / f"{lab}_{arm}_e{round(-__import__('math').log10(eps))}.json"
                    r = json.loads(f.read_text())
                    assert r["status"] == "ok" and r["residual_rz"] == 0 and not r["other_ops"], (lab, arm, r.get("error"))
                    rows.append(dict(label=lab, family="dv_recon", eps=eps, method=meth, arm=arm,
                                     t_count=int(r["t_count"]), qubits=int(r["qubits"]), cx=int(r["cx"]),
                                     err_bound=0.0 if not r.get("n_rz") else eps,
                                     source=str(f.relative_to(REPO)),
                                     note=f"input {c['bqskit_input_source']} (Clifford+T, 7 T/Toffoli; BQSKit leaves "
                                          f"ccx undecomposed); state_dist_vs_logical="
                                          f"{'skipped (>20 qubits)' if r['state_dist_vs_orig'] is None else format(r['state_dist_vs_orig'], '.1e')}; "
                                          f"n_rz={r['n_rz']}"))
        else:
            r = judged[lab]
            lg = r["logical_best_seed"]
            for level, m in (("routed", r), ("logical", lg)):
                has_err = r["err_trotter"] is not None and (r["error_level"] == "physical") == (level == "routed")
                rows.append(dict(label=lab, family="cvdv", eps="", method="Genesis", arm=f"seed{r['best_seed']}",
                                 level=level, one_op=m["one_op"], two_op=m["two_op"], total=m["total"],
                                 duration=m["duration"], complete=m.get("complete", True),
                                 unsynthesized=m.get("unsynthesized", 0),
                                 err_trotter=r["err_trotter"] if has_err else "",
                                 err_exact=r["err_exact"] if has_err else "",
                                 error_level=r["error_level"] if has_err else "",
                                 cutoffs_agree=r["cutoffs_agree"] if has_err else "", best_seed=r["best_seed"],
                                 source="v3/baselines/genesis/judged.jsonl",
                                 note=(f"best of seeds {r['seeds_total']} by routed total gates; " +
                                       ("routed = Genesis physical output (== --stats)" if level == "routed" else
                                        "logical = Genesis circuit before routing" +
                                        ("" if m.get("complete", True) else
                                         f"; INCOMPLETE: {m['unsynthesized']} multi-Pauli placeholders unsynthesized"))
                                       + ("; errors = process infidelity on the probe subspace, larger cutoff"
                                          if has_err else "") +
                                       ("; errors skipped (user decision 2026-10-20)"
                                        if r["err_trotter"] is None and level == "routed" else ""))))
    with open(BASELINES_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {BASELINES_CSV}: {len(rows)} rows")


if __name__ == "__main__":
    main()
