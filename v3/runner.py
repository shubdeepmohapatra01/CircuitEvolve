"""Apply a rule book to a circuit (SPEC section 6).

    optimize(circuit, book, eps, reference=None, domain="dv", pass_limit=20, label=None, time_limit=None) -> Result

Rule order (2026-10-20): reconstruction rules first, then the rest; within each group, rules are ordered PER CIRCUIT
by their solo gain (each rule run alone first), largest first, so a weaker rule cannot consume matches a stronger
one needs; by default both that order and the book order are run and the better kept (order='best'). For each rule
in the chosen order: find matches, apply one
at a time, verify each application, keep it only if the cost drops lexicographically; after an accepted
application the rule is re-triggered on the new circuit. Repeat passes until no rule fires or pass_limit.

Verification (DV, 2026-10-20 speed change):
  * per application, on its WINDOW: the differing middle of the old and new op lists (common prefix and suffix
    removed), re-indexed to the qubits it touches. Exact D[omega] check when both windows are Clifford+T (certified
    when the window has <= 14 qubits); otherwise the frozen numerical check (dense operator norm for <= 10
    qubits) at EXACT_TOL for 'exact' rules, or against the remaining ledger for 'approx' rules. Windows are
    equivalent up to global phase => whole circuits are. Window distances add up in the ledger (triangle
    inequality, cap eps/2).
  * relaxed rules, or a change of qubit count / measurements: whole-circuit check per application (relaxed mode).
  * once per rule pass (after the rule stops firing in that pass): whole-circuit check of the current circuit
    against the ORIGINAL input. If it fails, bisect over the pass's accepted applications to the first one whose
    result fails, revert to the circuit before it, record that application as a verification failure, and stop
    using the rule in this run.
Every log entry records the judge's method and whether the check was certified or sampled. Exceptions raised by
rule code are recorded as failures (verified False, reason 'exception: ...').

DV cost key: (T-count, qubits, CNOT). While optimizing, candidates are priced at the INPUT's eps_rz (conservative:
N_Rz only drops); the result is re-measured with eps_rz = (eps - spent) / N_Rz.
CV-DV: deferred (2026-10-20); an empty book returns the start circuit unchanged.
An empty book returns the input object unchanged with err_rules = 0.
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field

from .judge import dv as J
from .judge.frozen import check_frozen

KIND_FIRST = ("reconstruction",)
EXACT_TOL = 1e-8


@dataclass
class Result:
    circuit: object
    cost: dict
    err_rules: float                 # ledger: sum of measured window distances charged to rule applications
    err_bound: float                 # err_rules + synthesis budget actually reserved (DV)
    log: list = field(default_factory=list)
    passes: int = 0
    seconds: float = 0.0
    whole_checks: list = field(default_factory=list)
    rule_order: list = field(default_factory=list)
    solo_gains: dict = field(default_factory=dict)
    order_choice: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return dict(cost=self.cost, err_rules=self.err_rules, err_bound=self.err_bound, passes=self.passes,
                    applications=sum(e["accepted"] for e in self.log), attempts=len(self.log),
                    verify_failures=sum(not e.get("verified", True) for e in self.log),
                    certified=all(e.get("certified", False) for e in self.log if e["accepted"]) and
                    all(w.get("certified", False) for w in self.whole_checks),
                    verify_methods=sorted({e["method"] for e in self.log if e.get("method")}),
                    whole_checks=len(self.whole_checks), seconds=round(self.seconds, 2))


def dv_key(m: dict) -> tuple:
    return (m["t_count"], m["qubits"], m["cx"])


def ordered(book) -> list:
    book = list(book)
    return [r for r in book if r.kind in KIND_FIRST] + [r for r in book if r.kind not in KIND_FIRST]


# ------------------------------------------------------------------------------------------------ windows
def _seq(c):
    """Comparable op sequence of a DV circuit: core ops (name, qubits, angle) or ir gates (name, qubits, cond)."""
    if J.is_ir(c):
        return [(g.name, tuple(g.qubits), g.cond, g.cbit) for g in c.gates]
    return list(c.ops)


def window(old, new):
    """(old_ops, new_ops, qubits) of the changed middle, re-indexed to local qubits; None if not window-checkable
    (different qubit count, measurement / classical control in the window)."""
    if J.is_ir(old) != J.is_ir(new):
        return None
    n_old = old.n_qubits if J.is_ir(old) else old.n
    n_new = new.n_qubits if J.is_ir(new) else new.n
    if n_old != n_new:
        return None
    a, b = _seq(old), _seq(new)
    p = 0
    while p < min(len(a), len(b)) and a[p] == b[p]:
        p += 1
    s = 0
    while s < min(len(a), len(b)) - p and a[len(a) - 1 - s] == b[len(b) - 1 - s]:
        s += 1
    wa, wb = a[p:len(a) - s], b[p:len(b) - s]
    if J.is_ir(old) and any(g[0] == "measure" or g[2] is not None for g in wa + wb):
        return None
    qs = sorted({q for op in wa + wb for q in op[1]})
    loc = {q: i for i, q in enumerate(qs)}
    if J.is_ir(old):
        def build(w):
            c = J.IRCircuit(len(qs))
            for g in w:
                c.add(g[0], *[loc[q] for q in g[1]])
            return c
    else:
        def build(w):
            return ([(g, tuple(loc[q] for q in qq), ang) for g, qq, ang in w], len(qs))
    return build(wa), build(wb), qs, (p, len(a) - s, len(b) - s)


# ------------------------------------------------------------------------------------------------ DV
def gain_order(circuit, book, eps, reference=None, time_limit=None) -> tuple:
    """Order rules for THIS circuit by their solo gain (T removed when the rule runs alone), largest first, within
    the reconstruction-first groups. Prevents a weaker rule from consuming matches a stronger one needs."""
    if len(book) < 2:
        return list(book), {}
    t0_cost = None
    gains = {}
    for r in book:
        res = optimize(circuit, [r], eps, reference=reference, time_limit=time_limit, order="book")
        if t0_cost is None:
            t0_cost = (J.measure(circuit) if J._v2_verify.is_exact(circuit) else J.measure(circuit, eps))["t_count"]
        gains[r.name] = t0_cost - res.cost["t_count"]
    key = lambda r: -gains[r.name]                                   # noqa: E731
    first = sorted([r for r in book if r.kind in KIND_FIRST], key=key)
    rest = sorted([r for r in book if r.kind not in KIND_FIRST], key=key)
    return first + rest, gains


def optimize(circuit, book, eps: float, reference=None, domain: str = "dv", pass_limit: int = 20,
             label: str | None = None, time_limit: float | None = None, order: str = "best") -> Result:
    """order: 'best' (default for >= 2 rules: run the gain order and the book order, keep the lower cost; ties go to
    the gain order), 'gain' (rules ordered per circuit by solo gain, see gain_order) or 'book' (book order,
    reconstruction first). Measured 2026-10-20: with repeated passes a weaker rule first did not lose matches on
    qft/qpe/hhl/qae and was 6 T better on qft_8, so neither order dominates."""
    if order == "best" and domain == "dv" and len(book) > 1:
        solo = {r.name: optimize(circuit, [r], eps, reference, domain, pass_limit, label, time_limit, order="book")
                for r in book}
        firing = [r for r in book if any(e["accepted"] for e in solo[r.name].log)]
        if len(firing) <= 1:
            # at most one rule changes this circuit: if no other rule matches on its result, the solo run IS the
            # result (no interaction to order); saves the two full reruns
            only = firing[0] if firing else book[0]
            res = solo[only.name]
            if all(not r.trigger(res.circuit) for r in book if r is not only):
                res.order_choice = dict(chosen="solo", reason="only one rule fires on this circuit")
                res.rule_order = [only.name] + [r.name for r in book if r is not only]
                return res
        g = optimize(circuit, book, eps, reference, domain, pass_limit, label, time_limit, order="gain")
        b = optimize(circuit, book, eps, reference, domain, pass_limit, label, time_limit, order="book")
        best = b if dv_key(b.cost) < dv_key(g.cost) else g
        best.order_choice = dict(gain=g.cost["t_count"], book=b.cost["t_count"],
                                 chosen="book" if best is b else "gain")
        best.solo_gains = g.solo_gains
        return best
    check_frozen()
    t0 = time.time()
    deadline = t0 + time_limit if time_limit else None
    solo_gains = {}
    if order == "gain" and domain == "dv" and len(book) > 1:
        book, solo_gains = gain_order(circuit, ordered(book), eps, reference, time_limit)
    else:
        book = ordered(book)
    if domain == "cvdv":
        if book:
            raise NotImplementedError("CV-DV rule application is deferred (2026-10-20)")
        return Result(circuit, {}, 0.0, 0.0, seconds=time.time() - t0)
    ref = circuit if reference is None else reference
    exact = J._v2_verify.is_exact
    cap = eps / 2
    eps_rz_in = None if exact(circuit) else J.measure(circuit, eps)["eps_rz"]
    spent = 0.0

    def price(c):
        return J.measure(c) if exact(c) else J.measure(c, eps, eps_rz=eps_rz_in)

    def check(cand, refc, contract, budget):
        """Verdict of cand vs refc under the rule's contract."""
        if contract == "relaxed":
            return J.verify(cand, refc, mode="relaxed")
        if exact(cand) and exact(refc):
            return J.verify(cand, refc, mode="exact")
        return J.verify(cand, refc, mode="approx", eps=min(EXACT_TOL, budget) if contract == "exact" else budget)

    def record(entry, v, scope):
        entry.update(verified=bool(v.ok), mode=v.mode, distance=v.distance, reason=v.reason, method=v.method,
                     certified=bool(v.certified), n_inputs=v.n_inputs, scope=scope)

    log, whole, passes, cur = [], [], 0, circuit
    cur_cost = price(circuit)
    disabled = set()
    while book and passes < pass_limit:
        passes += 1
        fired = False
        for rule in book:
            if rule.name in disabled:
                continue
            start, start_cost, start_spent = cur, cur_cost, spent
            snaps = []                              # (entry, circuit after, cost after, spent after)
            changed = True
            while changed:
                changed = False
                try:
                    matches = list(rule.trigger(cur))
                except Exception as e:  # noqa: BLE001  (rule code)
                    log.append(dict(rule=rule.name, pass_=passes, match=None, accepted=False, verified=False,
                                    reason=f"exception in trigger: {type(e).__name__}: {e}",
                                    traceback=traceback.format_exc()[-1500:]))
                    disabled.add(rule.name)
                    break
                for i, m in enumerate(matches):
                    if deadline and time.time() > deadline:
                        log.append(dict(rule=rule.name, pass_=passes, match=i, accepted=False, verified=True,
                                        timeout=True))
                        return _finish(circuit, cur, eps, spent, log, passes, t0, whole)
                    entry = dict(rule=rule.name, pass_=passes, match=i, accepted=False)
                    try:
                        cand = rule.apply(cur, m)
                        w = None if rule.contract == "relaxed" else window(cur, cand)
                        if w is None:
                            v = check(cand, ref, rule.contract, cap - spent)
                            record(entry, v, "whole")
                            d = float(v.distance or 0.0) if v.mode == "approx" else 0.0
                            d_charge = max(0.0, d - spent) if v.ok else 0.0
                        else:
                            wo, wn, qs, span = w
                            entry["window"] = dict(qubits=len(qs), old_ops=span[1] - span[0],
                                                   new_ops=span[2] - span[0], at=span[0])
                            if span[1] == span[0] and span[2] == span[0]:
                                entry.update(verified=True, mode="identical", method="identical", certified=True,
                                             scope="window", distance=0.0, reason="")
                                d_charge = 0.0
                            else:
                                v = check(wn, wo, rule.contract, cap - spent)
                                record(entry, v, "window")
                                d_charge = float(v.distance or 0.0) if v.mode == "approx" else 0.0
                    except Exception as e:  # noqa: BLE001  (rule code)
                        entry.update(verified=False, reason=f"exception in apply/verify: {type(e).__name__}: {e}",
                                     traceback=traceback.format_exc()[-1500:])
                        log.append(entry)
                        disabled.add(rule.name)
                        changed = False
                        break
                    if entry["verified"]:
                        c_cost = price(cand)
                        entry["cost"] = {k: c_cost[k] for k in ("t_count", "rotations", "cx", "qubits")}
                        if dv_key(c_cost) < dv_key(cur_cost):
                            cur, cur_cost = cand, c_cost
                            spent += d_charge
                            entry.update(accepted=True, charged=d_charge)
                            snaps.append((entry, cur, cur_cost, spent))
                            fired = changed = True
                    log.append(entry)
                    if changed:
                        break                       # re-trigger on the new circuit
            if snaps:                               # whole-circuit check once per rule pass
                cur, cur_cost, spent = _pass_check(rule, ref, snaps, start, start_cost, start_spent, check, cap,
                                                   whole, disabled, passes)
        if not fired:
            break
    res = _finish(circuit, cur, eps, spent, log, passes, t0, whole)
    res.rule_order, res.solo_gains = [r.name for r in book], solo_gains
    return res


def _pass_check(rule, ref, snaps, start, start_cost, start_spent, check, cap, whole, disabled, passes):
    entry0, last, last_cost, last_spent = snaps[-1]
    if entry0.get("scope") == "whole" and entry0.get("verified"):
        # the last accepted application was itself checked whole-circuit against the ORIGINAL: same check, skip
        whole.append(dict(rule=rule.name, pass_=passes, after_application=len(snaps) - 1, ok=True,
                          method=entry0.get("method"), certified=entry0.get("certified", False),
                          distance=entry0.get("distance"), reason="", reused="per-application whole check"))
        return last, last_cost, last_spent

    def ok_at(k):
        c, sp = snaps[k][1], snaps[k][3]
        v = check(c, ref, rule.contract, min(cap, sp + EXACT_TOL))
        whole.append(dict(rule=rule.name, pass_=passes, after_application=k, ok=bool(v.ok), method=v.method,
                          certified=bool(v.certified), distance=v.distance, reason=v.reason))
        return v.ok

    if ok_at(len(snaps) - 1):
        return last, last_cost, last_spent
    lo, hi = 0, len(snaps) - 1                      # first failing snapshot in [lo, hi]; hi known to fail
    while lo < hi:
        mid = (lo + hi) // 2
        if ok_at(mid):
            lo = mid + 1
        else:
            hi = mid
    bad = snaps[lo][0]
    bad.update(verified=False, accepted=False, scope="whole-pass (bisected)",
               reason=f"whole-circuit check failed after this application (bisected): "
                      f"{whole[-1]['reason'] if not whole[-1]['ok'] else 'see whole_checks'}")
    for e, *_ in snaps[lo + 1:]:
        e.update(accepted=False, reverted=True)
    disabled.add(rule.name)
    if lo == 0:
        return start, start_cost, start_spent
    return snaps[lo - 1][1], snaps[lo - 1][2], snaps[lo - 1][3]


def _finish(circuit, cur, eps, spent, log, passes, t0, whole) -> Result:
    if J._v2_verify.is_exact(cur):
        final, synth = J.measure(cur), 0.0
    else:
        final, synth = J.measure(cur, eps - spent), eps - spent
    return Result(cur, final, spent, spent + synth, log, passes, time.time() - t0, whole)
