"""Tier-2 library evolution: keep a new library version only if it beats the previous one on the DEV circuits.

One generation (both arms use the same loop and the same acceptance rule):
  1. propose candidate rules (LLM arm: 1+ prompts with library, technique cards, T-containing windows and verifier
     feedback; control arm: the next rules of a Quartz-style enumerated pool, same number of verifications);
  2. verify each rule ONCE (`rules.verify_rule`, exact, k <= 4 qubits) — this is the budgeted evaluation;
  3. candidate library = current + verified new rules; apply it to every DEV start circuit to a fixpoint;
     numeric whole-circuit guard against the start circuit on every circuit;
  4. ACCEPT iff total DEV T strictly drops and no circuit's T rises (primary rule, as specified). Accepted libraries
     are pruned to the new rules that were applied at least once (re-evaluated; the pruned version is kept only if it
     gives the same per-circuit T). Rejections are logged with the reason.
A 'lex' acceptance variant ((T, gates) lexicographic on the totals, never raising any circuit's T) is available for
a secondary REPLAY of the recorded proposals; it is reported separately and never used for the frozen library.
"""
from __future__ import annotations

import json
import random
import time
from collections import Counter
from pathlib import Path

from ...blocks import REPO
from .apply import apply_library, cost, numeric_guard
from .commute import T_GATES
from .rules import VARS, Library, Rule, parse_rules, seq_text, verify_rule

CARDS = ["07_phase_folding_tpar.md", "09_nam_rotation_merging.md", "03_relative_phase_toffoli.md",
         "08_pyzx_zx_simplification.md"]


# ================================================================================================ evaluation
def evaluate(lib, starts: dict, guard: bool = True) -> dict:
    per, tot_t, tot_g = {}, 0, 0
    agg_apps, agg_t, agg_g = Counter(), Counter(), Counter()
    guard_fail = []
    for c, d in starts.items():
        res = apply_library(d["gates"], d["n"], lib)
        t, g = res["cost_after"]
        gr = numeric_guard(d["gates"], res["gates"], d["n"], n_states=2, seed=len(res["gates"])) if guard and \
            res["apps"] else dict(ok=True, method="unchanged" if not res["apps"] else "skipped")
        if gr.get("ok") is False:
            guard_fail.append(c)
        per[c] = dict(t0=d["t"], g0=d["gates_total"], t=t, g=g, apps=dict(res["apps"]), t_saved=dict(res["t_saved"]),
                      fixpoint=res["fixpoint"], guard=gr.get("method"), guard_ok=gr.get("ok"), gates=res["gates"])
        tot_t += t
        tot_g += g
        agg_apps.update(res["apps"])
        agg_t.update(res["t_saved"])
        agg_g.update(res["g_saved"])
    return dict(per=per, total_t=tot_t, total_g=tot_g, apps=dict(agg_apps), t_saved=dict(agg_t), g_saved=dict(agg_g),
                guard_fail=guard_fail)


def accept(prev: dict, cand: dict, mode: str = "T") -> tuple[bool, str]:
    if cand["guard_fail"]:
        return False, f"whole-circuit guard failed on {cand['guard_fail']}"
    worse = [c for c in cand["per"] if cand["per"][c]["t"] > prev["per"][c]["t"]]
    if worse:
        return False, f"raises T on {worse}"
    if mode == "T":
        if cand["total_t"] < prev["total_t"]:
            return True, f"total dev T {prev['total_t']} -> {cand['total_t']}"
        return False, (f"total dev T unchanged ({cand['total_t']}); gates {prev['total_g']} -> {cand['total_g']}")
    if (cand["total_t"], cand["total_g"]) < (prev["total_t"], prev["total_g"]):
        return True, f"(T, gates) {prev['total_t'], prev['total_g']} -> {cand['total_t'], cand['total_g']}"
    return False, f"(T, gates) unchanged ({cand['total_t']}, {cand['total_g']})"


# ================================================================================================ windows
def extract_window(gates, n, p, rng, max_q: int = 4, max_side: int = 10):
    """Convex window around gate p on <= max_q qubits: dict(Q, gates, before, after)."""
    Q = list(gates[p][1])
    # add partner qubits of nearby 2-qubit gates touching Q (most frequent first)
    part = Counter()
    for k in range(max(0, p - 12), min(len(gates), p + 13)):
        qs = gates[k][1]
        if len(qs) == 2 and (set(qs) & set(Q)):
            for q in qs:
                if q not in Q:
                    part[q] += 1
    for q, _ in part.most_common():
        if len(Q) >= max_q:
            break
        Q.append(q)
    Qs = set(Q)

    def walk(rng_idx):
        open_, got, ctx = set(Q), [], []
        for k in rng_idx:
            qs = gates[k][1]
            touch = set(qs) & Qs
            if not touch:
                continue
            if set(qs) <= Qs and touch <= open_:
                got.append(k)
            else:
                if len(ctx) < 4:
                    ctx.append(k)
                open_ -= touch
            if len(got) >= max_side or not open_:
                break
        return got, ctx

    left, ctx_l = walk(range(p - 1, -1, -1))
    right, ctx_r = walk(range(p + 1, len(gates)))
    idx = sorted(left) + [p] + right
    return dict(Q=Q, idx=idx, gates=[gates[k] for k in idx], before=[gates[k] for k in sorted(ctx_l)],
                after=[gates[k] for k in ctx_r])


def _fmt(gs, Q):
    names = {q: VARS[i] for i, q in enumerate(Q)}
    out = []
    for g, qs in gs:
        out.append(f"{g} " + " ".join(names.get(q, "o") for q in qs))
    return "; ".join(out) if out else "(none)"


def sample_windows(circuits: dict, k: int, rng, max_gates: int = 20) -> list:
    """k windows with T gates from different circuits (round-robin over a shuffled circuit order)."""
    names = sorted(circuits)
    rng.shuffle(names)
    out = []
    for c in names:
        g, n = circuits[c]["gates"], circuits[c]["n"]
        tpos = [i for i, (x, _) in enumerate(g) if x in T_GATES]
        if not tpos:
            continue
        p = rng.choice(tpos)
        w = extract_window(g, n, p, rng)
        if len(w["gates"]) > max_gates:
            w["gates"] = w["gates"][:max_gates]
        w["circuit"] = c
        w["t"] = sum(1 for x, _ in w["gates"] if x in T_GATES)
        out.append(w)
        if len(out) >= k:
            break
    return out


# ================================================================================================ LLM prompt
def cards_text() -> str:
    parts = []
    for c in CARDS:
        p = REPO / "docs/v2/cards" / c
        parts.append(f"--- card {c} ---\n" + p.read_text().strip())
    return "\n\n".join(parts)


PROMPT = """You are writing EXECUTABLE rewrite rules for a fault-tolerant quantum circuit optimizer.
Goal: lower the total T-count of exact Clifford+T circuits (unitary-preserving: no measurements, no ancillas).

## Rule format (literal DSL; anything else is ignored)
RULE <name>
PATTERN: <gates>
REPLACE: <gates or id>
MEANING: <one line: what identity this is>
END
Gates: h s sdg t tdg x z (one variable), cx cz (two variables; cx control first). Variables: a b c d (<= 4 qubits,
distinct qubits). Gates separated by ';'. Example: PATTERN: t a; cx a b; t a   REPLACE: cx a b; s a
Requirements (checked automatically):
- PATTERN and REPLACE must be EQUAL as unitaries on their qubits up to one global phase (proved exactly over all
  2^k basis inputs; a wrong rule is rejected — no partial credit).
- (T-count, total gates) of REPLACE must be lexicographically SMALLER than PATTERN (fewer T, or equal T and fewer
  gates). Rules that do not reduce T are allowed but only T reductions improve the score.
- <= 20 gates per side; every pattern gate after the first must share a variable with an earlier pattern gate.
## How rules are applied
Each rule is applied everywhere it matches, to a fixpoint, rules in library order. Matching is COMMUTATION-AWARE:
between matched gates, other gates may sit if they can be commuted out of the way using a fixed table: two gates
commute if on every shared qubit both act 'Z-like' (z s sdg t tdg, either qubit of cz, control of cx) or both act
'X-like' (x, target of cx); h commutes with nothing on its qubit. So a pattern only needs the gates that matter;
e.g. 't a; t a' also matches 't q0; cx q0 q1; t q0'. Gates that touch other qubits do not need to be listed.
The pattern gates must appear in the circuit in the pattern's order.

## Situation
The circuits are the best outputs of pyzx full_reduce / Nam et al. Light / TKET on Toffoli-based arithmetic
(adders, multi-controlled Toffolis, GF(2^n) multipliers): phase-polynomial merging (T-par / phase folding) has
already been done globally, so simple merges like 't a; t a -> s a' match NOWHERE. A useful rule must capture an
identity those tools miss, e.g. across Hadamard gates, Toffoli-structure identities, T/H interactions on 1-2
qubits, or relative-phase / CCZ-structure tricks that are exact as unitaries. Per-circuit current T:
{circuit_table}

## Current library ({n_rules} rules)
{library}

## Technique cards
{cards}

## Where T remains: windows of the CURRENT circuits (<= 4 qubits; variables a..d label the window's qubits,
## 'o' = a qubit outside the window; 'before'/'after' are neighbouring gates that leave the window)
{windows}

## Feedback on earlier proposals (verifier and evaluation results)
{feedback}

Propose {n_min}-{n_max} NEW rules (not already in the library or the feedback) that are exact identities and
should match these circuits and reduce T. Think about what each window computes before writing a rule. Output the
RULE blocks; a short sentence of reasoning before each block is fine.
"""


def build_prompt(lib, circuits, windows, feedback, n_min=3, n_max=6) -> str:
    ctab = ", ".join(f"{c}: {d['t']}" for c, d in sorted(circuits.items()))
    libtxt = "\n".join(r.dsl() for r in lib.rules) if lib.rules else "(empty)"
    wt = []
    for i, w in enumerate(windows, 1):
        wt.append(f"[W{i}] circuit {w['circuit']}, {len(w['Q'])} qubits, {len(w['gates'])} gates, T={w['t']}\n"
                  f"  before: {_fmt(w['before'], w['Q'])}\n  window: {_fmt(w['gates'], w['Q'])}\n"
                  f"  after:  {_fmt(w['after'], w['Q'])}")
    return PROMPT.format(circuit_table=ctab, n_rules=len(lib.rules), library=libtxt, cards=cards_text(),
                         windows="\n".join(wt), feedback=feedback or "(none yet)", n_min=n_min, n_max=n_max)


def feedback_text(history: list, max_items: int = 14) -> str:
    lines = []
    for h in history[-max_items:]:
        lines.append(f"- {h['dsl_one_line']} -> {h['outcome']}")
    return "\n".join(lines)


def one_line(r: Rule) -> str:
    return f"[{seq_text(r.pattern)}] -> [{seq_text(r.replacement)}]"


# ================================================================================================ control
def match_counts(pool, circuits: dict) -> dict:
    """Number of matches (first greedy match per start position, no application) of each pool rule."""
    from .apply import _qpos, find_match
    cnt = Counter()
    by_first = {}
    for i, r in enumerate(pool):
        by_first.setdefault(r.pattern[0][0], []).append(i)
    for c, d in circuits.items():
        g, n = d["gates"], d["n"]
        qp = _qpos(g, n)
        for p in range(len(g)):
            for i in by_first.get(g[p][0], ()):
                if find_match(g, qp, p, pool[i]) is not None:
                    cnt[i] += 1
    return cnt


class ControlProposer:
    """Next candidates from the enumerated pool: T-reducing rules that match the current circuits first, then any
    rule that matches (by match count), then T-reducing rules in random order, then the rest in random order."""

    def __init__(self, pool, seed=0):
        self.pool = list(pool)
        self.tried = set()
        self.rng = random.Random(seed)
        self.order = list(range(len(self.pool)))
        self.rng.shuffle(self.order)

    def propose(self, n: int, circuits: dict) -> list:
        import hashlib
        h = hashlib.sha256(repr(sorted((c, d["gates"]) for c, d in circuits.items())).encode()).hexdigest()
        if getattr(self, "_mc_key", None) != h:
            self._mc, self._mc_key = match_counts(self.pool, circuits), h
        mc = self._mc
        rank = {i: k for k, i in enumerate(self.order)}

        def key(i):
            r = self.pool[i]
            dt = r.cost_delta()[0]
            m = mc.get(i, 0)
            return (-(dt > 0 and m > 0), -(m > 0), -m if m else 0, -(dt > 0), rank[i])
        cand = sorted((i for i in range(len(self.pool)) if i not in self.tried), key=key)[:n]
        self.tried.update(cand)
        return [self.pool[i] for i in cand], {i: mc.get(i, 0) for i in cand}


# ================================================================================================ the loop
def current_circuits(starts, ev) -> dict:
    return {c: dict(gates=ev["per"][c]["gates"], n=starts[c]["n"], t=ev["per"][c]["t"]) for c in starts}


def step(lib, prev_ev, starts, proposed, gen, arm, version, mode="T", log=None, known=None):
    """Verify proposed rules, evaluate current+new, accept/reject. Returns (lib, ev, record)."""
    known = known if known is not None else set()
    recs, new = [], []
    n_verify = 0
    for r in proposed:
        key = r.key()
        if key in lib.keys() or key in known:
            recs.append(dict(name=r.name, dsl_one_line=one_line(r), outcome="duplicate (not re-verified)",
                             verified=None))
            continue
        known.add(key)
        n_verify += 1
        v = verify_rule(r)
        r.proof = dict(method=v["method"], certified=v["certified"], k=v.get("k"), global_phase=v.get("global_phase"))
        if v["ok"]:
            new.append(r)
            recs.append(dict(name=r.name, dsl_one_line=one_line(r), outcome="verified", verified=True,
                             meaning=r.meaning, rule=r.to_dict()))
        else:
            recs.append(dict(name=r.name, dsl_one_line=one_line(r), outcome=f"REJECTED by verifier: {v['reason'][:160]}",
                             verified=False, rule=r.to_dict()))
    # unique names inside the library
    names = {x.name for x in lib.rules}
    for r in new:
        base, j = r.name or "r", 1
        while r.name in names or not r.name:
            r.name = f"{base}_{j}"
            j += 1
        names.add(r.name)
    record = dict(gen=gen, arm=arm, n_proposed=len(proposed), n_verify_calls=n_verify, n_verified=len(new),
                  prev_total_t=prev_ev["total_t"], prev_total_g=prev_ev["total_g"])
    if not new:
        record.update(accepted=False, reason="no new verified rule", cand_total_t=prev_ev["total_t"],
                      cand_total_g=prev_ev["total_g"], lib_sha=lib.sha256, lib_version=lib.version)
        return lib, prev_ev, record, recs
    cand = lib.extended(new, version)
    ev = evaluate(cand, starts)
    ok, why = accept(prev_ev, ev, mode)
    for rc in recs:
        if rc.get("verified"):
            r = next(x for x in new if x.dsl() and one_line(x) == rc["dsl_one_line"])
            a, ts = ev["apps"].get(r.name, 0), ev["t_saved"].get(r.name, 0)
            rc["applications"], rc["t_saved"], rc["g_saved"] = a, ts, ev["g_saved"].get(r.name, 0)
            rc["outcome"] = f"verified; applied {a}x on dev, T saved {ts}, gates saved {rc['g_saved']}"
            rc["name"] = r.name
    record.update(cand_total_t=ev["total_t"], cand_total_g=ev["total_g"], reason=why)
    if ok:
        used = [r for r in new if ev["apps"].get(r.name, 0) > 0]
        if len(used) < len(new):
            pruned = lib.extended(used, version)
            ev2 = evaluate(pruned, starts)
            if all(ev2["per"][c]["t"] == ev["per"][c]["t"] for c in ev["per"]) and not ev2["guard_fail"]:
                cand, ev = pruned, ev2
                record["pruned_unused"] = len(new) - len(used)
        for rc in recs:
            if rc.get("verified"):
                kept = any(x.name == rc["name"] for x in cand.rules)
                rc["outcome"] += "; KEPT in library " + version if kept else "; not applied -> pruned"
        record.update(accepted=True, lib_sha=cand.sha256, lib_version=version, n_rules=len(cand.rules),
                      cand_total_t=ev["total_t"], cand_total_g=ev["total_g"])
        return cand, ev, record, recs
    for rc in recs:
        if rc.get("verified"):
            rc["outcome"] += f"; library candidate REJECTED ({why})"
    record.update(accepted=False, lib_sha=lib.sha256, lib_version=lib.version)
    return lib, prev_ev, record, recs
