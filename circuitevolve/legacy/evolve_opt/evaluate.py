"""Parent-side evaluation: run a program on circuits (sandboxed), VERIFY, cost, fitness, cache.

Verification of one output (all in the parent; the child's claims are not trusted except the error ledger,
which only programs' toolbox calls can change):
  1. gates in {h,x,z,s,sdg,t,tdg,cx,cz,rz}, qubit indices in range, finite angles;
  2. frozen whole-circuit check against the ORIGINAL qseed circuit (blocks/verify_block.circuit_check):
     n <= 10 dense unitary (phase-aligned operator norm d), 10 < n <= 20 four Haar-random statevectors;
  3. error accounting (total budget 1e-6):
       n <= 10 : bound = max(d, ledger) + #rz * eps_rz                     (d is an operator-norm distance)
       n  > 10 : bound = ledger + NUMERIC_SLACK + #rz * eps_rz, and the statevector distance (a lower bound on
                 the operator distance) must itself be <= ledger + NUMERIC_SLACK (catches wrong outputs)
     valid iff bound <= 1e-6.
  4. T-count recomputed by the parent (gridsynth at eps_rz = 1e-9, angles reduced to [-pi, pi]).
Fitness (lexicographic): (all circuits valid) -> geometric mean over circuits of T(program) / T(best classical)
-> total charged CPU seconds.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import EPS_RZ, ERROR_BUDGET, NUMERIC_SLACK, TOOLBOX_VERSION
from .split import check_dev
from .toolbox import CACHE_ROOT, CLIFFORD_RZ, _atomic_write, _read_json, gridsynth, ops_from_json, ops_to_json
from circuitevolve.blocks import REPO

EVAL_VERSION = "ev-v3"     # v3: spawn+verify lock (v1/v2 verdicts from multi-worker evaluation were unreliable)
BASELINE_PATH = REPO / "results" / "evolve_opt" / "baseline_dev.json"
DEFAULT_TIME_S = 300.0     # charged CPU seconds per circuit (seed on hhl_8: ~99 s)

_GS = None


def gs():
    global _GS
    if _GS is None:
        _GS = gridsynth()
    return _GS


# ------------------------------------------------------------------------------ references
def original(name: str) -> tuple[int, list]:
    """(n, ops json) of the ORIGINAL qseed circuit (U3+CX; shor via qiskit opt0), cached."""
    check_dev(name)
    p = CACHE_ROOT / "orig" / f"{name}.json"
    d = _read_json(p)
    if d is None:
        from circuitevolve.blocks.circuit_io import bqskit_to_ops, load_u3cx
        circ, note = load_u3cx(name)
        d = dict(n=circ.num_qudits, ops=ops_to_json(bqskit_to_ops(circ)), note=note)
        _atomic_write(p, json.dumps(d))
    return d["n"], d["ops"]


def baseline(names=None, compute_missing: bool = True) -> dict:
    """Best classical reference per dev circuit: min over pyzx / TKET of min(raw, canonical) T at 1e-9
    (blocks.classical.best_classical, the phase-0 / block-pipeline definition). Stored once in
    results/evolve_opt/baseline_dev.json (append-only: existing entries are never rewritten)."""
    from circuitevolve.blocks.classical import best_classical
    data = _read_json(BASELINE_PATH) or {}
    todo = [n for n in (names or []) if n not in data]
    if todo and compute_missing:
        for nm in todo:
            check_dev(nm)
            t0 = time.time()
            bc = best_classical(nm, gs(), check=True)
            rec = {}
            for k, v in bc["candidates"].items():
                rec[k] = dict(t=min(v["cost"]["t"], v["cost_raw"]["t"]), rz=v["cost"]["rz"], cx=v["cost"]["cx"],
                              check=v["check"].get("dist"), method=v["check"].get("method"))
            best = bc["best"]
            data[nm] = dict(n=bc["n"], best=best, t=rec[best]["t"], rz=rec[best]["rz"], candidates=rec,
                            seconds=round(time.time() - t0, 1))
            _atomic_write(BASELINE_PATH, json.dumps(data, indent=1, sort_keys=True))
    return data


# ------------------------------------------------------------------------------ verification
def verify_output(name: str, out: dict) -> dict:
    """Parent-side verification and costing of one child result (see module docstring).
    Runs under sandbox.NUMERIC_LOCK, which is also held while children are spawned: numpy distances
    computed while another thread forks a subprocess (or while other threads verify) came out WRONG on
    this machine (heisenberg_8: 0.74 instead of 3.5e-14; qft_8: 1.8 instead of 3e-15), 2026-10-11."""
    from .sandbox import NUMERIC_LOCK
    with NUMERIC_LOCK:
        return _verify_output(name, out)


def _verify_output(name: str, out: dict) -> dict:
    from circuitevolve.blocks import verify_block as vb
    from circuitevolve.blocks.cost_model import ops_cost
    n, orig = original(name)
    if not out.get("ok"):
        return dict(valid=False, reason=out.get("error", "child failed"))
    try:
        ops = ops_from_json(out["ops"])
    except Exception as e:
        return dict(valid=False, reason=f"bad ops: {e}")
    for g, qs, a in ops:
        if g not in CLIFFORD_RZ or any((not isinstance(q, int)) or q < 0 or q >= n for q in qs) or \
                len(qs) != (2 if g in ("cx", "cz") else 1) or (g == "cx" and qs[0] == qs[1]):
            return dict(valid=False, reason=f"illegal op {g} {qs}")
        if g == "rz" and not (isinstance(a, float) and math.isfinite(a)):
            return dict(valid=False, reason="non-finite angle")
    ledger = float(out.get("ledger", 0.0))
    if not (math.isfinite(ledger) and ledger >= 0):
        return dict(valid=False, reason="bad ledger")
    chk = vb.circuit_check(ops_from_json(orig), ops, n)
    if chk.get("method") == "skipped":
        return dict(valid=False, reason=f"n = {n} > 20: no whole-circuit check possible")
    cost = ops_cost(ops, gs())
    d = float(chk["dist"])
    if chk["method"] == "unitary":
        bound = max(d, ledger) + cost["rz"] * EPS_RZ
    else:
        if not d <= ledger + NUMERIC_SLACK:
            return dict(valid=False, reason=f"statevector distance {d:.3e} > ledger {ledger:.3e} + slack",
                        check=chk, cost=cost)
        bound = ledger + NUMERIC_SLACK + cost["rz"] * EPS_RZ
    rec = dict(valid=bound <= ERROR_BUDGET, check=chk, cost=cost, ledger=ledger, bound=bound,
               charged_s=out.get("charged_s"), cpu_s=out.get("cpu_s"), calls=out.get("calls"))
    if not rec["valid"]:
        rec["reason"] = f"error bound {bound:.3e} > {ERROR_BUDGET:g}"
    return rec


# ------------------------------------------------------------------------------ evaluation
def source_hash(src: str) -> str:
    return hashlib.sha256(src.encode()).hexdigest()


def eval_key(src: str, name: str, time_s: float) -> str:
    from circuitevolve.integrity import frozen_digest
    return hashlib.sha256(json.dumps([EVAL_VERSION, TOOLBOX_VERSION, frozen_digest(), time_s, name,
                                      source_hash(src)]).encode()).hexdigest()


def evaluate_circuit(src: str, name: str, time_s: float = DEFAULT_TIME_S, use_cache: bool = True,
                     tool_cache: bool = True, mem_mb: int = 4000) -> dict:
    from .sandbox import run_program
    key = eval_key(src, name, time_s)
    p = CACHE_ROOT / "evals" / key[:2] / f"{key}.json"
    if use_cache:
        hit = _read_json(p)
        if hit is not None:
            hit["cached"] = True
            return hit
    n, orig = original(name)
    budget = dict(time_s=time_s, error_budget=ERROR_BUDGET, eps_rz=EPS_RZ, numeric_slack=NUMERIC_SLACK, n=n)
    out = run_program(src, n, orig, budget, wall_s=2 * time_s + 90, mem_mb=mem_mb, cache=tool_cache)
    rec = verify_output(name, out)
    rec.update(circuit=name, n=n, wall_s=round(out.get("wall_s", 0.0), 2))
    if not rec["valid"]:
        rec.setdefault("reason", out.get("error"))
    _atomic_write(p, json.dumps(rec))
    rec["cached"] = False
    return rec


def fitness(results: dict, names, ref: dict) -> dict:
    """results: name -> verify record. Lexicographic key: (invalid?, geomean T ratio, charged seconds)."""
    names = list(names)
    valid = all(results.get(nm, {}).get("valid") for nm in names)
    ratios = {nm: results[nm]["cost"]["t"] / ref[nm]["t"] for nm in names if results.get(nm, {}).get("valid")}
    runtime = sum(float(results[nm].get("charged_s") or 0.0) for nm in names if nm in results)
    gm = math.exp(sum(math.log(r) for r in ratios.values()) / len(ratios)) if valid and ratios else float("inf")
    return dict(valid=valid, geomean=gm, runtime=round(runtime, 2), ratios=ratios,
                t={nm: results[nm]["cost"]["t"] for nm in names if results.get(nm, {}).get("valid")},
                key=[0 if valid else 1, gm, round(runtime, 2)],
                failures={nm: results.get(nm, {}).get("reason") for nm in names if not results.get(nm, {}).get("valid")})


def evaluate_program(src: str, names, ref: dict | None = None, workers: int = 4, time_s: float = DEFAULT_TIME_S,
                     use_cache: bool = True, stop_on_invalid: bool = False) -> dict:
    """Run + verify a program on every circuit in `names` (in parallel subprocesses). Returns
    {'results': {name: record}, 'fitness': {...}, 'seconds'}. Static-check failures never start a process."""
    from .sandbox import StaticCheckError, static_check
    names = list(names)
    ref = ref if ref is not None else baseline(names)
    t0 = time.time()
    try:
        static_check(src)
    except StaticCheckError as e:
        res = {nm: dict(valid=False, reason=f"static check: {e}", circuit=nm) for nm in names}
        return dict(results=res, fitness=fitness(res, names, ref), seconds=0.0, static_error=str(e))
    res = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {nm: ex.submit(evaluate_circuit, src, nm, time_s, use_cache) for nm in names}
        for nm, f in futs.items():
            try:
                res[nm] = f.result()
            except Exception as e:                     # parent-side failure is a failure of this candidate
                res[nm] = dict(valid=False, reason=f"evaluation error: {type(e).__name__}: {e}", circuit=nm)
    return dict(results=res, fitness=fitness(res, names, ref), seconds=round(time.time() - t0, 1))


def key_lt(a, b) -> bool:
    return tuple(a) < tuple(b)
