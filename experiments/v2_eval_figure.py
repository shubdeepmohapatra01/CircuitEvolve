"""Figure for the v2 held-out evaluation: per circuit, T-count relative to the best classical unitary-preserving
T of OUR runs (pyzx full_reduce / TKET FullPeepholeOptimise / Nam et al. Light file), for
  (a) best classical (= 1 by definition, reference line), (b) frozen tier-1 control, exact (unitary-preserving),
  (c) frozen tier-1 control, relaxed (clean ancillas + measurement), (d) best published value (not run by us).
Relaxed qubit / measurement overhead is printed in a right-hand column. Reads results/v2/eval/eval_results.csv.

    from experiments.v2_eval_figure import make_figure; fig = make_figure(csv_path); fig.savefig(...)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

FAMILY_ORDER = ["mcx_toffoli", "adder", "comparator", "gf2_mult", "modular", "hamming", "hidden_weighted_bit",
                "grover_oracle"]
FAMILY_LABEL = {"mcx_toffoli": "multi-controlled X", "adder": "adders", "gf2_mult": "GF(2^n) multipliers",
                "modular": "modular arithmetic", "hamming": "Hamming coding", "hidden_weighted_bit": "hidden weighted bit",
                "grover_oracle": "Grover oracle", "comparator": "comparator"}
C_EXACT = "#5b7fa6"      # tier-1 exact
C_RELAX = "#d1651c"      # tier-1 relaxed (focal)
C_PUB = "#555555"        # published


def make_figure(csv_path, fig=None):
    df = pd.read_csv(csv_path)
    ok = df["ok"].fillna(False).astype(bool)
    get = lambda c, arm, mode="exact": df[(df.circuit == c) & (df.arm == arm) & (df["mode"] == mode) & ok]  # noqa
    circs = df[(df.arm == "best_classical_ours") & ok][["circuit", "family", "n"]].drop_duplicates()
    circs["fo"] = circs["family"].map(lambda f: FAMILY_ORDER.index(f) if f in FAMILY_ORDER else 99)
    circs = circs.sort_values(["fo", "n", "circuit"]).reset_index(drop=True)
    N = len(circs)
    if fig is None:
        fig = plt.figure(figsize=(7.0, 0.30 * N + 1.5))
    ax = fig.add_axes([0.20, 0.10, 0.56, 0.80])
    ys = list(range(N))[::-1]
    n_rel_lt = 0
    for y, (_, r) in zip(ys, circs.iterrows()):
        c = r["circuit"]
        bo = float(get(c, "best_classical_ours")["t_count"].iloc[0])
        ex, rl, pb = get(c, "tier1_control", "exact"), get(c, "tier1_control", "relaxed"), get(c, "best_published")
        xs = []
        if len(ex):
            xe = ex["t_count"].iloc[0] / bo
            ax.scatter([xe], [y], s=34, facecolors="white", edgecolors=C_EXACT, linewidths=1.3, zorder=3)
            xs.append(xe)
            if xe > 1.3:
                ax.annotate("pyzx-pass plans (T = best classical)\nnot verified within 240 s", (xe, y),
                            xytext=(-6, 0), textcoords="offset points", ha="right", va="center", fontsize=6.5,
                            color=C_EXACT)
        if len(pb):
            xp = pb["t_count"].iloc[0] / bo
            ax.scatter([xp], [y], s=30, marker="s", facecolors="none", edgecolors=C_PUB, linewidths=1.0, zorder=2)
            xs.append(xp)
        if len(rl):
            xr = rl["t_count"].iloc[0] / bo
            n_rel_lt += xr < 1
            ax.scatter([xr], [y], s=44, marker="D", color=C_RELAX, zorder=4, edgecolors="white", linewidths=0.5)
            xs.append(xr)
            ax.text(1.02, y, f"+{int(rl['ancillas'].iloc[0])} q, {int(rl['measurements'].iloc[0])} meas",
                    transform=ax.get_yaxis_transform(), va="center", ha="left", fontsize=6.5, color=C_RELAX)
        if xs:
            ax.plot([min(xs + [1]), max(xs + [1])], [y, y], color="#dddddd", lw=0.8, zorder=1)
    ax.axvline(1.0, color="black", lw=0.9, zorder=1)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{c} ({int(n)} q)" for c, n in zip(circs.circuit, circs.n)])
    # family separators
    prev = None
    for y, f in zip(ys, circs.family):
        if prev is not None and f != prev:
            ax.axhline(y + 0.5, color="#bbbbbb", lw=0.5, ls=":")
        prev = f
    ax.set_xlabel("T-count / best classical T (our verified pyzx, TKET, Nam Light runs)")
    ax.set_ylim(-0.7, N - 0.3)
    xmax = max(1.1, ax.get_xlim()[1])
    ax.set_xlim(0.4, xmax + 0.03)
    ax.text(0.0, 1.01, "\u2190 fewer T", transform=ax.transAxes, ha="left", va="bottom", fontsize=6.5)
    ax.text(1.02, 1.01, "relaxed overhead", transform=ax.transAxes, ha="left", va="bottom", fontsize=6.5,
            color=C_RELAX)
    h = [plt.Line2D([], [], ls="", marker="o", mfc="white", mec=C_EXACT, mew=1.3, ms=6,
                    label="tier-1 control, exact (unitary-preserving)"),
         plt.Line2D([], [], ls="", marker="D", color=C_RELAX, ms=6,
                    label="tier-1 control, relaxed (ancillas + measurement)"),
         plt.Line2D([], [], ls="", marker="s", mfc="none", mec=C_PUB, ms=5.5,
                    label="best published (KvdW 2020 / Nam 2018; not our run)"),
         plt.Line2D([], [], color="black", lw=0.9, label="best classical, our runs = 1")]
    ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.45, -0.075), ncol=2, frameon=False, fontsize=6.5)
    ax.set_title(f"Measurement-based constructions lower T below best classical on {n_rel_lt} of {N} held-out "
                 f"circuits", loc="left", fontsize=8, pad=13)
    return fig, ax, dict(n=N, n_rel_lt=int(n_rel_lt))


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    f, _, info = make_figure(root / "results/v2/eval/eval_results.csv")
    f.savefig(root / "results/v2/eval/eval_figure.png", dpi=300, bbox_inches="tight")
    print(info)
