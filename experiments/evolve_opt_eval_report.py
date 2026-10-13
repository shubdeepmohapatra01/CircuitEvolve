"""Build results/evolve_opt/eval_table.csv (+ eval_table_long.csv, eval_summary.json) from the evaluation run files.
Inputs (all read, never written): results/evolve_opt/eval/{runs.jsonl, baseline_eval.json, bygate_adders.json},
results/bqskit_baselines/table3_bygate.csv, the published-baselines CSV (path argument), run summaries of the LLM
runs. Rule for the final row of (program, circuit): the run at the highest per-circuit time limit used for that
circuit (limits are raised identically for every program); earlier-limit rows are kept in the long table."""
import csv
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EO = REPO / "results" / "evolve_opt"
EV = EO / "eval"
CIRCS = ["add_17", "hhl_6", "mult_16", "qft_32", "shor_16", "add_41", "add_65"]
PROGS = ["best_classical_program", "seed_program", "control_greedy_s2", "llm_v1_s0", "llm_v2_s2"]
PUB_NAME = {"Add-17": "add_17", "HHL-6": "hhl_6", "Mult-16": "mult_16", "QFT-32": "qft_32", "Shor-16": "shor_16"}
PUB_CAVEAT = {"qft_32": "published QFT-32 is an approximate QFT; qseed qft_32 is the full QFT (not like-for-like)",
              "shor_16": "published Shor-16 counts (816 RZ) are a parameter-count convention, not a valid Clifford+T "
                         "compilation (not like-for-like)"}


def load(published_csv):
    runs = [json.loads(line) for line in open(EV / "runs.jsonl")]
    limit = {c: max(r["time_s"] for r in runs if r["circuit"] == c) for c in CIRCS}
    final = {}
    for r in runs:
        if r["time_s"] == limit[r["circuit"]]:
            final[(r["program"], r["circuit"])] = r          # last row at the final limit
    base = json.loads((EV / "baseline_eval.json").read_text())
    bygate = {}
    for row in csv.DictReader(open(REPO / "results" / "bqskit_baselines" / "table3_bygate.csv")):
        if row["method"].startswith("paper-convention by-gate") and row["input"].startswith("qseed"):
            bygate[row["circuit"]] = dict(t=int(row["t_count"]), rz=int(row["rz_count"]))
    p = EV / "bygate_adders.json"
    if p.exists():
        for k, v in json.loads(p.read_text()).items():
            bygate.setdefault(k, dict(t=v["t_count"], rz=v["rz_count"]))
    pub = {}
    for row in csv.DictReader(open(published_csv)):
        if row["paper"].startswith("2409.00433") and row["circuit"] in PUB_NAME:
            pub[PUB_NAME[row["circuit"]]] = dict(bygate=int(float(row["reference"])), q2=int(float(row["alt"])),
                                                 q3=int(float(row["theirs"])))
    return runs, limit, final, base, bygate, pub


def pct(a, b):
    return None if a is None or b in (None, 0) else round(100.0 * (a / b - 1.0), 2)


def build(published_csv):
    runs, limit, final, base, bygate, pub = load(published_csv)
    wide, long_rows = [], []
    for c in CIRCS:
        b = base[c]
        bc_t = b["t"]
        row = dict(circuit=c, n=b["n"], time_limit_s=limit[c],
                   numerically_verified=b["n"] <= 20,
                   check_method=("unitary" if b["n"] <= 10 else "statevector (4 Haar states)" if b["n"] <= 20
                                 else "none (n > 20): NOT numerically verified"),
                   published_bygate_T=pub.get(c, {}).get("bygate"), published_2Q_T=pub.get(c, {}).get("q2"),
                   published_3Q_T=pub.get(c, {}).get("q3"), published_caveat=PUB_CAVEAT.get(c, ""),
                   reproduced_bygate_T=bygate.get(c, {}).get("t"), reproduced_bygate_rz=bygate.get(c, {}).get("rz"),
                   pyzx_T=b["candidates"]["pyzx"]["t"], pyzx_rz=b["candidates"]["pyzx"]["rz"],
                   tket_T=b["candidates"]["tket"]["t"], tket_rz=b["candidates"]["tket"]["rz"],
                   best_classical_T=bc_t, best_classical_rz=b["rz"], best_classical_pipeline=b["best"],
                   best_classical_bound=b["rz"] * 1e-9)
        for p in PROGS:
            r = final.get((p, c))
            cost = (r or {}).get("cost") or {}
            t = cost.get("t")
            chk = (r or {}).get("check") or {}
            row.update({f"{p}_T": t, f"{p}_rz": cost.get("rz"), f"{p}_bound": (r or {}).get("bound"),
                        f"{p}_valid": bool((r or {}).get("valid")),
                        f"{p}_check_dist": chk.get("dist"),
                        f"{p}_charged_cpu_s": round(r["charged_s"], 1) if r and r.get("charged_s") is not None else None,
                        f"{p}_fail_reason": None if (r or {}).get("valid") else (r or {}).get("reason"),
                        f"{p}_pct_vs_best_classical": pct(t, bc_t) if (r or {}).get("valid") else None,
                        f"{p}_pct_vs_published_3Q": pct(t, pub.get(c, {}).get("q3")) if (r or {}).get("valid") else None})
        wide.append(row)
    for r in runs:
        cost = r.get("cost") or {}
        chk = r.get("check") or {}
        long_rows.append(dict(program=r["program"], circuit=r["circuit"], n=r.get("n"), time_limit_s=r["time_s"],
                              final=final.get((r["program"], r["circuit"])) is r, valid=r.get("valid"),
                              numerically_verified=r.get("numerically_verified"), T=cost.get("t"), rz=cost.get("rz"),
                              cx=cost.get("cx"), bound=r.get("bound"), ledger=r.get("ledger"),
                              check_method=chk.get("method"), check_dist=chk.get("dist"),
                              charged_cpu_s=r.get("charged_s"), wall_s=r.get("wall_s"), reason=r.get("reason"),
                              program_sha256=r.get("program_sha256"), eval_version=r.get("eval_version"),
                              finished=r.get("finished")))
    # geomeans of T / T(best classical) over circuits where every program is valid
    allv = [w["circuit"] for w in wide if all(w[f"{p}_valid"] for p in PROGS)]
    verified = [c for c in allv if base[c]["n"] <= 20]
    gm = {}
    for label, cs in (("all_valid", allv), ("numerically_verified_and_valid", verified)):
        gm[label] = dict(circuits=cs, geomean={p: round(math.exp(sum(math.log(
            next(w for w in wide if w["circuit"] == c)[f"{p}_T"] / base[c]["t"]) for c in cs) / len(cs)), 5)
            for p in PROGS} if cs else {})
    # LLM cost
    cost = {}
    for tag in ("evo_s0_v3_120", "evo_s1_v3_120", "evo_s2_v3_120", "evo_s0_120", "smoke_live_8"):
        s = json.loads((EO / tag / "summary.json").read_text())
        cost[tag] = dict(proposer_calls=s["stats"]["proposer_calls"], reflector_calls=s["stats"]["reflector_calls"],
                         calls=s["backend"]["calls"], input_tokens=s["backend"]["input_tokens"],
                         output_tokens=s["backend"]["output_tokens"], failed=s["backend"]["failed"],
                         wall_s=s["seconds"])
    three = ["evo_s0_v3_120", "evo_s1_v3_120", "evo_s2_v3_120"]
    cost["total_3_seeds"] = {k: round(sum(cost[t][k] for t in three), 1) for k in
                             ("proposer_calls", "reflector_calls", "calls", "input_tokens", "output_tokens", "wall_s")}
    return wide, long_rows, gm, cost


def write_csv(path, rows):
    keys = list(rows[0].keys())
    for r in rows:
        keys += [k for k in r if k not in keys]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    wide, long_rows, gm, cost = build(sys.argv[1])
    for name, rows in (("eval_table.csv", wide), ("eval_table_long.csv", long_rows)):
        p = EO / name
        assert not p.exists(), f"{p} exists (results are append-only)"
        write_csv(p, rows)
    (EO / "eval_summary.json").write_text(json.dumps(dict(geomeans=gm, llm_cost=cost), indent=1))
    print(json.dumps(gm, indent=1))
    print(json.dumps(cost["total_3_seeds"]))
