"""P2 report from whatever exists (safe to run at any time; reads results files only).

    .venv/bin/python -m v3.report.p2_report

Writes v3/report/figures/p2_dv_angle_tcount.png, p2_dv_recon_tcount.png, p2_dv_qubits.png (+ one CSV each) and
v3/results/p2/SUMMARY.md. eps = 1e-3. Bars per circuit: TKET, pyzx, BQSKit-FT, BQSKit-DPF, ours (= the LLM-built
book applied by the runner; hatched when any kept application used a relaxed contract). The hand-written P1
same-Pauli merge is a separate reference row in the summary, never a bar and never "ours".
"""
from __future__ import annotations

import csv
import json
import time
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ..paths import BASELINES_CSV, REPORT, RESULTS, RULES  # noqa: E402
from .fig_baselines import COLOR, INK, MUTED, style  # noqa: E402

EPS = 1e-3
SAMPLED_NOTE: dict = {}                    # filled in main(): ours rows, for the "sampled check, not a proof" labels
P2 = RESULTS / "p2"
OUT = REPORT / "figures"
METHODS = ["TKET", "pyzx", "BQSKit-FT", "BQSKit-DPF", "ours"]


def jl(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def load():
    base = [r for r in csv.DictReader(open(BASELINES_CSV)) if r["family"] in ("dv_angle", "dv_recon")]
    base = [r for r in base if r["family"] == "dv_recon" or float(r["eps"]) == EPS]
    ours = {}
    for r in jl(P2 / "ours.jsonl"):
        ours[r["label"]] = r                                    # latest row per circuit
    state = json.loads((P2 / "state.json").read_text()) if (P2 / "state.json").exists() else {}
    return base, ours, state


def value(base, ours, lab, m, col):
    if m == "ours":
        r = ours.get(lab)
        return (r[col], r["relaxed"]) if r else (None, False)
    h = [r for r in base if r["label"] == lab and r["method"] == m]
    return (float(h[0][col]), False) if h else (None, False)


def bars(ax, labels, base, ours, col, log=False, fmt="{:.0f}"):
    w = 0.8 / len(METHODS)
    rows = []
    for j, m in enumerate(METHODS):
        for i, lab in enumerate(labels):
            v, relaxed = value(base, ours, lab, m, col)
            rows.append([lab, m, v, relaxed])
            if v is None:
                continue
            x = i - 0.4 + w * (j + 0.5)
            ax.bar(x, v, width=w * 0.92, color=COLOR[m], edgecolor="white" if not relaxed else INK,
                   hatch="///" if relaxed else None, linewidth=1 if not relaxed else 0.6,
                   label=m if i == 0 or not any(r[1] == m and r[2] is not None for r in rows[:-1]) else None)
            ax.annotate(fmt.format(v), (x, v), ha="center", va="bottom", fontsize=5.5, color=MUTED, rotation=90,
                        xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(range(len(labels)))
    if log:
        ax.set_yscale("log")
    return rows



def run_state(state):
    """Derived from the plan, not the stale 'finished' stamp of an earlier resume."""
    if state.get("stopped"):
        return "stopped - " + state["stopped"]
    plan = state.get("plan", [])
    if plan and all(state.get("done", {}).get(l, 0) >= b for l, b in plan):
        return "finished"
    return "running (P2 not finished)"


def circuit_status(state, lab):
    used = state.get("done", {}).get(lab, 0)
    budget = dict(state.get("plan", [])).get(lab, 0)
    if state.get("status", {}).get(lab) == "running":
        return f"running (attempt {used + 1})"
    if budget and used >= budget:
        return "done"
    return "partial" if used else "not run"

def ticklabels(ax, labels, state):
    """Benchmark names only; certified / sampled status and 'not run' are in SUMMARY.md."""
    names = list(labels)
    ax.set_xticklabels(names, color=INK, fontsize=7.5)


def legend(fig, ax):
    h, l = ax.get_legend_handles_labels()
    seen = {}
    for hh, ll in zip(h, l):
        seen.setdefault(ll, hh)
    fig.legend([seen[m] for m in METHODS if m in seen], [m for m in METHODS if m in seen], frameon=False,
               fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, 0.92))


def figures(base, ours, state):
    OUT.mkdir(parents=True, exist_ok=True)
    angle = list(dict.fromkeys(r["label"] for r in base if r["family"] == "dv_angle"))
    recon = list(dict.fromkeys(r["label"] for r in base if r["family"] == "dv_recon"))

    fig, ax = plt.subplots(figsize=(9, 4.4))
    rows = bars(ax, angle, base, ours, "t_count", log=True)
    style(ax, "T-count (log)", log=True)
    ax.set_ylim(top=ax.get_ylim()[1] * 1.8)
    ticklabels(ax, angle, state)
    legend(fig, ax)
    fig.suptitle(f"Angle circuits: T-count (eps = {EPS:g})", color=INK)
    fig.tight_layout(rect=(0, 0.03, 1, 0.86))
    fig.savefig(OUT / "p2_dv_angle_tcount.png", dpi=160)
    plt.close(fig)
    write_csv("p2_dv_angle_tcount", ["label", "method", "t_count", "relaxed"], rows)

    fig, ax = plt.subplots(figsize=(9, 4.4))
    rows = bars(ax, recon, base, ours, "t_count")
    style(ax, "T-count")
    ax.set_ylim(top=ax.get_ylim()[1] * 1.15)
    ticklabels(ax, recon, state)
    legend(fig, ax)
    fig.suptitle("Reconstruction circuits: T-count", color=INK)
    fig.tight_layout(rect=(0, 0.03, 1, 0.86))
    fig.savefig(OUT / "p2_dv_recon_tcount.png", dpi=160)
    plt.close(fig)
    write_csv("p2_dv_recon_tcount", ["label", "method", "t_count", "relaxed"], rows)

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2))
    rows = []
    for ax, labs, t in ((axes[0], angle, "Angle circuits"), (axes[1], recon, "Reconstruction circuits")):
        rows += [[t] + r for r in bars(ax, labs, base, ours, "qubits")]
        style(ax, "qubits")
        ax.set_ylim(top=ax.get_ylim()[1] * 1.15)
        ticklabels(ax, labs, state)
        ax.set_title(t, color=INK, fontsize=10)
    legend(fig, axes[1])
    fig.suptitle("Qubit count", color=INK)
    fig.tight_layout(rect=(0, 0.03, 1, 0.86))
    fig.savefig(OUT / "p2_dv_qubits.png", dpi=160)
    plt.close(fig)
    write_csv("p2_dv_qubits", ["family", "label", "method", "qubits", "relaxed"], rows)
    return angle, recon


def write_csv(name, header, rows):
    with open(OUT / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def summary(base, ours, state, angle, recon):
    raw = jl(P2 / "attempts.jsonl")
    voided = {(n["label"], n["attempt"]) for n in raw if n.get("type") == "annotation" and n.get("voided")}
    attempts = [a for a in raw if a.get("type") != "annotation" and
                not ((a["label"], a["attempt"]) in voided and a.get("decision") == "harness_error")]
    for a in attempts:                                           # annotations override estimate / measured / limitation
        for n in raw:
            if n.get("type") == "annotation" and n["label"] == a["label"] and n["attempt"] == a["attempt"]:
                a.update({k: n[k] for k in ("estimate", "measured", "limitation") if k in n})
    tokens = jl(P2 / "tokens.jsonl")
    events = jl(RESULTS / "events.jsonl")
    per_attempt = defaultdict(lambda: dict(cost=0.0, inp=0, out=0, cache_read=0, cache_create=0, calls=0))
    for t in tokens:
        a = per_attempt[(t["label"], t["attempt"])]
        a["cost"] += t.get("cost_usd") or 0.0
        a["inp"] += t.get("input_tokens") or 0
        a["out"] += t.get("output_tokens") or 0
        a["cache_read"] += t.get("cache_read_tokens") or 0
        a["cache_create"] += t.get("cache_creation_tokens") or 0
        a["calls"] += 1
    from ..tools.evaluate import load_rule
    accepted = {}
    for p in sorted((RULES / "accepted").glob("*.py")):
        try:
            accepted[p.stem] = load_rule(p)
        except Exception:  # noqa: BLE001
            pass
    adm = {}
    for e in events:
        if e.get("event") == "admission" and e.get("decision") == "admit":
            adm[e["rule"]["name"]] = e
    L = [f"# P2 summary (DV only, eps = {EPS:g}) - generated {time.strftime('%Y-%m-%d %H:%M')}", ""]
    st = state.get("status", {})
    stopped = state.get("stopped")
    n_att = len(attempts)
    total_cost = sum(t.get("cost_usd") or 0.0 for t in tokens)
    L += [f"Attempts recorded: {n_att}; LLM calls: {len(tokens)}; total LLM cost: ${total_cost:.2f}. "
          f"Run state: {run_state(state)}.", ""]
    L += ["## Rules admitted (LLM-found; hand-written P1 rules excluded)", "",
          "| rule | kind | contract | helped (circuit: before -> after T) | attempt | target: est. vs measured T saved | limitation | LLM calls | tokens in / out (cache read) | cost |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    if not accepted:
        L.append("| (none yet) | | | | | | | | | |")
    for name, r in accepted.items():
        e = adm.get(name, {})
        helped = "; ".join(f"{h['label']}: {h['before']} -> {h['after']}" for h in e.get("helped", []))
        at = next((a for a in attempts if a.get("admitted") == name), None)
        tk = per_attempt.get((at["label"], at["attempt"])) if at else None
        est = ((at or {}).get("estimate") or {}).get("t_saving")
        mes = ((at or {}).get("measured") or {}).get("t_saving")
        L.append(f"| {name} | {r.kind} | {r.contract} | {helped} | {at['label'] + ' a' + str(at['attempt']) if at else '?'} | "
                 f"{est if est is not None else '?'} vs {mes if mes is not None else '?'} | {(at or {}).get('limitation') or '-'} | "
                 f"{tk['calls'] if tk else '?'} | {tk['inp'] if tk else '?'} / {tk['out'] if tk else '?'} "
                 f"({tk['cache_read'] if tk else '?'}) | {'$%.2f' % tk['cost'] if tk else '?'} |")
    L += ["", "## Per circuit: ours vs best baseline", "",
          "| circuit | P2 status | attempts used / budget | admitted here | best baseline | ours T | vs best | ours qubits | relaxed | certified |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for lab in angle + recon:
        bl = [(r["method"], int(r["t_count"])) for r in base if r["label"] == lab]
        bm, bv = min(bl, key=lambda x: x[1])
        o = ours.get(lab)
        att = [a for a in attempts if a["label"] == lab]
        here = [a["admitted"] + ("" if a["admitted"] in accepted else " (retired)") for a in att if a.get("admitted")]
        budget = dict(state.get("plan", [])).get(lab, "?")
        used = state.get("done", {}).get(lab, len(att))
        ub = f"{used} / {budget}" if used or st.get(lab) == "running" else "not run"
        if o:
            d = 100.0 * (o["t_count"] - bv) / bv
            L.append(f"| {lab} | {circuit_status(state, lab)} | {ub} | {', '.join(here) or '-'} | {bm} {bv} | "
                     f"{o['t_count']} | {d:+.1f}% | {o['qubits']} | {'yes' if o['relaxed'] else 'no'} | "
                     f"{'n/a (nothing applied)' if not o['applications'] else ('yes' if o['certified'] else 'no: sampled check, not a proof')} |")
        else:
            L.append(f"| {lab} | {circuit_status(state, lab)} | {ub} | - | {bm} {bv} | n/a | | | | |")
    not_run = [l for l in angle + recon if state.get("done", {}).get(l, 0) == 0 and st.get(l) != "running"]
    L += ["", f"**Not run** (zero P2 attempts): {', '.join(not_run) or 'none'}.", ""]
    ref = list(csv.DictReader(open(RESULTS / "p1" / "handwritten_reference.csv"))) \
        if (RESULTS / "p1" / "handwritten_reference.csv").exists() else []
    ref = [r for r in ref if float(r["eps"]) == EPS and r["fired"] == "True"]
    L += ["## Reference row (NOT ours): hand-written P1 same-Pauli merge, eps 1e-3", "",
          "| circuit | before -> after T | applications |", "|---|---|---|"]
    L += [f"| {r['label']} | {r['t_before']} -> {r['t_after']} | {r['applications']} |" for r in ref]
    retired = sorted((RULES / "retired").glob("*.reason.json"))
    L += ["", "## Retired (superseded)", ""]
    L += [f"- {json.loads(p.read_text())['rule']} replaced by {json.loads(p.read_text())['replaced_by']}"
          for p in retired] or ["- none"]
    dec = defaultdict(int)
    for a in attempts:
        dec[a.get("decision")] += 1
    L += ["", "## Attempt outcomes", "", ", ".join(f"{k}: {v}" for k, v in sorted(dec.items(), key=str)) or "none", "",
          "## Caveats", "",
          "- eps 1e-3 only; DV only (CV-DV deferred). Baselines from v3/baselines/baselines.csv (frozen).",
          "- Verification: every rule application checked exactly on its changed window (Clifford+T: D[omega]; "
          "continuous angles: dense operator norm), plus one whole-circuit check per rule pass against the original. "
          "Checks are sampled, not proofs (column 'certified') when: the circuit has more than 2^14 basis inputs "
          "(mcx_10, adder_8); a numerical check is on 11-20 qubits (qae_13); or a relaxed (measurement) result has "
          "more measurement branches than are enumerated (method 'branchwise-exhaustive+sampled-branches': every "
          "basis input, sampled branches; adder_6, mult_4, modred_21).",
          "- Admission: full DV suite at eps 1e-3, 300 s per circuit.",
          "- BQSKit-FT / BQSKit-DPF on reconstruction start from the Nam Clifford+T files (they leave ccx "
          "undecomposed) and return the input T-count unchanged.",
          "- Relaxed results (clean ancillas / measurement) are hatched in the figures and never counted as "
          "unitary-preserving.",
          "", "Figures: report/figures/p2_dv_angle_tcount.png, p2_dv_recon_tcount.png, p2_dv_qubits.png (+ CSVs)."]
    (P2 / "SUMMARY.md").write_text("\n".join(L) + "\n")


def main():
    P2.mkdir(parents=True, exist_ok=True)
    base, ours, state = load()
    SAMPLED_NOTE["ours"] = ours
    angle, recon = figures(base, ours, state)
    summary(base, ours, state, angle, recon)
    print("wrote", P2 / "SUMMARY.md")


if __name__ == "__main__":
    main()
