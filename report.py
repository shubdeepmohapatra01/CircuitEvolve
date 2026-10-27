"""CircuitEvolve test-set T-count table + B0/B1/B2 vs L0/L1/L2 figures."""
import argparse, json, csv
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent
COLORS = {"B0": "#2878d6", "B1": "#ee6a37", "B2": "#1db07e", "L0": "#f0a000", "L1": "#b07ad8", "L2": "#8c564b"}
LEGEND = {"B0": "B0 TKET+gridsynth", "B1": "B1 TKET+pyzx+gridsynth", "B2": "B2 BQSKit DPF Synth (PKAC)",
          "L0": "L0 LLM", "L1": "L1 pyzx+LLM", "L2": "L2 DPF(k=3)+LLM"}
HATCH_NOTE = ("B2 hatched: phase-kickback output fails an equivalence check upstream "
              "(bqskit-ft greedy_ntro @c04a322); stored value shown.")
E2E_NOTE = "* end-to-end re-check too large to simulate; every rule application was verified locally"

def read_csv_rows(path, key):
    if not Path(path).exists(): return {}
    with open(path, newline="") as f:
        return {r[key]: r for r in csv.DictReader(f)}

def load_splits(path):
    d = json.load(open(path))
    return [{"label": t.get("plot_name", t["name"]), "family": t["family"]} for t in d["test"]]

def load_b0_b1(path):
    rows = read_csv_rows(path, "circuit")
    return {c: {"B0": float(r["L0_T"]), "B1": float(r["L1_T"])} for c, r in rows.items() if r["split"] == "test"}

def load_b2(baselines_path, b4_path):
    vals, hatch = {}, {}
    for c, r in read_csv_rows(baselines_path, "circuit").items():
        v = r.get("B2 BQSKit-DPF (best)", "")
        if v:
            vals[c], hatch[c] = float(v), float(r.get("dpf_ancillas") or 0) > 0
    for r in csv.DictReader(open(b4_path, encoding="utf-8-sig")):   # several rows per label (one per eps)
        c = r["label"]
        if r["arm"] == "B4" and float(r["eps"]) == 1e-3 and c not in vals:
            vals[c], hatch[c] = float(r["t_count"]), float(r.get("ancillas") or 0) > 0
    return vals, hatch

def build_table(circuits, b0b1, b2, arms):
    recs = []
    for c in circuits:
        lab, fam = c["label"], c["family"]
        rec = {"circuit": lab, "family": fam, "B0": None, "B1": None, **b0b1.get(lab, {}), "B2": b2.get(lab)}
        ours = {}
        for arm, rows in arms.items():
            r = rows.get(lab)
            rec[arm] = float(r["t"]) if r else None
            rec[f"{arm}_no_playbook"] = float(r["t_no_playbook"]) if r else None
            if r: ours[arm] = (float(r["t"]), float(r["qubits"]))
        # B0/B1 ARE the L0/L1 pipelines with an empty playbook (same inputs, same stages): take them from there.
        if rec.get("L0_no_playbook") is not None: rec["B0"] = rec["L0_no_playbook"]
        if rec.get("L1_no_playbook") is not None: rec["B1"] = rec["L1_no_playbook"]
        base = {k: rec[k] for k in ("B0", "B1", "B2") if rec.get(k) is not None}
        bb = min(base, key=base.get) if base else None
        bo = min(ours, key=lambda a: ours[a][0]) if ours else None
        rec["best_baseline"], rec["best_baseline_T"] = bb, base.get(bb)
        rec["best_ours"], rec["best_ours_T"] = bo, ours[bo][0] if bo else None
        rec["qubits_best_ours"] = ours[bo][1] if bo else None
        rec["delta_vs_best"] = (ours[bo][0] - base[bb]) if (bb and bo) else None
        recs.append(rec)
    return pd.DataFrame(recs)

def plot_family(df, fam, bars, title, outpath, hatch, e2e):
    rows = df[df.family == fam]
    if rows.empty: return
    fig, axes = plt.subplots(1, len(rows), figsize=(2.3 * len(rows), 3.3), squeeze=False)
    used = set()
    for ax, (_, row) in zip(axes[0], rows.iterrows()):
        vals = [(b, row[b]) for b in bars if pd.notna(row.get(b))]
        if not vals:
            ax.text(0.5, 0.5, "n/a", ha="center", transform=ax.transAxes)
        top = max((v for _, v in vals), default=1)
        for x, (b, v) in enumerate(vals):
            h = "//" if (b == "B2" and hatch.get(row.circuit)) else None
            ax.bar(x, v, color=COLORS[b], hatch=h, edgecolor="black", linewidth=0.5)
            ax.text(x, v + 0.01 * top, f"{int(v)}", ha="center", va="bottom", fontsize=7)
            if row.circuit in e2e.get(b, set()):
                ax.text(x, v + 0.09 * top, "*", ha="center", va="bottom", fontsize=10, color="red")
            used.add(b)
        ax.set_xticks(range(len(vals))); ax.set_xticklabels([b for b, _ in vals], fontsize=7, rotation=45)
        ax.set_title(row.circuit, fontsize=8)
        ax.set_ylim(bottom=0)
    axes[0][0].set_ylabel("T-count")
    fig.suptitle(title)
    handles = [plt.Rectangle((0, 0), 1, 1, color=COLORS[b]) for b in bars if b in used]
    fig.legend(handles, [LEGEND[b] for b in bars if b in used], loc="lower center",
               ncol=max(len(handles), 1), fontsize=7, bbox_to_anchor=(0.5, -0.02))
    notes = [n for cond, n in ((any(hatch.values()) and "B2" in used, HATCH_NOTE),
                                (any(e2e.values()), E2E_NOTE)) if cond]
    if notes: fig.text(0.5, -0.14, "\n".join(notes), ha="center", fontsize=6, wrap=True)
    fig.tight_layout(rect=[0, 0.1, 1, 0.94])
    fig.savefig(outpath, dpi=300, bbox_inches="tight")
    plt.close(fig)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--results", default=str(REPO / "results"))
    args = ap.parse_args()
    circuits = load_splits(REPO / "splits.json")
    b0b1 = load_b0_b1(REPO / "baselines" / "b0_b1_recomputed.csv")
    b2, hatch = load_b2(REPO / "baselines" / "baselines.csv", REPO / "baselines" / "b4_dpf_synth.csv")
    arms = {a: read_csv_rows(Path(args.results) / f"test_{a}.csv", "circuit") for a in ("L0", "L1", "L2")}
    e2e = {a: {c for c, r in rows.items() if r.get("e2e_check") not in (None, "ok")} for a, rows in arms.items()}
    df = build_table(circuits, b0b1, b2, arms)
    out_dir = Path(args.results); out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "t_counts.csv", index=False); print(df.to_string(index=False))
    plot_family(df, "toffoli", ["B0", "B1", "L0", "L1"], "Toffoli-level circuits (lower is better)",
                out_dir / "t_counts_toffoli.png", hatch, e2e)
    plot_family(df, "rotation", ["B0", "B1", "B2", "L0", "L1", "L2"],
                "Clifford+Rz circuits, eps = 1e-3 (lower is better)", out_dir / "t_counts_rotation.png", hatch, e2e)

if __name__ == "__main__":
    main()
