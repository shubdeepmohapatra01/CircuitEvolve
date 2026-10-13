"""End-to-end block pipeline (v1).

  qseed QASM -> best classical Clifford+Rz (pyzx | TKET, lower T)            classical.py
             -> QuickPartitioner(3) blocks, windows of <= 40 gates          partition.py
             -> deterministic in-block passes (verified per block)         passes.py
             -> rule library applied to every block of a known structure   rules.py
             -> LLM proposals per distinct structure (budgeted)            proposer.py
             -> reassembly; whole-circuit check vs the ORIGINAL qseed circuit (verify_block.circuit_check)
Error bound reported: d(input, original) [measured] + sum of accepted block distances + #rz * eps_rz.
Every block keeps its original ops unless a verified, strictly cheaper rewrite exists.
"""
from __future__ import annotations

import time

from circuitevolve.blocks import verify_block as vb
from circuitevolve.blocks.classical import best_classical
from circuitevolve.blocks.cost_model import EPS_RZ, Gridsynth, canonicalize, cost_key, improves, ops_cost
from circuitevolve.blocks.partition import group, make_block, partition, reassemble, to_global
from circuitevolve.blocks.passes import classical_pass
from .rules import RuleLibrary


def run_pipeline(name: str, complete=None, gs: Gridsynth | None = None, library: RuleLibrary | None = None,
                 block_size: int = 3, max_gates: int = 40, max_calls: int = 12, batch: int = 4, k: int = 3,
                 playbook=None, use_classical_pass: bool = True, rng_seed: int = 0, log=None,
                 reflect_every: int = 0, max_rounds_per_struct: int = 2, check: bool = True,
                 input_pipeline: str | None = None, global_fold: bool = False) -> dict:
    """input_pipeline=None uses the best classical result; 'tket'/'pyzx'/'minrz' force one (controls
    only: gains against a forced, non-best input are NOT gains against the best classical result)."""
    t0 = time.time()
    gs = gs or Gridsynth()
    library = library if library is not None else RuleLibrary()
    bc = best_classical(name, gs, check=check)
    n, src = bc["n"], (input_pipeline or bc["best"])
    # canonical input: rz angles reduced to [-pi, pi] (exact up to global phase). The BASELINE is the
    # lower of the phase-0 count (raw angles) and the canonical count, so angle reduction is never a gain.
    inp = canonicalize(bc["candidates"][src]["ops"])
    raw_cost = bc["candidates"][src]["cost_raw"]
    can_cost = ops_cost(inp, gs)
    in_cost = min((raw_cost, can_cost), key=lambda c: c["t"])
    fold_dist = 0.0
    if global_fold:       # optional whole-circuit phase fold + 1q resynthesis before partitioning
        from circuitevolve.blocks.passes import classical_pass as _cp
        folded = _cp(inp, n)
        if improves(ops_cost(folded, gs), ops_cost(inp, gs)):
            chk0 = vb.circuit_check(inp, folded, n)
            if chk0.get("dist", 1.0) <= 1e-8:
                fold_dist, inp = chk0["dist"], folded
    fold_cost = ops_cost(inp, gs)
    raw_blocks = partition(inp, n, block_size, max_gates)

    # 1. deterministic in-block passes
    blocks, block_err, cls_changed = [], {}, 0
    for b in raw_blocks:
        new = classical_pass(b.ops, b.n) if use_classical_pass else b.ops
        if new != b.ops:
            v = vb.verify_instance(b.ops, new, b.n)
            if v["ok"] and improves(ops_cost(new, gs), ops_cost(b.ops, gs)):
                nb = make_block(b.index, to_global(b, new), b.part, b.window)
                nb.meta["classical_dist"] = v["dist"]
                block_err[b.index] = v["dist"]
                blocks.append(nb)
                cls_changed += 1
                continue
        blocks.append(b)
    after_cls = reassemble(blocks)
    cls_cost = ops_cost(after_cls, gs)
    base_costs = {b.index: ops_cost(b.ops, gs) for b in blocks}
    groups = group(blocks)

    # 2. library rules on every block with a known structure
    final_local = {b.index: b.ops for b in blocks}
    lib_applied = {}
    for b in blocks:
        r = library.apply(b, gs, base_costs[b.index])
        if r:
            lib_applied[b.index] = r

    # 3. LLM proposals per distinct structure
    llm = dict(best={}, stats={}, log=[])
    if complete is not None and max_calls > 0:
        from .proposer import search_structures
        unsolved = {s: bl for s, bl in groups.items() if not any(b.index in lib_applied for b in bl)}
        llm = search_structures(unsolved, gs, complete, library, base_costs, max_calls=max_calls, batch=batch,
                                k=k, playbook=playbook, rng_seed=rng_seed, circuit=name, log=log,
                                reflect_every=reflect_every, max_rounds_per_struct=max_rounds_per_struct)
    chosen = {}
    for src_name, recs in (("library", lib_applied), ("llm", llm["best"])):
        for i, r in recs.items():
            if i not in chosen or cost_key(r["cost"]) < cost_key(chosen[i][1]["cost"]):
                chosen[i] = (src_name, r)
    for i, (_, r) in chosen.items():
        final_local[i] = r["ops"]
        block_err[i] = block_err.get(i, 0.0) + r["dist"]

    # 4. reassembly + whole-circuit check against the ORIGINAL qseed circuit
    final = []
    for b in blocks:
        final.extend(to_global(b, final_local[b.index]))
    out_cost = ops_cost(final, gs)
    chk = vb.circuit_check(bc["original"], final, n) if check else dict(method="skipped")
    in_dist = bc["candidates"][src].get("check", {}).get("dist")
    bound = (in_dist or 0.0) + fold_dist + sum(block_err.values()) + out_cost["rz"] * EPS_RZ
    rules_used = sorted({r.get("rule") for _, r in chosen.values() if r.get("rule")})
    return dict(
        circuit=name, n=n, input_pipeline=src, best_classical_pipeline=bc["best"], block_size=block_size, max_gates=max_gates,
        classical={k_: dict(raw=v["cost_raw"], canonical=v["cost"]) for k_, v in bc["candidates"].items()},
        input_cost=in_cost, input_cost_raw=raw_cost, input_cost_canonical=can_cost,
        global_fold=global_fold, after_global_fold=fold_cost if global_fold else None, after_classical_pass=cls_cost, output_cost=out_cost,
        t_saved=in_cost["t"] - out_cost["t"], rz_saved=in_cost["rz"] - out_cost["rz"],
        t_saved_classical_pass=in_cost["t"] - cls_cost["t"],
        n_blocks=len(blocks), n_structures=len(groups), classical_pass_blocks=cls_changed,
        library_blocks=sum(1 for s, _ in chosen.values() if s == "library"),
        llm_blocks=sum(1 for s, _ in chosen.values() if s == "llm"), rules_used=rules_used,
        input_dist_to_original=in_dist, sum_block_dist=sum(block_err.values()),
        error_bound=bound, whole_circuit_check=chk, llm_stats=llm["stats"],
        seconds=round(time.time() - t0, 1), final_ops=final)
