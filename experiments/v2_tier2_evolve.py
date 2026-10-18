"""Tier-2 experiment: evolve the executable rule library on DEV circuits; LLM arm vs no-LLM enumeration control.

Run inside a Claude Science kernel (host.llm is injected, never imported):

    import sys; sys.path.insert(0, ".")
    from experiments.v2_tier2_evolve import run_llm_arm, run_control_arm
    llm_out = run_llm_arm(host.llm, host.reasoning_model(), tag="run1", generations=15, prompts_per_gen=2)
    ctl_out = run_control_arm(tag="run1", schedule=llm_out["verify_schedule"])

Outputs (append-only, one directory per tag): results/v2/tier2/<tag>/
    {arm}_generations.jsonl  one line per generation (totals, accepted, reason, library sha)
    {arm}_rules.jsonl        one line per proposed rule (verification result, applications, T saved, outcome)
    {arm}_llm_calls.jsonl    (llm arm) one line per call: prompt sha/length, response text, usage
    libraries/{arm}_vK.json  every accepted library version (SHA-256 inside)
DEV circuits only (circuitevolve.v2.tier2.circuits.DEV); held-out circuits are never loaded.
"""
from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path

from circuitevolve import integrity
from circuitevolve.blocks import REPO
from circuitevolve.llm_backends import make_api_backend
from circuitevolve.v2.tier2 import evolve as E
from circuitevolve.v2.tier2.circuits import start_circuits
from circuitevolve.v2.tier2.enumerate_ids import candidate_pool
from circuitevolve.v2.tier2.rules import Library, parse_rules

OUT = REPO / "results/v2/tier2"
CONTROL_SPECS = ((1, 8), (2, 6), (3, 4))


def _outdir(tag):
    d = OUT / tag
    (d / "libraries").mkdir(parents=True, exist_ok=True)
    return d


def _jl(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj, default=str) + "\n")


def _strip(ev):
    return {c: {k: v for k, v in p.items() if k != "gates"} for c, p in ev["per"].items()}


def run_llm_arm(llm, model, tag="run1", generations=15, prompts_per_gen=2, windows_per_prompt=6, seed=0,
                max_tokens=6000, token_cap=1_200_000):
    d = _outdir(tag)
    dig0 = integrity.frozen_digest()
    starts = start_circuits()
    be = make_api_backend(llm, model=model, max_tokens=max_tokens, max_concurrency=prompts_per_gen)
    lib = Library([], "v0", meta=dict(arm="llm"))
    lib.save(d / "libraries/llm_v0.json")
    ev = E.evaluate(lib, starts)
    _jl(d / "llm_generations.jsonl", dict(gen=0, arm="llm", accepted=True, reason="v0 (empty library)",
                                         cand_total_t=ev["total_t"], cand_total_g=ev["total_g"],
                                         lib_sha=lib.sha256, lib_version="v0", per=_strip(ev)))
    rng = random.Random(seed)
    history, known, schedule = [], set(), []
    vk, calls = 0, 0
    for gen in range(1, generations + 1):
        tok = be.stats.get("input_tokens", 0) + be.stats.get("output_tokens", 0)
        if tok > token_cap:
            _jl(d / "llm_generations.jsonl", dict(gen=gen, arm="llm", stopped=f"token cap {tok} > {token_cap}"))
            break
        cur = E.current_circuits(starts, ev)
        prompts = []
        for _ in range(prompts_per_gen):
            W = E.sample_windows(cur, windows_per_prompt, rng)
            prompts.append(E.build_prompt(lib, cur, W, E.feedback_text(history)))
        t0 = time.time()
        res = be(prompts)
        calls += len(prompts)
        proposed = []
        for i, (p, r) in enumerate(zip(prompts, res)):
            text = r if isinstance(r, str) else ""
            rules, errs = parse_rules(text, "llm") if text else ([], [])
            for rr in rules:
                rr.name = f"g{gen}p{i}_{rr.name}"[:48]
            proposed += rules
            _jl(d / "llm_llm_calls.jsonl", dict(gen=gen, idx=i, prompt_sha=hashlib.sha256(p.encode()).hexdigest(),
                                               prompt_chars=len(p), error=None if text else str(r),
                                               n_rules=len(rules), parse_errors=errs, response=text,
                                               seconds=round(time.time() - t0, 1)))
            for name, e in errs:
                history.append(dict(dsl_one_line=f"RULE {name}", outcome=f"PARSE ERROR: {e}"))
        nxt = f"v{vk + 1}"
        lib2, ev2, rec, recs = E.step(lib, ev, starts, proposed, gen, "llm", nxt, known=known)
        schedule.append(rec["n_verify_calls"])
        if rec["accepted"]:
            vk += 1
            lib2.meta = dict(arm="llm", gen=gen)
            lib2.save(d / f"libraries/llm_{nxt}.json")
        lib, ev = lib2, ev2
        rec.update(tokens=dict(be.stats), calls=calls, per=_strip(ev))
        _jl(d / "llm_generations.jsonl", rec)
        for rc in recs:
            _jl(d / "llm_rules.jsonl", dict(gen=gen, **rc))
        history += recs
        print(f"[llm] gen {gen}: proposed {rec['n_proposed']} verified {rec['n_verified']} "
              f"T {rec['prev_total_t']}->{rec['cand_total_t']} accepted={rec['accepted']} tok={tok}", flush=True)
    integrity.check_unchanged(dig0)
    out = dict(final=lib, ev=ev, verify_schedule=schedule, calls=calls, tokens=dict(be.stats))
    json.dump(dict(verify_schedule=schedule, calls=calls, tokens=dict(be.stats), final_sha=lib.sha256,
                   final_version=lib.version), open(d / "llm_summary.json", "w"), indent=1)
    return out


def run_control_arm(tag="run1", schedule=(), seed=0, specs=CONTROL_SPECS, random_samples=20000):
    d = _outdir(tag)
    dig0 = integrity.frozen_digest()
    starts = start_circuits()
    t0 = time.time()
    pool = candidate_pool(specs=specs, random_samples=random_samples, seed=seed)
    for i, r in enumerate(pool):
        r.name = f"enum{i}"
    prop = E.ControlProposer(pool, seed=seed)
    lib = Library([], "v0", meta=dict(arm="control"))
    lib.save(d / "libraries/control_v0.json")
    ev = E.evaluate(lib, starts)
    _jl(d / "control_generations.jsonl", dict(gen=0, arm="control", accepted=True, reason="v0 (empty library)",
                                             cand_total_t=ev["total_t"], cand_total_g=ev["total_g"],
                                             lib_sha=lib.sha256, lib_version="v0", pool_size=len(pool),
                                             pool_t_reducing=sum(1 for r in pool if r.cost_delta()[0] > 0),
                                             pool_seconds=round(time.time() - t0, 1), specs=specs,
                                             random_samples=random_samples, per=_strip(ev)))
    known, vk = set(), 0
    for gen, n in enumerate(schedule, 1):
        cur = E.current_circuits(starts, ev)
        rules, mc = prop.propose(n, cur)
        nxt = f"v{vk + 1}"
        lib2, ev2, rec, recs = E.step(lib, ev, starts, rules, gen, "control", nxt, known=known)
        if rec["accepted"]:
            vk += 1
            lib2.meta = dict(arm="control", gen=gen)
            lib2.save(d / f"libraries/control_{nxt}.json")
        lib, ev = lib2, ev2
        rec.update(per=_strip(ev), matches_of_proposed=sorted(mc.values(), reverse=True))
        _jl(d / "control_generations.jsonl", rec)
        for rc in recs:
            _jl(d / "control_rules.jsonl", dict(gen=gen, **rc))
        print(f"[control] gen {gen}: verified {rec['n_verified']}/{rec['n_verify_calls']} "
              f"T {rec['prev_total_t']}->{rec['cand_total_t']} accepted={rec['accepted']}", flush=True)
    integrity.check_unchanged(dig0)
    json.dump(dict(schedule=list(schedule), final_sha=lib.sha256, final_version=lib.version, pool_size=len(pool)),
              open(d / "control_summary.json", "w"), indent=1)
    return dict(final=lib, ev=ev, pool=pool)


def replay(tag, arm, mode="lex"):
    """Secondary analysis: re-run the acceptance over the RECORDED verified proposals of `arm` with another
    acceptance mode (no new proposals, no new LLM calls). Returns list of per-generation dicts and the library."""
    from circuitevolve.v2.tier2.rules import Rule
    d = OUT / tag
    starts = start_circuits()
    by_gen = {}
    for line in open(d / f"{arm}_rules.jsonl"):
        r = json.loads(line)
        if r.get("verified"):
            by_gen.setdefault(r["gen"], []).append(Rule.from_dict(r["rule"]))
    lib = Library([], "v0")
    ev = E.evaluate(lib, starts)
    out, vk = [], 0
    for gen in sorted(by_gen):
        nxt = f"v{vk + 1}"
        lib2, ev2, rec, _ = E.step(lib, ev, starts, by_gen[gen], gen, arm + "_replay_" + mode, nxt, mode=mode)
        if rec["accepted"]:
            vk += 1
        lib, ev = lib2, ev2
        out.append(dict(gen=gen, accepted=rec["accepted"], total_t=ev["total_t"], total_g=ev["total_g"],
                        reason=rec["reason"], n_rules=len(lib.rules)))
    return out, lib, ev
