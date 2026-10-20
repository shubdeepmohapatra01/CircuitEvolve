
# Vertical-bar figures for the beamer deck. Reads only committed results (via meeting/data.py).
import numpy as np, matplotlib as mpl, matplotlib.pyplot as plt, pandas as pd
exec(open("meeting/data.py").read())
try:
    apply_figure_style(sizes=(7.5, 7, 6.5))
except NameError:
    pass
mpl.rcParams.update({"font.size": 7.5, "axes.labelsize": 7.5, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
                     "legend.fontsize": 6, "axes.spines.top": False, "axes.spines.right": False})
OUTD = Path("meeting/bars"); OUTD.mkdir(exist_ok=True)
C = dict(tket="#94A3B8", pyzx="#475569", plan="#2563EB", llm="#C2410C", g1="#0F766E", dpf="#7C3AED")
W, H = 4.4, 1.65

def grouped(ax, labels, series, bw=None):
    n, k = len(labels), len(series)
    bw = bw or min(0.8 / k, 0.22)
    xs = np.arange(n)
    for i, (name, vals, col) in enumerate(series):
        off = (i - (k - 1) / 2) * bw
        v = np.array(vals, dtype=float)
        ok = ~np.isnan(v)
        ax.bar(xs[ok] + off, v[ok], width=bw * 0.92, color=col, label=name, zorder=3)
    ax.set_xticks(xs, labels, rotation=35, ha="right", rotation_mode="anchor")
    ax.set_xlim(-0.6, n - 0.2)
    ax.grid(axis="y", color="#E5E7EB", lw=0.6, zorder=0)
    return xs, bw

def save(fig, name):
    fig.savefig(OUTD / name, dpi=300, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)

# ---------------- reconstruction: trained / never trained
def recon_fig(df, name, ymax_pad=1.42):
    red = lambda col: [100 * (r.naive_T - r[col]) / r.naive_T if not pd.isna(r[col]) else np.nan for _, r in df.iterrows()]
    series = [("TKET", red("B0_tket"), C["tket"]), ("pyzx", red("B1_pyzx"), C["pyzx"]),
              ("planner (no LLM)", red("control_relaxed"), C["plan"]), ("LLM loop", red("llm_relaxed"), C["llm"])]
    fig, ax = plt.subplots(figsize=(W, H)); fig.subplots_adjust(left=0.115, right=0.995, top=0.97, bottom=0.34)
    xs, bw = grouped(ax, list(df.circuit), series)
    llm = np.array(series[3][1]); top = np.nanmax([np.nanmax(s[1]) for s in series])
    for j, (_, r) in enumerate(df.iterrows()):
        d = int(r.llm_relaxed - r.control_relaxed)
        if d < 0:
            ax.text(xs[j] + 1.5 * bw, llm[j] + top * 0.02, f"\u2212{abs(d)} T", ha="center", va="bottom", fontsize=6.5, color=C["llm"], fontweight="bold")
    ax.set_ylim(0, top * ymax_pad); ax.set_ylabel("T-count reduction\nvs naive (%)")
    ax.legend(frameon=False, ncol=4, loc="upper center", handlelength=1.0, columnspacing=1.0, borderaxespad=0.1)
    ax.set_yticks([0, 20, 40, 60, 80])
    save(fig, name)

dev = rec[rec.split == "dev"].reset_index(drop=True)
nt = rec[rec.split != "dev"].reset_index(drop=True)
recon_fig(dev, "bar_recon_trained.png"); recon_fig(nt, "bar_recon_frozen.png")

# ---------------- angle
order = ["qft_8", "hhl_8", "heisenberg_6", "hubbard_8", "qml_13", "qpe_8", "qae_13", "tfim_6"]
a = ang.set_index("circuit").loc[order].reset_index()
pc = lambda col: [100 * (r.B0_tket - r[col]) / r.B0_tket if not pd.isna(r[col]) else np.nan for _, r in a.iterrows()]
series = [("pyzx", pc("B1_pyzx"), C["pyzx"]), ("BQSKit-FT DPF", pc("B3g_bqskit_dpf_gridsynth"), C["dpf"]),
          ("G1 (no LLM)", pc("G1_pass"), C["g1"]), ("G1 + LLM", pc("llm_arm_A"), C["llm"])]
fig, ax = plt.subplots(figsize=(W, H)); fig.subplots_adjust(left=0.115, right=0.995, top=0.88, bottom=0.31)
xs, bw = grouped(ax, order, series)
ax.axhline(0, color="#64748B", lw=0.8, zorder=4); ax.axvline(4.5, color="#94A3B8", lw=0.8, ls=":", zorder=1)
ax.set_ylim(-18, 58); ax.set_ylabel("T-count reduction\nvs TKET (%)")
ax.text(2.0, 52, "DEV (playbook learning on)", ha="center", fontsize=6.5, color="#334155")
ax.text(6.0, 52, "held-out (LLM not run)", ha="center", fontsize=6.5, color="#334155")
ax.legend(frameon=False, ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.0), handlelength=1.0, columnspacing=1.0, borderaxespad=0.2)
ax.set_yticks([-10, 0, 10, 20, 30, 40, 50])
save(fig, "bar_angle.png")

# ---------------- rules (vertical grouped bars)
rc_a, an_a = R["recon"], R["angle"]
fig, ax = plt.subplots(figsize=(3.5, 1.75))
labels = ["Reconstruction", "Angle"]
ser = [("written by reflector LLM", [rc_a["added"], an_a["added"]], "#CBD5E1"),
       ("promoted to active", [15, 0], C["llm"]), ("retired", [rc_a["retired"], an_a["retired"]], "#94A3B8")]
xs, bw = grouped(ax, labels, ser, bw=0.24)
ax.set_xticks(xs, labels, rotation=0, ha="center")
for i, (_, vals, _) in enumerate(ser):
    for j, v in enumerate(vals):
        ax.text(xs[j] + (i - 1) * bw, v + 1.5, str(v), ha="center", va="bottom", fontsize=7, fontweight="bold" if i == 1 else None)
        if v == 0: ax.plot([xs[j] + (i - 1) * bw] * 2, [0, 0.8], color=C["llm"], lw=2, zorder=4)
ax.set_ylim(0, 100); ax.set_ylabel("number of rules")
ax.legend(frameon=False, ncol=1, loc="upper right", handlelength=1.0, borderaxespad=0.1)
save(fig, "bar_rules.png")

# ---------------- cascade (zero-LLM demo)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(W, H), gridspec_kw=dict(width_ratios=[4.2, 1.4], wspace=0.3))
c1 = [("naive", 112, "#CBD5E1"), ("TKET", 96, C["tket"]), ("pyzx", 64, C["pyzx"]), ("angle\nonly", 96, C["g1"]),
      ("recon.\nonly", 32, C["plan"]), ("cascade", 32, "#7C2D12")]
c2 = [("angle\nonly", 162, C["g1"]), ("cascade", 130, "#7C2D12")]
for ax, cc, tl in ((a1, c1, "cuccaro_8"), (a2, c2, "cuccaro_4 + 5 rotations")):
    ax.bar(range(len(cc)), [c[1] for c in cc], color=[c[2] for c in cc], width=0.7, zorder=3)
    for i, c in enumerate(cc): ax.text(i, c[1] + max(x[1] for x in cc) * 0.02, str(c[1]), ha="center", va="bottom", fontsize=7, fontweight="bold" if c[0] == "cascade" else None)
    ax.set_xticks(range(len(cc)), [c[0] for c in cc], rotation=0, ha="center")
    ax.set_ylim(0, max(x[1] for x in cc) * 1.15); ax.grid(axis="y", color="#E5E7EB", lw=0.6, zorder=0)
    ax.set_title(tl, fontsize=7.5, loc="left")
fig.subplots_adjust(left=0.1, right=0.995, top=0.9, bottom=0.27); a1.set_ylabel("T-count")
save(fig, "bar_cascade.png")
print(sorted(p.name for p in OUTD.glob("*.png")))
