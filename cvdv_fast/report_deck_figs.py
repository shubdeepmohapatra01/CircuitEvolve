import csv, json
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib as mpl, matplotlib.pyplot as plt
R = Path(__file__).resolve().parent
rows = list(csv.DictReader(open(R / "report" / "comparison.csv")))
SH = {"kerr_small": "Kerr", "boseHubbard_small": "Bose-Hubbard", "z2Higgs_small": "Z2-Higgs",
      "heisenberg_small": "Heisenberg", "electronicVibration_small": "Electron-vib."}
mpl.rcParams.update({"font.size": 11, "axes.titlesize": 12, "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 10,
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "savefig.dpi": 300})
C_G, C_O = "#9e9e9e", "#1f5fa8"
f = lambda v: float(v) if v not in ("", "None") else np.nan
x = np.arange(len(rows)); w = 0.4
def bars(gk, ok, title, ylabel, fmt, fname, ylim=None, nan_text="not finished"):
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    g = np.array([f(r[gk]) for r in rows]); o = np.array([f(r[ok]) for r in rows])
    top = ylim or np.nanmax(np.concatenate([g, o])) * 1.15
    for xs, vals, col, lab in ((x - w/2, g, C_G, "Genesis"), (x + w/2, o, C_O, "Ours")):
        ax.bar(xs, np.nan_to_num(vals), w, color=col, label=lab)
        for xi, v in zip(xs, vals):
            ax.text(xi, (0 if np.isnan(v) else v) + 0.012 * top, nan_text if np.isnan(v) else fmt(v), ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(x); ax.set_xticklabels([SH[r["benchmark"]] for r in rows]); ax.tick_params(axis="x", length=0)
    ax.set_ylim(0, top); ax.set_title(title, loc="left"); ax.set_ylabel(ylabel); ax.legend(loc="upper left")
    fig.savefig(R / "report" / fname, bbox_inches="tight"); plt.close(fig)
bars("genesis_total", "ours_total", "Number of gates (lower is better)", "gates", lambda v: f"{v:.0f}", "deck_gates.png")
bars("genesis_max_infid", "ours_max_infid", "Error vs the intended Trotter step (lower is better)", "infidelity",
     lambda v: "~0" if v < 1e-3 else f"{v:.2f}", "deck_error_step.png", ylim=1.2)
print("ok")
