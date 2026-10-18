"""P3.6 — zero-LLM cascade demo: raw cuccaro_8 + a mixed (adder + rotation) circuit.

Deterministic, NO LLM: the reconstruction stage is driven by the scripted deterministic
control route (v2/tier1/control.py, the no-LLM arm), the angle stage by a declining backend
(G1 graduated pass + TKET entry still run — both deterministic). Writes, once (append-only):

  benchmarks/mixed/cuccaro_4_rot.qasm            the mixed demo circuit (open decision 4:
                                                 benchmarks/mixed/), built here: cuccaro_4
                                                 body + a 5-rotation payload
  results/engine/recon_bench/DEMO.md             arm tables with per-stage attribution

Arms per circuit: angle-only | reconstruction-only (control) | cascade | best classical
(B0/B1 from the committed baselines where recorded). The relaxed column is SEPARATE: rows
whose constructions use measurement-based uncompute are marked relaxed and never compared
silently against unitary-preserving rows.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from circuitevolve.engine.run import optimize  # noqa: E402
from circuitevolve.v2.tier1.control import control_plans  # noqa: E402
from circuitevolve.v2.tier1.recognize import load_logical, summarize  # noqa: E402

RB = ROOT / "results" / "engine" / "recon_bench"
MIXED = ROOT / "benchmarks" / "mixed" / "cuccaro_4_rot.qasm"
DEMO = RB / "DEMO.md"

PAYLOAD = ["rz(0.3) q[1];", "cx q[1],q[2];", "rz(0.45) q[2];", "cx q[1],q[2];",
           "rz(0.3) q[1];", "rz(0.2) q[3];", "cx q[3],q[4];", "rz(0.2) q[3];"]


def nones(ps):
    return ["NONE"] * len(ps)


def scripted(name: str, budget: int):
    rows = {r["name"]: r for r in csv.DictReader(open(ROOT / "benchmarks/nam_arith/MANIFEST.csv"))}
    dz = [int(x) for x in str(rows[name].get("zero_init_qubits") or "").split()]
    _, lc = load_logical(str(ROOT / "benchmarks/nam_arith" / rows[name]["logical_path"]), name=name)
    s = summarize(lc, declared_zero=dz, name=name)
    plans = iter([p.to_json() for _, _, p in control_plans(lc, s, budget)])

    def complete(ps):
        return [next(plans, "NONE") for _ in ps]
    return complete, dz


def run_arms(source, name: str, dz, budget: int, runs_dir: Path) -> dict:
    arms = {}
    comp, _ = scripted(name, budget)
    arms["cascade"] = optimize(source, 1e-3, comp, manifest={"declared_zero": dz},
                               runs_dir=runs_dir / "cascade", n_calls=budget, batch=1)
    comp2, _ = scripted(name, budget)
    arms["reconstruction_only"] = optimize(source, 1e-3, comp2,
                                           manifest={"declared_zero": dz, "method": "reconstruction"},
                                           runs_dir=runs_dir / "recon", n_calls=budget, batch=1)
    arms["angle_only"] = optimize(source, 1e-3, nones, manifest={"method": "angle"},
                                  runs_dir=runs_dir / "angle", n_calls=1, batch=1)
    return arms


def table(name: str, arms: dict, classical_rows: list) -> str:
    lines = [f"### {name}", "",
             "| arm | contract | T after | notes |", "|---|---|---|---|"]
    for arm, cont, t, note in classical_rows:
        lines.append(f"| {arm} | {cont} | {t} | {note} |")
    a = arms["angle_only"]
    lines.append(f"| angle-only | approx | {a['t_after']} | TKET entry "
                 f"{'fired' if a.get('tket_entry') else 'off'}; declining loop (0 accepts); "
                 f"metric = named T + rotation synthesis estimate |")
    r = arms["reconstruction_only"]
    lines.append(f"| reconstruction-only (control) | relaxed | {r['t_after']} | deterministic "
                 f"control route; named T; measurements allowed (relaxed verifier) |")
    c = arms["cascade"]
    st = " -> ".join(f"{x['method']}({x['t_before']}->{x['t_after']})" for x in c["stages"])
    lines.append(f"| cascade | relaxed | {c['t_after']} | per-stage: {st} |")
    lines += ["", "Per-stage attribution (cascade):", ""]
    for x in c["stages"]:
        v = {True: "yes", False: "FAILED", None: "whole-circuit check skipped (size cap)"}[x["verified"]]
        lines.append(f"- {x['method']} [{x['contract']}]: {x['t_before']} -> {x['t_after']} "
                     f"(verified: {v})")
    if c.get("tket_entry"):
        te = c["tket_entry"]
        lines.append(f"- deterministic TKET entry pass ({te['why']}): "
                     f"{te['t_before']} -> {te['t_after']} named T (never sold as LLM gains)")
    if c.get("pre_opt") and c["pre_opt"].get("reports"):
        for rep in c["pre_opt"]["reports"]:
            lines.append(f"- graduated pass {rep['id']} ({rep['rule']}): {rep['merges']} merges")
    return "\n".join(lines) + "\n"


def main() -> None:
    if DEMO.exists():
        raise SystemExit(f"{DEMO} exists (results/ is append-only); refusing")
    runs = RB / "demo_runs"

    # ---------------------------------------------------------------- cuccaro_8, raw
    arms8 = run_arms(str(ROOT / "benchmarks/nam_arith/generated/cuccaro_8.qasm"),
                     "cuccaro_8", scripted("cuccaro_8", 4)[1], 4, runs / "cuccaro_8")
    base = {(r["circuit"], r["arm"]): r for r in csv.DictReader(open(RB / "baselines.csv"))}
    classical8 = [("best classical B0 (TKET)", "exact", base[("cuccaro_8", "B0_tket")]["t_count"],
                   "committed baseline (decomposed twin)"),
                  ("best classical B1 (pyzx)", "exact", base[("cuccaro_8", "B1_pyzx")]["t_count"],
                   "committed baseline (v2 record)")]

    # ---------------------------------------------------------------- mixed circuit
    if not MIXED.exists():
        MIXED.parent.mkdir(parents=True, exist_ok=True)
        body = (ROOT / "benchmarks/nam_arith/generated/cuccaro_4.qasm").read_text().strip()
        MIXED.write_text(body + "\n" + "\n".join(PAYLOAD) + "\n")
    sha = hashlib.sha256(MIXED.read_bytes()).hexdigest()
    armsM = run_arms(str(MIXED), "cuccaro_4", scripted("cuccaro_4", 2)[1], 2, runs / "mixed")

    md = [
        "# Method cascade demo (P3.6) — zero LLM",
        "",
        "Reproduce: `.venv/bin/python experiments/engine_cascade_demo.py` (delete nothing; the",
        "script refuses to overwrite — this file documents the run that produced it).",
        "",
        "No LLM anywhere: reconstruction = scripted deterministic control route (v2/tier1),",
        "angle = declining backend (TKET entry + graduated G1 still run, both deterministic).",
        "",
        "CONTRACT COLUMNS ARE SEPARATE (CLAUDE.md invariant: relaxed never mixes with",
        "unitary-preserving): 'relaxed' rows use measurement-based uncompute, verified by the",
        "frozen v2 relaxed verifier; 'approx'/'exact' rows are unitary-preserving. The mixed",
        "circuit's angle numbers are in the angle METRIC column (named T + gridsynth estimate",
        "for general-angle rotations at eps_rz); reconstruction rows count named T only.",
        "",
        table("cuccaro_8 (raw, benchmarks/nam_arith/generated/cuccaro_8.qasm)", arms8, classical8),
        "",
        table(f"mixed: cuccaro_4 + 5-rotation payload (benchmarks/mixed/cuccaro_4_rot.qasm, "
              f"sha256 {sha[:16]}...)", armsM, []),
        "",
        "Mixed-input semantics (P3.6): reconstruction operates on the largest Toffoli-bearing",
        "grid segment through the frozen verifier and passes rotation segments through",
        "untouched; the angle stage receives the rotation-richest measurement-free segment.",
        "Stage rows therefore do not form one monotone T chain for mixed input - the columns",
        "differ by design and are never summed across contracts.",
    ]
    DEMO.write_text("\n".join(md))
    print(f"wrote {DEMO.relative_to(ROOT)}; mixed circuit sha256 {sha}")
    for nm, arms in (("cuccaro_8", arms8), ("mixed", armsM)):
        print(nm, {k: v["t_after"] for k, v in arms.items()})


if __name__ == "__main__":
    main()
