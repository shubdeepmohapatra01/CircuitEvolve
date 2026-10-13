"""Self-evolving rulebook loop (mutator -> verifier -> metrics -> selector -> playbook).

One campaign targets one term kind on a fixed instance set (generic angles x photon bounds).
  mutator  : LLM proposes K new rule functions per round, given the DSL, conventions, the current
             rules of that kind with their scores, the playbook, and the history of attempts.
  verifier : library static check + the frozen certificate on every instance (via Compiler.evaluate).
  metrics  : per instance, cheapest certified (r, duration, two_op, one_op) with eps <= eps_share;
             infeasible if no r <= r_max qualifies.
  selector : a proposal is appended to the rulebook iff it is feasible on an instance where the
             current best is infeasible, or strictly cheaper (lexicographic) on at least one instance.
  playbook : after each round a short reflection call proposes at most one new insight.
Everything is logged to <run_dir>/log.jsonl; accepted rules are appended to rulebook/rules.py with a
@provenance line and a ledger record.
"""
from __future__ import annotations

import json
import math
import os
import re
import time

from . import library as L
from .compiler import Compiler, part_hamiltonian
from .terms import Poly, classify

INF = (math.inf, math.inf, math.inf)

DSL_DOC = """
You write rules for a certified compiler of hybrid qubit-oscillator Hamiltonian simulation.
A rule is a Python function  def rule_<kind>__<name>(t, g, r):  that emits gates (time order = call order)
implementing exp(-i H) for one term.  Allowed: plain Python arithmetic, for-loops over range/lists, if,
local variables, tuples/lists, builtins range len abs min max float int complex round enumerate zip list
tuple sum reversed; `m` is a math namespace (m.pi m.sqrt m.sin m.cos m.tan m.atan2 m.exp m.log m.acos
m.asin m.cexp m.phase m.conj m.floor m.ceil).  NOT allowed: import, while, lambda, class, try, with,
attribute access on anything except g, t, m, names starting with '_' or dunders, helper functions
(only rule_* functions).  Raise ValueError to decline a term.

t (the term):  t.kind, t.theta (float), t.phi, t.alpha (complex, displacement kinds), t.label (Pauli
letters), t.q (list of qubit wires), t.m (list of qumode wires).
g (gate builder), wires are tuples like ('q', 3) or ('qm', 0):
  qubit:  g.h(q) g.x(q) g.y(q) g.z(q) g.s(q) g.sdg(q) g.t(q) g.tdg(q) g.rx(th,q) g.ry(th,q) g.rz(th,q) g.r(th,ph,q)
  oscillator / hybrid:  g.R(th, qm)  g.D(alpha, qm)  g.BS(th, ph, qm_a, qm_b)  g.CR(th, q, qm)  g.CP(q, qm)  g.CD(alpha, q, qm)
  ancillas: g.anc_qubit(k=0), g.anc_mode(k=0) return ancilla wires (start in |0> / vacuum, k = 0,1,2,...
  for several distinct ancillas).  Ancillas MUST be returned to |0>/vacuum (residual counts as error).
Conventions:  rx(θ)=e^{-iθX/2} (same for ry, rz),  R(θ)=e^{-iθ n},  D(α)=e^{α a† - α* a},
  BS(θ,φ)=e^{-iθ/2 (e^{iφ} a† b + e^{-iφ} a b†)},  CR(θ)=e^{-iθ/2 σz n},  CP = CR(π),  CD(α)=e^{σz(α a† - α* a)}.
r: integer >= 1 the compiler may raise to buy precision (e.g. repetitions); exact rules ignore it.
Rules may do compile-time numerical work in plain Python (e.g. fixed-count for-loop iterations to solve
for angles, using complex arithmetic); only the emitted gates are certified.  Keep it under ~1 s per call.

Certificate (frozen, you cannot change it): eps = min over global phase of the worst-case error
|| V(|ψ>|0_anc>) - e^{iφ} exp(-iH)|ψ>|0_anc> || over ALL states |ψ> of the system wires with total photon
number <= n_max, computed in a truncated Fock space at two increasing cutoffs that must agree.
Cost (Genesis model): duration = critical path with latency 1 for one-wire gates and 20 for multi-wire
gates; ties broken by #multi-wire gates then #one-wire gates.  The compiler picks, per term, the cheapest
(rule, r) with eps <= eps_share.
"""


def instances_for(kind, thetas, n_maxes):
    out = []
    for nm in n_maxes:
        for th in thetas:
            if kind == "n2":
                n = Poly({((), ((0, 1, 1),)): 1.0})
                H = (n * n).scale(th)
            else:
                raise KeyError(kind)
            out.append({"H": H, "part": classify(H)[0], "theta": th, "n_max": nm})
    return out


def score_rule(fn, inst, eps_share, r_max, n_sys=(0, 1)):
    comp = Compiler({}, n_max=inst["n_max"], n_sys_q=n_sys[0], n_sys_m=n_sys[1], r_max=r_max)
    part, H = inst["part"], inst["H"]
    ev1 = comp.evaluate(part, H, fn, 1)
    if ev1 is None:
        try:
            comp.emit(part, fn, 1)
            why = "rejected (ISA/wire/unreliable certificate)"
        except Exception as e:  # noqa: BLE001 - feedback to the mutator
            why = f"{type(e).__name__}: {e}"[:200]
        return {"feasible": False, "why": why}
    out = {"eps_r1": ev1[1]["eps"], "cost_r1": ev1[2]}
    ev4 = comp.evaluate(part, H, fn, 4)
    if ev4 is not None:
        out["eps_r4"] = ev4[1]["eps"]
    res = comp.best_r(part, H, fn, eps_share)
    if res is None:
        out.update(feasible=False, why=f"no r <= {r_max} reaches eps {eps_share:g}")
    else:
        out.update(feasible=True, r=res[0], eps=res[1][1]["eps"], cost=res[1][2])
    return out


def best_table(rules, kind, insts, eps_share, r_max):
    table = []
    for inst in insts:
        best, who = INF, None
        per = {}
        for name, fn in rules.get(kind, []):
            s = score_rule(fn, inst, eps_share, r_max)
            per[name] = s
            if s.get("feasible") and tuple(s["cost"]) < best:
                best, who = tuple(s["cost"]), name
        table.append({"theta": inst["theta"], "n_max": inst["n_max"], "best": best, "who": who, "per": per})
    return table


def _fmt_score(s):
    if not s.get("feasible") and "eps_r1" not in s:
        return s.get("why", "?")
    txt = f"eps(r=1)={s['eps_r1']:.2e}"
    if "eps_r4" in s:
        txt += f", eps(r=4)={s['eps_r4']:.2e}"
    txt += f", cost(r=1)={tuple(s['cost_r1'])}"
    if s.get("feasible"):
        txt += f"  -> FEASIBLE at r={s['r']}: duration={s['cost'][0]}, 2op={s['cost'][1]}, 1op={s['cost'][2]}"
    else:
        txt += f"  -> {s.get('why')}"
    return txt


def build_prompt(kind, kind_doc, rules_src, table, history, playbook, eps_share, k_idx):
    lines = [DSL_DOC, f"\nTARGET KIND: {kind}.  {kind_doc}", f"eps_share = {eps_share:g} per term.",
             "\nCURRENT RULES FOR THIS KIND (source):\n```python\n" + rules_src + "\n```",
             "\nCURRENT BEST PER INSTANCE:"]
    for row in table:
        lines.append(f"  theta={row['theta']:+.4f} n_max={row['n_max']:2d}: best={row['who']} cost={row['best']}")
        for name, s in row["per"].items():
            lines.append(f"      {name}: {_fmt_score(s)}")
    lines.append("\nPLAYBOOK (accumulated insights):\n" + playbook)
    if history:
        lines.append("\nPREVIOUS PROPOSALS IN THIS CAMPAIGN (most recent last):")
        for h in history[-8:]:
            lines.append(f"--- {h['name']} ({'ACCEPTED' if h['accepted'] else 'rejected'})")
            lines.append("```python\n" + h["code"][:2500] + "\n```")
            for s, inst in zip(h["scores"], h["insts"]):
                lines.append(f"   theta={inst[0]:+.4f} n_max={inst[1]:2d}: {_fmt_score(s)}")
    lines.append(f"""
TASK: propose ONE new rule `rule_{kind}__<name>` (choose a new descriptive name; proposal slot {k_idx})
that is cheaper than the current best on at least one instance, or feasible where none is.  Think about
exact constructions on the bounded subspace (n <= n_max), about how error scales with r, and about
gate cost.  Derive the construction carefully (signs, factors of 2 in the conventions above).
Reason step by step in plain text first (at most ~60 lines of derivation, check signs and factors),
then give exactly one ```python code block containing only the rule function.""")
    return "\n".join(lines)


def extract_code(text):
    blocks = re.findall(r"```python\s*\n(.*?)```", text, re.S)
    return blocks[-1].strip() + "\n" if blocks else None


def accepted_over(table, scores):
    gain = False
    for row, s in zip(table, scores):
        if s.get("feasible") and tuple(s["cost"]) < row["best"]:
            gain = True
    return gain


def append_rule(rulebook_dir, code, kind, name, evidence, model, iteration):
    stamp = time.strftime("%Y-%m-%d %H:%M")
    with open(os.path.join(rulebook_dir, "rules.py"), "a") as f:
        f.write(f"\n\n# {'-' * 93}\n# @provenance: llm-loop | {stamp} | model={model} | iteration={iteration}\n")
        f.write(code)
    with open(os.path.join(rulebook_dir, "ledger.jsonl"), "a") as f:
        f.write(json.dumps({"rule": name, "kind": kind, "origin": "llm-loop", "added": stamp, "model": model,
                            "iteration": iteration, "evidence": evidence}) + "\n")


def kind_source(src, kind):
    """Source of the rule_<kind>__* functions in a rulebook."""
    out, keep = [], False
    for line in src.splitlines():
        if line.startswith("def "):
            keep = line.startswith(f"def rule_{kind}__")
        elif line and not line.startswith((" ", "\t", "#")):
            keep = False
        if keep:
            out.append(line)
    return "\n".join(out)


def run_campaign(llm, model, rulebook_dir, run_dir, kind, kind_doc, insts, rounds=3, k=4,
                 eps_share=1e-4, r_max=256, log=print):
    os.makedirs(run_dir, exist_ok=True)
    logf = open(os.path.join(run_dir, "log.jsonl"), "a")
    history = []
    for rnd in range(rounds):
        src = open(os.path.join(rulebook_dir, "rules.py")).read()
        rules = L.load(src)
        table = best_table(rules, kind, insts, eps_share, r_max)
        playbook = open(os.path.join(rulebook_dir, "playbook.md")).read()
        prompts = [build_prompt(kind, kind_doc, kind_source(src, kind), table, history, playbook, eps_share, j)
                   for j in range(k)]
        t0 = time.time()
        replies = llm([{"prompt": p, "model": model, "max_tokens": 12000, "temperature": 1.0,
                        "thinking": {"type": "disabled"}} for p in prompts], max_concurrency=k)
        log(f"round {rnd}: {k} proposals in {time.time() - t0:.0f}s; best now "
            + ", ".join(f"{r['who']}:{r['best'][0]}" for r in table))
        existing = set(n for n, _ in rules.get(kind, []))
        for j, rep in enumerate(replies):
            rec = {"round": rnd, "slot": j, "time": time.time()}
            text = rep.get("text", "") if isinstance(rep, dict) else ""
            code = extract_code(text)
            rec["reply"] = text
            rec["llm_error"] = rep.get("error") if isinstance(rep, dict) else str(rep)
            rec["stop_reason"] = rep.get("stop_reason") if isinstance(rep, dict) else None
            if not code:
                rec["status"] = "no code"
                logf.write(json.dumps(rec) + "\n")
                continue
            mname = re.search(rf"def (rule_{kind}__\w+)\s*\(", code)
            if not mname:
                rec["status"] = "bad name"
                logf.write(json.dumps(rec) + "\n")
                continue
            fname = mname.group(1)
            short = fname[len(f"rule_{kind}__"):]
            if short in existing:
                short = f"{short}_{rnd}_{j}"
                code = code.replace(fname, f"rule_{kind}__{short}", 1)
                fname = f"rule_{kind}__{short}"
            try:
                cand = L.load(code)
                fn = dict(cand[kind])[short]
            except Exception as e:  # noqa: BLE001
                rec.update(status="static check failed", error=str(e)[:300], code=code)
                history.append({"name": fname, "code": code, "accepted": False,
                                "scores": [{"feasible": False, "why": f"static check: {e}"[:200]}] * len(insts),
                                "insts": [(i["theta"], i["n_max"]) for i in insts]})
                logf.write(json.dumps(rec) + "\n")
                continue
            scores = [score_rule(fn, inst, eps_share, r_max) for inst in insts]
            acc = accepted_over(table, scores)
            rec.update(status="accepted" if acc else "rejected", name=fname, code=code,
                       scores=[{k2: (list(v) if isinstance(v, tuple) else v) for k2, v in s.items()} for s in scores])
            history.append({"name": fname, "code": code, "accepted": acc, "scores": scores,
                            "insts": [(i["theta"], i["n_max"]) for i in insts]})
            log(f"  slot {j}: {fname}: " + " | ".join(
                (f"{s['cost'][0]}@r{s['r']}" if s.get("feasible") else f"x(eps1={s.get('eps_r1', float('nan')):.1e})")
                for s in scores) + ("  ACCEPTED" if acc else ""))
            if acc:
                ev = [{"theta": i["theta"], "n_max": i["n_max"], **{k2: (list(v) if isinstance(v, tuple) else v)
                       for k2, v in s.items()}} for i, s in zip(insts, scores)]
                append_rule(rulebook_dir, code, kind, fname, ev, model, rnd)
                existing.add(short)
                rules = L.load(open(os.path.join(rulebook_dir, "rules.py")).read())
                table = best_table(rules, kind, insts, eps_share, r_max)
            logf.write(json.dumps(rec, default=str) + "\n")
        logf.flush()
        reflect(llm, model, rulebook_dir, kind, history[-k:], log)
    logf.close()
    return history


REFLECT = """You curate a short playbook of insights for an LLM that writes gate-synthesis rules for
hybrid qubit-oscillator circuits (conventions and DSL as below).  Here is the current playbook and the
latest round of proposals with their certified results.  If (and only if) the results reveal a NEW,
specific, verified lesson (e.g. a construction that is exact on a subspace, an error-scaling fact, a
recurring sign/convention mistake), reply with ONE new numbered-style bullet (<= 3 lines) starting with
'INSIGHT:'.  Otherwise reply 'NONE'.  Do not restate existing bullets."""


def reflect(llm, model, rulebook_dir, kind, rnd_hist, log=print):
    pb_path = os.path.join(rulebook_dir, "playbook.md")
    pb = open(pb_path).read()
    lines = [REFLECT, DSL_DOC, "\nPLAYBOOK:\n" + pb, f"\nROUND RESULTS (kind {kind}):"]
    for h in rnd_hist:
        lines.append(f"--- {h['name']} ({'ACCEPTED' if h['accepted'] else 'rejected'})\n```python\n{h['code'][:2000]}\n```")
        for s, inst in zip(h["scores"], h["insts"]):
            lines.append(f"   theta={inst[0]:+.4f} n_max={inst[1]:2d}: {_fmt_score(s)}")
    rep = llm([{"prompt": "\n".join(lines), "model": model, "max_tokens": 600, "thinking": {"type": "disabled"}}])[0]
    txt = (rep.get("text") or "").strip()
    if txt.startswith("INSIGHT:"):
        n = sum(1 for l in pb.splitlines() if re.match(r"^\d+\.", l)) + 1
        with open(pb_path, "a") as f:
            f.write(f"{n}. {txt[len('INSIGHT:'):].strip()}  [auto, {time.strftime('%Y-%m-%d')}]\n")
        log(f"  playbook += {txt[:120]}")
