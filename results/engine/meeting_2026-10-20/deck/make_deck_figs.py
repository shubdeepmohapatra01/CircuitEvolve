
# Simplified deck figures: one baseline vocabulary (B0..B3), ours split into deterministic vs LLM.
# Axis convention on every result slide: T-count divided by B0 (TKET + gridsynth). Lower is better.
# Reads only committed results via meeting/data.py. No new computation.
import numpy as np, matplotlib as mpl, matplotlib.pyplot as plt, pandas as pd
from pathlib import Path
exec(open("meeting/data.py").read())
mpl.rcParams.update({"font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
                     "legend.fontsize": 7, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 110, "savefig.dpi": 300})
OUT = Path("meeting/bars"); OUT.mkdir(parents=True, exist_ok=True)
CB1, CB2, CB3 = "#475569", "#7C3AED", "#C4B5FD"
CDET, CLLM, CPLAN = "#0F766E", "#C2410C", "#2563EB"
W, H = 4.4, 1.95

def grouped(ax, labels, series, ymax):
    n, k = len(labels), len(series)
    bw = min(0.78 / k, 0.2); xs = np.arange(n)
    for i, (name, vals, col) in enumerate(series):
        off = (i - (k - 1) / 2) * bw
        v = np.array(vals, float); ok = ~np.isnan(v)
        clipped = ok & (v > ymax)
        ax.bar(xs[ok] + off, np.minimum(v[ok], ymax), width=bw * 0.9, color=col, label=name, zorder=3)
        for j in np.where(clipped)[0]:                      # clipped bar: marked, never silent
            ax.plot(xs[j] + off, ymax, marker="^", ms=3.5, color=col, zorder=5, clip_on=False)
            ax.text(xs[j] + off + 0.055, ymax - 0.02, f"{v[j]:.1f}x", ha="left", va="top", fontsize=6.5,
                    color="#4C1D95", fontweight="bold")
    ax.axhline(1.0, color="#64748B", lw=0.9, ls="--", zorder=4)
    ax.set_xticks(xs, labels, rotation=28, ha="right", rotation_mode="anchor")
    ax.set_xlim(-0.6, n - 0.25); ax.set_ylim(0, ymax); ax.grid(axis="y", color="#E5E7EB", lw=0.6, zorder=0)
    return xs, bw

def save(fig, name):
    fig.savefig(OUT / name, bbox_inches="tight", pad_inches=0.03); plt.close(fig)

YL = "T-count / B0\n(lower is better)"

# ---------- A. rotation circuits: all four baselines exist here
dev = ["qft_8", "hhl_8", "heisenberg_6", "hubbard_8", "qml_13"]
a = ang.set_index("circuit").loc[dev].reset_index()
rat = lambda col: [r[col] / r.B0_tket if not pd.isna(r[col]) else np.nan for _, r in a.iterrows()]
fig, ax = plt.subplots(figsize=(W, H)); fig.subplots_adjust(left=0.125, right=0.995, top=0.84, bottom=0.3)
# "merge pass, no LLM" (the deterministic G1 pass) removed from the chart per user request;
# "ours" is now the single LLM-loop bar (which runs on top of that pass, per the pipeline slide).
grouped(ax, dev, [("B1 pyzx", rat("B1_pyzx"), CB1), ("B2 BQSKit-FT", rat("B2_bqskit_ft"), CB2),
                  ("B3 BQSKit-DPF", rat("B3_bqskit_dpf_published"), CB3),
                  ("ours", rat("llm_arm_A"), CLLM)],
        ymax=2.0)
ax.set_ylabel(YL); ax.set_yticks([0, 0.5, 1.0, 1.5, 2.0])
ax.text(-0.5, 1.04, "B0", fontsize=6.5, color="#64748B", va="bottom")
ax.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 0.99), handlelength=1.0,
          columnspacing=0.9, borderaxespad=0.0)
save(fig, "fig_angle.png")

# ---------- B. Toffoli circuits: reconstruction applies; no BQSKit arms computed here
def recon_fig(names, name):
    # "planner, no LLM" (the deterministic control route) removed from the chart per user request;
    # the comparison here is now B1 pyzx (generic, no Toffoli-structure awareness) vs our LLM loop.
    d = rec.set_index("circuit").loc[names].reset_index()
    r_ = lambda col: [x[col] / x.B0_tket for _, x in d.iterrows()]
    fig, ax = plt.subplots(figsize=(W, H)); fig.subplots_adjust(left=0.125, right=0.995, top=0.86, bottom=0.3)
    xs, bw = grouped(ax, names, [("B1 pyzx", r_("B1_pyzx"), CB1),
                                 ("ours: LLM reconstruction", r_("llm_relaxed"), CLLM)], ymax=1.25)
    v = np.array(r_("llm_relaxed")); p = np.array(r_("B1_pyzx"))
    for j in range(len(d)):
        if v[j] < p[j]:
            dT = int(d.llm_relaxed.iloc[j] - d.B1_pyzx.iloc[j])
            ax.text(xs[j] + bw, v[j] + 0.03, f"\u2212{abs(dT)} T", ha="center", va="bottom", fontsize=6.5,
                    color=CLLM, fontweight="bold")
    ax.set_ylabel(YL); ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.text(-0.5, 1.03, "B0", fontsize=6.5, color="#64748B", va="bottom")
    ax.legend(frameon=False, ncol=2, loc="lower center", bbox_to_anchor=(0.5, 0.99), handlelength=1.0,
              columnspacing=0.9, borderaxespad=0.0)
    save(fig, name)

recon_fig(["cuccaro_4", "cuccaro_8", "barenco_tof_5", "tof_5", "rc_adder_6"], "fig_recon_trained.png")
recon_fig(["cuccaro_16", "adder_8", "barenco_tof_10", "mod_adder_1024", "gf2^4_mult"], "fig_recon_frozen.png")

# ---------- C. the two variants against each other (zero-LLM cascade demo)
fig, ax = plt.subplots(figsize=(3.5, 1.95)); fig.subplots_adjust(left=0.15, right=0.98, top=0.88, bottom=0.26)
groups = ["cuccaro_8\n(Toffoli only)", "cuccaro_4 + rotations\n(mixed)"]
ser = [("angle only", [96, 162], CDET), ("reconstruction only", [32, np.nan], CPLAN),
       ("reconstruction + angle", [32, 130], CLLM)]
xs = np.arange(2); bw = 0.24
for i, (nm, vals, col) in enumerate(ser):
    v = np.array(vals, float); ok = ~np.isnan(v)
    ax.bar(xs[ok] + (i - 1) * bw, v[ok], width=bw * 0.9, color=col, label=nm, zorder=3)
    for j in np.where(ok)[0]:
        ax.text(xs[j] + (i - 1) * bw, v[j] + 3, str(int(v[j])), ha="center", va="bottom", fontsize=7)
ax.text(1, 8, "n/a", ha="center", fontsize=6.5, color=CPLAN)
ax.set_xticks(xs, groups, fontsize=7); ax.set_ylabel("T-count"); ax.set_ylim(0, 215)
ax.grid(axis="y", color="#E5E7EB", lw=0.6, zorder=0)
ax.legend(frameon=False, ncol=1, loc="upper left", handlelength=1.0, borderaxespad=0.15)
save(fig, "fig_stages.png")
print(sorted(p.name for p in OUT.glob("fig_*.png")))
