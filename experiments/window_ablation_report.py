"""Table, paired statistics and figure for the playbook ablation (results/window_runs/ablation_v1/).

    build_table()  -> pandas DataFrame, one row per circuit x arm x seed (from _ablation_progress.jsonl + logs)
    paired_stats(df) -> dict: per-circuit and pooled paired differences (learned - none, learned - placebo,
                        placebo - none) in T-reduction percentage points, sign test and bootstrap 95 % CI
    make_figure(df, control) -> matplotlib Figure
Reduction vs B0 is 100 * (B0 - T) / B0 (positive = fewer T than TKET + gridsynth); B0 = stage-1 t_count_canon.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "window_runs" / "ablation_v1"
STAGE1_CSV = REPO / "results" / "window_runs" / "stage1" / "stage1_results.csv"
HELDOUT = ("qft_8", "qpe_8", "qae_13", "hhl_8")
ARMS = ("none", "learned", "placebo")


def b0_table() -> dict:
    with STAGE1_CSV.open() as f:
        return {r["circuit"]: int(r["B0"]) for r in csv.DictReader(f) if float(r["eps"]) == 1e-3}


def build_table():
    import pandas as pd
    b0 = b0_table()
    rows = []
    for line in (OUT / "_ablation_progress.jsonl").read_text().splitlines():
        r = json.loads(line)
        st = r["stats"]
        props = st["candidates"]
        fc = r["final_check"] or {}
        assert r["t_before"] == b0[r["name"]], (r["tag"], r["t_before"], b0[r["name"]])
        rows.append(dict(
            circuit=r["name"], arm=r["arm"], seed=r["seed"], tag=r["tag"], qubits=r["n"], B0=b0[r["name"]],
            T_final=r["t_after"], pct_vs_B0=round(100 * (r["t_after"] - b0[r["name"]]) / b0[r["name"]], 3),
            reduction_pct=round(100 * (b0[r["name"]] - r["t_after"]) / b0[r["name"]], 3),
            rz_before=r["rz"][0], rz_after=r["rz"][1], llm_calls=r["calls"], proposal_calls=st["proposal_calls"],
            reflect_calls=st["reflect_calls"], calls_to_best=r.get("calls_to_best"), proposals=props,
            fix_proposals=st["fix_proposals"], window_proposals=st["window_proposals"], declined=st["declined"],
            parse_errors=st["parse_errors"], rejected_verifier=st["rejected_verifier"],
            rejected_metric=st["rejected_metric"], rejected_ledger=st["rejected_ledger"],
            rejected_whole=st["rejected_whole"], accepted=st["accepted"],
            acceptance_rate=round(st["accepted"] / props, 4) if props else 0.0,
            llm_errors=st["llm_errors"], input_tokens=r["tokens"]["input"], output_tokens=r["tokens"]["output"],
            tokens=r["tokens"]["input"] + r["tokens"]["output"], error_bound=r["bound"],
            final_check_method=fc.get("method"), final_check_dist=fc.get("dist"), final_check_ok=fc.get("ok"),
            playbook_sha256=r.get("playbook_sha256") or "", model=r["model"], seconds=r["seconds"]))
    df = pd.DataFrame(rows)
    # valid = every LLM call returned (no backend error); a circuit x seed block enters the paired comparison only
    # if all three arms are valid there (matched LLM calls)
    df["valid"] = df["llm_errors"] == 0
    blk = df.groupby(["circuit", "seed"])["valid"].transform(lambda v: bool(v.all()) and len(v) == len(ARMS))
    df["in_paired"] = blk.astype(bool)
    df["arm"] = pd.Categorical(df["arm"], ARMS, ordered=True)
    df["circuit"] = pd.Categorical(df["circuit"], HELDOUT, ordered=True)
    return df.sort_values(["circuit", "arm", "seed"]).reset_index(drop=True)


def _sign_test(d) -> float:
    """Two-sided exact binomial sign test on nonzero differences."""
    d = [x for x in d if abs(x) > 1e-12]
    n = len(d)
    if n == 0:
        return 1.0
    k = sum(x > 0 for x in d)
    m = min(k, n - k)
    p = sum(math.comb(n, i) for i in range(0, m + 1)) / 2 ** n * 2
    return min(1.0, p)


def _boot(d, n_boot=20000, seed=0):
    d = np.asarray(d, float)
    rng = np.random.default_rng(seed)
    means = rng.choice(d, size=(n_boot, len(d)), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired_stats(df) -> dict:
    df = df[df.in_paired]
    piv = df.pivot_table(index=["circuit", "seed"], columns="arm", values="reduction_pct", observed=True)
    out = {}
    for a, b in (("learned", "none"), ("learned", "placebo"), ("placebo", "none")):
        d = (piv[a] - piv[b]).dropna()
        per = {c: dict(diffs=[round(x, 3) for x in d.xs(c, level="circuit").tolist()],
                       mean=round(float(d.xs(c, level="circuit").mean()), 3))
               for c in HELDOUT if c in d.index.get_level_values(0)}
        lo, hi = _boot(d.values)
        out[f"{a}-{b}"] = dict(n_pairs=int(len(d)), mean_pp=round(float(d.mean()), 3),
                               median_pp=round(float(d.median()), 3), positive=int((d > 1e-12).sum()),
                               negative=int((d < -1e-12).sum()), ties=int((d.abs() <= 1e-12).sum()),
                               sign_test_p=round(_sign_test(d.values), 4), boot95=(round(lo, 3), round(hi, 3)),
                               per_circuit=per)
    return out


def make_figure(df, control: dict):
    import matplotlib.pyplot as plt
    colors = {"none": "#8c8c8c", "placebo": "#c9a227", "learned": "#1f5fa8"}
    labels = {"none": "no playbook", "placebo": "placebo playbook", "learned": "learned playbook (dev_v1)"}
    ctrl = {r["name"]: 100 * (b0_table()[r["name"]] - r["t"]) / b0_table()[r["name"]] for r in control["rows"]}
    fig, (ax_top, ax) = plt.subplots(2, 1, sharex=True, figsize=(6.8, 4.2),
                                     gridspec_kw=dict(height_ratios=[1, 2.6], hspace=0.08))
    off = {"none": -0.24, "placebo": 0.0, "learned": 0.24}
    rng = np.random.default_rng(1)
    drawn_ex = False
    for i, c in enumerate(HELDOUT):
        for arm in ARMS:
            sel = df[(df.circuit == c) & (df.arm == arm)]
            v = sel[sel.in_paired]["reduction_pct"].to_numpy()
            x = i + off[arm]
            jit = rng.uniform(-0.045, 0.045, len(v))
            ax.scatter(x + jit, v, s=16, color=colors[arm], alpha=0.75, lw=0, zorder=3,
                       label=labels[arm] if i == 0 else None)
            ex = sel[sel.valid & ~sel.in_paired]["reduction_pct"].to_numpy()
            if len(ex):
                ax.scatter(np.full(len(ex), x), ex, s=16, facecolor="white", edgecolor=colors[arm], lw=0.9,
                           zorder=3, label="valid run, block incomplete (not in mean)" if not drawn_ex else None)
                drawn_ex = True
            if len(v):
                ax.hlines(v.mean(), x - 0.09, x + 0.09, color=colors[arm], lw=2.2, zorder=4)
        ax_top.scatter(i, ctrl[c], marker="D", s=26, color="black", zorder=3,
                       label="no-LLM same-Pauli merge rule" if i == 0 else None)
    lo = min(0.0, df.reduction_pct.min()) - 0.3
    hi = df.reduction_pct.max() + 1.9
    ax.set_ylim(lo, hi)
    cv = list(ctrl.values())
    ax_top.set_ylim(min(cv) - 1.5, max(cv) + 3.0)
    ax.axhline(0, color="black", lw=0.6, zorder=1)
    for a in (ax, ax_top):
        a.spines["top"].set_visible(False)
        a.spines["right"].set_visible(False)
    ax_top.spines["bottom"].set_visible(False)
    ax_top.tick_params(axis="x", length=0)
    d = 0.012
    for a, y in ((ax_top, 0), (ax, 1)):
        a.plot((-d, +d), (y - d * 3, y + d * 3), transform=a.transAxes, color="black", lw=0.8, clip_on=False)
    ax.set_xticks(range(len(HELDOUT)))
    ax.set_xticklabels(HELDOUT)
    ax.set_xlim(-0.55, len(HELDOUT) - 0.45)
    ax.set_ylabel("T reduction vs TKET + gridsynth (%)")
    ax.yaxis.set_label_coords(-0.075, 0.68)
    ax_top.set_title("Held-out circuits: playbook arms vs no-LLM merge rule (eps 1e-3)", loc="left")
    ax.legend(frameon=False, loc="upper left", ncol=1, handletextpad=0.3, borderaxespad=0.2)
    ax_top.legend(frameon=False, loc="upper right", handletextpad=0.3, borderaxespad=0.1)
    ax.text(1.0, -0.17, "higher = fewer T", transform=ax.transAxes, ha="right", va="top")
    return fig
