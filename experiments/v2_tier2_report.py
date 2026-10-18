"""Tier-2 DEV report: freeze libraries, secondary analyses, CSVs and DEV_REPORT.md (no LLM calls).

    import sys; sys.path.insert(0, "."); from experiments.v2_tier2_report import build; build("run1")

Reads results/v2/tier2/<tag>/*.jsonl written by experiments/v2_tier2_evolve.py. Writes into results/v2/tier2/:
    library_final.json (+ .sha256, .md)          frozen primary library of the LLM arm (last accepted version)
    library_control_final.json (+ .sha256, .md)  frozen primary library of the no-LLM control
    library_lex_secondary_{llm,control}.json      SECONDARY replay libraries ((T, gates) acceptance) - not primary
    dev_results.csv, generations.csv, rules_verified.csv, diagnostics.json, DEV_REPORT.md
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from circuitevolve.blocks import REPO
from circuitevolve.v2.tier2 import evolve as E
from circuitevolve.v2.tier2.apply import apply_library, cost, exact_guard, load_qasm, numeric_guard
from circuitevolve.v2.tier2.circuits import ARMS, EXCLUDED, start_circuits
from circuitevolve.v2.tier2.rules import Library, Rule, seq_cost

OUT = REPO / "results/v2/tier2"


def _read(path):
    return [json.loads(l) for l in open(path)] if Path(path).is_file() else []


def _last_library(d: Path, arm: str) -> Library:
    vs = sorted((d / "libraries").glob(f"{arm}_v*.json"), key=lambda p: int(p.stem.split("_v")[-1]))
    return Library.load(vs[-1])


def _freeze(lib: Library, name: str, note: str) -> str:
    lib.meta = dict(lib.meta, frozen_note=note)
    sha = lib.save(OUT / f"{name}.json")
    (OUT / f"{name}.sha256").write_text(f"{sha}  {name}.json (content hash of the ordered rule list)\n")
    (OUT / f"{name}.md").write_text(lib.markdown() + f"\n{note}\n")
    return sha


def _verified_rules(d, arm):
    return [Rule.from_dict(r["rule"]) for r in _read(d / f"{arm}_rules.jsonl") if r.get("verified")]


def build(tag: str = "run1", exact_guard_max_qubits: int = 10):
    import sys
    sys.path.insert(0, str(REPO))
    from experiments.v2_tier2_evolve import replay
    from circuitevolve.v2 import baselines as B

    d = OUT / tag
    starts = start_circuits()
    gens = {a: _read(d / f"{a}_generations.jsonl") for a in ("llm", "control")}
    rules = {a: _read(d / f"{a}_rules.jsonl") for a in ("llm", "control")}
    calls = _read(d / "llm_llm_calls.jsonl")
    summ = json.load(open(d / "llm_summary.json"))

    # ---------------------------------------------------------------- freeze primary libraries
    lib_llm, lib_ctl = _last_library(d, "llm"), _last_library(d, "control")
    sha_llm = _freeze(lib_llm, "library_final", f"Frozen from results/v2/tier2/{tag} (LLM arm, last accepted version "
                      f"{lib_llm.version}).")
    sha_ctl = _freeze(lib_ctl, "library_control_final", f"Frozen from results/v2/tier2/{tag} (no-LLM control, last "
                      f"accepted version {lib_ctl.version}).")
    ev_llm, ev_ctl = E.evaluate(lib_llm, starts), E.evaluate(lib_ctl, starts)

    # ---------------------------------------------------------------- secondary: lex replay
    rep = {}
    for a in ("llm", "control"):
        steps, lib, ev = replay(tag, a, mode="lex")
        lib.version = f"lex-replay-{a}"
        lib.meta = dict(arm=a, secondary=True)
        sha = _freeze(lib, f"library_lex_secondary_{a}", "SECONDARY replay with (T, gates) acceptance over the "
                      "recorded verified proposals; not the primary (T-only) library.")
        rep[a] = dict(steps=steps, lib=lib, ev=ev, sha=sha)

    # ---------------------------------------------------------------- diagnostics
    from circuitevolve.v2.tier2.enumerate_ids import candidate_pool
    from experiments.v2_tier2_evolve import CONTROL_SPECS
    pool = candidate_pool(specs=CONTROL_SPECS, random_samples=20000, seed=0)
    tpool = [r for r in pool if r.cost_delta()[0] > 0]
    mc = E.match_counts(tpool, starts)
    diag = dict(pool_size=len(pool), pool_t_reducing=len(tpool), pool_specs=CONTROL_SPECS,
                t_reducing_pool_rules_matching_any_start=len(mc), t_reducing_pool_total_matches=sum(mc.values()))
    llm_ver, ctl_ver = _verified_rules(d, "llm"), _verified_rules(d, "control")
    diag["llm_verified_rules"] = len(llm_ver)
    diag["llm_verified_t_reducing"] = sum(1 for r in llm_ver if r.cost_delta()[0] > 0)
    diag["control_verified_rules"] = len(ctl_ver)
    diag["control_verified_t_reducing"] = sum(1 for r in ctl_ver if r.cost_delta()[0] > 0)
    # transfer: all verified rules of each arm on every OTHER (non-best) verified exact classical DEV output
    transfer = []
    for c, s in starts.items():
        for cand in s["candidates"]:
            if cand["status"] != "ok" or cand["arm"] == s["arm"]:
                continue
            g, n = load_qasm(REPO / cand["path"])
            row = dict(circuit=c, arm=cand["arm"], n=n, t0=cost(g)[0], g0=cost(g)[1])
            for a, rs in (("llm", llm_ver), ("control", ctl_ver)):
                lib = Library([Rule(f"{a}{i}", r.pattern, r.replacement, r.side) for i, r in enumerate(rs)])
                res = apply_library(g, n, lib)
                gd = numeric_guard(g, res["gates"], n) if res["apps"] else dict(ok=True)
                row[f"{a}_t"], row[f"{a}_g"], row[f"{a}_guard"] = res["cost_after"][0], res["cost_after"][1], gd["ok"]
            transfer.append(row)
    diag["transfer_rows"] = len(transfer)
    diag["transfer_llm_t_saved"] = sum(r["t0"] - r["llm_t"] for r in transfer)
    diag["transfer_control_t_saved"] = sum(r["t0"] - r["control_t"] for r in transfer)
    diag["transfer_llm_g_saved"] = sum(r["g0"] - r["llm_g"] for r in transfer)
    diag["transfer_control_g_saved"] = sum(r["g0"] - r["control_g"] for r in transfer)
    diag["transfer_guard_all_ok"] = all(r["llm_guard"] and r["control_guard"] for r in transfer)
    with open(OUT / "transfer_nonbest_dev.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(transfer[0]))
        w.writeheader()
        w.writerows(transfer)

    # ---------------------------------------------------------------- per-circuit table (+ exact guards)
    tab = B.table()
    out_rows = []
    for c, s in starts.items():
        bc = B.best_classical(c, 0, tab=tab)
        row = dict(circuit=c, qubits=s["n"], start_arm=s["arm"], start_t=s["t"], start_gates=s["gates_total"],
                   best_classical_t=None if bc is None else int(bc["t_count"]),
                   best_classical_arm=None if bc is None else bc["arm"],
                   best_classical_source=None if bc is None else bc["source"])
        for a, ev in (("llm", ev_llm), ("control", ev_ctl), ("llm_lex", rep["llm"]["ev"]),
                      ("control_lex", rep["control"]["ev"])):
            p = ev["per"][c]
            row[f"{a}_t"], row[f"{a}_gates"] = p["t"], p["g"]
            changed = p["gates"] != s["gates"]
            if changed:
                eg = exact_guard(s["gates"], p["gates"], s["n"], max_qubits=exact_guard_max_qubits)
                ng = numeric_guard(s["gates"], p["gates"], s["n"], n_states=3, seed=7)
                row[f"{a}_check"] = (f"exact:{eg['method']}:{eg['ok']}" if eg["ok"] is not None else
                                     f"numeric:{ng['method']}:{ng['ok']}")
            else:
                row[f"{a}_check"] = "unchanged"
        row["llm_vs_best_classical_t"] = (None if row["best_classical_t"] is None
                                          else row["llm_t"] - row["best_classical_t"])
        out_rows.append(row)
    for c, why in EXCLUDED.items():
        out_rows.append(dict(circuit=c, start_arm="excluded", start_t=None, llm_check=why))
    keys = list(out_rows[0])
    with open(OUT / "dev_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(out_rows)

    # ---------------------------------------------------------------- generations / rules CSV
    with open(OUT / "generations.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "gen", "n_proposed", "n_verify_calls", "n_verified", "cand_total_t", "cand_total_g",
                    "accepted", "library_version", "library_sha256", "reason"])
        for a in ("llm", "control"):
            for g in gens[a]:
                if "stopped" in g:
                    continue
                w.writerow([a, g["gen"], g.get("n_proposed", ""), g.get("n_verify_calls", ""), g.get("n_verified", ""),
                            g["cand_total_t"], g["cand_total_g"], g["accepted"], g.get("lib_version"),
                            g.get("lib_sha"), g.get("reason")])
        for a in ("llm", "control"):
            for s in rep[a]["steps"]:
                w.writerow([a + "_lex_replay", s["gen"], "", "", "", s["total_t"], s["total_g"], s["accepted"],
                            "", "", s["reason"]])
    with open(OUT / "rules_verified.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "gen", "name", "pattern", "replacement", "k", "dT", "dgates", "applications_dev",
                    "t_saved_dev", "g_saved_dev", "meaning", "outcome"])
        for a in ("llm", "control"):
            for r in rules[a]:
                if not r.get("verified"):
                    continue
                rr = Rule.from_dict(r["rule"])
                dt, dg = rr.cost_delta()
                w.writerow([a, r["gen"], r["name"], r["rule"]["pattern"], r["rule"]["replacement"], rr.k, dt, dg,
                            r.get("applications", ""), r.get("t_saved", ""), r.get("g_saved", ""),
                            r["rule"].get("meaning", ""), r["outcome"]])

    # ---------------------------------------------------------------- outcome counts
    def counts(rs):
        c = Counter()
        for r in rs:
            o = r["outcome"]
            c["duplicate" if o.startswith("duplicate") else "parse_error" if o.startswith("PARSE") else
              "malformed" if "malformed" in o else "not_identity" if "REJECTED by verifier" in o else "verified"] += 1
        return dict(c)
    oc = {a: counts(rules[a]) for a in rules}
    parse_errs = sum(len(c["parse_errors"]) for c in calls)
    oc["llm"]["parse_error"] = parse_errs
    diag["outcomes"] = oc
    diag["llm_calls"] = summ["calls"]
    diag["tokens"] = summ["tokens"]
    diag["verify_schedule"] = summ["verify_schedule"]
    diag["frozen"] = dict(library_final=sha_llm, library_control_final=sha_ctl,
                          lex_llm=rep["llm"]["sha"], lex_control=rep["control"]["sha"])
    diag["lex_replay"] = {a: dict(total_t=rep[a]["ev"]["total_t"], total_g=rep[a]["ev"]["total_g"],
                                  n_rules=len(rep[a]["lib"].rules),
                                  rules=[dict(name=r.name, pattern=r.to_dict()["pattern"],
                                              replacement=r.to_dict()["replacement"],
                                              apps=rep[a]["ev"]["apps"].get(r.name, 0),
                                              g_saved=rep[a]["ev"]["g_saved"].get(r.name, 0))
                                         for r in rep[a]["lib"].rules]) for a in rep}
    diag["start_total_t"] = sum(s["t"] for s in starts.values())
    diag["start_total_gates"] = sum(s["gates_total"] for s in starts.values())
    json.dump(diag, open(OUT / "diagnostics.json", "w"), indent=1, default=str)
    return dict(rows=out_rows, diag=diag, rep=rep, ev_llm=ev_llm, ev_ctl=ev_ctl, lib_llm=lib_llm, lib_ctl=lib_ctl,
                transfer=transfer, gens=gens)
