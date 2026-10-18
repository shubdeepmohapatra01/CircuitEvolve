"""v2 held-out evaluation (track "Evaluation"): frozen tier-1 NO-LLM control + frozen tier-2 libraries, no LLM arms.

User decision (2026-10-14): the LLM arms were null on DEV (tier 1: never beat the control; tier 2: frozen library v0
empty for both arms), so the held-out circuits are evaluated WITHOUT LLM arms. Nothing in tier1/tier2 code, prompts,
toolbox or libraries is changed; FROZEN.md hashes and library SHA-256s are checked before every circuit.

Per held-out circuit (split v2-nam-arith-1, benchmarks/nam_arith/split_v2.json):
  tier1_control      frozen deterministic control (circuitevolve.v2.tier1.control), SAME evaluation budget rule as
                     on dev: 8 compile+verify evaluations (= the 8 LLM calls per dev circuit; control order truncated
                     to 8). Best verified plan per mode (exact = unitary-preserving; relaxed = ancillas/measurement).
  tier2_final        frozen primary library results/v2/tier2/library_final.json (v0, empty) applied to the best
                     classical exact Clifford+T output (same start-circuit rule as tier 2 on dev) -> T must be unchanged.
  tier2_lexsec       secondary control library library_lex_secondary_control.json (30 gate-count rules, dT = 0).
  tier1+tier2_*      both libraries applied to the tier-1 control's EXACT output (relaxed outputs measure; tier 2 is
                     unitary-only).
Every output is verified with circuitevolve.v2.verify against the LOGICAL circuit; the verdict mode and certified flag
are recorded (sampled checks are labelled, and re-run with 2 further seeds).

Run one circuit (one process per circuit; CPU-bound, so processes, not threads):
    .venv/bin/python experiments/v2_eval_heldout.py --circuit adder_8
Writes results/v2/eval/per_circuit/<c>.json, logs/<c>_control.jsonl, circuits/<c>__<arm>_<mode>.qasm.
Never overwrites an existing per-circuit JSON (append-only); use --tag for a new run.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("XDG_CONFIG_HOME", str(ROOT / ".venv" / "xdg"))

import pandas as pd  # noqa: E402

from circuitevolve import integrity  # noqa: E402
from circuitevolve.ir import to_qasm3  # noqa: E402
from circuitevolve.v2 import baselines as BL  # noqa: E402
from circuitevolve.v2 import verify as V  # noqa: E402
from circuitevolve.v2.metric import measure  # noqa: E402
from circuitevolve.v2.tier1.compile import DEFAULT_LIMITS, reference_for  # noqa: E402
from circuitevolve.v2.tier1.loop import run_control_arm  # noqa: E402
from circuitevolve.v2.tier1.recognize import load_logical, summarize  # noqa: E402
from circuitevolve.v2.tier2 import apply as T2  # noqa: E402
from circuitevolve.v2.tier2.rules import Library  # noqa: E402
from circuitevolve.v2.verify import NotExact  # noqa: E402

BENCH = ROOT / "benchmarks" / "nam_arith"
OUT = ROOT / "results" / "v2" / "eval"
T1 = ROOT / "results" / "v2" / "tier1"
T2DIR = ROOT / "results" / "v2" / "tier2"
SPLIT = json.loads((BENCH / "split_v2.json").read_text())
HELDOUT = list(SPLIT["heldout"])
BUDGET = 8          # dev rule: control evaluations = LLM calls per circuit (FROZEN.md: 8)
SKIP = {
    "shor_14": "rotation-dominated (continuous cp/ccp); frozen toolbox tier1-toolbox-v1 has no rotation route "
               "(same reason as shor_12 on dev); tier 2 is exact Clifford+T only; not run",
    "shor_16": "rotation-dominated (continuous cp/ccp); frozen toolbox tier1-toolbox-v1 has no rotation route "
               "(same reason as shor_12 on dev); tier 2 is exact Clifford+T only; not run",
}
LIBS = {"tier2_final": ("library_final.json", "library_final.sha256"),
        "tier2_lexsec": ("library_lex_secondary_control.json", "library_lex_secondary_control.sha256")}
OUR_ARMS = ("pyzx_fr", "tket_fpo", "tket_fpo_logical", "nam_light_file")      # our runs / authors' Light file
PUBLISHED_ARMS = ("kvdw2020_pyzx_todd", "kvdw2020_pyzx", "best_prev_as_reported_by_kvdw2020", "nam2018_light",
                  "nam2018_heavy", "tpar_as_reported_by_nam2018")
START_ARMS = {
    "pyzx_fr": ["results/v2/bench_runs/run2/circuits/{c}__pyzx_fr.qasm",
                "results/v2/bench_runs/run3_large/circuits/{c}__pyzx_fr.qasm"],
    "tket_fpo": ["results/v2/bench_runs/run2/circuits/{c}__tket_fpo.qasm",
                 "results/v2/bench_runs/run3_large/circuits/{c}__tket_fpo.qasm"],
    "tket_fpo_logical": ["results/v2/bench_runs/run2/circuits/{c}__tket_fpo_logical.qasm",
                         "results/v2/bench_runs/run3_large/circuits/{c}__tket_fpo_logical.qasm"],
    "nam_light_file": ["benchmarks/nam_arith/nam/{c}_light.qasm"],
}
RESEED = (1, 2)


# ============================================================================================ freeze checks
def frozen_checks() -> dict:
    """FROZEN.md file hashes, frozen verifier digest, tier-2 library SHA-256s (content + .sha256 file)."""
    txt = (T1 / "FROZEN.md").read_text()
    pairs = re.findall(r"\| `([^`]+)` \| `([0-9a-f]{64})` \|", txt)
    bad = [f for f, h in pairs if hashlib.sha256((ROOT / f).read_bytes()).hexdigest() != h]
    if not pairs or bad:
        raise RuntimeError(f"FROZEN.md hash mismatch: {bad} (checked {len(pairs)})")
    dig = re.search(r"frozen verifier digest \(circuitevolve.integrity\): `([0-9a-f]{64})`", txt).group(1)
    if integrity.frozen_digest() != dig:
        raise RuntimeError("frozen verifier digest differs from FROZEN.md")
    libs = {}
    for k, (js, sh) in LIBS.items():
        lib = Library.load(T2DIR / js, reverify=True)
        want = (T2DIR / sh).read_text().split()[0]
        if lib.sha256 != want:
            raise RuntimeError(f"{js}: sha {lib.sha256} != {want}")
        libs[k] = lib
    return dict(files_checked=len(pairs), verifier_digest=dig, libraries={k: dict(sha256=v.sha256, n_rules=len(
        v.rules), version=v.version) for k, v in libs.items()}), libs


# ============================================================================================ loading
def manifest_row(name: str) -> dict:
    m = pd.read_csv(BENCH / "MANIFEST.csv")
    return m[m["name"] == name].iloc[0].to_dict()


def load_heldout(name: str):
    if name not in HELDOUT:
        raise ValueError(f"{name} is not a held-out circuit of {SPLIT['version']}")
    row = manifest_row(name)
    dz = [] if pd.isna(row["zero_init_qubits"]) or str(row["zero_init_qubits"]).strip() == "" else \
        [int(x) for x in str(row["zero_init_qubits"]).split()]
    orig, lc = load_logical(BENCH / row["logical_path"], name=name)
    return orig, lc, summarize(lc, dz, name), row


def normalization_check(orig, lc) -> dict:
    """Same rule as experiments/v2_tier1_dev.normalization_check (ccx-normalized vs original QASM)."""
    if lc.n <= 14:
        v = V.verify(lc.to_ir(), orig, "exact")
    else:
        v = V.verify(orig, V.ReferenceSpec.from_circuit(lc.to_ir()), "exact")
    return dict(ok=v.ok, certified=v.certified, method=v.method, reason=v.reason)


def baseline_bars(name: str) -> dict:
    """Best of OUR runs (verified=True rows of baselines_new.csv, arms OUR_ARMS) and best PUBLISHED value
    (KvdW2020 / Nam2018 table numbers), plus what BL.best_classical(name, 0) returns (all comparable arms)."""
    rows = [r for r in csv.DictReader(open(ROOT / "results/v2/baselines_new.csv")) if r["circuit"] == name
            and r["eps"] == "0"]
    ours = {r["arm"]: int(float(r["t_count"])) for r in rows if r["arm"] in OUR_ARMS
            and "verified=True" in (r["notes"] or "")}
    pub = {r["arm"]: int(float(r["t_count"])) for r in rows if r["arm"] in PUBLISHED_ARMS and r["t_count"]}
    heavy = {r["arm"]: (int(float(r["t_count"])), "verified=True" in (r["notes"] or "")) for r in rows
             if r["arm"] == "nam_heavy_file"}
    bo = min(ours.items(), key=lambda kv: (kv[1], kv[0])) if ours else (None, None)
    bp = min(pub.items(), key=lambda kv: (kv[1], kv[0])) if pub else (None, None)
    bc = BL.best_classical(name, 0.0)
    return dict(ours=ours, best_ours_arm=bo[0], best_ours_T=bo[1], published=pub, best_pub_arm=bp[0],
                best_pub_T=bp[1], nam_heavy=heavy,
                best_classical_fn=None if bc is None else dict(t=float(bc["t_count"]), arm=bc["arm"],
                                                               ties=bc["ties"], origin=bc["origin"]))


def start_circuit(name: str, n_logical: int) -> dict:
    """Tier-2 start-circuit rule (circuitevolve.v2.tier2.circuits.start_circuits, applied to a held-out circuit):
    the verified exact Clifford+T output with the lowest (T, gates) among OUR_ARMS whose T equals the CSV value."""
    rows = {r["arm"]: r for r in csv.DictReader(open(ROOT / "results/v2/baselines_new.csv"))
            if r["circuit"] == name and r["eps"] == "0"}
    cands = []
    for arm, pats in START_ARMS.items():
        path = next((ROOT / p.format(c=name) for p in pats if (ROOT / p.format(c=name)).is_file()), None)
        row = rows.get(arm)
        info = dict(arm=arm, path=None if path is None else str(path.relative_to(ROOT)))
        if row is None or path is None:
            info["status"] = "no file / no baseline row"
        elif "verified=True" not in (row.get("notes") or ""):
            info["status"] = "not verified in baselines_new.csv"
        else:
            try:
                g, n = T2.load_qasm(path)
            except (NotExact, ValueError) as e:
                info["status"] = f"not exact Clifford+T ({str(e)[:60]})"
            else:
                t, tot = T2.cost(g)
                info.update(t=t, gates_total=tot, n=n, csv_t=int(float(row["t_count"])))
                info["status"] = "ok" if t == info["csv_t"] and n == n_logical else \
                    f"T mismatch vs CSV {row['t_count']} or n={n} != {n_logical}"
                if info["status"] == "ok":
                    info["_gates"] = g
        cands.append(info)
    ok = [x for x in cands if x["status"] == "ok"]
    if not ok:
        return dict(ok=False, candidates=cands)
    b = min(ok, key=lambda x: (x["t"], x["gates_total"], x["arm"]))
    return dict(ok=True, gates=b["_gates"], n=b["n"], arm=b["arm"], path=b["path"], t=b["t"],
                gates_total=b["gates_total"], candidates=[{k: v for k, v in x.items() if k != "_gates"}
                                                          for x in cands])


# ============================================================================================ verification
def _limits():
    return V.Limits(**DEFAULT_LIMITS)


def verify_ops(gates, n, lc, seed=0) -> dict:
    v = V.verify((T2.to_ops(gates), n), reference_for(lc, ()), "exact", data_map=list(range(lc.n)),
                 limits=_limits(), seed=seed)
    return dict(ok=bool(v.ok), verdict_mode=v.mode, certified=bool(v.certified), method=v.method,
                reason=v.reason, unitary_preserving=bool(v.unitary_preserving))


def reseed_compiled(comp, lc) -> dict:
    """Re-run a sampled verification of a tier-1 circuit with further seeds (labelled; still not a proof)."""
    out = {}
    for sd in RESEED:
        v = V.verify(comp.circuit, reference_for(lc, comp.zero_qubits), comp.mode, data_map=list(range(lc.n)),
                     limits=_limits(), seed=sd)
        out[str(sd)] = dict(ok=bool(v.ok), method=v.method, certified=bool(v.certified), reason=v.reason)
    return out


def reseed_ops(gates, n, lc) -> dict:
    return {str(sd): {k: v for k, v in verify_ops(gates, n, lc, seed=sd).items() if k in ("ok", "method",
                                                                                         "certified", "reason")}
            for sd in RESEED}


def ops_metrics(gates, n, n_data) -> dict:
    m = measure((T2.to_ops(gates), n), data_qubits=n_data)
    return {k: m[k] for k in ("t_count", "t_depth", "qubits", "ancillas", "measurements", "cx", "gates")}


# ============================================================================================ one circuit
def run_circuit(name: str, tag: str = "eval_v1") -> dict:
    out_json = OUT / "per_circuit" / f"{tag}_{name}.json"
    if out_json.exists():
        raise FileExistsError(f"{out_json} exists (append-only; use a new --tag)")
    for sub in ("per_circuit", "logs", "circuits"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    freeze, libs = frozen_checks()
    V.check_integrity()
    rec = dict(circuit=name, tag=tag, budget=BUDGET, freeze=freeze, started=time.strftime("%Y-%m-%d %H:%M:%S"))
    if name in SKIP:
        rec.update(skipped=SKIP[name])
        out_json.write_text(json.dumps(rec, indent=1, default=str))
        return rec
    orig, lc, s, mrow = load_heldout(name)
    rec.update(family=mrow["family"], n=lc.n, ccx=int(mrow["ccx_count"]), declared_zero=list(s.declared_zero)
               if hasattr(s, "declared_zero") else str(mrow["zero_init_qubits"]))
    t0 = time.time()
    rec["normalization"] = dict(normalization_check(orig, lc), seconds=round(time.time() - t0, 1))
    if not rec["normalization"]["ok"]:
        rec["error"] = f"normalization not equivalent: {rec['normalization']['reason']}"
        out_json.write_text(json.dumps(rec, indent=1, default=str))
        return rec
    rec["bars"] = baseline_bars(name)
    arms = []

    # ---------------------------------------------------------------- tier 1 control (frozen, no LLM)
    t0 = time.time()
    ctl = run_control_arm(lc, s, BUDGET, OUT / "logs" / f"{tag}_{name}_control.jsonl", {}, {})
    t_ctl = round(time.time() - t0, 1)
    rec["tier1_control"] = dict(evaluations=ctl.evaluations, seconds=t_ctl, n_ok=sum(bool(r.get("ok"))
                                                                                    for r in ctl.records),
                                records=[{k: r.get(k) for k in ("variant", "global_pass", "ok", "verdict_mode",
                                                                "t_count", "qubits", "measurements", "certified",
                                                                "method", "reason", "seconds")}
                                         for r in ctl.records])
    exact_comp = None
    for mode in ("exact", "relaxed"):
        b = ctl.best.get(mode)
        if b is None:
            arms.append(dict(arm="tier1_control", mode=mode, ok=False, runtime_s=t_ctl,
                             notes=f"no verified {mode} plan in {BUDGET} evaluations"))
            continue
        comp = b.get("_compiled")
        rs = reseed_compiled(comp, lc) if not b["certified"] else None
        (OUT / "circuits" / f"{tag}_{name}__tier1_control_{mode}.qasm").write_text(to_qasm3(comp.circuit))
        arms.append(dict(arm="tier1_control", mode=mode, ok=True, t_count=b["t_count"], t_depth=b["t_depth"],
                         qubits=b["qubits"], ancillas=b["ancillas"], measurements=b["measurements"], cx=b["cx"],
                         gates=b.get("gates"), verdict_mode=b["verdict_mode"], certified=b["certified"],
                         method=b["method"], unitary_preserving=b["unitary_preserving"],
                         zero_qubits=" ".join(map(str, b.get("zero_qubits", []))), variant=b.get("variant"),
                         global_pass=b.get("global_pass"), routes=json.dumps(b.get("plan_compact", {}).get(
                             "routes", {})), found_at_eval=b.get("call"), runtime_s=t_ctl,
                         eval_seconds=b.get("seconds"), reseed=rs))
        if mode == "exact":
            exact_comp = comp

    # ---------------------------------------------------------------- tier 2 on the best classical start circuit
    st = start_circuit(name, lc.n)
    rec["tier2_start"] = {k: v for k, v in st.items() if k != "gates"}
    starts = []
    if st["ok"]:
        starts.append(("tier2", st["gates"], st["n"], f"start={st['arm']} ({st['path']})"))
    else:
        arms.append(dict(arm="tier2_final", mode="exact", ok=False, notes="no eligible exact start circuit"))
    if exact_comp is not None:
        g1, n1 = T2.from_ir(exact_comp.circuit)
        starts.append(("tier1+tier2", g1, n1, "start=tier1_control exact output"))
    for prefix, g0, n0, note in starts:
        for lk, lib in libs.items():
            t0 = time.time()
            res = T2.apply_library(g0, n0, lib)
            t_apply = round(time.time() - t0, 2)
            t0 = time.time()
            ver = verify_ops(res["gates"], n0, lc)
            t_ver = round(time.time() - t0, 1)
            rs = reseed_ops(res["gates"], n0, lc) if ver["ok"] and not ver["certified"] else None
            m = ops_metrics(res["gates"], n0, lc.n)
            arm = lk if prefix == "tier2" else f"tier1+{lk}"
            (OUT / "circuits" / f"{tag}_{name}__{arm}_exact.qasm").write_text(T2.to_qasm(res["gates"], n0))
            arms.append(dict(arm=arm, mode="exact", ok=ver["ok"], **m, verdict_mode=ver["verdict_mode"],
                             certified=ver["certified"], method=ver["method"],
                             unitary_preserving=ver["unitary_preserving"], reason=ver["reason"],
                             t_before=res["cost_before"][0], gates_before=res["cost_before"][1],
                             t_after=res["cost_after"][0], gates_after=res["cost_after"][1],
                             applications=sum(res["apps"].values()), fixpoint=res["fixpoint"],
                             library_sha256=lib.sha256, library_rules=len(lib.rules), runtime_s=t_apply,
                             verify_seconds=t_ver, reseed=rs, notes=note))
    rec["arms"] = arms
    V.check_integrity()
    rec["freeze_after_ok"] = integrity.frozen_digest() == freeze["verifier_digest"]
    rec["seconds"] = round(time.time() - t_start, 1)
    out_json.write_text(json.dumps(rec, indent=1, default=str))
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--circuit", required=True)
    ap.add_argument("--tag", default="eval_v1")
    a = ap.parse_args()
    r = run_circuit(a.circuit, a.tag)
    short = [(x["arm"], x["mode"], x.get("t_count"), x.get("certified")) for x in r.get("arms", [])]
    print(json.dumps(dict(circuit=a.circuit, seconds=r.get("seconds"), skipped=r.get("skipped"),
                          error=r.get("error"), arms=short), default=str))
