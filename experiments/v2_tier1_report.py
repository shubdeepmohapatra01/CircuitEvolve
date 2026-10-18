"""Build results/v2/tier1/DEV_REPORT.md, dev_results.csv and FROZEN.md from a tier-1 dev run (no recomputation).

    .venv/bin/python experiments/v2_tier1_report.py dev_v1
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "results" / "v2" / "tier1"

FROZEN_FILES = ["circuitevolve/v2/tier1/recognize.py", "circuitevolve/v2/tier1/plan.py",
                "circuitevolve/v2/tier1/compile.py", "circuitevolve/v2/tier1/prompt.py",
                "circuitevolve/v2/tier1/loop.py", "circuitevolve/v2/tier1/control.py",
                "circuitevolve/v2/verify.py", "circuitevolve/v2/metric.py", "experiments/v2_tier1_dev.py",
                "docs/v2/cards/INDEX.md"] + sorted(str(p.relative_to(ROOT)) for p in
                                                   (ROOT / "docs/v2/cards").glob("[0-9][0-9]_*.md"))


def sha(p) -> str:
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def _i(x):
    return "-" if x is None or (isinstance(x, float) and pd.isna(x)) else str(int(x))


def _routes(js) -> str:
    if not isinstance(js, str) or not js:
        return ""
    try:
        d = json.loads(js)
    except json.JSONDecodeError:
        return js
    if isinstance(d, list):
        return ", ".join(d)
    return "; ".join(f"{k}: {len(v)}" for k, v in d.items())


def build(tag: str):
    df = pd.read_csv(OUT / f"{tag}_dev_results.csv")
    meta = json.loads((OUT / f"{tag}_run.json").read_text())
    df.insert(0, "tag", tag)
    df.to_csv(OUT / "dev_results.csv", index=False)
    circuits = [c for c in meta["circuits"]]
    get = {(r.circuit, r.arm, r.mode): r for r in df.itertuples()}
    pc = {m["circuit"]: m for m in meta["per_circuit"]}

    def cell(c, arm, mode, field="t_count"):
        r = get.get((c, arm, mode))
        if r is None or not r.ok:
            return None
        return getattr(r, field)

    L = [f"# Tier 1 (compilation strategy) - development report, run `{tag}`", ""]
    tok = meta.get("tokens", {})
    L += [f"Model `{meta.get('model')}` (in-platform host.llm via `make_api_backend`, thinking disabled); "
          f"{meta['calls_per_circuit']} LLM calls per circuit; the no-LLM control gets the SAME number of "
          f"compile+verify evaluations. Split `v2-nam-arith-1`, DEV circuits only ({len(circuits)} run; skipped: "
          + "; ".join(f"{k} - {v}" for k, v in meta.get("skipped", {}).items()) + ").",
          f"Tokens: {tok.get('input_tokens', 0):,} input + {tok.get('output_tokens', 0):,} output in "
          f"{tok.get('calls', 0)} calls; wall time {meta['seconds']:.0f} s. Frozen verifier digest unchanged "
          f"(`{meta['frozen_digest'][:16]}...`, checked before and after).", "",
          "Every number below comes from `" + f"{tag}_dev_results.csv" + "` (written by `experiments/v2_tier1_dev.py`)"
          " or from the reused baseline files through `circuitevolve.v2.baselines.best_classical(c, eps=0)`. "
          "Each candidate was verified against the LOGICAL circuit (ccx-normalized Nam QASM; normalization itself "
          "checked against the original QASM, exhaustive for n <= 14, sampled above). `cert` = the check is a proof "
          "(exhaustive inputs and branches); `samp` = sampled inputs and/or branches (n > 14 or too many "
          "measurement branches), NOT a proof.", "",
          "Arms: **LLM** = best verified plan from the model; **control** = deterministic route sets V1-V4 x global "
          "passes (`circuitevolve/v2/tier1/control.py`) at the same evaluation budget; **V1** = the control "
          "restricted to the named heuristic (clean compute/uncompute pairs -> temporary_and, rest 7 T); "
          "**best classical** = lowest reused unitary-preserving T-count on record (pyzx / TKET / Nam et al. files / "
          "published TODD etc.).", ""]
    # ---------------------------------------------------------------- exact table
    L += ["## A. Unitary-preserving (mode `exact`: same qubits, no measurement, no zero-init promise)", "",
          "| circuit | n | best classical (arm) | pyzx_fr | tket_fpo | control | LLM | LLM - control | LLM - classical "
          "| LLM check | LLM routes |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    wins = dict(exact=[0, 0, 0], relaxed=[0, 0, 0])
    vs_cl = dict(exact=[0, 0, 0], relaxed=[0, 0, 0])
    for c in circuits:
        bc = get.get((c, "best_classical", "exact"))
        llm, ctl = cell(c, "llm", "exact"), cell(c, "control", "exact")
        r = get.get((c, "llm", "exact"))
        n = _i(cell(c, "control", "exact", "qubits")) if ctl is not None else "-"
        d = "-" if llm is None or ctl is None else f"{int(llm - ctl):+d}"
        dc = "-" if llm is None or bc is None or pd.isna(bc.t_count) else f"{int(llm - bc.t_count):+d}"
        if llm is not None and ctl is not None:
            wins["exact"][0 if llm < ctl else (1 if llm == ctl else 2)] += 1
        if llm is not None and bc is not None and not pd.isna(bc.t_count):
            vs_cl["exact"][0 if llm < bc.t_count else (1 if llm == bc.t_count else 2)] += 1
        chk = "-" if r is None or not r.ok else ("cert" if r.certified else "samp")
        L.append(f"| {c} | {n} | {_i(bc.t_count)} ({bc.best_classical_arm}) | {_i(bc.pyzx_fr_T)} | "
                 f"{_i(bc.tket_fpo_T)} | {_i(ctl)} | {_i(llm)} | {d} | {dc} | {chk} | "
                 f"{_routes(r.routes) if r is not None and r.ok else ''} |")
    L += ["", f"LLM vs control (exact): better {wins['exact'][0]}, equal {wins['exact'][1]}, worse "
          f"{wins['exact'][2]}. LLM vs best classical: better {vs_cl['exact'][0]}, equal {vs_cl['exact'][1]}, "
          f"worse {vs_cl['exact'][2]}.", ""]
    # ---------------------------------------------------------------- relaxed table
    L += ["## B. Relaxed (mode `relaxed`: clean ancillas, measurement + feed-forward, declared zero-init promise)",
          "",
          "Not the same contract as table A: the classical column is the best UNITARY-PRESERVING number and is shown "
          "only as a reference point; no classical relaxed baseline exists in the reused files, so the control is "
          "the relevant comparison.", "",
          "| circuit | best classical exact | V1 (spec) | control | LLM | LLM - control | LLM qubits / anc / meas | "
          "zero-init promise | LLM check | LLM routes |", "|---|---|---|---|---|---|---|---|---|---|"]
    for c in circuits:
        bc = get.get((c, "best_classical", "exact"))
        llm, ctl, v1 = cell(c, "llm", "relaxed"), cell(c, "control", "relaxed"), cell(c, "control_V1_spec",
                                                                                     "relaxed")
        r = get.get((c, "llm", "relaxed"))
        d = "-" if llm is None or ctl is None else f"{int(llm - ctl):+d}"
        if llm is not None and ctl is not None:
            wins["relaxed"][0 if llm < ctl else (1 if llm == ctl else 2)] += 1
        if llm is not None and bc is not None and not pd.isna(bc.t_count):
            vs_cl["relaxed"][0 if llm < bc.t_count else (1 if llm == bc.t_count else 2)] += 1
        res = "-" if r is None or not r.ok else f"{_i(r.qubits)} / {_i(r.ancillas)} / {_i(r.measurements)}"
        zp = "" if r is None or not r.ok or not isinstance(r.zero_qubits, str) else r.zero_qubits
        chk = "-" if r is None or not r.ok else ("cert" if r.certified else "samp")
        L.append(f"| {c} | {_i(bc.t_count)} | {_i(v1)} | {_i(ctl)} | {_i(llm)} | {d} | {res} | "
                 f"{('q' + zp.replace(' ', ' q')) if zp else 'none'} | {chk} | "
                 f"{_routes(r.routes) if r is not None and r.ok else ''} |")
    L += ["", f"LLM vs control (relaxed): better {wins['relaxed'][0]}, equal {wins['relaxed'][1]}, worse "
          f"{wins['relaxed'][2]}. Relaxed LLM T vs best classical exact T: lower {vs_cl['relaxed'][0]}, equal "
          f"{vs_cl['relaxed'][1]}, higher {vs_cl['relaxed'][2]} (different contracts).", ""]
    # ---------------------------------------------------------------- control details
    L += ["## C. Control: which variant won", "", "| circuit | exact: variant + pass, T | relaxed: variant + pass, T, "
          "qubits / meas |", "|---|---|---|"]
    for c in circuits:
        parts = []
        for mode in ("exact", "relaxed"):
            r = get.get((c, "control", mode))
            if r is None or not r.ok:
                parts.append("-")
            else:
                extra = f", {_i(r.qubits)} / {_i(r.measurements)}" if mode == "relaxed" else ""
                parts.append(f"{r.variant} + {r.global_pass}, {_i(r.t_count)}{extra}")
        L.append(f"| {c} | {parts[0]} | {parts[1]} |")
    # ---------------------------------------------------------------- LLM call stats
    L += ["", "## D. LLM call outcomes", "", "| circuit | calls | verified | plan rejected | verifier rejected | "
          "LLM errors | input tok | output tok | LLM-arm wall s |", "|---|---|---|---|---|---|---|---|---|"]
    tot = [0] * 6
    for c in circuits:
        m = pc.get(c)
        if not m:
            L.append(f"| {c} | ERROR: {meta['errors'].get(c, '')[:120]} |||||||")
            continue
        t = m["llm_tokens"]
        vals = [m["llm_evals"], m["llm_ok"], m["llm_parse_or_plan_rejects"], m["llm_verifier_rejects"],
                m["llm_errors"]]
        tot = [a + b for a, b in zip(tot, vals + [0])]
        L.append(f"| {c} | " + " | ".join(map(str, vals)) + f" | {t.get('input_tokens', 0):,} | "
                 f"{t.get('output_tokens', 0):,} | {m['llm_seconds']} |")
    L.append(f"| total | {tot[0]} | {tot[1]} | {tot[2]} | {tot[3]} | {tot[4]} | | | |")
    (OUT / f"{tag}_DEV_REPORT_tables.md").write_text("\n".join(L) + "\n")
    return L, wins, vs_cl, df, meta


def frozen(tag: str, meta: dict):
    from circuitevolve.v2.tier1.compile import DEFAULT_LIMITS
    from circuitevolve.v2.tier1.plan import GLOBAL_PASSES, TOOLBOX, TOOLBOX_VERSION
    from circuitevolve.v2.tier1.prompt import PROMPT_VERSION, TEMPLATE
    L = [f"# Tier 1 - FROZEN prompt, plan format and toolbox (from run `{tag}`)", "",
         "The held-out evaluation must reuse these files unchanged; re-check every SHA-256 below before running "
         "(`shasum -a 256 <file>`). A changed hash = a different method; record it as a new version.", "",
         f"- prompt template version: `{PROMPT_VERSION}`; SHA-256 of the template string: "
         f"`{hashlib.sha256(TEMPLATE.encode()).hexdigest()}`",
         f"- toolbox version: `{TOOLBOX_VERSION}`; routes: {', '.join(TOOLBOX)}; global passes: "
         f"{', '.join(GLOBAL_PASSES)}",
         f"- model: `{meta.get('model')}` via `make_api_backend(host.llm, model=host.reasoning_model(), "
         f"max_tokens=4000, max_concurrency=1)`, thinking disabled",
         f"- budget: {meta['calls_per_circuit']} LLM calls per circuit, target schedule relaxed/exact alternating "
         f"(call 0 relaxed); control budget = number of LLM evaluations",
         f"- verifier limits (compile.DEFAULT_LIMITS): {DEFAULT_LIMITS}; verify.Limits defaults otherwise",
         f"- card selection: `prompt.select_cards` (3 by recognizer features + up to 2 requested)",
         f"- frozen verifier digest (circuitevolve.integrity): `{meta['frozen_digest']}`", "",
         "## Prompt assembly", "",
         "`prompt.build_prompt(summary, lc, target, best, feedback, cards, classical)` fills `prompt.TEMPLATE` with: "
         "the recognizer summary (`Summary.text(lc)`: qubit roles, Toffoli list, pairs with class, unpaired Toffolis, "
         "multi-controlled-X cascades, repeated blocks, rotation content, normalized gate list if <= 120 gates), "
         "`plan.toolbox_text()`, the card INDEX table, the selected full cards, the naive 7 T/Toffoli cost, the best "
         "classical exact T-count string, the best verified plan per leaderboard so far, and the last 4 results "
         "(verified metrics or verifier/plan rejection reasons). Reply = one JSON plan (`plan.parse_plan`; literal "
         "json + regex, no exec/eval).", "",
         "## File hashes", "", "| file | sha256 |", "|---|---|"]
    for f in FROZEN_FILES:
        L.append(f"| `{f}` | `{sha(f)}` |")
    (OUT / "FROZEN.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "dev_v1"
    L, wins, vs, df, meta = build(tag)
    frozen(tag, meta)
    print("\n".join(L))
