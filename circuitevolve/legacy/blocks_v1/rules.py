"""Persistent library of verified block rewrite rules, and their application to blocks.

A rule maps a structure signature (partition.structure_text, angles abstracted) to a replacement
program (program.py text) over the instance angles a_i (exact rule) and/or free parameters p_j
(parametric template, fitted per instance). Every APPLICATION is verified on the concrete instance by
verify_block (FROZEN); the library only decides what is tried, never what is accepted.

JSON layout (playbooks/blocks/rules.json by default; results snapshots are append-only copies):
  {"version": 1, "eps_block": 1e-8, "rules": [
     {"id", "sig", "structure", "n", "k", "replacement", "kind": "exact"|"parametric", "n_params",
      "general": bool (exact rules: passed the >=32-sample check), "verification": {...},
      "gain": {"<circuit>": {"blocks": int, "t_saved": int, "rz_saved": int}},
      "origin": {...}, "created": iso time}]}
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from circuitevolve.blocks import REPO
from circuitevolve.blocks import verify_block as vb
from circuitevolve.blocks.cost_model import Gridsynth, cost_key, improves, ops_cost
from .program import ParseError, Program, block_program, fit_params, parse_program

DEFAULT_PATH = REPO / "playbooks" / "blocks" / "rules.json"


def try_rewrite(block, prog: Program, gs: Gridsynth, eps: float = vb.EPS_BLOCK, fit_restarts: int = 6,
                seed: int = 0, x0=None) -> dict:
    """Materialise `prog` on `block`'s instance (fitting p_j if any), verify, and cost it.
    Returns a record with ok, ops (local), dist, cost, p."""
    rec: dict = dict(kind=prog.kind)
    try:
        p = []
        if prog.n_params:
            target = vb.unitary(block.ops, block.n)
            p, d_fit = fit_params(prog, target, block.angles, restarts=fit_restarts, seed=seed,
                                  tol=eps * 0.5, x0=x0)
            rec["fit_dist"] = d_fit
        ops = prog.materialize(block.angles, p)
    except (ValueError, ZeroDivisionError, OverflowError, IndexError) as e:
        return dict(rec, ok=False, reason=f"{type(e).__name__}: {e}")
    v = vb.verify_instance(block.ops, ops, block.n, eps)
    rec.update(ok=v["ok"], dist=v["dist"], fro=v["fro"], ops=ops, p=[float(x) for x in p])
    if v["ok"]:                      # only verified rewrites are costed (no gridsynth on wrong angles)
        rec["cost"] = ops_cost(ops, gs)
    return rec


def check_general(block, prog: Program, eps: float = vb.EPS_BLOCK, samples: int = vb.N_RANDOM_SAMPLES,
                  seed: int = 0) -> dict:
    """>=32-random-sample check of an exact rule (no free parameters)."""
    ident = block_program(block.ops, block.n)
    k = len(block.angles)
    return vb.verify_rule(lambda a: ident.materialize(a), lambda a: prog.materialize(a), k, block.angles,
                          block.n, eps=eps, samples=samples, seed=seed)


class RuleLibrary:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else DEFAULT_PATH
        self.data = dict(version=1, eps_block=vb.EPS_BLOCK, rules=[])
        if self.path.exists():
            self.data = json.loads(self.path.read_text())

    @property
    def rules(self) -> list:
        return self.data["rules"]

    def for_sig(self, sig: str) -> list:
        return [r for r in self.rules if r["sig"] == sig]

    def add(self, block, prog: Program, verification: dict, general: bool, origin: dict) -> dict:
        for r in self.for_sig(block.sig):
            if r["replacement"] == prog.to_text():
                return r
        r = dict(id=f"B{len(self.rules) + 1}", sig=block.sig, structure=block.structure, n=block.n,
                 k=len(block.angles), replacement=prog.to_text(), kind=prog.kind, n_params=prog.n_params,
                 general=bool(general), verification=_clean(verification), gain={}, origin=origin,
                 created=time.strftime("%Y-%m-%dT%H:%M:%S"))
        self.rules.append(r)
        return r

    def save(self, path: Path | None = None) -> Path:
        p = Path(path) if path else self.path
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1))
        os.replace(tmp, p)
        return p

    def to_markdown(self) -> str:
        out = ["# Block rewrite-rule library", "",
               f"eps_block = {self.data['eps_block']:g} (phase-aligned operator norm, verify_block.py)", ""]
        for r in self.rules:
            out += [f"## {r['id']} ({r['kind']}, {r['n']} qubits, {r['k']} input angles, "
                    f"general={r['general']})", "", "pattern:", "```", r["structure"], "```",
                    "replacement:", "```", r["replacement"], "```",
                    f"verification: {json.dumps(r['verification'])}", f"gain: {json.dumps(r['gain'])}", ""]
        return "\n".join(out)

    def apply(self, block, gs: Gridsynth, base_cost: dict | None = None) -> dict | None:
        """Best verified, strictly improving rule application for `block`, or None."""
        base_cost = base_cost or ops_cost(block.ops, gs)
        best = None
        for r in self.for_sig(block.sig):
            try:
                prog = parse_program(r["replacement"], block.n, len(block.angles))
            except ParseError:
                continue
            rec = try_rewrite(block, prog, gs)
            if rec["ok"] and improves(rec["cost"], base_cost) and \
                    (best is None or cost_key(rec["cost"]) < cost_key(best["cost"])):
                best = dict(rec, rule=r["id"])
        return best


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("ops",)}
