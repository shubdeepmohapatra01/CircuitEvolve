"""Figures for the Genesis-vs-ours comparison (reads report/comparison.csv)."""
import csv, sys
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parent
rows = list(csv.DictReader(open(ROOT / "report" / "comparison.csv")))
SHORT = {"kerr_small": "Kerr", "boseHubbard_small": "Bose-Hubbard", "z2Higgs_small": "Z2-Higgs",
         "heisenberg_small": "Heisenberg", "electronicVibration_small": "Electron-vibration"}
mpl.rcParams.update({"font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7,
                     "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "xtick.direction": "out", "ytick.direction": "out",
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
                     "savefig.dpi": 300, "font.family": "DejaVu Sans"})
C_G, C_O = "#8c8c8c", "#1f5fa8"   # Genesis (comparator, grey) / ours (focal, blue)
lab = [SHORT[r["benchmark"]] for r in rows]
y = np.arange(len(rows))[::-1]
f = lambda v: float(v) if v not in ("", "None", None) else np.nan

def dumbbell(ax, g, o, xlabel, title):
    for yi, a, b in zip(y, g, o):
        if np.isfinite(a) and np.isfinite(b):
            ax.plot([a, b], [yi, yi], color="#c8c8c8", lw=1.2, zorder=1)
    ax.scatter(g, y, s=28, color=C_G, zorder=2, label="Genesis (ISCA'25)")
    ax.scatter(o, y, s=34, color=C_O, zorder=3, label="LLM rule book (ours)")
    ax.set_xscale("log"); ax.set_yticks(y); ax.set_yticklabels(lab)
    ax.set_xlabel(xlabel); ax.set_title(title, loc="left"); ax.margins(x=0.15, y=0.08)

fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.4), sharey=True, gridspec_kw=dict(wspace=0.3))
dumbbell(axs[0], [f(r["genesis_total"]) for r in rows], [f(r["ours_total"]) for r in rows], "total gates (routed)", "Gate count")
dumbbell(axs[1], [f(r["genesis_duration"]) for r in rows], [f(r["ours_duration"]) for r in rows],
         "duration (1 per 1-op, 20 per 2-op gate)", "Circuit duration")
axs[1].tick_params(labelleft=False)
axs[0].legend(loc="lower left", bbox_to_anchor=(0.0, 1.08), ncol=2, handletextpad=0.2, borderaxespad=0)
fig.text(0.99, 1.0, "lower = better", ha="right", va="bottom", fontsize=6.5, color="#555555")
fig.savefig(ROOT / "report" / "fig_gates_duration.png", bbox_inches="tight")

fig2, ax = plt.subplots(figsize=(4.2, 2.4))
gi = np.array([f(r["genesis_max_infid"]) for r in rows]); oi = np.array([f(r["ours_max_infid"]) for r in rows])
floor = 1e-16
dumbbell(ax, np.maximum(gi, floor), np.maximum(oi, floor), "max probe infidelity vs Trotter step", "Correctness of the compiled step")
ax.axvline(1e-3, color="#b03030", lw=0.8, ls="--", zorder=0)
ax.text(1.3e-3, y.min() + 0.5, "error budget 1e-3", color="#b03030", fontsize=6.5, va="center", ha="left")
for yi, r, gv in zip(y, rows, gi):
    if "logical" in r["genesis_err_note"]:
        ax.annotate("*", (gv, yi), xytext=(5, 2), textcoords="offset points", ha="left", va="bottom", fontsize=7, color=C_G)
ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.1), ncol=2, handletextpad=0.2, borderaxespad=0)
ax.set_xlim(3e-17, 8)
fig2.savefig(ROOT / "report" / "fig_error.png", bbox_inches="tight")
for fg in (fig, fig2):
    r_ = fg.canvas.get_renderer()
    texts = [t for t in fg.findobj(mpl.text.Text) if t.get_text().strip() and t.get_visible()]
    bb = [t.get_window_extent(r_) for t in texts]
    ov = [(texts[i].get_text(), texts[j].get_text()) for i in range(len(bb)) for j in range(i + 1, len(bb)) if bb[i].overlaps(bb[j])]
    print("overlaps:", ov)
