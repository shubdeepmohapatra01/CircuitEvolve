"""Build results/v2/eval/eval_results.csv and EVAL_REPORT.md from results/v2/eval/per_circuit/<tag>_*.json
(written by experiments/v2_eval_heldout.py) plus the DEV CSVs of both tiers. No computation of new numbers except
ratios / counts of the values read from those files.

    .venv/bin/python experiments/v2_eval_report.py [--tag eval_v1]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "v2" / "eval"
SPLIT = json.loads((ROOT / "benchmarks/nam_arith/split_v2.json").read_text())
HELDOUT = list(SPLIT["heldout"])
FAMILY_ORDER = ["mcx_toffoli", "adder", "comparator", "gf2_mult", "modular", "hamming", "hidden_weighted_bit",
                "grover_oracle", "shor"]


def _f(x):
    return None if x is None or (isinstance(x, float) and pd.isna(x)) else x


def _i(x):
    x = _f(x)
    return "-" if x is None else f"{int(x)}"


def load(tag):
    recs = {}
    for c in HELDOUT:
        p = OUT / "per_circuit" / f"{tag}_{c}.json"
        if p.exists():
            recs[c] = json.loads(p.read_text())
    return recs


def rows_from(recs) -> list:
    rows = []
    for c in HELDOUT:
        r = recs.get(c)
        if r is None:
            rows.append(dict(circuit=c, arm="missing", ok=False, notes="no per-circuit result (run not finished)"))
            continue
        if r.get("skipped"):
            rows.append(dict(circuit=c, arm="skipped", ok=False, notes=r["skipped"]))
            continue
        if r.get("error"):
            note = r["error"]
            if (r.get("normalization") or {}).get("method") == "infeasible":
                note = ("BLOCKED (verifier coverage, not a refutation): the recognizer's ccx-normalized logical "
                        "circuit keeps unfused h/ccz gates, so the reference is not permutation-like and n > 14 makes "
                        "the frozen exact check infeasible; tier-1 outputs could not be verified, circuit stopped. "
                        "Raw: " + r["normalization"]["reason"])
            rows.append(dict(circuit=c, arm="blocked", ok=False, notes=note))
            continue
        b = r["bars"]
        base = dict(circuit=c, family=r["family"], n=r["n"], ccx=r["ccx"],
                    best_classical_ours_T=b["best_ours_T"], best_classical_ours_arm=b["best_ours_arm"],
                    best_published_T=b["best_pub_T"], best_published_arm=b["best_pub_arm"],
                    best_classical_fn_T=(b["best_classical_fn"] or {}).get("t"),
                    best_classical_fn_arm=(b["best_classical_fn"] or {}).get("arm"),
                    pyzx_fr_T=b["ours"].get("pyzx_fr"), tket_fpo_T=b["ours"].get("tket_fpo"),
                    tket_fpo_logical_T=b["ours"].get("tket_fpo_logical"),
                    nam_light_T=b["ours"].get("nam_light_file"))
        rows.append(dict(base, arm="best_classical_ours", mode="exact", ok=b["best_ours_T"] is not None,
                         t_count=b["best_ours_T"], qubits=r["n"], ancillas=0, measurements=0,
                         unitary_preserving=True, source="our run (results/v2/baselines_new.csv, verified=True)",
                         method=b["best_ours_arm"]))
        rows.append(dict(base, arm="best_published", mode="exact", ok=b["best_pub_T"] is not None,
                         t_count=b["best_pub_T"], unitary_preserving=True,
                         source="published table value (not run by us)", method=b["best_pub_arm"]))
        for a in r["arms"]:
            rs = a.get("reseed")
            reseed_ok = None if not rs else all(v["ok"] for v in rs.values())
            d = dict(base, **{k: a.get(k) for k in (
                "arm", "mode", "ok", "t_count", "t_depth", "qubits", "ancillas", "measurements", "cx", "gates",
                "verdict_mode", "certified", "method", "unitary_preserving", "zero_qubits", "variant", "global_pass",
                "routes", "found_at_eval", "runtime_s", "eval_seconds", "verify_seconds", "applications",
                "t_before", "gates_before", "t_after", "gates_after", "library_sha256", "notes", "reason")})
            d["reseed_seeds"] = None if not rs else ",".join(rs)
            d["reseed_all_ok"] = reseed_ok
            d["reseed_status"] = reseed_status(a)
            d["check"] = check_label(a)
            d["source"] = "this evaluation (frozen tier-1 control / frozen tier-2 library)"
            rows.append(d)
    df = pd.DataFrame(rows)
    ok = df["ok"].fillna(False).astype(bool) & df["t_count"].notna() & df["best_classical_ours_T"].notna()
    df.loc[ok, "delta_vs_classical"] = df.loc[ok, "t_count"] - df.loc[ok, "best_classical_ours_T"]
    df.loc[ok, "ratio_vs_classical"] = (df.loc[ok, "t_count"] / df.loc[ok, "best_classical_ours_T"]).round(4)
    df.insert(0, "tag", recs[next(iter(recs))]["tag"] if recs else "")
    return df


def reseed_status(a: dict) -> str | None:
    """'ok' (all further seeds pass), 'inconclusive' (some seed hit the verifier time limit, none refuted),
    'FAILED' (a seed refuted equivalence), None (no reseed: certified or not verified)."""
    rs = a.get("reseed")
    if not rs:
        return None
    if all(v["ok"] for v in rs.values()):
        return "ok"
    if all(v["ok"] or str(v.get("reason", "")).startswith("time limit") for v in rs.values()):
        return "inconclusive"
    return "FAILED"


def check_label(a: dict) -> str:
    if not a.get("ok"):
        r = str(a.get("reason") or a.get("notes") or "")
        return "not verified (time limit)" if r.startswith("time limit") else "-"
    lab = "cert" if a.get("certified") else "samp"
    st = reseed_status(a)
    if st == "ok":
        lab += ", +2 seeds ok"
    elif st == "inconclusive":
        lab += ", +2 seeds: time limit on " + ",".join(k for k, v in a["reseed"].items() if not v["ok"])
    elif st == "FAILED":
        lab += ", RESEED REFUTED"
    return lab


def dev_tables() -> str:
    t1 = pd.read_csv(ROOT / "results/v2/tier1/dev_results.csv")
    t1 = t1[t1["arm"].isin(["llm", "control", "best_classical"])]
    out = ["### Tier 1 (DEV, run `dev_v1`; `results/v2/tier1/dev_results.csv`)", "",
           "| mode | circuits | LLM < control | LLM = control | LLM > control | LLM no valid plan | "
           "control < best classical | control = | control > |", "|---|---|---|---|---|---|---|---|---|"]
    bc = t1[t1["arm"] == "best_classical"].set_index("circuit")["t_count"]
    for mode in ("exact", "relaxed"):
        L = t1[(t1["arm"] == "llm") & (t1["mode"] == mode)].set_index("circuit")
        C = t1[(t1["arm"] == "control") & (t1["mode"] == mode)].set_index("circuit")
        cs = list(C.index)
        lb = le = lw = ln = 0
        for c in cs:
            if not bool(L.loc[c, "ok"]):
                ln += 1
                continue
            dlt = L.loc[c, "t_count"] - C.loc[c, "t_count"]
            lb += dlt < 0
            le += dlt == 0
            lw += dlt > 0
        cb = sum(C.loc[c, "t_count"] < bc[c] for c in cs if bool(C.loc[c, "ok"]))
        ce = sum(C.loc[c, "t_count"] == bc[c] for c in cs if bool(C.loc[c, "ok"]))
        cw = sum(C.loc[c, "t_count"] > bc[c] for c in cs if bool(C.loc[c, "ok"]))
        out.append(f"| {mode} | {len(cs)} | {lb} | {le} | {lw} | {ln} | {cb} | {ce} | {cw} |")
    out += ["", "Best classical on DEV = `best_classical(c, 0)` as used in the tier-1 dev report, which INCLUDES "
            "published TODD/KvdW2020 rows (not only our runs). Relaxed rows compare a different contract "
            "(ancillas, measurement) with a unitary-preserving number. LLM cost on DEV: 128 calls, 905,089 input + "
            "58,206 output tokens (`dev_v1_run.json`).", ""]
    t2 = pd.read_csv(ROOT / "results/v2/tier2/dev_results.csv")
    out += ["### Tier 2 (DEV, run `run1`; `results/v2/tier2/dev_results.csv`)", "",
            "| arm | total start T | total final T | T saved | total start gates | gates after (T-only library) | "
            "gates after lex secondary replay |", "|---|---|---|---|---|---|---|"]
    for arm in ("llm", "control"):
        out.append(f"| {arm} | {int(t2['start_t'].sum())} | {int(t2[f'{arm}_t'].sum())} | "
                   f"{int(t2['start_t'].sum() - t2[f'{arm}_t'].sum())} | {int(t2['start_gates'].sum())} | "
                   f"{int(t2[f'{arm}_gates'].sum())} | {int(t2[f'{arm}_lex_gates'].sum())} |")
    out += ["", f"{int(t2['start_t'].notna().sum())} DEV circuits (shor_12 excluded). Both primary libraries froze at v0 (empty). LLM cost: 36 "
            "calls, 229,474 input + 68,095 output tokens (`results/v2/tier2/DEV_REPORT.md`). The no-LLM enumeration "
            "control verified the same number of rules per generation.", ""]
    return "\n".join(out)


def _get(df, c, arm, mode="exact"):
    s = df[(df["circuit"] == c) & (df["arm"] == arm) & (df["mode"] == mode)]
    return None if s.empty else s.iloc[0].to_dict()


def _d(x, ref):
    if x is None or ref is None or pd.isna(x) or pd.isna(ref):
        return "-"
    v = int(x) - int(ref)
    return f"{v:+d}"


def tables(df, recs) -> dict:
    evald = [c for c in HELDOUT if c in recs and not recs[c].get("skipped") and not recs[c].get("error")]
    fam = {c: recs[c]["family"] for c in evald}
    evald.sort(key=lambda c: (FAMILY_ORDER.index(fam[c]) if fam[c] in FAMILY_ORDER else 99, recs[c]["n"], c))
    A = ["| circuit | family | n | best classical, our runs (arm) | pyzx_fr | tket_fpo | Nam Light | tier-1 control "
         "exact (variant + pass) | vs ours | check | tier-2 v0 (start) | tier-2 lex-secondary: gates before -> after "
         "(T) | tier-1 + tier-2 v0 / lex T | best published (arm) | published vs ours |",
         "|" + "---|" * 15]
    B = ["| circuit | n | best classical exact, ours | tier-1 control relaxed T | vs ours | ratio | qubits (anc) | "
         "measurements | T-depth (exact -> relaxed) | zero-init promise used | check | routes |", "|" + "---|" * 12]
    cnt = dict(ex_lt=0, ex_eq=0, ex_gt=0, ex_none=0, rel_lt=0, rel_eq=0, rel_gt=0, rel_none=0, best_lt=0,
               best_eq=0, best_gt=0, pub_lt=0, pub_eq=0, rel_lt_pub=0, rel_eq_pub=0, rel_gt_pub=0, n_pub=0,
               t2_changed_T=0, t2_unchanged=0)
    for c in evald:
        o = _get(df, c, "best_classical_ours")
        bo = o["t_count"] if o else None
        ex = _get(df, c, "tier1_control", "exact")
        rl = _get(df, c, "tier1_control", "relaxed")
        t2 = _get(df, c, "tier2_final")
        t2l = _get(df, c, "tier2_lexsec")
        b2 = _get(df, c, "tier1+tier2_final")
        b2l = _get(df, c, "tier1+tier2_lexsec")
        pub = _get(df, c, "best_published")
        bp = pub["t_count"] if pub and pub["ok"] else None
        if ex and ex["ok"]:
            k = "ex_lt" if ex["t_count"] < bo else "ex_eq" if ex["t_count"] == bo else "ex_gt"
            cnt[k] += 1
        else:
            cnt["ex_none"] += 1
        if rl and rl["ok"]:
            k = "rel_lt" if rl["t_count"] < bo else "rel_eq" if rl["t_count"] == bo else "rel_gt"
            cnt[k] += 1
            if bp is not None:
                cnt["rel_lt_pub" if rl["t_count"] < bp else "rel_eq_pub" if rl["t_count"] == bp else
                    "rel_gt_pub"] += 1
        else:
            cnt["rel_none"] += 1
        cands = [x["t_count"] for x in (ex, rl) if x and x["ok"]]
        if cands:
            m = min(cands)
            cnt["best_lt" if m < bo else "best_eq" if m == bo else "best_gt"] += 1
        if bp is not None:
            cnt["n_pub"] += 1
            cnt["pub_lt" if bp < bo else "pub_eq"] += 1
        for t in (t2, b2):
            if t and t.get("t_before") is not None and not pd.isna(t.get("t_before")):
                cnt["t2_unchanged" if int(t["t_after"]) == int(t["t_before"]) else "t2_changed_T"] += 1
        ex_txt = "-" if not (ex and ex["ok"]) else f"{_i(ex['t_count'])} ({ex['variant']} + {ex['global_pass']})"
        t2_txt = "-" if not t2 else f"{_i(t2['t_after'])} ({t2['notes'].split(' ')[0].replace('start=', '')})" + \
            ("" if t2["ok"] else " [verify: time limit]")
        t2l_txt = "-" if not t2l else f"{_i(t2l['gates_before'])} -> {_i(t2l['gates_after'])} ({_i(t2l['t_after'])})" + \
            ("" if t2l["ok"] else " [verify: time limit]")
        both = "-" if not b2 else f"{_i(b2['t_after'])} / {_i(b2l['t_after']) if b2l else '-'}" + \
            ("" if (b2["ok"] and (b2l is None or b2l["ok"])) else " [some verify: time limit]")
        A.append(f"| {c} | {fam[c]} | {recs[c]['n']} | {_i(bo)} ({o['method']}) | {_i(o['pyzx_fr_T'])} | "
                 f"{_i(o['tket_fpo_T'])} | {_i(o['nam_light_T'])} | {ex_txt} | {_d(ex['t_count'] if ex and ex['ok'] else None, bo)} | "
                 f"{ex['check'] if ex else '-'} | {t2_txt} | {t2l_txt} | {both} | "
                 f"{_i(bp)} ({pub['method'] if bp is not None else 'none'}) | {_d(bp, bo)} |")
        if rl and rl["ok"]:
            B.append(f"| {c} | {recs[c]['n']} | {_i(bo)} | {_i(rl['t_count'])} | {_d(rl['t_count'], bo)} | "
                     f"{rl['t_count'] / bo:.2f} | {_i(rl['qubits'])} (+{_i(rl['ancillas'])}) | {_i(rl['measurements'])} | "
                     f"{_i(ex['t_depth']) if ex and ex['ok'] else '-'} -> {_i(rl['t_depth'])} | "
                     f"{rl['zero_qubits'] or 'none'} | {rl['check']} | {_routes(rl['routes'])} |")
        else:
            B.append(f"| {c} | {recs[c]['n']} | {_i(bo)} | - | - | - | - | - | - | - | no verified relaxed plan | - |")
    return dict(A="\n".join(A), B="\n".join(B), cnt=cnt, evald=evald)


def _routes(js) -> str:
    try:
        d = json.loads(js)
    except Exception:
        return "-"
    return "; ".join(f"{k}: {len(v)}" for k, v in d.items()) or "none"


def build(tag="eval_v1"):
    recs = load(tag)
    df = rows_from(recs)
    df.to_csv(OUT / "eval_results.csv", index=False)
    return df, recs


def write_report(df, recs, tag="eval_v1", figure_ref="eval_figure.png"):
    t = tables(df, recs)
    k = t["cnt"]
    E = len(t["evald"])
    ok = df["ok"].fillna(False).astype(bool)
    ex = df[(df.arm == "tier1_control") & (df["mode"] == "exact") & ok].set_index("circuit")
    rl = df[(df.arm == "tier1_control") & (df["mode"] == "relaxed") & ok].set_index("circuit")
    bo = df[df.arm == "best_classical_ours"].set_index("circuit")["t_count"]
    lex = df[df.arm == "tier2_lexsec"]
    lex2 = df[df.arm == "tier1+tier2_lexsec"]
    skipped = df[df.arm == "skipped"]["circuit"].tolist()
    blocked = df[df.arm == "blocked"]["circuit"].tolist()
    worse_rel = [c for c in rl.index if rl.loc[c, "t_count"] > bo[c]]
    worse_ex = [c for c in ex.index if ex.loc[c, "t_count"] > bo[c]]
    secs = {c: recs[c].get("seconds") for c in t["evald"]}
    tsec = {c: recs[c]["tier1_control"]["seconds"] for c in t["evald"]}
    fr = next(r for r in recs.values() if r.get("freeze"))["freeze"]
    L = []
    L += [f"# v2 held-out evaluation report (run `{tag}`)", "",
          "Track \"Evaluation\", 2026-10-14. Split `v2-nam-arith-1`, HELD-OUT circuits only. **No LLM arms** "
          "(user decision after the DEV phase: both LLM arms were null on DEV); LLM tokens used in this evaluation: 0. "
          "Code: `experiments/v2_eval_heldout.py` (runs), `experiments/v2_eval_report.py` (this file + "
          "`eval_results.csv`), `experiments/v2_eval_figure.py` (figure). Raw per-circuit records: "
          "`per_circuit/<tag>_<circuit>.json`; per-evaluation logs: `logs/`; verified circuits: `circuits/`.", ""]
    L += ["## Verdict", "",
          f"1. **LLM arms: null on DEV, not run on held-out (by decision).** Tier 1: the LLM never produced a verified "
          f"plan with lower T than the deterministic no-LLM control at the same budget (exact 16/16 equal; relaxed 13 "
          f"equal, 2 worse, 1 no valid plan). Tier 2: neither the LLM arm nor the enumeration control lowered DEV T "
          f"(758 -> 758); both primary libraries froze at v0 (empty). See the DEV summary below.",
          f"2. **Unitary-preserving (exact) results do not beat best classical on held-out.** The frozen tier-1 control "
          f"in exact mode equals the best of our classical runs on {k['ex_eq']}/{E} circuits and is worse on "
          f"{k['ex_gt']} ({', '.join(worse_ex) or 'none'}: its pyzx-pass plans reach T = best classical but did not "
          f"finish verification within the frozen 240 s limit, so the best VERIFIED exact plan is the one without a "
          f"global pass). The frozen tier-2 library v0 is empty: T unchanged on all {E} start circuits and on all "
          f"{E} tier-1 exact outputs (0 rule applications). The secondary control library (30 gate-count rules, "
          f"dT = 0 by construction) also leaves T unchanged and removes {int(lex.gates_before.sum() - lex.gates_after.sum())} "
          f"of {int(lex.gates_before.sum())} gates on the classical start circuits "
          f"({100 * (lex.gates_before.sum() - lex.gates_after.sum()) / lex.gates_before.sum():.1f} %) and "
          f"{int(lex2.gates_before.sum() - lex2.gates_after.sum())} of {int(lex2.gates_before.sum())} on the tier-1 "
          f"exact outputs. The best published unitary-preserving numbers (mostly pyzx+TODD, Kissinger & van de "
          f"Wetering 2020; not run by us) are lower than our best classical run on {k['pub_lt']} of {k['n_pub']} "
          f"circuits that have a published value.",
          f"3. **Measurement-based constructions (relaxed contract) lower T below best classical on {k['rel_lt']}/{E} "
          f"held-out circuits** (worse on {k['rel_gt']}: {', '.join(worse_rel)}); total T over the {E} circuits "
          f"{int(rl.t_count.sum())} vs {int(bo[rl.index].sum())} for best classical "
          f"({100 * (rl.t_count.sum() / bo[rl.index].sum() - 1):+.1f} %). min(exact, relaxed) is below best classical on "
          f"{k['best_lt']}/{E} and equal on {k['best_eq']}. Relaxed T is also below the best PUBLISHED unitary-preserving "
          f"value on {k['rel_lt_pub']} of {k['rel_lt_pub'] + k['rel_eq_pub'] + k['rel_gt_pub']} circuits with a "
          f"published value. The price is extra qubits (+1 to +16), mid-circuit measurements (9 to 241) and, where the "
          f"plan relies on them, a zero-init promise on the declared ancilla qubits of the benchmark (a different "
          f"contract from the unitary benchmarks; see table B).",
          "4. **These gains are known constructions, not LLM discoveries.** Every winning relaxed plan is the "
          "deterministic control variant V2 (`max_relaxed`) + pyzx: Gidney's temporary logical-AND with "
          "measurement-based uncomputation (arXiv:1709.06648, 2018), Jones' 4-T Toffoli with measurement "
          "(PRA 87, 022328, 2013) and the compute-only clean AND, applied by a fixed rule. No LLM was involved on "
          "held-out, and on DEV the LLM selected the same routes no better than this rule.", ""]
    L += ["## Freeze check (before every circuit)", "",
          f"- `results/v2/tier1/FROZEN.md`: {fr['files_checked']} file SHA-256s re-checked (recognizer, plan, compile, "
          f"prompt, loop, control, v2 verify/metric, dev driver, 12 card files): all equal. Frozen verifier digest "
          f"`{fr['verifier_digest'][:16]}...` equal before and after every circuit.",
          f"- Tier-2 libraries re-loaded with every rule re-verified exactly: `library_final.json` v0, "
          f"{fr['libraries']['tier2_final']['n_rules']} rules, SHA-256 `{fr['libraries']['tier2_final']['sha256'][:16]}...`; "
          f"`library_lex_secondary_control.json`, {fr['libraries']['tier2_lexsec']['n_rules']} rules, SHA-256 "
          f"`{fr['libraries']['tier2_lexsec']['sha256'][:16]}...` (both equal to the `.sha256` files). Previous library "
          f"version: none (v0 is the first and only accepted primary version), so \"vs previous version\" is v0 vs the "
          f"unmodified start circuit.",
          f"- Evaluation budget = the DEV rule: 8 compile+verify evaluations per circuit (= 8 LLM calls per DEV circuit; "
          f"control order `control.ORDER[:8]`: V1/V2/V3/V4 + pyzx, V2/V1/V3 + none, V2 + pyzx_then_tket), verifier "
          f"limits `compile.DEFAULT_LIMITS` (branch_budget 131072, 240 s). The control is deterministic, so one run is "
          f"the whole distribution; the \"2-3 seeds\" of the plan are applied to the VERIFIER instead: every sampled "
          f"(non-certified) verdict was re-checked with sampling seeds 1 and 2.", ""]
    L += ["## Scope", "",
          f"22 held-out circuits; **{E} evaluated**; not evaluated: " +
          "; ".join(f"`{c}` (skipped: rotation-dominated, the frozen toolbox has no rotation route, as for shor_12 on "
                    f"DEV; tier 2 is exact Clifford+T only)" for c in skipped) + "; " +
          "; ".join(f"`{c}` (BLOCKED: verifier coverage - the frozen recognizer's normalization keeps a few unfused "
                    f"h/ccz gates, so the logical reference is not permutation-like and n > 14 makes the exact check "
                    f"infeasible; tier-1 outputs cannot be verified, so the circuit was stopped as instructed; this is "
                    f"not an inequivalence)" for c in blocked) + ". gf2^32_mult is large_optional (not in the split).",
          ""]
    L += ["## A. Unitary-preserving results (mode `exact`: same qubits, no measurement)", "",
          "`best classical, our runs` = lowest VERIFIED T among our pyzx full_reduce, TKET FullPeepholeOptimise "
          "(Clifford+T or logical input) and the Nam et al. Light output file (`results/v2/baselines_new.csv`, "
          "`verified=True`; Nam Heavy not used - its qcla_mod_7 file is not equivalent). `best published` = lowest "
          "table value among KvdW2020 (pyzx, pyzx+TODD, best previous as reported) and Nam2018 (light/heavy, T-par as "
          "reported); NOT run or verified by us. `check`: `cert` = exhaustive proof; `samp` = sampled inputs (n > 14), "
          "not a proof; `+2 seeds ok` = re-checked with two further sampling seeds; `time limit` = a re-check did not "
          "finish within 240 s (inconclusive, no counterexample). Tier-2 columns: v0 applied to the best classical "
          "exact output (start file in brackets) and to the tier-1 exact output.", "", t["A"], ""]
    L += ["## B. Relaxed results (mode `relaxed`: clean ancillas, measurement + feed-forward, declared zero-init "
          "promise)", "",
          "Different contract from table A: correct on every input with the listed promise qubits in |0>, for every "
          "measurement branch, ancillas returned to |0>. The comparison column is the best UNITARY-PRESERVING number "
          "(no classical relaxed baseline exists in the reused files). Every relaxed winner is control V2 + pyzx.", "",
          t["B"], ""]
    L += ["## C. Figure", "", f"![T relative to best classical per held-out circuit]({figure_ref})", "",
          f"Per held-out circuit ({E} evaluated; shor_14/16 skipped, qcla_adder_10/qcla_com_7 blocked), T-count divided "
          "by the best classical unitary-preserving T of our verified runs (vertical line = 1; (a) in the task). "
          "Open circles: frozen tier-1 control, exact (b). Diamonds: frozen tier-1 control, relaxed (c), with its extra "
          "qubits and mid-circuit measurements in the right column. Open squares: best published value (d), not run by "
          "us (absent for cuccaro_16, grover_5, mod_adder_1024). gf2^16_mult exact: the pyzx-pass plans have T = 1040 "
          "but did not verify within the frozen 240 s limit; the plotted point is the best verified exact plan (1792).",
          ""]
    L += ["## D. DEV results of both tiers (from the DEV CSVs; LLM vs no-LLM control)", "", dev_tables(), ""]
    L += ["## E. Runtime (wall seconds, one process per circuit, 6 in parallel on a 12-core laptop)", "",
          "| circuit | tier-1 control (8 evaluations) | whole circuit incl. tier 2, re-seeded checks |", "|---|---|---|"]
    for c in t["evald"]:
        L.append(f"| {c} | {tsec[c]} | {secs[c]} |")
    L += ["", "Most time is verification (sparse exact simulation of pyzx outputs, which contain many H gates) and the "
          "pyzx pass on the largest circuits (gf2^16_mult: 2,404 s for the first evaluation, pyzx pass plus a verification that hit the 240 s limit).", ""]
    L += ["## Caveats", "",
          "1. Sampled verification (`samp`) is strong evidence, not a proof; a result is certified only when inputs AND measurement branches are exhaustive (here: the n <= 14 exact results and relaxed mod_red_21). "
          "Timed-out re-checks are listed as inconclusive; no re-check refuted any result.",
          "2. Two tier-1+tier-2 verdicts timed out (gf2^10_mult v0, gf2^9_mult lex-secondary). For v0 the circuit is "
          "gate-for-gate the Clifford+T expansion of the verified tier-1 exact output (0 rule applications); the lex-secondary one changed gates "
          "only (T unchanged), and is reported as not verified.",
          "3. The relaxed contract uses the benchmark's declared zero-init qubits (`MANIFEST.csv` zero_init_qubits) "
          "wherever the compiled plan relies on them (column `zero-init promise used` in table B); those results are valid only under that promise.",
          "4. The T-depth of relaxed plans is higher than exact on the gf2 multipliers and csum_mux_9 (probably because the measured gadgets split the circuit into segments that the global pass optimizes separately; not investigated) and lower elsewhere; T-depth was not optimized by either tier.",
          "5. Published values come from the papers' own tables and settings and were not re-run; our best classical "
          "runs are the reference for all ratios.", ""]
    (OUT / "EVAL_REPORT.md").write_text("\n".join(L))
    return t


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="eval_v1")
    a = ap.parse_args()
    df, recs = build(a.tag)
    write_report(df, recs, a.tag)
    print(len(df), "rows;", sum(1 for c in HELDOUT if c in recs), "circuits with results", file=sys.stderr)
