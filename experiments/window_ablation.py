"""Playbook ablation for the window core: does a learned shared playbook help on HELD-OUT circuits?

Protocol (results/window_runs/ablation_v1/REPORT.md; docs/CORE.md "Playbook ablation"):
  * every run: eps_total = 1e-3, TKET FullPeepholeOptimise input (core.circuit.load_input), ledger v1, canonical
    T (core.metric, BQSKit convention), in-platform backend host.llm with ONE pinned model (the reasoning
    model resolved once), thinking disabled, max_tokens 2000, batch 5, archive 4, p_best 0.7,
    windows ranked by T-cost with seed-dependent tie order (WindowLoop(seeded_ties=True));
  * step 1 (learn): ONE fresh playbook playbooks/dev_v1.json, evidence = accepted AND T reduced, learned in the
    fixed order DEV on development circuits only, 33 LLM calls per circuit (30 proposer + reflector every 10
    proposer calls), seed 0; the loop snapshots the playbook after every circuit (<tag>_playbook.{json,md});
    then frozen (SHA-256 in FROZEN.sha256);
  * step 2 (placebo): playbooks/placebo_v1.json, same number of ACTIVE rules, generic task-agnostic text,
    rendered by the same Playbook.render path; frozen and hashed;
  * step 3 (ablation): HELDOUT x ARMS {none, learned, placebo} x seeds, 20 proposer calls each, no reflector
    (frozen playbooks; the none arm has no playbook), so LLM calls are matched exactly; the playbook files are
    re-hashed before every run; every best circuit is checked against the ORIGINAL qseed circuit (loop summary
    final_check_vs_original); one JSON line per LLM call in results/window_runs/ablation_v1/<tag>.jsonl;
  * no-LLM control: the same-Pauli merge rule (experiments/window_pmerge_control.run_one) once per circuit.

Usage from a platform kernel (env circuitevolve-dev, where `host` exists):
    from experiments.window_ablation import learn_dev, run_ablation, run_control
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from circuitevolve.blocks.cost_model import CACHE_DIR  # noqa: E402
from circuitevolve.core.circuit import load_input, original_ops  # noqa: E402
from circuitevolve.core.loop import WindowLoop  # noqa: E402
from circuitevolve.core.metric import BqskitTMetric  # noqa: E402
from circuitevolve.search.playbook import Playbook  # noqa: E402

EPS = 1e-3
DEV = ("qft_4", "qft_5", "qft_6", "qft_7", "qpe_6", "qae_11", "qae_15")
HELDOUT = ("qft_8", "qpe_8", "qae_13", "hhl_8")
ARMS = ("none", "learned", "placebo")
OUT = REPO / "results" / "window_runs" / "ablation_v1"
DEV_PB = REPO / "playbooks" / "dev_v1.json"
PLACEBO_PB = REPO / "playbooks" / "placebo_v1.json"
FROZEN = OUT / "FROZEN.sha256"
CACHE = CACHE_DIR / "bqskit_conv_ablation"      # own gridsynth cache (another track may write the shared one)
COMMON = dict(batch=5, archive_size=4, p_best=0.7, ledger_rule="v1", seeded_ties=True)
MAX_TOKENS = 2000
DEV_CALLS, DEV_REFLECT_EVERY = 33, 10
HO_CALLS = 20


def sha256(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _cache():
    if not CACHE.exists():
        src = CACHE_DIR / "bqskit_conv"
        if src.is_dir():
            shutil.copytree(src, CACHE)
        CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE


def _backend(host, model):
    from circuitevolve.llm_backends import make_api_backend
    return make_api_backend(host.llm, model=model, max_tokens=MAX_TOKENS, max_concurrency=COMMON["batch"])


def _loop(name, be, pb, tag, n_calls, reflect_every, seed):
    circ = load_input(name)
    orig, n = original_ops(name)
    assert n == circ.n
    lp = WindowLoop(circ, orig, EPS, be, playbook=pb, tag=tag, runs_dir=OUT, n_calls=n_calls,
                    reflect_every=reflect_every, seed=seed, **COMMON)
    lp.metric = BqskitTMetric(EPS, cache_dir=_cache())
    return lp


def _record(s, extra) -> dict:
    bs = s.get("backend_stats", {})
    return dict(extra, tag=s["tag"], name=s["name"], n=s["n"], t_before=s["t_before"], t_after=s["t_after"],
                rz=(s["before"]["rz"], s["after"]["rz"]), calls=s["calls"], stats=s["stats"],
                tokens=dict(input=bs.get("input_tokens", 0), output=bs.get("output_tokens", 0)),
                backend=dict(bs), final_check=s["final_check_vs_original"], bound=s["ledger"]["bound"],
                seconds=s["seconds"], playbook=s.get("playbook"))


def _done(progress: Path) -> set:
    if not progress.exists():
        return set()
    return {json.loads(x)["tag"] for x in progress.read_text().splitlines() if x.strip()}


def learn_dev(host, model: str, order=DEV, seed: int = 0) -> list:
    """Step 1. Resumable: skips tags already in _dev_progress.jsonl and continues the shared playbook file."""
    OUT.mkdir(parents=True, exist_ok=True)
    prog = OUT / "_dev_progress.jsonl"
    done, res = _done(prog), []
    for name in order:
        tag = f"dev_{name}_e3"
        if tag in done:
            continue
        pb = Playbook.load(DEV_PB) if DEV_PB.exists() else Playbook(evidence="improvement")
        assert pb.evidence == "improvement" and not pb.frozen
        be = _backend(host, model)
        lp = _loop(name, be, pb, tag, DEV_CALLS, DEV_REFLECT_EVERY, seed)
        s = lp.run()
        pb.save(DEV_PB)
        rec = _record(s, dict(step="learn", arm="learning", seed=seed, model=model, playbook_sha256=sha256(DEV_PB)))
        with prog.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        res.append(rec)
    return res


def frozen_hashes() -> dict:
    return dict(line.split()[::-1] for line in FROZEN.read_text().splitlines() if line.strip()) if FROZEN.exists() else {}


def _arm_playbook(arm):
    if arm == "none":
        return None, None
    p = DEV_PB if arm == "learned" else PLACEBO_PB
    want = frozen_hashes().get(p.name)
    got = sha256(p)
    if want is None or want != got:
        raise RuntimeError(f"{p.name}: sha256 {got} does not match FROZEN.sha256 ({want})")
    pb = Playbook.load(p, frozen=True)
    return pb, got


def run_ablation(host, model: str, circuits=HELDOUT, arms=ARMS, seeds=(0, 1, 2), progress_cb=None,
                 tag_suffix: str = "", rerun_of: str | None = None) -> list:
    """Step 3. Order: seed-major, then circuit, then arm, so a budget cut always drops whole seeds for all arms.
    Resumable via _ablation_progress.jsonl. A run whose LLM calls failed for an infrastructure reason (e.g. the
    per-frame host.llm token ceiling) is re-run under a NEW tag (tag_suffix, e.g. "_rerun"; logs are append-only)
    with rerun_of naming the reason; the report uses the rerun and lists the invalid original."""
    prog = OUT / "_ablation_progress.jsonl"
    done, res = _done(prog), []
    for seed in seeds:
        for name in circuits:
            for arm in arms:
                tag = f"ho_{name}_{arm}_s{seed}{tag_suffix}"
                if tag in done:
                    continue
                pb, h = _arm_playbook(arm)
                be = _backend(host, model)
                lp = _loop(name, be, pb, tag, HO_CALLS, 0, seed)
                t0 = time.time()
                s = lp.run()
                if h is not None:
                    assert sha256(DEV_PB if arm == "learned" else PLACEBO_PB) == h      # unchanged by the run
                rec = _record(s, dict(step="ablation", arm=arm, seed=seed, model=model, playbook_sha256=h,
                                      wall=round(time.time() - t0, 1), rerun_of=rerun_of))
                rec["calls_to_best"] = calls_to_best(OUT / f"{tag}.jsonl")
                with prog.open("a") as f:
                    f.write(json.dumps(rec, default=str) + "\n")
                res.append(rec)
                if progress_cb:
                    progress_cb(rec)
    return res


def calls_to_best(jsonl: Path):
    """LLM call index of the accepted proposal that first reached the final best T (None if nothing improved)."""
    lines = [json.loads(x) for x in jsonl.read_text().splitlines()]
    end = next(x for x in lines if x["kind"] == "end")["summary"]
    if end["t_after"] >= end["t_before"]:
        return None
    hits = [x["call"] for x in lines if x["kind"] == "propose" and x.get("accepted") and x.get("t_after") is not None
            and x["t_after"] <= end["t_after"]]
    return min(hits) if hits else None


def run_control(circuits=HELDOUT) -> dict:
    """No-LLM same-Pauli merge control, once per held-out circuit (refused if the output exists)."""
    from experiments.window_pmerge_control import run_one
    out = OUT / "control_pmerge.json"
    metric = BqskitTMetric(1.0, cache_dir=CACHE_DIR / "bqskit_conv_control_ablation")
    rows = [run_one(c, EPS, metric) for c in circuits]
    d = dict(description="experiments/window_pmerge_control.run_one at eps 1e-3 (no LLM, same windows, frozen "
                         "verifier, ledger v1, same metric); final circuit checked vs the original", rows=rows)
    with out.open("x") as f:
        json.dump(d, f, indent=1)
    return d
