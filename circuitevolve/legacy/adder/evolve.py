"""Classical search over SliceProgram: random mutation + MAP-Elites archive.

This is the P3 arm (no LLM) and the ablation baseline for every later LLM arm: same
representation, same verifier, same fitness, same evaluation budget.

Fitness is lexicographic (minimize): (T per bit, T-count at n_eval, qubits at n_eval, T-depth at
n_eval, size). T per bit = (T(n_eval) - T(4)) / (n_eval - 4) is the asymptotic cost; ranking by
T(n_eval) alone lets a large one-off constant hide a better slope. A candidate that fails
verification has no fitness at all; it never enters the archive.

Search-side budget (not a verifier change): a candidate may contain at most MAX_MEAS_PER_BIT
measurement events per bit (measure + and_uncompute). Each measurement doubles the branches the
exhaustive phase check enumerates; without this cap neutral compute/uncompute pairs accumulate and
a single evaluation takes seconds. Winners are always re-verified at n = 1..16 with default limits.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from circuitevolve.ir import ARITY, TIER_A, TIER_B
from circuitevolve.spec import AdderSpec
from circuitevolve.verify import Limits, verify
from .slice import ROLES, SliceProgram, build

TIERS = {"A": frozenset(TIER_A), "B": frozenset(TIER_B)}
MAX_TEMPLATE = 40
MAX_MEAS_PER_BIT = 2


# ---------------------------------------------------------------------------------------------
def _random_gate(rng, vocab, labels):
    name = rng.choice(sorted(vocab))
    roles = tuple(rng.sample(ROLES, ARITY[name]))
    if name == "measure":
        return (name, roles, None, f"m{rng.randrange(1000)}")
    cond = rng.choice(labels) if labels and name not in ("and_compute", "and_uncompute") and rng.random() < 0.3 else None
    return (name, roles, cond, None)


def mutate(prog: SliceProgram, vocab, rng: random.Random) -> SliceProgram:
    t = dict(prog.templates())
    key = rng.choices(["fwd", "top", "bwd"], weights=[0.4, 0.2, 0.4])[0]
    g = list(t[key])
    op = rng.choice(["insert", "delete", "replace_name", "replace_roles", "swap", "duplicate"])
    labels = [x[3] for x in g if x[0] == "measure"]
    if op == "insert" and len(g) < MAX_TEMPLATE:
        g.insert(rng.randrange(len(g) + 1), _random_gate(rng, vocab, labels))
    elif op == "delete" and g:
        del g[rng.randrange(len(g))]
    elif op == "replace_name" and g:
        i = rng.randrange(len(g))
        name, roles, cond, label = g[i]
        same = [v for v in vocab if ARITY[v] == ARITY[name] and v != "measure" and name != "measure"]
        if same:
            new = rng.choice(sorted(same))
            g[i] = (new, roles, None if new in ("and_compute", "and_uncompute") else cond, label)
    elif op == "replace_roles" and g:
        i = rng.randrange(len(g))
        name, roles, cond, label = g[i]
        g[i] = (name, tuple(rng.sample(ROLES, len(roles))), cond, label)
    elif op == "swap" and len(g) >= 2:
        i = rng.randrange(len(g) - 1)
        g[i], g[i + 1] = g[i + 1], g[i]
    elif op == "duplicate" and g and len(g) < MAX_TEMPLATE:
        i = rng.randrange(len(g))
        if g[i][0] != "measure":
            g.insert(i + 1, g[i])
    t[key] = tuple(g)
    return SliceProgram(t["fwd"], t["top"], t["bwd"])


# ---------------------------------------------------------------------------------------------
@dataclass
class Evaluator:
    tier: str
    n_check: tuple = (1, 2, 3, 4)
    n_eval: int = 8
    cache: dict = field(default_factory=dict)
    calls: int = 0

    def seen(self, prog: SliceProgram) -> bool:
        return hash(prog) in self.cache

    def __call__(self, prog: SliceProgram):
        key = hash(prog)
        if key in self.cache:
            return self.cache[key]
        self.calls += 1
        meas = lambda t: sum(1 for g in t if g[0] in ("measure", "and_uncompute"))
        if meas(prog.fwd) + meas(prog.bwd) > MAX_MEAS_PER_BIT or meas(prog.top) > MAX_MEAS_PER_BIT:
            res = (False, None, _Rejected("L0", "search budget: too many measurements per bit"))
            self.cache[key] = res
            return res
        lim = Limits(exhaustive_n=4, sampled_inputs=24, branch_budget=4096, sampled_branches=4,
                     trust_gadget_lemma=True)
        r = verify(lambda n: build(prog, n), AdderSpec(), list(self.n_check) + [self.n_eval], TIERS[self.tier], lim)
        if r.ok:
            c, c4 = r.costs[self.n_eval], r.costs[4]
            slope = (c["t_count"] - c4["t_count"]) / (self.n_eval - 4)
            res = (True, (slope, c["t_count"], c["qubits"], c["t_depth"], prog.size()), _Rejected("pass", "", True))
        else:
            res = (False, None, _Rejected(r.level, r.reason))
        self.cache[key] = res
        return res


@dataclass
class _Rejected:
    level: str
    reason: str
    ok: bool = False


def crossover(p1: SliceProgram, p2: SliceProgram, rng: random.Random) -> SliceProgram:
    """Uniform choice of each template from either parent, plus one-point crossover in one template."""
    t1, t2 = p1.templates(), p2.templates()
    t = {k: (t1[k] if rng.random() < 0.5 else t2[k]) for k in t1}
    if rng.random() < 0.5:
        k = rng.choice(list(t))
        a, b = t1[k], t2[k]
        i, j = rng.randint(0, len(a)), rng.randint(0, len(b))
        t[k] = tuple(a[:i] + b[j:])[:MAX_TEMPLATE]
    return SliceProgram(t["fwd"], t["top"], t["bwd"])


def map_elites(seed: SliceProgram, tier: str, budget: int, rng_seed: int, log_every: int = 250,
               crossover_rate: float = 0.0, progress_path=None, progress_every: int = 20000):
    """Returns (archive, trajectory, stats). archive: {cell: (fitness, prog)}; cell = (T/bit, size bin)."""
    rng = random.Random(rng_seed)
    ev = Evaluator(tier)
    ok, fit, _ = ev(seed)
    assert ok, "seed program must verify"
    archive = {(fit[0], fit[4] // 4): (fit, seed)}
    best = fit
    traj = [(ev.calls, best[0])]
    failures = {"L0": 0, "L1": 0, "L2": 0}
    t0 = time.time()
    while ev.calls < budget:
        elites = list(archive.values())
        _, parent = rng.choice(elites)
        if crossover_rate and len(elites) > 1 and rng.random() < crossover_rate:
            child = crossover(parent, rng.choice(elites)[1], rng)
        else:
            child = mutate(parent, TIERS[tier], rng)
        if rng.random() < 0.3:
            child = mutate(child, TIERS[tier], rng)
        if progress_path and ev.calls % progress_every == 0 and not ev.seen(child):
            import json
            with open(progress_path, "w") as f:
                json.dump({"evals": ev.calls, "best": best, "cells": len(archive),
                           "seconds": round(time.time() - t0)}, f)
        seen = ev.seen(child)
        ok, fit, rep = ev(child)
        if not ok:
            if not seen:
                failures[rep.level] = failures.get(rep.level, 0) + 1
            continue
        cell = (fit[0], fit[4] // 4)
        inc = archive.get(cell)
        if inc is None or fit <= inc[0]:
            archive[cell] = (fit, child)
        if fit < best:
            best = fit
        if ev.calls % log_every == 0 or fit[0] < traj[-1][1]:
            traj.append((ev.calls, best[0]))
    traj.append((ev.calls, best[0]))
    stats = {"evals": ev.calls, "cache_hits_excluded": True, "seconds": round(time.time() - t0, 1),
             "failures": failures, "archive_cells": len(archive), "best": best}
    return archive, traj, stats
