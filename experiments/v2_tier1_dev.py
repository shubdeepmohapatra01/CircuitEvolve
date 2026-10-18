"""Tier 1 development run: LLM compilation plans vs NO-LLM control (same evaluation budget) vs best classical.

Platform kernel (env circuitevolve-dev):
    from experiments.v2_tier1_dev import run_api
    run_api(host, tag="dev_v1", calls=8, workers=4)

Writes (append-only; refuses to overwrite an existing tag):
    results/v2/tier1/logs/<tag>_<circuit>_{llm,control}.jsonl    one line per evaluation (prompt, reply, verdict)
    results/v2/tier1/plans/<tag>_<circuit>.json                  best plan per arm x mode (+ metrics)
    results/v2/tier1/circuits/<tag>_<circuit>_<arm>_<mode>.qasm   best verified circuit (OpenQASM 3)
    results/v2/tier1/summaries/<circuit>.json / .txt             recognizer output (what the LLM read)
    results/v2/tier1/<tag>_dev_results.csv                       one row per circuit x arm x mode
    results/v2/tier1/<tag>_run.json                              run metadata (tokens, timings, integrity digests)
Only DEV circuits of split v2-nam-arith-1 are allowed (held-out names raise).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("XDG_CONFIG_HOME", str(ROOT / ".venv" / "xdg"))

import pandas as pd  # noqa: E402

from circuitevolve import integrity  # noqa: E402
from circuitevolve.ir import to_qasm3  # noqa: E402
from circuitevolve.v2 import baselines as BL  # noqa: E402
from circuitevolve.v2 import verify as V  # noqa: E402
from circuitevolve.v2.tier1.loop import run_control_arm, run_llm_arm  # noqa: E402
from circuitevolve.v2.tier1.recognize import load_logical, summarize  # noqa: E402

BENCH = ROOT / "benchmarks" / "nam_arith"
OUT = ROOT / "results" / "v2" / "tier1"
SPLIT = json.loads((BENCH / "split_v2.json").read_text())
DEV = list(SPLIT["dev"])
HELDOUT = set(SPLIT["heldout"]) | set(SPLIT.get("large_optional", []))
SKIP = {"shor_12": "rotation-dominated (cp:490, ccp:150, 5 ccx); toolbox v1 has no rotation route and "
                   "best_classical() has no comparable row; not run"}
TOKEN_CAP = 1_300_000


def dev_circuits():
    return [c for c in DEV if c not in SKIP]


def load_dev(name: str):
    if name in HELDOUT or name not in DEV:
        raise ValueError(f"{name} is not a DEV circuit of split {SPLIT.get('version')}")
    m = pd.read_csv(BENCH / "MANIFEST.csv")
    row = m[m["name"] == name].iloc[0]
    dz = [] if pd.isna(row["zero_init_qubits"]) else [int(x) for x in str(row["zero_init_qubits"]).split()]
    orig, lc = load_logical(BENCH / row["logical_path"], name=name)
    s = summarize(lc, dz, name)
    return orig, lc, s


def normalization_check(orig, lc) -> dict:
    """Normalized (ccx-form) circuit vs the original QASM, exact mode."""
    if lc.n <= 14:
        v = V.verify(lc.to_ir(), orig, "exact")
    else:   # original has h/ccz (not permutation-like); the normalized one is: use it as the reference, sampled
        v = V.verify(orig, V.ReferenceSpec.from_circuit(lc.to_ir()), "exact")
    return dict(ok=v.ok, certified=v.certified, method=v.method, reason=v.reason)


def classical_bar(name: str, tab) -> dict:
    b = BL.best_classical(name, 0.0, tab=tab)
    sel = tab[(tab["circuit"] == name) & (tab["eps_setting"] == "0") & tab["valid"]]
    runs = {a: float(sel[sel["arm"] == a]["t_count"].min()) for a in ("pyzx_fr", "tket_fpo", "nam_light_file",
                                                                       "nam_heavy_file") if (sel["arm"] == a).any()}
    if b is None:
        return dict(t=None, arm=None, text="none on record", runs=runs)
    return dict(t=float(b["t_count"]), arm=b["arm"], ties=b["ties"], origin=b["origin"], runs=runs,
                text=f"{int(b['t_count'])} ({b['arm']}; pyzx_fr={runs.get('pyzx_fr')}, tket_fpo={runs.get('tket_fpo')})")


class TokenGuard:
    """Wraps a backend; refuses calls once the run-wide token total exceeds TOKEN_CAP."""
    lock = threading.Lock()
    total = Counter()

    def __init__(self, inner):
        self.inner = inner
        self.stats = inner.stats

    def __call__(self, prompts):
        with TokenGuard.lock:
            used = TokenGuard.total["input_tokens"] + TokenGuard.total["output_tokens"]
        if used > TOKEN_CAP:
            return [RuntimeError(f"token cap {TOKEN_CAP} reached ({used})") for _ in prompts]
        before = Counter(self.inner.stats)
        out = self.inner(prompts)
        with TokenGuard.lock:
            for k in ("input_tokens", "output_tokens", "calls"):
                TokenGuard.total[k] += self.inner.stats.get(k, 0) - before.get(k, 0)
        return out


def _row(name, arm, mode, rec, bar, extra=None):
    r = dict(circuit=name, arm=arm, mode=mode, ok=rec is not None)
    if rec is not None:
        r.update(t_count=rec["t_count"], t_depth=rec["t_depth"], qubits=rec["qubits"], ancillas=rec["ancillas"],
                 measurements=rec["measurements"], cx=rec["cx"], verdict_mode=rec["verdict_mode"],
                 certified=rec["certified"], method=rec["method"], unitary_preserving=rec["unitary_preserving"],
                 zero_qubits=" ".join(map(str, rec.get("zero_qubits", []))), global_pass=rec.get("global_pass"),
                 routes=json.dumps(rec.get("plan_compact", {}).get("routes", {})), found_at_eval=rec.get("call"),
                 variant=rec.get("variant", ""))
    r.update(best_classical_T=bar["t"], best_classical_arm=bar["arm"], pyzx_fr_T=bar["runs"].get("pyzx_fr"),
             tket_fpo_T=bar["runs"].get("tket_fpo"))
    if rec is not None and bar["t"]:
        r["delta_vs_classical"] = rec["t_count"] - bar["t"]
        r["ratio_vs_classical"] = round(rec["t_count"] / bar["t"], 4)
    if extra:
        r.update(extra)
    return r


def run_circuit(name, tag, complete, calls, tab, log=print):
    t0 = time.time()
    orig, lc, s = load_dev(name)
    norm = normalization_check(orig, lc)
    if not norm["ok"]:
        raise RuntimeError(f"{name}: normalization not equivalent: {norm['reason']}")
    sd = OUT / "summaries"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / f"{name}.json").write_text(json.dumps(s.to_dict(), indent=1, default=str))
    (sd / f"{name}.txt").write_text(s.text(lc))
    bar = classical_bar(name, tab)
    pc, vc = {}, {}
    logs = OUT / "logs"
    llm = run_llm_arm(lc, s, complete, calls, logs / f"{tag}_{name}_llm.jsonl", bar["text"], pc, vc)
    t1 = time.time()
    ctl = run_control_arm(lc, s, llm.evaluations, logs / f"{tag}_{name}_control.jsonl", pc, vc)
    t2 = time.time()
    # control restricted to the task's named heuristic (V1) - reported separately
    v1 = {}
    for rec in ctl.records:
        if rec.get("variant") == "V1" and rec.get("ok"):
            mode = "exact" if rec["verdict_mode"] == "exact" else "relaxed"
            if mode not in v1 or (rec["t_count"], rec["qubits"], rec["t_depth"]) < \
                    (v1[mode]["t_count"], v1[mode]["qubits"], v1[mode]["t_depth"]):
                from circuitevolve.v2.tier1.prompt import compact_plan
                v1[mode] = dict(rec, plan_compact=compact_plan(rec["plan"]), variant="V1")
    rows = []
    for mode in ("exact", "relaxed"):
        rows.append(_row(name, "llm", mode, llm.best.get(mode), bar))
        rows.append(_row(name, "control", mode, ctl.best.get(mode), bar))
        rows.append(_row(name, "control_V1_spec", mode, v1.get(mode), bar))
    rows.append(dict(circuit=name, arm="best_classical", mode="exact", ok=bar["t"] is not None, t_count=bar["t"],
                     verdict_mode="exact", unitary_preserving=True, best_classical_T=bar["t"],
                     best_classical_arm=bar["arm"], pyzx_fr_T=bar["runs"].get("pyzx_fr"),
                     tket_fpo_T=bar["runs"].get("tket_fpo"), routes=json.dumps(bar.get("ties", [])),
                     method="reused (circuitevolve.v2.baselines.best_classical, eps=0)"))
    plans = {}
    cd = OUT / "circuits"
    cd.mkdir(parents=True, exist_ok=True)
    for arm, res in (("llm", llm), ("control", ctl)):
        for mode, rec in res.best.items():
            comp = rec.get("_compiled")
            plans[f"{arm}/{mode}"] = dict(plan=rec["plan"], **{k: rec.get(k) for k in (
                "t_count", "t_depth", "qubits", "ancillas", "measurements", "verdict_mode", "certified", "method",
                "zero_qubits", "routes", "call", "variant", "digest")})
            if comp is not None:
                (cd / f"{tag}_{name}_{arm}_{mode}.qasm").write_text(to_qasm3(comp.circuit))
    (OUT / "plans" / f"{tag}_{name}.json").write_text(json.dumps(dict(
        circuit=name, tag=tag, summary_digest=s.digest, normalization=norm, best_classical=bar, plans=plans),
        indent=1, default=str))
    meta = dict(circuit=name, normalization=norm, llm_evals=llm.evaluations, control_evals=ctl.evaluations,
                llm_tokens=llm.tokens, llm_seconds=round(t1 - t0, 1), control_seconds=round(t2 - t1, 1),
                llm_ok=sum(bool(r.get("ok")) for r in llm.records),
                llm_parse_or_plan_rejects=sum(str(r.get("reason", "")).startswith("plan rejected") for r in llm.records),
                llm_verifier_rejects=sum((not r.get("ok")) and r.get("stage") == "verify" for r in llm.records),
                llm_errors=sum(r.get("stage") == "llm" for r in llm.records))
    log(f"{name}: llm best {({m: r['t_count'] for m, r in llm.best.items()})} control "
        f"{({m: r['t_count'] for m, r in ctl.best.items()})} classical {bar['t']} ({meta['llm_seconds']}s)")
    return rows, meta


def run(complete_factory, tag="dev_v1", calls=8, workers=4, circuits=None, log=print):
    for sub in ("logs", "plans", "circuits", "summaries"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    csv = OUT / f"{tag}_dev_results.csv"
    if csv.exists():
        raise FileExistsError(f"{csv} exists (results are append-only; use a new tag)")
    d0 = integrity.frozen_digest()
    V.check_integrity()
    tab = BL.table()
    names = circuits or dev_circuits()
    t0 = time.time()
    results, errors = {}, {}

    def job(nm):
        try:
            results[nm] = run_circuit(nm, tag, complete_factory(), calls, tab, log)
        except Exception as e:      # recorded, never silently dropped
            import traceback
            errors[nm] = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}"
            log(f"{nm}: ERROR {e}")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(job, names))
    V.check_integrity()
    assert integrity.frozen_digest() == d0
    rows = [r for nm in names if nm in results for r in results[nm][0]]
    for nm, why in SKIP.items():
        if circuits is None:
            rows.append(dict(circuit=nm, arm="skipped", mode="", ok=False, method=why))
    pd.DataFrame(rows).to_csv(csv, index=False)
    meta = dict(tag=tag, calls_per_circuit=calls, workers=workers, circuits=names, skipped=SKIP,
                seconds=round(time.time() - t0, 1), tokens=dict(TokenGuard.total), token_cap=TOKEN_CAP,
                frozen_digest=d0, per_circuit=[results[nm][1] for nm in names if nm in results], errors=errors)
    (OUT / f"{tag}_run.json").write_text(json.dumps(meta, indent=1, default=str))
    return rows, meta


def run_api(host, tag="dev_v1", calls=8, workers=4, circuits=None, max_tokens=4000):
    from circuitevolve.llm_backends import make_api_backend
    model = host.reasoning_model()

    def factory():
        return TokenGuard(make_api_backend(host.llm, model=model, max_tokens=max_tokens, max_concurrency=1))
    rows, meta = run(factory, tag=tag, calls=calls, workers=workers, circuits=circuits)
    meta["model"] = model
    (OUT / f"{tag}_run.json").write_text(json.dumps(meta, indent=1, default=str))
    return rows, meta
