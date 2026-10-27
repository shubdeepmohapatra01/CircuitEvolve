"""P0 baseline-only figures (SPEC section 9 layout, no "ours" bars yet). Reads only v3/baselines/baselines.csv.

    .venv/bin/python -m v3.report.fig_baselines      -> v3/report/figures/p0_*.png + p0_*.csv (numbers per figure)

Colors are fixed per method across all figures (color follows the entity); "ours" (P2+) takes slot 5 (magenta),
hatched when relaxed.
"""
from __future__ import annotations

import csv

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ..paths import BASELINES_CSV, REPORT  # noqa: E402

OUT = REPORT / "figures"
COLOR = {"TKET": "#2a78d6", "pyzx": "#eb6834", "BQSKit-FT": "#1baf7a", "BQSKit-DPF": "#eda100",
         "Genesis": "#008300", "ours": "#e87ba4"}
DV_METHODS = ["TKET", "pyzx", "BQSKit-FT", "BQSKit-DPF"]
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3de"


def style(ax, ylabel, log=False):
    ax.set_ylabel(ylabel, color=INK)
    if log:
        ax.set_yscale("log")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED)


def grouped(ax, labels, methods, value, fmt="{:.0f}", log=False):
    w = 0.8 / len(methods)
    for j, m in enumerate(methods):
        xs, ys = [], []
        for i, lab in enumerate(labels):
            v = value(lab, m)
            if v is not None:
                xs.append(i - 0.4 + w * (j + 0.5))
                ys.append(v)
        bars = ax.bar(xs, ys, width=w * 0.92, color=COLOR[m], label=m, edgecolor="white", linewidth=1)
        for b, y in zip(bars, ys):
            ax.annotate(fmt.format(y), (b.get_x() + b.get_width() / 2, y), ha="center", va="bottom", fontsize=6,
                        color=MUTED, rotation=90, xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, color=INK)
    if log:
        ax.set_yscale("log")


def write_csv(name, header, rows):
    with open(OUT / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(BASELINES_CSV)))
    angle = [r for r in rows if r["family"] == "dv_angle"]
    recon = [r for r in rows if r["family"] == "dv_recon"]
    cv_all = [r for r in rows if r["family"] == "cvdv"]
    cv = [r for r in cv_all if r["level"] == "routed"]
    cv_log = [r for r in cv_all if r["level"] == "logical"]
    cv_err = [r for r in cv_all if r["err_trotter"] != ""]
    a_labels = list(dict.fromkeys(r["label"] for r in angle))
    r_labels = list(dict.fromkeys(r["label"] for r in recon))
    c_labels = [r["label"] for r in cv]

    def get(rs, lab, m, col, eps=None):
        h = [r for r in rs if r["label"] == lab and r["method"] == m and (eps is None or float(r["eps"]) == eps)]
        return float(h[0][col]) if h and h[0][col] != "" else None

    # 1. DV angle T-count, one panel per eps
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=False)
    out = []
    for ax, eps in zip(axes, (1e-3, 1e-5)):
        grouped(ax, a_labels, DV_METHODS, lambda l, m: get(angle, l, m, "t_count", eps), log=True)
        style(ax, "T-count (log)", log=True)
        ax.set_title(f"eps = {eps:g}", color=INK, fontsize=10)
        out += [[l, eps, m, get(angle, l, m, "t_count", eps)] for l in a_labels for m in DV_METHODS]
    for ax in axes:
        ax.set_ylim(top=ax.get_ylim()[1] * 1.6)
    fig.legend(*axes[0].get_legend_handles_labels(), frameon=False, fontsize=8, ncol=4, loc="upper center",
               bbox_to_anchor=(0.5, 0.93))
    fig.suptitle("DV angle circuits: T-count of the baselines (tfim_6 = control)", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(OUT / "p0_dv_angle_tcount.png", dpi=160)
    write_csv("p0_dv_angle_tcount", ["label", "eps", "method", "t_count"], out)

    # 2. DV reconstruction T-count
    fig, ax = plt.subplots(figsize=(8, 4))
    grouped(ax, r_labels, DV_METHODS, lambda l, m: get(recon, l, m, "t_count"))
    style(ax, "T-count")
    ax.set_ylim(top=ax.get_ylim()[1] * 1.15)
    fig.legend(*ax.get_legend_handles_labels(), frameon=False, fontsize=8, ncol=4, loc="upper center",
               bbox_to_anchor=(0.5, 0.92))
    fig.suptitle("DV reconstruction circuits: T-count of the baselines (exact)", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(OUT / "p0_dv_recon_tcount.png", dpi=160)
    write_csv("p0_dv_recon_tcount", ["label", "method", "t_count"],
              [[l, m, get(recon, l, m, "t_count")] for l in r_labels for m in DV_METHODS])

    # 3. Qubit count, both DV families
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw=dict(width_ratios=[1, 1]))
    for ax, rs, labs, t in ((axes[0], [r for r in angle if float(r["eps"]) == 1e-3], a_labels, "DV angle"),
                            (axes[1], recon, r_labels, "DV reconstruction")):
        grouped(ax, labs, DV_METHODS, lambda l, m, rs=rs: get(rs, l, m, "qubits"))
        style(ax, "qubits")
        ax.set_title(t, color=INK, fontsize=10)
    fig.legend(*axes[0].get_legend_handles_labels(), frameon=False, fontsize=8, ncol=4, loc="upper center",
               bbox_to_anchor=(0.5, 0.92))
    fig.suptitle("Qubit count (no baseline adds ancillas)", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(OUT / "p0_dv_qubits.png", dpi=160)
    write_csv("p0_dv_qubits", ["family", "label", "method", "qubits"],
              [["dv_angle", l, m, get(angle, l, m, "qubits", 1e-3)] for l in a_labels for m in DV_METHODS] +
              [["dv_recon", l, m, get(recon, l, m, "qubits")] for l in r_labels for m in DV_METHODS])

    # 4. CV-DV gate count: routed total, routed 2-op, logical total (incomplete where placeholders remain)
    short = [l.replace("_small", "") for l in c_labels]
    tick = {"boseHubbard": "boseHub.", "heisenberg": "heis.", "electronicVibration": "elVib"}
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.8))
    for ax, rs, col, t in ((axes[0], cv, "total", "routed: total gates"), (axes[1], cv, "two_op", "routed: 2-op gates"),
                           (axes[2], cv_log, "total", "logical (pre-routing): total gates")):
        grouped(ax, short, ["Genesis"], lambda l, m, rs=rs, col=col: get(rs, l + "_small", m, col))
        style(ax, "gates")
        ax.set_xticklabels([tick.get(x, x) for x in short], color=INK)
        ax.set_ylim(top=ax.get_ylim()[1] * 1.12)
        ax.set_title(t, color=INK, fontsize=10)
    for i, r in enumerate(cv_log):
        if r["complete"] == "False":
            axes[2].annotate(f"+{r['unsynthesized']} unsynth.\npauli", (i, float(r["total"])), ha="center",
                             va="bottom", fontsize=6, color=MUTED, xytext=(0, 26), textcoords="offset points")
    fig.suptitle("CV-DV: Genesis gate count (best of 5 seeds by routed total); ours will be compared per level",
                 color=INK)
    fig.tight_layout()
    fig.savefig(OUT / "p0_cvdv_gates.png", dpi=160)
    write_csv("p0_cvdv_gates", ["label", "method", "level", "total", "two_op", "one_op", "duration", "complete",
                                "unsynthesized", "best_seed"],
              [[r["label"], "Genesis", r["level"], r["total"], r["two_op"], r["one_op"], r["duration"], r["complete"],
                r["unsynthesized"], r["best_seed"]] for r in cv_all])

    # 5. CV-DV error: err_exact, err_trotter (log)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    for ax, col, t in ((axes[0], "err_exact", "err_exact (vs exp(-iHt))"),
                       (axes[1], "err_trotter", "err_trotter (vs ordered Trotter product)")):
        grouped(ax, short, ["Genesis"], lambda l, m, col=col: (lambda v: None if v is None else max(v, 1e-16))(
                    get(cv_err, l + "_small", m, col)),
                fmt="{:.2g}", log=True)
        style(ax, "process infidelity (log)", log=True)
        ax.set_xticklabels([tick.get(x, x) for x in short], color=INK)
        ax.set_title(t, color=INK, fontsize=10)
    notes = [f"{r['label'].replace('_small', '')}: {r['error_level']}, cutoffs agree={r['cutoffs_agree']}" for r in cv_err]
    fig.text(0.01, 0.005, "; ".join(notes), fontsize=6, color=MUTED)
    fig.suptitle("CV-DV: Genesis error (process infidelity on the probe subspace); z2Higgs / heisenberg / "
                 "electronicVibration skipped (user decision)", color=INK, fontsize=10)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "p0_cvdv_error.png", dpi=160)
    write_csv("p0_cvdv_error", ["label", "method", "err_exact", "err_trotter", "error_level", "cutoffs_agree"],
              [[r["label"], "Genesis", r["err_exact"], r["err_trotter"], r["error_level"], r["cutoffs_agree"]] for r in cv_err])
    print("figures in", OUT)


if __name__ == "__main__":
    main()
