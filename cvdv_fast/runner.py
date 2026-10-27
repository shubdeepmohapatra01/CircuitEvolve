"""Apply a rule book to one benchmark (v3 runner semantics, CV-DV verifier + Genesis metrics).

    compile_benchmark(label, rules, eps=1e-3, route_seeds=range(5), whole=True) -> dict

1. Spec = Genesis IR terms (one Trotter step, t = 1, IR order) -> classified commuting parts.
2. Synthesis: for each part, every synth rule of that kind is tried; each emission is window-checked
   (judge.verify.window_check: <= 3-photon subspace, K = 12/16). Exact contract: dist <= EXACT_TOL. Approx: r is
   doubled (<= R_MAX) until dist <= share of the remaining budget. Cheapest local (duration, 2-op, 1-op) wins;
   its measured distance is charged to the ledger.
3. Logical rewrites (stage logical/both): match, apply one at a time, rewrite_check the changed window, keep only
   if distance <= EXACT_TOL (exact) / remaining ledger (approx) AND the logical cost key strictly drops.
4. Routing: Genesis' own router (cvdv.route, SWAP phase fixed), seeds 0..4, best by physical total gates
   (same policy as the Genesis baseline).
5. Physical rewrites (stage physical/both): as 3, plus every new multi-wire gate must act on a wire tuple
   already coupled in the routed circuit.
6. Whole-circuit check of the physical circuit vs the ordered Trotter product (final router map applied).
Cost key = (valid, duration, 2-op, 1-op) on the physical circuit (Genesis metrics, latency 1 / 20).
"""
from __future__ import annotations

import importlib.util
import json
import time
import traceback
from pathlib import Path

from . import bench, paths
from cvdv import isa as ISA
from cvdv import metrics as MET
from cvdv import route as ROUTE
from cvdv import terms as TERMS
from cvdv.compiler import part_hamiltonian
from cvdv.library import Builder, TermView
from .judge import verify as V

EXACT_TOL = 1e-6
R_MAX = 64


def load_rule(path):
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.RULE


def load_book(folders=("handwritten_seeds", "accepted")):
    rules = []
    for f in folders:
        d = paths.RULES / ("handwritten" if f == "handwritten_seeds" else f)
        for p in sorted(d.glob("*.py")):
            rules.append(load_rule(p))
    return rules


def key_of(ops):
    m = MET.metrics(ops)
    return (m["duration"], m["two_op"], m["one_op"], m["total"]), m


def _parts(label):
    items = []
    for k, t in enumerate(bench.load_terms(label)):
        H = TERMS.hamiltonian_of(t)
        for part in TERMS.classify(H):
            items.append((k, part, part_hamiltonian(part)))
    return items


def _sys_sizes(items):
    nq = 1 + max([w[1] for _, p, _ in items for w in p.wires if w[0] == "q"], default=-1)
    nm = 1 + max([w[1] for _, p, _ in items for w in p.wires if w[0] == "qm"], default=-1)
    return nq, nm


def _emit(rule, part, nq, nm, r):
    g = Builder(nq, nm)
    g._site_m = next((w[1] for w in part.wires if w[0] == "qm"), 0)
    g._site_q = next((w[1] for w in part.wires if w[0] == "q"), 0)
    out = rule.synth(TermView(part), g, r)
    if out is False:
        return None
    ops = g.ops
    if not ops or ISA.check(ops, ISA.GENESIS):
        return None
    sysw = set(part.wires)
    for o in ops:  # only the part's wires and ancillas above the system registers
        for w in o.wires:
            if w not in sysw and not ((w[0] == "q" and w[1] >= nq) or (w[0] == "qm" and w[1] >= nm)):
                return None
    return ops


def synthesize(label, rules, eps, log):
    items = _parts(label)
    nq, nm = _sys_sizes(items)
    synth = [r for r in rules if r.kind == "synth"]
    choice, spent = [], 0.0
    cache = {}
    # exact pass first so approximate parts share whatever budget remains
    order = sorted(range(len(items)), key=lambda i: 0)
    pending = []
    for i in order:
        k, part, H = items[i]
        best = None
        for rule in synth:
            if part.kind not in rule.term_kinds:
                continue
            try:
                ops = _emit(rule, part, nq, nm, 1)
            except Exception as e:  # noqa: BLE001
                log.append(dict(event="synth_exception", rule=rule.name, part=repr(part), err=repr(e)[:200]))
                continue
            if ops is None:
                continue
            ck = (repr(part), rule.name, 1)
            if ck not in cache:
                cache[ck] = V.window_check(H, ops)["dist"]
            d = cache[ck]
            if d <= EXACT_TOL:
                kk, _ = key_of(ops)
                if best is None or kk < best[0]:
                    best = (kk, rule.name, 1, ops, d)
        if best:
            choice.append((i, best))
        else:
            pending.append(i)
    spent = sum(b[4] for _, b in choice)
    for n_left, i in enumerate(pending):
        k, part, H = items[i]
        share = (eps / 2 - spent) / (len(pending) - n_left)
        best = None
        for rule in synth:
            if part.kind not in rule.term_kinds:
                continue
            r = 1
            while r <= R_MAX:
                try:
                    ops = _emit(rule, part, nq, nm, r)
                except Exception as e:  # noqa: BLE001
                    log.append(dict(event="synth_exception", rule=rule.name, part=repr(part), err=repr(e)[:200]))
                    ops = None
                if ops is None:
                    break
                d = V.window_check(H, ops)["dist"]
                if d <= share:
                    kk, _ = key_of(ops)
                    if best is None or kk < best[0]:
                        best = (kk, rule.name, r, ops, d)
                    break
                if rule.contract == "exact":
                    break
                r *= 2
        if best is None:
            return None, dict(failed_part=repr(part), share=share)
        choice.append((i, best))
        spent += best[4]
    choice.sort()
    ops, report = [], []
    for i, (kk, name, r, o, d) in choice:
        k, part, H = items[i]
        ops.extend(o)
        report.append(dict(term=k, part=repr(part), kind=part.kind, rule=name, r=r, dist=d, n_ops=len(o)))
    return ops, dict(parts=report, synth_err=spent, n_sys_q=nq, n_sys_m=nm)


def _coupled(ops):
    return {tuple(sorted(o.wires)) for o in ops if len(o.wires) > 1}


def rewrite_pass(ops, rules, stage, budget, log, max_apps=2000):
    rw = [r for r in rules if r.kind == "rewrite" and r.stage in (stage, "both")]
    coupled = _coupled(ops) if stage == "physical" else None
    spent, apps = 0.0, []
    changed = True
    while changed and len(apps) < max_apps:
        changed = False
        for rule in rw:
            fails = 0
            while len(apps) < max_apps:
                try:
                    ms = rule.trigger(ops)
                except Exception as e:  # noqa: BLE001
                    log.append(dict(event="trigger_exception", rule=rule.name, err=repr(e)[:200]))
                    break
                if not ms:
                    break
                applied = False
                for m in ms[: 50]:
                    try:
                        i0, i1, new = rule.apply(ops, m)
                    except Exception as e:  # noqa: BLE001
                        log.append(dict(event="apply_exception", rule=rule.name, err=repr(e)[:200]))
                        fails += 1
                        continue
                    new = list(new)
                    if ISA.check(new, ISA.GENESIS):
                        fails += 1
                        continue
                    if coupled is not None and any(len(o.wires) > 1 and tuple(sorted(o.wires)) not in coupled
                                                   for o in new):
                        fails += 1
                        continue
                    cand = ops[:i0] + new + ops[i1 + 1:]
                    if key_of(cand)[0] >= key_of(ops)[0]:
                        continue
                    old = ops[i0:i1 + 1]
                    d = V.rewrite_check(old, new)["dist"] if (old or new) else 0.0
                    tol = EXACT_TOL if rule.contract == "exact" else (budget - spent)
                    if d > tol:
                        log.append(dict(event="rewrite_verify_fail", rule=rule.name, stage=stage, dist=d))
                        fails += 1
                        continue
                    ops = cand
                    spent += d
                    apps.append(dict(rule=rule.name, stage=stage, dist=d, removed=len(old), added=len(new)))
                    applied = changed = True
                    break
                if not applied or fails > 20:
                    break
    return ops, spent, apps


def compile_benchmark(label, rules, eps=paths.EPS, route_seeds=range(5), whole=True, whole_cutoffs=None):
    t0 = time.time()
    log = []
    ops, rep = synthesize(label, rules, eps, log)
    if ops is None:
        return dict(label=label, valid=False, reason="synthesis failed", detail=rep, log=log)
    logical0 = key_of(ops)[1]
    ops, sp_l, apps_l = rewrite_pass(ops, rules, "logical", eps / 4, log)
    logical = key_of(ops)[1]
    best = None
    for s in route_seeds:
        phys, info = ROUTE.route(ops, seed=s)
        m = MET.metrics(phys)
        if best is None or m["total"] < best[1]["total"]:
            best = (phys, m, info)
    phys, m0, info = best
    phys, sp_p, apps_p = rewrite_pass(phys, rules, "physical", eps / 4, log)
    m = MET.metrics(phys)
    err_ledger = rep["synth_err"] + sp_l + sp_p
    out = dict(label=label, method="ours", **m, logical_after_synth=logical0, logical=logical, routed_before_rw=m0,
               route_seed=info["seed"], n_swaps=info["n_swaps"], err_ledger=err_ledger, parts=rep["parts"],
               rewrites=apps_l + apps_p, log=log[-50:],
               n_qubits=len({w for o in phys for w in o.wires if w[0] == "q"}),
               n_qumodes=len({w for o in phys for w in o.wires if w[0] == "qm"}))
    if whole:
        Hs = bench.hamiltonians(label)
        kw = {} if whole_cutoffs is None else dict(cutoffs=whole_cutoffs)
        w = V.whole_check(Hs, phys, final_map=info["final_map"], **kw)
        out.update(max_infid=w["max_infid"], mean_infid=w["mean_infid"], cutoff_gap=w["cutoff_gap"],
                   whole_per_K=w["per_K"])
        out["valid"] = bool(err_ledger <= eps and w["max_infid"] <= eps)
    else:
        out["valid"] = bool(err_ledger <= eps)
    out["seconds"] = round(time.time() - t0, 1)
    out["_phys_ops"] = phys
    out["_final_map"] = info["final_map"]
    return out
