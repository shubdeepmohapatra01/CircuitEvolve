"""Simple grouped bar charts: Genesis vs ours (reads report/comparison.csv)."""
import csv
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib as mpl, matplotlib.pyplot as plt
R = Path(__file__).resolve().parent
rows = list(csv.DictReader(open(R / "report" / "comparison.csv")))
SH = {"kerr_small": "Kerr", "boseHubbard_small": "Bose-\nHubbard", "z2Higgs_small": "Z2-\nHiggs",
      "heisenberg_small": "Heisen-\nberg", "electronicVibration_small": "Electron-\nvibration"}
mpl.rcParams.update({"font.size": 9, "axes.titlesize": 10, "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 9,
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "savefig.dpi": 300})
C_G, C_O = "#9e9e9e", "#1f5fa8"
f = lambda v: float(v) if v not in ("", "None") else np.nan
x = np.arange(len(rows)) * 1.15; w = 0.46
panels = [("Number of gates", "genesis_total", "ours_total", lambda v: f"{v:.0f}"),
          ("Circuit duration", "genesis_duration", "ours_duration", lambda v: f"{v:.0f}"),
          ("Error (infidelity)", "genesis_max_infid", "ours_max_infid", lambda v: "~0" if v < 1e-3 else f"{v:.2f}")]
fig, axs = plt.subplots(1, 3, figsize=(13, 3.4), gridspec_kw=dict(wspace=0.28))
for ax, (title, gk, ok, fmt) in zip(axs, panels):
    g = np.array([f(r[gk]) for r in rows]); o = np.array([f(r[ok]) for r in rows])
    top = np.nanmax(np.concatenate([g, o]))
    for xs, vals, col, lab in ((x - w / 2, g, C_G, "Genesis"), (x + w / 2, o, C_O, "Ours (LLM rule book)")):
        ax.bar(xs, np.nan_to_num(vals), w, color=col, label=lab)
        for xi, v in zip(xs, vals):
            ax.text(xi, (0 if np.isnan(v) else v) + 0.015 * top, ("not\nfinished" if title.startswith("Error") else "pending") if np.isnan(v) else fmt(v),
                    ha="center", va="bottom", fontsize=6, rotation=0)
    ax.set_title(title, loc="left"); ax.set_xticks(x); ax.set_xticklabels([SH[r["benchmark"]] for r in rows])
    ax.set_ylim(0, top * 1.25); ax.tick_params(axis="x", length=0)
axs[2].set_ylim(0, 1.25)
axs[0].legend(loc="upper right")
fig.text(0.5, -0.04, "Lower is better in all panels. Error = how far the circuit is from the intended Trotter step "
         "(0 = exact, 1 = completely wrong); ours is below 1e-8 everywhere. Genesis Kerr error measured on its logical circuit.", ha="center", fontsize=8, color="#444444")
fig.savefig(R / "report" / "fig_bars.png", bbox_inches="tight")
rr = fig.canvas.get_renderer()
T = [t for t in fig.findobj(mpl.text.Text) if t.get_text().strip() and t.get_visible()]
B = [t.get_window_extent(rr) for t in T]
print("overlaps:", [(T[i].get_text(), T[j].get_text()) for i in range(len(B)) for j in range(i + 1, len(B)) if B[i].overlaps(B[j])])
