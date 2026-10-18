"""Tier-2 start circuits: for each DEV circuit, the best classical EXACT Clifford+T output.

Candidates (all already computed and verified by the Benchmarks track; nothing is recomputed here):
    pyzx_fr          results/v2/bench_runs/run2/circuits/<c>__pyzx_fr.qasm
    tket_fpo         results/v2/bench_runs/run2/circuits/<c>__tket_fpo.qasm          (skipped if non-pi/4 rotations)
    tket_fpo_logical results/v2/bench_runs/run2/circuits/<c>__tket_fpo_logical.qasm  (same)
    nam_light_file   benchmarks/nam_arith/nam/<c>_light.qasm  (authors' Light output; Heavy is not used: the Heavy
                     qcla_mod_7 file is known to be non-equivalent, and Light == Heavy in T on every dev circuit)
A candidate is eligible only if results/v2/baselines_new.csv marks that (circuit, arm) `verified=True` and the T-count
we count on the loaded file equals the CSV value. The start circuit is the eligible one with the lowest
(T, total gates). shor_12 is excluded from tier 2: it has continuous cp/ccp rotations and no exact Clifford+T
output (MANIFEST.csv), so it is out of tier-2 scope (exact Clifford+T, unitary-preserving).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from ...blocks import REPO
from ..verify import NotExact
from .apply import cost, load_qasm

DEV = ["barenco_tof_3", "barenco_tof_4", "barenco_tof_5", "csla_mux_3", "cuccaro_4", "cuccaro_8", "gf2^4_mult",
       "gf2^5_mult", "gf2^6_mult", "mod5_4", "mod_mult_55", "rc_adder_6", "shor_12", "tof_3", "tof_4", "tof_5",
       "vbe_adder_3"]
EXCLUDED = {"shor_12": "continuous cp/ccp rotations; no exact Clifford+T output exists (out of tier-2 scope)"}
ARMS = {
    "pyzx_fr": "results/v2/bench_runs/run2/circuits/{c}__pyzx_fr.qasm",
    "tket_fpo": "results/v2/bench_runs/run2/circuits/{c}__tket_fpo.qasm",
    "tket_fpo_logical": "results/v2/bench_runs/run2/circuits/{c}__tket_fpo_logical.qasm",
    "nam_light_file": "benchmarks/nam_arith/nam/{c}_light.qasm",
}


def _assert_dev_split():
    sp = json.loads((REPO / "benchmarks/nam_arith/split_v2.json").read_text()) \
        if (REPO / "benchmarks/nam_arith/split_v2.json").is_file() else None
    if sp is None:
        return
    dev = set(sp.get("dev", [])) if isinstance(sp.get("dev"), list) else None
    if dev is not None:
        assert set(DEV) == dev, f"DEV list differs from split_v2.json: {sorted(set(DEV) ^ dev)}"


def baseline_rows() -> dict:
    out = {}
    with open(REPO / "results/v2/baselines_new.csv") as f:
        for r in csv.DictReader(f):
            if r["circuit"] in DEV:
                out[(r["circuit"], r["arm"])] = r
    return out


def start_circuits(names=None) -> dict:
    """{circuit: dict(gates, n, arm, path, t, gates_total, candidates=[...])} for DEV circuits (shor_12 excluded)."""
    _assert_dev_split()
    rows = baseline_rows()
    out = {}
    for c in names or DEV:
        if c not in DEV:
            raise ValueError(f"{c} is not a DEV circuit (held-out circuits may not be used by tier-2 evolution)")
        if c in EXCLUDED:
            continue
        cands = []
        for arm, pat in ARMS.items():
            path = REPO / pat.format(c=c)
            row = rows.get((c, arm))
            info = dict(arm=arm, path=str(path.relative_to(REPO)))
            if row is None or not path.is_file():
                info["status"] = "no file / no baseline row"
            elif "verified=True" not in (row.get("notes") or ""):
                info["status"] = "not verified in baselines_new.csv"
            else:
                try:
                    g, n = load_qasm(path)
                except (NotExact, ValueError) as e:
                    info["status"] = f"not exact Clifford+T ({str(e)[:60]})"
                else:
                    t, tot = cost(g)
                    info.update(t=t, gates_total=tot, n=n, csv_t=int(row["t_count"]))
                    info["status"] = "ok" if t == int(row["t_count"]) else f"T mismatch vs CSV {row['t_count']}"
                    if info["status"] == "ok":
                        info["_gates"] = g
            cands.append(info)
        ok = [x for x in cands if x["status"] == "ok"]
        if not ok:
            raise RuntimeError(f"{c}: no eligible exact start circuit: {cands}")
        best = min(ok, key=lambda x: (x["t"], x["gates_total"], x["arm"]))
        out[c] = dict(gates=best["_gates"], n=best["n"], arm=best["arm"], path=best["path"], t=best["t"],
                      gates_total=best["gates_total"],
                      candidates=[{k: v for k, v in x.items() if k != "_gates"} for x in cands])
    return out
