"""End-to-end SMOKE of the block pipeline v1 on small DEV circuits with a small LLM budget.

From a Claude Science kernel on the repo venv:
    from circuitevolve.search.llm import make_api_backend
    from experiments.blocks_smoke import run_smoke
    be = make_api_backend(host.llm, model=host.reasoning_model(), max_tokens=4000, max_concurrency=4)
    run_smoke(be, tag="smoke_v1", plan={"tfim_4": 12, "heisenberg_4": 14, "qft_5": 10})
Writes results/blocks/<tag>/ (refuses to overwrite): summary.json, summary.csv, calls.jsonl,
rules.json + rules.md (library snapshot), playbook.json + playbook.md, <circuit>_out.qasm.
Evaluation circuits are refused by circuit_io.bench_path.
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from circuitevolve.blocks import REPO
from circuitevolve.blocks.circuit_io import ops_to_qasm
from circuitevolve.blocks.cost_model import Gridsynth
from circuitevolve.blocks.pipeline import run_pipeline
from circuitevolve.blocks.rules import RuleLibrary
from circuitevolve.integrity import check_unchanged, frozen_digest
from circuitevolve.search.playbook import Playbook

SEED_RULES = [
    "Phase-polynomial view: between H gates every rz acts on a parity (XOR) of wires, tracked through "
    "the CNOTs; rz gates on the same parity merge into one rz(sum), and an rz on a parity that is later "
    "recreated can be moved there.",
    "If angles coincide numerically in every instance (e.g. a0 == a1), an exact rewrite in a_i cannot "
    "use that (it is checked on random angles); write a template with free parameters p_j instead, "
    "which is fitted per instance.",
    "A 2-qubit unitary needs at most 3 cx; with p_j parameters a template 'Euler(q0) Euler(q1) cx "
    "rz rz cx ...' can replace a 2-qubit stretch that currently holds more rotations than the template.",
]


def run_smoke(backend, tag: str, plan: dict, block_size: int = 3, max_gates: int = 40, batch: int = 4,
              k: int = 3, reflect_every: int = 8, seed: int = 0, library_path: Path | None = None,
              use_playbook: bool = True, **pipeline_kwargs) -> dict:
    """pipeline_kwargs go to run_pipeline (e.g. input_pipeline='tket', use_classical_pass=False for a
    positive control; such runs are not comparisons against the best classical result)."""
    out = REPO / "results" / "blocks" / tag
    assert not out.exists(), f"{out} exists; results are append-only"
    out.mkdir(parents=True)
    digest = frozen_digest()
    gs = Gridsynth()
    lib = RuleLibrary(library_path or (out / "rules.json"))
    pb = Playbook()
    for t in SEED_RULES:
        pb.add(t, 0, origin="seed")
    log: list = []
    rows, full = [], {}
    tok0 = dict(backend.stats)
    t0 = time.time()
    for name, calls in plan.items():
        r = run_pipeline(name, complete=backend, gs=gs, library=lib, block_size=block_size,
                         max_gates=max_gates, max_calls=calls, batch=batch, k=k,
                         playbook=pb if use_playbook else None,
                         rng_seed=seed, log=log, reflect_every=reflect_every if use_playbook else 0,
                         **pipeline_kwargs)
        (out / f"{name}_out.qasm").write_text(ops_to_qasm(r["final_ops"], r["n"]))
        r = {k_: v for k_, v in r.items() if k_ != "final_ops"}
        full[name] = r
        st = r["llm_stats"]
        rows.append(dict(circuit=name, n=r["n"], input_pipeline=r["input_pipeline"],
                         best_classical_pipeline=r["best_classical_pipeline"],
                         input_t=r["input_cost"]["t"], input_rz=r["input_cost"]["rz"],
                         input_t_raw=r["input_cost_raw"]["t"], input_t_canonical=r["input_cost_canonical"]["t"],
                         after_classical_pass_t=r["after_classical_pass"]["t"],
                         output_t=r["output_cost"]["t"], output_rz=r["output_cost"]["rz"],
                         t_saved=r["t_saved"], rz_saved=r["rz_saved"], n_blocks=r["n_blocks"],
                         n_structures=r["n_structures"], llm_calls=st.get("calls", 0),
                         reflect_calls=st.get("reflect_calls", 0), programs=st.get("programs", 0),
                         parse_errors=st.get("parse_errors", 0), verified=st.get("verified", 0),
                         improving=st.get("improving", 0), rules_added=st.get("rules_added", 0),
                         llm_blocks=r["llm_blocks"], library_blocks=r["library_blocks"],
                         whole_check=r["whole_circuit_check"].get("method"),
                         whole_dist=r["whole_circuit_check"].get("dist"), error_bound=r["error_bound"],
                         seconds=r["seconds"]))
        print(json.dumps(rows[-1]), flush=True)
    check_unchanged(digest)
    tok = {k_: backend.stats.get(k_, 0) - tok0.get(k_, 0) for k_ in set(backend.stats) | set(tok0)}
    summary = dict(tag=tag, plan=plan, pipeline_kwargs=pipeline_kwargs, use_playbook=use_playbook, block_size=block_size, max_gates=max_gates, k=k, batch=batch,
                   reflect_every=reflect_every, frozen_digest=digest, backend=tok,
                   wall_s=round(time.time() - t0, 1), circuits=full, rows=rows,
                   n_rules=len(lib.rules))
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    with open(out / "summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(out / "calls.jsonl", "w") as f:
        for e in log:
            f.write(json.dumps(e, default=str) + "\n")
    lib.save(out / "rules.json")
    (out / "rules.md").write_text(lib.to_markdown())
    pb.save(out / "playbook.json")
    (out / "playbook.md").write_text(pb.to_markdown() or "")
    return summary
