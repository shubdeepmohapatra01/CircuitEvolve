"""Apply a rule book to a circuit. The v3 runner's semantics, with the redundant work removed.

    optimize(circuit, book, eps, reference=None, order='best', ledger=None, solo=None, ...) -> Result

Unchanged from v3 (the numbers must not move): rule order (reconstruction first, then by solo gain per
circuit, better of gain order and book order), one application at a time, every APPLICATION verified on its
changed window, one whole-circuit check per rule pass against the ORIGINAL circuit, bisection to the first
bad application on a failed pass check, lexicographic cost key (T, qubits, CX), re-trigger after an accept.

What v4 removes (V4_README sections 5.1 and 6.4):

1. `check_frozen()` once per process, not per `optimize` and per `verify`      (3.3 ms -> 0 per call)
2. the reference ReferenceSpec and its dense unitary / probe images are cached (39% of a whole check)
3. **price before verify**: v3 verified an application and then asked whether it improved. qft_8 attempts
   40 applications to accept 19; pricing costs 1.4 ms and a whole-circuit check 48 ms. So the order is
   reversed: an application that does not lower the cost is dropped without verification. Only KEPT
   applications are verified, which is what acceptance depends on.
4. window checks memoised on the normalised (old, new, k) pair
5. the **solo runs are computed once** and shared between the gain order and the book order (v3 ran them
   twice; 6 of 12 solo runs in the P2 book were literal duplicates)
6. preconditions and a trigger-only pre-pass drop rules that cannot fire, for free / in ~ms, before any
   verification happens

`order`:
    'book'    book order (reconstruction kinds first)
    'gain'    per circuit, by each rule's solo gain, largest first
    'best'    run both, keep the lower cost (v3's default; ties go to the gain order)
    'min_all' 'best' plus every single-rule result: `min(book_order, gain_order, best_single_rule)`.
              V4_README 5.2 - the P2 six-rule book is 6 T WORSE on qft_8 than `pauli_frame_rotation_merge`
              alone, so a book must never be allowed to score worse than one of its own rules.

The error budget is a `Ledger` (v4/ledger.py): approx rules draw their measured window distance from a
shared pool of eps/2 and the draw is recorded per rule.
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field

from .api import describe
from .api import budget as api_budget
from .caps import OpcodeBudget, OpcodeExceeded
from .judge import dv as J
from .judge.certify import certify
from .judge.frozen import check_frozen
from .ledger import Ledger

KIND_FIRST = ("reconstruction",)
EXACT_TOL = 1e-8
PASS_LIMIT = 20


@dataclass
class Result:
    circuit: object
    cost: dict
    err_rules: float                 # ledger: sum of measured distances charged to rule applications
    err_bound: float                 # err_rules + the synthesis budget actually reserved
    log: list = field(default_factory=list)
    passes: int = 0
    seconds: float = 0.0
    whole_checks: list = field(default_factory=list)
    rule_order: list = field(default_factory=list)
    solo_gains: dict = field(default_factory=dict)
    order_choice: dict = field(default_factory=dict)
    ledger: Ledger | None = None
    excluded: dict = field(default_factory=dict)      # rule -> precondition reason (free, not a rejection)
    never_fired: list = field(default_factory=list)   # rules whose trigger matched nowhere (~ms pre-pass)
    opcodes: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return dict(cost=self.cost, err_rules=self.err_rules, err_bound=self.err_bound, passes=self.passes,
                    applications=sum(e["accepted"] for e in self.log), attempts=len(self.log),
                    verify_failures=sum(not e.get("verified", True) for e in self.log
                                        if e.get("verified") is not None),
                    priced_out=sum(1 for e in self.log if e.get("reason") == "no cost decrease"),
                    certified=all(e.get("certified", False) for e in self.log if e["accepted"]) and
                    all(w.get("certified", False) for w in self.whole_checks),
                    verify_methods=sorted({e["method"] for e in self.log if e.get("method")}),
                    whole_checks=len(self.whole_checks), excluded=dict(self.excluded),
                    never_fired=list(self.never_fired), seconds=round(self.seconds, 2),
                    ledger=self.ledger.report() if self.ledger else None)


def dv_key(m: dict) -> tuple:
    return (m["t_count"], m["qubits"], m["cx"])


def ordered(book) -> list:
    book = list(book)
    return [r for r in book if r.kind in KIND_FIRST] + [r for r in book if r.kind not in KIND_FIRST]


# ------------------------------------------------------------------------------------------------ windows
def _seq(c):
    if J.is_ir(c):
        return [(g.name, tuple(g.qubits), g.cond, g.cbit) for g in c.gates]
    return list(c.ops)


def window(old, new):
    """(old_local, new_local, qubits, span) of the changed middle, re-indexed to the qubits it touches;
    None when not window-checkable (different qubit count, measurement / classical control inside)."""
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
            c = J.IRCircuit(len(qs)) if hasattr(J, "IRCircuit") else None
            from circuitevolve.ir import Circuit as IRC
            c = IRC(len(qs))
            for g in w:
                c.add(g[0], *[loc[q] for q in g[1]])
            return c
    else:
        def build(w):
            return ([(g, tuple(loc[q] for q in qq), ang) for g, qq, ang in w], len(qs))
    return build(wa), build(wb), qs, (p, len(a) - s, len(b) - s)


# ------------------------------------------------------------------------------------------------ pre-passes
def prefilter(circuit, book) -> tuple:
    """(usable rules, {rule: reason}) from the DECLARED preconditions only. Free: no trigger runs."""
    d = describe(circuit)
    keep, out = [], {}
    for r in book:
        why = r.precondition.excludes(d)
        if why:
            out[r.name] = why
        else:
            keep.append(r)
    return keep, out


def trigger_prepass(circuit, book, opcode_budget=None, ledger=None) -> tuple:
    """(rules that match somewhere on this circuit, names that match nowhere, opcode report).

    V4_README section 0: `never_fires` cost 20.86 h of the P2 run to discover nothing, because
    `evaluate()` computed `n_match` and then ran both `optimize` calls anyway. A trigger-only pass over
    the whole suite x 6 rules costs 0.48 s."""
    keep, none, rep = [], [], {}
    for r in book:
        ms, b = _call(r.trigger, circuit, r, opcode_budget, rep_ops := {}, ledger=ledger)
        rep[r.name] = dict(b, opcodes_total=rep_ops.get(r.name))
        if ms is None:
            none.append(r.name)
        else:
            (keep if ms else none).append(r if ms else r.name)
    return keep, none, rep


# ------------------------------------------------------------------------------------------------ orders
def solo_runs(circuit, book, eps, reference=None, pass_limit=PASS_LIMIT, opcode_budget=None,
              ledger_total=None) -> dict:
    """{rule name: Result of that rule ALONE on this circuit}. Computed once and shared by every order."""
    return {r.name: optimize(circuit, [r], eps, reference=reference, pass_limit=pass_limit, order="book",
                             opcode_budget=opcode_budget, ledger_total=ledger_total)
            for r in book}


def gain_order(circuit, book, base_t: int, solo: dict) -> tuple:
    """Order rules for THIS circuit by their solo gain, largest first, inside the reconstruction-first
    groups. Prevents a weaker rule from consuming matches a stronger one needs."""
    gains = {r.name: base_t - solo[r.name].cost["t_count"] for r in book}
    key = lambda r: -gains[r.name]                                 # noqa: E731
    first = sorted([r for r in book if r.kind in KIND_FIRST], key=key)
    rest = sorted([r for r in book if r.kind not in KIND_FIRST], key=key)
    return first + rest, gains


# ------------------------------------------------------------------------------------------------ entry
def optimize(circuit, book, eps: float, reference=None, pass_limit: int = PASS_LIMIT,
             label: str | None = None, order: str = "best", ledger: Ledger | None = None,
             ledger_total: float | None = None, solo: dict | None = None,
             opcode_budget: int | None = None, skip_prepass: bool = False,
             price_first: bool = True) -> Result:
    """Run `book` on `circuit`. `ledger` continues an existing budget (the book's draws are already in it);
    `ledger_total` starts a fresh one at that total (default: eps).

    `price_first=True` (the default, V4_README 6.4) drops an application that does not lower the cost
    WITHOUT verifying it: qft_8 attempts 40 and keeps 19, pricing costs 1.4 ms and a whole-circuit check
    48 ms, and acceptance only ever depended on the kept ones.

    `price_first=False` restores v3's order - verify, then price - which verifies every application the
    rule proposes. It is slower by exactly the work P0 removed and is here for AUDITS: the planted-bug
    gate (v4/tools/planted_gate.py) needs to observe the verifier's verdict on a control rule that does
    not improve anything, and a correctness sweep over a rule's whole match set needs the same."""
    check_frozen()
    t0 = time.time()
    book = list(book)
    if not book:
        led = ledger or Ledger(eps if ledger_total is None else ledger_total)
        return _finish(circuit, circuit, led, [], 0, t0, [], order_choice={})

    excluded, never = {}, []
    if not skip_prepass:
        book, excluded = prefilter(circuit, book)
        if not book:
            led = ledger or Ledger(eps if ledger_total is None else ledger_total)
            r = _finish(circuit, circuit, led, [], 0, t0, [], order_choice={})
            r.excluded = excluded
            return r

    if order in ("best", "gain", "min_all") and len(book) > 1:
        return _multi_order(circuit, book, eps, reference, pass_limit, label, order, ledger, ledger_total,
                            solo, opcode_budget, excluded, t0, price_first)
    return _run(circuit, ordered(book), eps, reference, pass_limit, ledger, ledger_total, opcode_budget,
                excluded, never, t0, price_first)


def _multi_order(circuit, book, eps, reference, pass_limit, label, order, ledger, ledger_total, solo,
                 opcode_budget, excluded, t0, price_first=True) -> Result:
    """'best' / 'gain' / 'min_all': the solo runs are computed ONCE here and shared by both orderings."""
    total = ledger.total if ledger is not None else (eps if ledger_total is None else ledger_total)
    base = _price_fn(circuit, eps, ledger, ledger_total, reference)(circuit)
    # trigger-only pre-pass: a rule that matches NOWHERE on this circuit needs no solo run (V4_README 5.1)
    live, dead, _ = trigger_prepass(circuit, book, opcode_budget,
                                    ledger or Ledger(total))
    if not live:
        led = ledger or Ledger(total)
        r = _finish(circuit, circuit, led, [], 0, t0, [], order_choice=dict(chosen="no rule triggers"))
        r.excluded, r.never_fired = excluded, dead
        return r
    book = live
    if solo is None:
        solo = solo_runs(circuit, book, eps, reference, pass_limit, opcode_budget, ledger_total=total)
    firing = [r for r in book if any(e["accepted"] for e in solo[r.name].log)]
    never = dead + [r.name for r in book if r not in firing]
    if order != "min_all" and len(firing) <= 1:
        # at most one rule changes this circuit: if no other rule matches on its result, the solo run IS
        # the result (no interaction to order), which saves the two full re-runs
        only = firing[0] if firing else book[0]
        res = solo[only.name]
        if all(not r.trigger(res.circuit) for r in book if r is not only):
            res.order_choice = dict(chosen="solo", reason="only one rule fires on this circuit")
            res.rule_order = [only.name] + [r.name for r in book if r is not only]
            res.excluded, res.never_fired = excluded, never
            return res

    def run(order_book, gains=None):
        r = _run(circuit, order_book, eps, reference, pass_limit,
                 None if ledger is None else ledger.copy(), ledger_total, opcode_budget, excluded, never,
                 t0, price_first)
        if gains is not None:
            r.solo_gains = gains
        return r

    gbook, gains = gain_order(circuit, book, base["t_count"], solo)
    g = run(gbook, gains)
    if order == "gain":
        g.order_choice = dict(chosen="gain")
        return g
    b = run(ordered(book))
    cands = [("gain", g), ("book", b)]
    if order == "min_all":
        cands += [(f"solo:{n}", solo[n]) for n in sorted(solo)]
    name, best = min(cands, key=lambda kv: dv_key(kv[1].cost))     # ties: gain, then book, then solos
    best.order_choice = dict(gain=g.cost["t_count"], book=b.cost["t_count"], chosen=name,
                             solos={n: solo[n].cost["t_count"] for n in sorted(solo)}
                             if order == "min_all" else None)
    best.solo_gains = gains
    best.excluded, best.never_fired = excluded, never
    return best


def _price_fn(circuit, eps, ledger, ledger_total, price_ref=None):
    """Pricing while optimising, at the eps_rz of the circuit the run is MEASURED AGAINST.

    The frozen metric's convention (core/metric.py) is eps_rz = eps_synth / N_Rz, and the runner prices
    candidates at the INPUT's eps_rz because N_Rz only ever drops, so the synthesis bound N_Rz * eps_rz
    still holds. `price_ref` is that input: the ORIGINAL circuit, which is also the verification
    reference - NOT whatever intermediate circuit this particular call happens to start from.

    This matters, and it bit this build. `check_on_target` applies a candidate to the book's cached
    residual, which has fewer rotations than the original (qft_8: 33 vs 48) and therefore a COARSER
    eps_rz. Pricing there made gridsynth words shorter and turned two merges on qft_8 into a 6 T
    "improvement" that a run from the original does not see. Pricing against the reference removes the
    dependence on where the search happens to start.
    """
    exact = J.is_exact
    total = (ledger.total if ledger is not None else (eps if ledger_total is None else ledger_total))
    base = circuit if price_ref is None else price_ref
    eps_rz_in = None if exact(base) else J.measure(base, total)["eps_rz"]

    def price(c):
        return J.measure(c) if exact(c) else J.measure(c, total, eps_rz=eps_rz_in)
    return price


# ------------------------------------------------------------------------------------------------ the loop
def _run(circuit, book, eps, reference, pass_limit, ledger, ledger_total, opcode_budget, excluded, never,
         t0, price_first=True) -> Result:
    opcodes: dict = {}
    led = ledger if ledger is not None else Ledger(eps if ledger_total is None else ledger_total)
    ref = circuit if reference is None else reference
    exact = J.is_exact
    price = _price_fn(circuit, eps, led, ledger_total, reference)

    def check(cand, refc, rule, budget):
        """Verdict of cand vs refc under the rule's two tags, via the cheapest certificate that applies
        (v4/judge/certify.py): `algebraic` for the phase-folding class - O(ops), no matrices, and a
        proof - then `exact_ring`, `branch_kraus` or `numeric_block`."""
        return certify(cand if False else refc, cand, rule, budget, EXACT_TOL)

    def record(entry, v, scope):
        """`v` is a Certificate (window / whole-circuit check) - see v4/judge/certify.py."""
        entry.update(v.to_verdict_fields())
        entry["scope"] = scope

    log, whole, passes, cur = [], [], 0, circuit
    cur_cost = price(circuit)
    disabled = set()
    while book and passes < pass_limit:
        passes += 1
        fired = False
        for rule in book:
            if rule.name in disabled:
                continue
            start, start_cost = cur, cur_cost
            snaps = []                         # (entry, circuit after, cost after, charge of this application)
            changed = True
            while changed:
                changed = False
                matches, rep = _call(rule.trigger, cur, rule, opcode_budget, opcodes,
                                    ledger=led)
                if matches is None:
                    log.append(dict(rule=rule.name, pass_=passes, match=None, accepted=False, verified=False,
                                    reason=rep["reason"], traceback=rep.get("traceback", "")))
                    disabled.add(rule.name)
                    break
                for i, m in enumerate(matches):
                    entry = dict(rule=rule.name, pass_=passes, match=i, accepted=False)
                    spent_before = led.draws.get(rule.name, 0.0)
                    cand, rep = _call(rule.apply, cur, rule, opcode_budget, opcodes, m,
                                      ledger=led)
                    if cand is None:
                        entry.update(verified=False, reason=rep["reason"], traceback=rep.get("traceback", ""))
                        log.append(entry)
                        disabled.add(rule.name)
                        break
                    # ---- PRICE BEFORE VERIFY (V4_README 6.4): a candidate that does not lower the
                    # cost is dropped here, for 1.4 ms, instead of after a 48 ms whole-circuit check.
                    # With price_first=False the two steps swap, which verifies every application.
                    try:
                        c_cost = price(cand)
                    except Exception as e:                               # noqa: BLE001 (rule output)
                        entry.update(verified=False, reason=f"cannot price candidate: {type(e).__name__}: {e}")
                        log.append(entry)
                        disabled.add(rule.name)
                        break
                    entry["cost"] = {k: c_cost[k] for k in ("t_count", "rotations", "cx", "qubits")}
                    improves = dv_key(c_cost) < dv_key(cur_cost)
                    if price_first and not improves:
                        back = led.draws.get(rule.name, 0.0) - spent_before
                        if back > 0:
                            led.refund(rule.name, back)           # dropped: the rule keeps no error
                        entry.update(verified=None, reason="no cost decrease", priced_out=True)
                        log.append(entry)
                        continue
                    # ---- verify the application
                    try:
                        w = None if rule.resource_class != "unitary" else window(cur, cand)
                        if w is None:
                            v = check(cand, ref, rule, led.remaining)
                            record(entry, v, "whole")
                            d = float(v.distance or 0.0) if v.kind == "numeric_block" else 0.0
                            d_charge = max(0.0, d - led.spent) if v.ok else 0.0
                        else:
                            wo, wn, qs, span = w
                            entry["window"] = dict(qubits=len(qs), old_ops=span[1] - span[0],
                                                   new_ops=span[2] - span[0], at=span[0])
                            if span[1] == span[0] and span[2] == span[0]:
                                entry.update(verified=True, mode="identical", method="identical",
                                             certified=True, scope="window", distance=0.0, reason="",
                                             certificate="identical")
                                d_charge = 0.0
                            else:
                                v = check(wn, wo, rule, led.remaining)
                                record(entry, v, "window")
                                d_charge = float(v.distance or 0.0) if v.kind == "numeric_block" else 0.0
                    except Exception as e:                               # noqa: BLE001 (rule code)
                        entry.update(verified=False,
                                     reason=f"exception in apply/verify: {type(e).__name__}: {e}",
                                     traceback=traceback.format_exc()[-1500:])
                        log.append(entry)
                        disabled.add(rule.name)
                        break
                    if not improves:
                        back = led.draws.get(rule.name, 0.0) - spent_before
                        if back > 0:
                            led.refund(rule.name, back)
                        entry.update(accepted=False, priced_out=True,
                                     reason=(entry.get("reason") or "") + " | no cost decrease")
                        log.append(entry)
                        continue
                    if entry["verified"]:
                        # a rule that drew its own error already spent it; the runner charges only the
                        # difference between the MEASURED distance and what the rule reserved
                        drawn = led.draws.get(rule.name, 0.0) - spent_before
                        d_charge = max(0.0, d_charge - drawn)
                        entry["rule_drew"] = drawn
                        if d_charge and not led.draw(rule.name, d_charge):
                            entry.update(accepted=False, reason=f"draw {d_charge:.3e} exceeds the remaining "
                                                                f"rule budget {led.remaining:.3e}")
                            log.append(entry)
                            continue
                        cur, cur_cost = cand, c_cost
                        entry.update(accepted=True, charged=d_charge)
                        snaps.append((entry, cur, cur_cost, d_charge))
                        fired = changed = True
                    log.append(entry)
                    if changed:
                        break                   # re-trigger on the new circuit
            if snaps:                           # whole-circuit check once per rule pass
                cur, cur_cost = _pass_check(rule, ref, snaps, start, start_cost, check, led, whole,
                                            disabled, passes)
        if not fired:
            break
    res = _finish(circuit, cur, led, log, passes, t0, whole, order_choice={})
    res.rule_order = [r.name for r in book]
    res.excluded, res.never_fired, res.opcodes = excluded, never, opcodes
    return res


def _call(fn, circuit, rule, opbudget, opcodes, *extra, ledger=None):
    """Call rule code, under an opcode budget and with the live error ledger installed.

    `v4.api.budget` is how a rule sees the shared error budget (V4_README section 8): `remaining()` and
    `draw(amount)`. The ledger is installed here, around every call into rule code, so a rule can decide
    how much of the 5e-4 its own rewrite is worth - and so a rule running OUTSIDE a runner sees 0.0 and
    a refused draw, and must then do the exact rewrite or nothing.

    -> (value, {}) on success, or (None, {'reason': ...}) when the rule raised or ran out of budget."""
    try:
        with api_budget.installed(ledger, rule.name):
            if opbudget:
                b = OpcodeBudget(opbudget)
                try:
                    with b:
                        out = fn(circuit, *extra)
                finally:
                    opcodes[rule.name] = opcodes.get(rule.name, 0) + b.used
                return out, b.report()
            return fn(circuit, *extra), {}
    except OpcodeExceeded as e:
        return None, dict(reason=str(e))
    except Exception as e:                                               # noqa: BLE001 (rule code)
        return None, dict(reason=f"exception in {getattr(fn, '__name__', 'rule')}: {type(e).__name__}: {e}",
                          traceback=traceback.format_exc()[-1500:])


def _pass_check(rule, ref, snaps, start, start_cost, check, led, whole, disabled, passes):
    entry0, last, last_cost, _ = snaps[-1]
    if entry0.get("scope") == "whole" and entry0.get("verified"):
        whole.append(dict(rule=rule.name, pass_=passes, after_application=len(snaps) - 1, ok=True,
                          method=entry0.get("method"), certified=entry0.get("certified", False),
                          distance=entry0.get("distance"), reason="",
                          reused="per-application whole check"))
        return last, last_cost

    def ok_at(k):
        c = snaps[k][1]
        v = check(c, ref, rule, min(led.rule_share, led.spent + EXACT_TOL))
        whole.append(dict(rule=rule.name, pass_=passes, after_application=k, ok=bool(v.ok),
                          method=v.method, certificate=v.kind, certified=bool(v.certified),
                          distance=v.distance, reason=v.reason))
        return v.ok

    if ok_at(len(snaps) - 1):
        return last, last_cost
    lo, hi = 0, len(snaps) - 1                 # first failing snapshot in [lo, hi]; hi known to fail
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
    for e, *_rest in snaps[lo:]:
        if e is not bad:
            e.update(accepted=False, reverted=True)
    for _e, _c, _k, charge in snaps[lo:]:      # give the reverted applications' draws back
        if charge:
            led.refund(rule.name, charge)
    disabled.add(rule.name)
    if lo == 0:
        return start, start_cost
    return snaps[lo - 1][1], snaps[lo - 1][2]


def _finish(circuit, cur, led: Ledger, log, passes, t0, whole, order_choice) -> Result:
    if J.is_exact(cur):
        final = J.measure(cur)
        bound = led.spent
    else:
        final = J.measure(cur, led.total - led.spent)
        bound = led.bound(final["rotations"])
    r = Result(cur, final, led.spent, bound, log, passes, time.time() - t0, whole)
    r.ledger, r.order_choice = led, order_choice
    return r
