import csv
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib as mpl, matplotlib.pyplot as plt
R = Path(__file__).resolve().parent
rows = list(csv.DictReader(open(R / "report" / "comparison.csv")))
SH = {"kerr_small": "Kerr", "boseHubbard_small": "Bose-Hubbard", "z2Higgs_small": "Z2-Higgs",
      "heisenberg_small": "Heisenberg", "electronicVibration_small": "Electron-vib."}
mpl.rcParams.update({"font.size": 11, "axes.titlesize": 12, "xtick.labelsize": 10, "ytick.labelsize": 10,
                     "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 300})
fig, ax = plt.subplots(figsize=(7.5, 3.6))
x = np.arange(len(rows))
for xi, r in zip(x, rows):
    v = r["ours_max_infid"]
    if v in ("", "None"):
        ax.text(xi, 3e-15, "check not\nfinished", ha="center", va="bottom", fontsize=8.5, color="#666666")
        continue
    v = float(v)
    ax.plot([xi, xi], [1e-17, v], color="#1f5fa8", lw=1.5, alpha=0.5)
    ax.scatter([xi], [v], s=60, color="#1f5fa8", zorder=3)
    m, e = f"{v:.1e}".split("e")
    ax.text(xi + 0.12, v, f"{m}e{int(e)}", va="center", fontsize=9)
ax.axhline(1e-3, color="#b03030", lw=1, ls="--")
ax.text(len(rows) - 0.55, 1.6e-3, "allowed error 1e-3", color="#b03030", fontsize=9, ha="right", va="bottom")
ax.set_yscale("log"); ax.set_ylim(1e-16, 1e-1)
ax.set_xticks(x); ax.set_xticklabels([SH[r["benchmark"]] for r in rows]); ax.tick_params(axis="x", length=0)
ax.set_xlim(-0.5, len(rows) - 0.3)
ax.set_title("Error of our circuits vs the intended Trotter step (lower is better)", loc="left")
ax.set_ylabel("infidelity")
fig.savefig(R / "report" / "deck_error_ours.png", bbox_inches="tight")
print("ok")
