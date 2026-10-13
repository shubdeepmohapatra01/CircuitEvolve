"""LLM proposer for block rewrites: prompt builder, response handling, and the per-structure search loop.

One prompt per distinct block STRUCTURE (not per block). Each candidate program is
  1. parsed literally (program.py),
  2. materialised on the representative instance (free parameters fitted), verified by verify_block,
  3. if it verifies and is cheaper: exact rules get the >=32-random-sample generality check, then the
     rewrite is tried on EVERY instance of the structure (each instance verified on its own angles),
  4. stored in the RuleLibrary if it improves at least one instance.
Verifier outcomes are fed back in the next round's prompt for that structure. A search.playbook.Playbook
can be passed: its rules are rendered into prompts and its A/B evidence is recorded exactly as in
search/llm.py; reflector calls (if enabled) are counted as LLM calls.
The backend is any `complete(list[str]) -> list[str | Exception]` (search/llm.py make_api_backend).
"""
from __future__ import annotations

import json
import math
import random
import time

from circuitevolve.blocks import verify_block as vb
from circuitevolve.blocks.cost_model import Gridsynth, cost_key, improves, ops_cost
from .program import ParseError, block_program, extract_programs, parse_program, potential_rz
from .rules import RuleLibrary, check_general, try_rewrite

TASK = """You are optimising one block of a fault-tolerant quantum circuit (Clifford+T target).
Every rz(theta) whose angle is NOT a multiple of pi/4 must later be synthesised by gridsynth at
eps = 1e-9, costing about 90-95 T gates each. Gates h, s, sdg, x, z, cx, cz are free; t/tdg cost 1 T;
rz at a multiple of pi/4 costs 0 or 1 T. So the goal is a program with the SAME unitary (up to global
phase) and FEWER non-Clifford rz (then fewer T, then fewer cx)."""

FORMAT = """Program format (one gate per line, local qubits q0..q{nm1}):
  h q0 | s q1 | sdg q1 | x q2 | z q0 | t q0 | tdg q0 | cx q0 q1 | cz q1 q2 | rz(EXPR) q0
EXPR may use: numbers, pi, + - * /, the block's input angles a0..a{km1} (an EXACT rewrite, valid for
all angle values: it is checked on the instance and on 32 random angle vectors), and free parameters
p0, p1, ... (a TEMPLATE: the parameters are fitted numerically for each instance; use them when the new
angles are not simple expressions of the inputs). rz(theta) = diag(e^(-i theta/2), e^(i theta/2));
cx q0 q1 has control q0. The verifier accepts iff the phase-aligned operator-norm distance to the
original block is <= 1e-8 on the actual angles."""


def _vals(angles) -> str:
    return ", ".join(f"a{i}={x:.10g}" for i, x in enumerate(angles))


def build_prompt(rep, instances, base_cost: dict, feedback, rules_text: str = "", k: int = 3) -> str:
    n, kk = rep.n, len(rep.angles)
    prog = block_program(rep.ops, n).to_text()
    others = [b for b in instances if b is not rep][:3]
    inst = "\n".join(f"  instance {j}: {_vals(b.angles)}" for j, b in enumerate([rep] + others))
    fb = ""
    if feedback:
        fb = "Earlier proposals for this block and the verifier's verdicts:\n" + "\n\n".join(
            f"--- verdict: {why}\n{src.strip()}" for src, why in feedback[-6:]) + "\n\n"
    rules = (rules_text + "\n\n") if rules_text else ""
    return f"""{TASK}

{FORMAT.format(nm1=n - 1, km1=max(kk - 1, 0))}

Block ({n} qubits, {kk} input angles, {len(rep.ops)} gates; {len(instances)} block(s) in the circuit share
this structure with different angle values):
```block
{prog}
```
Angle values (radians):
{inst}
Current cost of this instance: {base_cost['rz']} non-Clifford rz, {base_cost['t']} T total, {base_cost['cx']} cx.

{fb}{rules}Propose up to {k} DIFFERENT rewrites with fewer non-Clifford rz. Think about which rotations commute
through the CNOTs, which can merge, and whether the block's unitary has a cheaper decomposition.
Output each rewrite as its own ```block fenced code block containing only program lines; put any
reasoning in plain text outside the fences, at most ~250 words in total (you cannot run code; do not
write simulated outputs). If you believe no cheaper program exists, say so briefly and output nothing."""


def _why(rec, base_cost) -> str:
    if not rec.get("ok"):
        if "reason" in rec:
            return f"rejected ({rec['reason'][:160]})"
        return f"rejected: distance {rec.get('dist', float('nan')):.2e} > 1e-8"
    c = rec["cost"]
    if not improves(c, base_cost):
        return f"verified but not an improvement ({c['rz']} rz / {c['t']} T vs {base_cost['rz']} rz / {base_cost['t']} T; need fewer non-Clifford rz without more T)"
    return f"ACCEPTED: {c['rz']} rz / {c['t']} T (was {base_cost['rz']} rz / {base_cost['t']} T)"


def evaluate_candidate(src: str, rep, instances, gs: Gridsynth, base_costs: dict, eps=vb.EPS_BLOCK,
                       seed: int = 0) -> dict:
    """Parse + verify + generality + apply-to-all. base_costs: block.index -> cost dict."""
    try:
        prog = parse_program(src, rep.n, len(rep.angles))
    except ParseError as e:
        return dict(ok=False, stage="parse", why=f"parse error: {e}")
    if not prog.ops:
        return dict(ok=False, stage="parse", why="empty program")
    base = base_costs[rep.index]
    prz = potential_rz(prog, rep.angles)
    if prz > base["rz"]:
        return dict(ok=False, stage="precheck", prog=prog,
                    why=f"not tried: up to {prz} non-Clifford rz, the block has {base['rz']}")
    rec = try_rewrite(rep, prog, gs, eps=eps, seed=seed)
    out = dict(stage="instance", prog=prog, rep=rec, why=_why(rec, base_costs[rep.index]), ok=False,
               verified=bool(rec.get("ok")))
    if not rec.get("ok") or not improves(rec["cost"], base_costs[rep.index]):
        return out
    general = None
    if prog.kind == "exact":
        g = check_general(rep, prog, eps=eps, seed=seed)
        general = dict(ok=g["ok"], fails=g["fails"], samples=g["samples"], max_dist=g["max_dist"])
    applied = {}
    for b in instances:
        r = rec if b is rep else try_rewrite(b, prog, gs, eps=eps, seed=seed, x0=rec.get("p") or None)
        if r.get("ok") and improves(r["cost"], base_costs[b.index]):
            applied[b.index] = r
    t_saved = sum(base_costs[i]["t"] - r["cost"]["t"] for i, r in applied.items())
    rz_saved = sum(base_costs[i]["rz"] - r["cost"]["rz"] for i, r in applied.items())
    out.update(stage="applied", ok=bool(applied), general=general, applied=applied, t_saved=t_saved,
               rz_saved=rz_saved)
    if general is not None and not general["ok"]:
        out["why"] += f"; NOT general (fails on {general['fails']}/{general['samples']} random angle vectors)"
    out["why"] += f"; applied to {len(applied)}/{len(instances)} instances, saves {t_saved} T"
    return out


def search_structures(groups: dict, gs: Gridsynth, complete, library: RuleLibrary, base_costs: dict,
                      max_calls: int = 12, batch: int = 4, k: int = 3, playbook=None, rng_seed: int = 0,
                      min_rz: int = 2, circuit: str = "", log=None, reflect_every: int = 0,
                      max_rounds_per_struct: int = 2) -> dict:
    """Spend at most max_calls proposer calls (+ reflector calls if reflect_every) over the structure
    groups, most promising first (sum of non-Clifford rz over instances). Returns per-block best
    accepted rewrite {block.index: rec} and stats."""
    rng = random.Random(rng_seed)
    order = sorted((s for s, bl in groups.items() if base_costs[bl[0].index]["rz"] >= min_rz),
                   key=lambda s: -sum(base_costs[b.index]["rz"] for b in groups[s]))
    feedback: dict[str, list] = {s: [] for s in order}
    rounds: dict[str, int] = {s: 0 for s in order}
    solved: set = set()
    best: dict[int, dict] = {}
    stats = dict(calls=0, reflect_calls=0, llm_errors=0, programs=0, parse_errors=0, verified=0,
                 improving=0, rules_added=0, structures_tried=0, structures_eligible=len(order))
    recent_imp, recent_fail = [], []
    log = log if log is not None else []
    while stats["calls"] < max_calls:
        todo = [s for s in order if s not in solved and rounds[s] < max_rounds_per_struct]
        todo.sort(key=lambda s: rounds[s])           # breadth first: new structures before second rounds
        todo = todo[:min(batch, max_calls - stats["calls"])]
        if not todo:
            break
        prompts, shown_hidden = [], []
        for s in todo:
            rep = groups[s][0]
            texts, shown, hidden = (playbook.select(rng) if playbook is not None else ([], [], []))
            rt = playbook.render(texts) if playbook is not None else ""
            prompts.append(build_prompt(rep, groups[s], base_costs[rep.index], feedback[s], rt, k))
            shown_hidden.append((shown, hidden))
        t0 = time.time()
        resps = complete(prompts)
        dt = time.time() - t0
        for s, prompt, resp, (shown, hidden) in zip(todo, prompts, resps, shown_hidden):
            stats["calls"] += 1
            rounds[s] += 1
            if rounds[s] == 1:
                stats["structures_tried"] += 1
            entry = dict(circuit=circuit, sig=s, round=rounds[s], call=stats["calls"], seconds=round(dt, 1),
                         n_instances=len(groups[s]), base_rz=base_costs[groups[s][0].index]["rz"],
                         prompt_chars=len(prompt), candidates=[])
            if isinstance(resp, Exception):
                stats["llm_errors"] += 1
                entry["error"] = str(resp)[:300]
                log.append(entry)
                continue
            entry["response_chars"] = len(resp)
            pc: dict = {}
            srcs = extract_programs(resp, max_programs=k, counts=pc)
            stats["non_program_blocks"] = stats.get("non_program_blocks", 0) + pc.get("non_program_block", 0)
            n_pass = 0
            improved = False
            rep = groups[s][0]
            for src in srcs:
                stats["programs"] += 1
                ev = evaluate_candidate(src, rep, groups[s], gs, base_costs, seed=stats["programs"])
                if ev["stage"] == "parse":
                    stats["parse_errors"] += 1
                if ev.get("verified"):
                    stats["verified"] += 1
                    n_pass += 1
                feedback[s].append((src, ev["why"]))
                cand = dict(src=src, why=ev["why"], stage=ev["stage"])
                if "rep" in ev:
                    cand.update(dist=ev["rep"].get("dist"), cost=ev["rep"].get("cost"),
                                kind=ev["rep"].get("kind"))
                if ev.get("ok"):
                    improved = True
                    stats["improving"] += 1
                    ver = dict(eps_block=vb.EPS_BLOCK, instance_dist=ev["rep"]["dist"],
                               instance_fro=ev["rep"]["fro"], general=ev["general"],
                               instances_verified=len(ev["applied"]),
                               max_instance_dist=max(r["dist"] for r in ev["applied"].values()))
                    gen = bool(ev["general"] and ev["general"]["ok"])
                    before = len(library.rules)
                    rule = library.add(rep, ev["prog"], ver, gen, dict(circuit=circuit, call=stats["calls"]))
                    stats["rules_added"] += len(library.rules) - before
                    rule["gain"][circuit] = dict(blocks=len(ev["applied"]), t_saved=ev["t_saved"],
                                                 rz_saved=ev["rz_saved"])
                    cand.update(rule=rule["id"], t_saved=ev["t_saved"], applied=len(ev["applied"]))
                    for i, r in ev["applied"].items():
                        if i not in best or cost_key(r["cost"]) < cost_key(best[i]["cost"]):
                            best[i] = dict(r, rule=rule["id"])
                    recent_imp.append((base_costs[rep.index]["t"], ev["rep"]["cost"]["t"],
                                       block_program(rep.ops, rep.n).to_text(), src))
                else:
                    recent_fail.append((src, ev["why"]))
                entry["candidates"].append(cand)
            if not srcs:
                feedback[s].append(("(no program)", "the response contained no ```block program"))
            if improved:
                solved.add(s)
            if playbook is not None:
                playbook.record(shown, hidden, len(srcs), n_pass, improved)
                playbook.update_status(stats["calls"])
            log.append(entry)
        if (playbook is not None and reflect_every and not playbook.frozen
                and stats["calls"] % reflect_every < batch and (recent_imp or recent_fail)):
            rp = playbook.reflect_prompt(TASK, recent_imp[-3:], recent_fail[-6:],
                                         {k_: stats[k_] for k_ in ("calls", "programs", "verified", "improving")})
            rr = complete([rp])[0]
            stats["reflect_calls"] += 1
            if not isinstance(rr, Exception):
                applied, errs = playbook.apply_deltas(rr, stats["calls"])
                log.append(dict(circuit=circuit, reflect=True, applied=applied, errors=errs))
            recent_imp, recent_fail = [], []
    return dict(best=best, stats=stats, log=log)
