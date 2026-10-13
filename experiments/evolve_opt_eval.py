"""EVALUATION run of the frozen optimizer programs (first and only use of the evaluation circuits).

Nothing in circuitevolve/ is modified. This script lifts the two DEVELOPMENT guards in-process only
(blocks.circuit_io.bench_path refusal and evolve_opt.evaluate.check_dev) for the evaluation circuits listed in
benchmarks/split.json ("eval" + "eval_transfer"), and otherwise calls the unchanged evaluator:
  * sandbox.run_program (same child, same toolbox tb-v1, same static check, same limits: time_s per circuit,
    wall 2*time_s+90, 4 GB RSS cap);
  * evaluate.verify_output (ev-v3; frozen verify_block.circuit_check; budget 1e-6; eps_rz 1e-9; slack 1e-8)
    for n <= 20;
  * for n > 20 the frozen check is impossible (circuit_check returns 'skipped'; verify_output would refuse).
    Those outputs are costed and error-ACCOUNTED exactly as verify_output does for n > 10
    (bound = ledger + 1e-8 + #rz * 1e-9) but are flagged numerically_verified = False. They are NOT verified.

Subcommands
  baseline            best_classical() (pyzx / TKET, min(raw, canonical) T at 1e-9) per eval circuit
                      -> results/evolve_opt/eval/baseline_eval.json   (own process: no fork/numpy mixing)
  run <circ,...> [--time-s S] [--workers W] [--programs a,b]
                      -> appends one JSON line per (program, circuit) to results/evolve_opt/eval/runs.jsonl,
                         output ops to results/evolve_opt/eval/outputs/<program>__<circuit>__t<S>.json.gz
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from circuitevolve.blocks import circuit_io  # noqa: E402
from circuitevolve.evolve_opt import EPS_RZ, ERROR_BUDGET, NUMERIC_SLACK, TOOLBOX_VERSION, split  # noqa: E402
from circuitevolve.evolve_opt import evaluate as ev  # noqa: E402
from circuitevolve.evolve_opt.programs import BEST_CLASSICAL_PROGRAM, SEED_PROGRAM  # noqa: E402

OUT = REPO / "results" / "evolve_opt" / "eval"
FROZEN = REPO / "results" / "evolve_opt" / "frozen"
EVAL_SET = list(dict.fromkeys(split.load_split()["eval"] + split.load_split()["eval_transfer"]))

PROGRAMS = {
    "seed_program": SEED_PROGRAM,
    "best_classical_program": BEST_CLASSICAL_PROGRAM,
    "llm_v2_s2": (FROZEN / "v2" / "optimizer_llm_evo_s2_v3.py").read_text(),
    "llm_v1_s0": (FROZEN / "v1" / "optimizer_llm_evo_s0_v3.py").read_text(),
    "control_greedy_s2": (FROZEN / "v1" / "optimizer_control_greedy_s2.py").read_text(),
}
EXPECTED_SHA = {   # frozen/v1, frozen/v2 SHA256SUMS
    "llm_v2_s2": "efacca60548e2ba62794e012a5ef504c69bcd498aed4e5aa9daf8d953638eeab",
    "llm_v1_s0": "d6ccdcd56bcaee77f99be7e5ed6db4caf4f90d4739336c137eca0aa3ed51de3d",
    "control_greedy_s2": "e9b300fc6c642adab0cc19f83e556578101b47b475f838c747a7ac19fe0762e3",
}
for _k, _h in EXPECTED_SHA.items():
    assert hashlib.sha256(PROGRAMS[_k].encode()).hexdigest() == _h, f"frozen program {_k} hash mismatch"


# ------------------------------------------------------------------ lift the development guards (in-process)
_orig_bench_path = circuit_io.bench_path


def _eval_bench_path(name: str):
    stem = name.split("/")[-1].removesuffix(".qasm")
    if stem in EVAL_SET:
        fam = stem.rsplit("_", 1)[0]
        return circuit_io.QASM_DIR / fam / f"{stem}.qasm"
    return _orig_bench_path(name)


def _eval_only(name: str) -> str:
    if name not in EVAL_SET:
        raise PermissionError(f"{name} is not an evaluation circuit (this script evaluates only {EVAL_SET})")
    return name


circuit_io.bench_path = _eval_bench_path
ev.check_dev = _eval_only


# ------------------------------------------------------------------ baseline
def cmd_baseline(names):
    from circuitevolve.blocks.classical import best_classical
    p = OUT / "baseline_eval.json"
    data = json.loads(p.read_text()) if p.exists() else {}
    for nm in names:
        if nm in data:
            continue
        t0 = time.time()
        bc = best_classical(nm, ev.gs(), check=True)
        rec = {}
        for k, v in bc["candidates"].items():
            rec[k] = dict(t=min(v["cost"]["t"], v["cost_raw"]["t"]), t_canonical=v["cost"]["t"],
                          t_raw=v["cost_raw"]["t"], rz=v["cost"]["rz"], cx=v["cost"]["cx"],
                          check=v["check"].get("dist"), method=v["check"].get("method"))
        best = bc["best"]
        data[nm] = dict(n=bc["n"], best=best, t=rec[best]["t"], rz=rec[best]["rz"], candidates=rec,
                        seconds=round(time.time() - t0, 1))
        OUT.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=1, sort_keys=True))
        print(nm, best, rec[best]["t"], rec[best]["rz"], data[nm]["seconds"], flush=True)


# ------------------------------------------------------------------ evaluation of one (program, circuit)
def verify_wide(name: str, out: dict) -> dict:
    """n > 20: same legality checks + error accounting as evaluate._verify_output for n > 10, minus the
    (impossible) statevector check. NOT a verification."""
    from circuitevolve.blocks.cost_model import ops_cost
    from circuitevolve.evolve_opt.sandbox import NUMERIC_LOCK
    from circuitevolve.evolve_opt.toolbox import CLIFFORD_RZ, ops_from_json
    with NUMERIC_LOCK:
        n, _ = ev.original(name)
        if not out.get("ok"):
            return dict(valid=False, reason=out.get("error", "child failed"))
        ops = ops_from_json(out["ops"])
        for g, qs, a in ops:
            if g not in CLIFFORD_RZ or any((not isinstance(q, int)) or q < 0 or q >= n for q in qs) or \
                    len(qs) != (2 if g in ("cx", "cz") else 1) or (g == "cx" and qs[0] == qs[1]):
                return dict(valid=False, reason=f"illegal op {g} {qs}")
            if g == "rz" and not (isinstance(a, float) and math.isfinite(a)):
                return dict(valid=False, reason="non-finite angle")
        ledger = float(out.get("ledger", 0.0))
        if not (math.isfinite(ledger) and ledger >= 0):
            return dict(valid=False, reason="bad ledger")
        cost = ops_cost(ops, ev.gs())
        bound = ledger + NUMERIC_SLACK + cost["rz"] * EPS_RZ
        rec = dict(valid=bound <= ERROR_BUDGET, check=dict(method="skipped (n > 20): NOT numerically verified", n=n),
                   cost=cost, ledger=ledger, bound=bound, charged_s=out.get("charged_s"), cpu_s=out.get("cpu_s"),
                   calls=out.get("calls"))
        if not rec["valid"]:
            rec["reason"] = f"error bound {bound:.3e} > {ERROR_BUDGET:g}"
        return rec


def run_one(prog: str, name: str, time_s: float) -> dict:
    from circuitevolve.evolve_opt.sandbox import run_program
    src = PROGRAMS[prog]
    n, orig = ev.original(name)
    budget = dict(time_s=time_s, error_budget=ERROR_BUDGET, eps_rz=EPS_RZ, numeric_slack=NUMERIC_SLACK, n=n)
    t0 = time.time()
    out = run_program(src, n, orig, budget, wall_s=2 * time_s + 90, mem_mb=4000, cache=True)
    if n <= 20:
        rec = ev.verify_output(name, out)
        rec["numerically_verified"] = bool(rec.get("check", {}).get("method") in ("unitary", "statevector"))
    else:
        rec = verify_wide(name, out)
        rec["numerically_verified"] = False
    if not rec["valid"]:
        rec.setdefault("reason", out.get("error"))
    rec.update(program=prog, program_sha256=ev.source_hash(src), circuit=name, n=n, time_s=time_s,
               wall_s=round(out.get("wall_s", 0.0), 2), child_wall_s=out.get("child_wall_s"),
               eval_version=ev.EVAL_VERSION, toolbox_version=TOOLBOX_VERSION, error_budget=ERROR_BUDGET,
               eps_rz=EPS_RZ, numeric_slack=NUMERIC_SLACK, finished=time.strftime("%Y-%m-%dT%H:%M:%S"),
               parent_wall_s=round(time.time() - t0, 2))
    if out.get("ok"):
        od = OUT / "outputs"
        od.mkdir(parents=True, exist_ok=True)
        f = od / f"{prog}__{name}__t{int(time_s)}.json.gz"
        if not f.exists():
            with gzip.open(f, "wt") as fh:
                json.dump(dict(n=n, ops=out["ops"], ledger=out.get("ledger")), fh)
        rec["output_file"] = str(f.relative_to(REPO))
    return rec


def cmd_run(names, progs, time_s, workers):
    from circuitevolve.integrity import frozen_digest
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / "runs.jsonl"
    digest = frozen_digest()
    jobs = [(p, nm) for nm in names for p in progs]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(run_one, p, nm, time_s): (p, nm) for p, nm in jobs}
        for f in futs:
            p, nm = futs[f]
            try:
                rec = f.result()
            except Exception as e:  # noqa: BLE001
                rec = dict(valid=False, reason=f"evaluation error: {type(e).__name__}: {e}", program=p, circuit=nm,
                           time_s=time_s)
            rec["frozen_digest"] = digest
            with open(log, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            c = rec.get("cost") or {}
            print(f"{p:24s} {nm:9s} valid={rec.get('valid')} T={c.get('t')} rz={c.get('rz')} "
                  f"bound={rec.get('bound')} charged={rec.get('charged_s')} wall={rec.get('wall_s')} "
                  f"reason={rec.get('reason')}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["baseline", "run"])
    ap.add_argument("circuits")
    ap.add_argument("--time-s", type=float, default=ev.DEFAULT_TIME_S)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--programs", default=",".join(PROGRAMS))
    a = ap.parse_args()
    names = [_eval_only(x) for x in a.circuits.split(",")]
    if a.cmd == "baseline":
        cmd_baseline(names)
    else:
        cmd_run(names, a.programs.split(","), a.time_s, a.workers)
