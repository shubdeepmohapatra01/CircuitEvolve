"""Apply a tier-2 rule library to an exact Clifford+T circuit, to a fixpoint.

Circuit representation: a list of concrete gates (name, qubits) over {h s sdg t tdg x z cx cz}.

Matching (commutation-aware, deterministic, greedy, no backtracking)
    For a start position i whose gate matches pattern[0] (binding its variables), each further pattern gate j is
    searched forward among the next `lookahead` gates on the qubits already bound to pattern[j]'s variables; the
    first gate that matches (consistent bindings, fresh variables bound to fresh qubits) is taken.
    The candidate match at positions p0 < ... < p_last is then VALIDATED: let Q be the union of matched qubits and
    U the unmatched gates strictly between p0 and p_last that touch Q.
      * 'left'  placement: every u in U commutes with every matched gate BEFORE it -> u moves left of the match;
                the replacement is put after all unmatched gates of the range;
      * 'right' placement: every u in U commutes with every matched gate AFTER it -> u moves right of the match;
                the replacement is put before them.
    Gates not touching Q commute with the match trivially. Side condition 'contiguous': U must be empty.
    This is a sufficient condition for the matched gates to be brought together by exact commutations, so the
    rewrite preserves the unitary (rules are verified identities, `rules.verify_rule`).

Fixpoint: repeated deterministic passes (positions in order, rules in library order) until a pass applies nothing.
Every rule strictly decreases (T, gates), so the number of applications is bounded by T0 * G0 + G0.
"""
from __future__ import annotations

import bisect
import time
from collections import Counter

import numpy as np

from .commute import T_GATES, commute

LOOKAHEAD = 24


# ================================================================================================ conversions
def from_ir(c) -> tuple[list, int]:
    """ir.Circuit -> (gates, n); ccx/ccz expanded to Clifford+T; measurement / feed-forward refused."""
    e = c.expand("clifford_t")
    out = []
    for g in e.gates:
        if g.name == "measure" or g.cond is not None:
            raise ValueError("tier 2 is unitary-only: circuit has measurements / classical control")
        out.append((g.name, tuple(g.qubits)))
    return out, c.n_qubits


def load_qasm(path) -> tuple[list, int]:
    from ..verify import parse_qasm_ir
    with open(path) as f:
        return from_ir(parse_qasm_ir(f.read()))


def to_qasm(gates, n) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{n}];"]
    for g, qs in gates:
        lines.append(f"{g} " + ",".join(f"q[{q}]" for q in qs) + ";")
    return "\n".join(lines) + "\n"


def to_ops(gates):
    return [(g, tuple(qs), None) for g, qs in gates]


def cost(gates) -> tuple:
    return (sum(1 for g, _ in gates if g in T_GATES), len(gates))


# ================================================================================================ matching
def _qpos(gates, n) -> list:
    qp = [[] for _ in range(n)]
    for i, (_, qs) in enumerate(gates):
        for q in qs:
            qp[q].append(i)
    return qp


def _bind(pg, cg, env, used) -> dict | None:
    """Try to match pattern gate pg=(name, vars) to concrete gate cg=(name, qubits) under env (var->qubit)."""
    if pg[0] != cg[0]:
        return None
    orders = [cg[1]]
    if cg[0] == "cz":
        orders.append(cg[1][::-1])
    for qs in orders:
        new = dict(env)
        ok = True
        for v, q in zip(pg[1], qs):
            if v in new:
                if new[v] != q:
                    ok = False
                    break
            else:
                if q in used or q in new.values():
                    ok = False
                    break
                new[v] = q
        if ok:
            return new
    return None


def find_match(gates, qp, i, rule, lookahead: int = LOOKAHEAD):
    """Return (positions, env, placement) for a match of `rule` starting at gate i, or None."""
    pat = rule.pattern
    env = _bind(pat[0], gates[i], {}, set())
    if env is None:
        return None
    pos = [i]
    taken = {i}
    last = i
    for pg in pat[1:]:
        qset = sorted({env[v] for v in pg[1] if v in env})
        cand = []
        for q in qset:
            lst = qp[q]
            k = bisect.bisect_right(lst, last)
            cand.extend(lst[k:k + lookahead])
        found = None
        for p in sorted(set(cand))[:lookahead]:
            if p in taken:
                continue
            e2 = _bind(pg, gates[p], env, set())
            if e2 is not None:
                found = (p, e2)
                break
        if found is None:
            return None
        p, env = found
        pos.append(p)
        taken.add(p)
        last = p
    p0, pl = pos[0], pos[-1]          # positions increase along the pattern by construction
    qm = sorted({q for p in pos for q in gates[p][1]})
    between = set()
    for q in qm:
        lst = qp[q]
        a, b = bisect.bisect_right(lst, p0), bisect.bisect_left(lst, pl)
        between.update(lst[a:b])
    between -= taken
    if not between:
        return pos, env, "left"
    if rule.side == "contiguous":
        return None
    U = sorted(between)
    left_ok = all(commute(gates[u], gates[p]) for u in U for p in pos if p < u)
    if left_ok:
        return pos, env, "left"
    right_ok = all(commute(gates[u], gates[p]) for u in U for p in pos if p > u)
    if right_ok:
        return pos, env, "right"
    return None


def rewrite(gates, pos, env, placement, rule) -> list:
    p0, pl = pos[0], pos[-1]
    taken = set(pos)
    mid = [gates[k] for k in range(p0 + 1, pl) if k not in taken]
    rep = [(g, tuple(env[v] for v in vs)) for g, vs in rule.replacement]
    body = mid + rep if placement == "left" else rep + mid
    return gates[:p0] + body + gates[pl + 1:]


def apply_library(gates, n, library, max_passes: int = 1000, lookahead: int = LOOKAHEAD, log_apps: bool = False,
                  time_limit_s: float = 600.0) -> dict:
    """Apply library rules to a fixpoint. Returns dict(gates, cost_before, cost_after, apps (Counter by rule name),
    t_saved (Counter), passes, applications [(rule, pos0, dT, dG)] if log_apps, fixpoint (bool))."""
    t0 = time.time()
    rules = list(library.rules) if hasattr(library, "rules") else list(library)
    by_first = {}
    for r in rules:
        by_first.setdefault(r.pattern[0][0], []).append(r)
    g = list(gates)
    c0 = cost(g)
    apps, tsaved, gsaved, applog = Counter(), Counter(), Counter(), []
    passes, fix = 0, False
    while passes < max_passes:
        passes += 1
        changed = False
        qp = _qpos(g, n)
        i = 0
        while i < len(g):
            hit = False
            for r in by_first.get(g[i][0], ()):
                m = find_match(g, qp, i, r, lookahead)
                if m is None:
                    continue
                pos, env, pl = m
                dt, dg = r.cost_delta()
                g = rewrite(g, pos, env, pl, r)
                qp = _qpos(g, n)
                apps[r.name] += 1
                tsaved[r.name] += dt
                gsaved[r.name] += dg
                if log_apps:
                    applog.append((r.name, pos[0], dt, dg))
                hit = changed = True
                break
            if hit:
                i = max(0, i - 2)
            else:
                i += 1
            if time.time() - t0 > time_limit_s:
                break
        if not changed:
            fix = True
            break
        if time.time() - t0 > time_limit_s:
            break
    c1 = cost(g)
    assert c0[0] - c1[0] == sum(tsaved.values()) and c0[1] - c1[1] == sum(gsaved.values())
    return dict(gates=g, cost_before=c0, cost_after=c1, apps=apps, t_saved=tsaved, g_saved=gsaved, passes=passes,
                applications=applog, fixpoint=fix, seconds=round(time.time() - t0, 3))


# ================================================================================================ guards
_M1 = {
    "h": np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2),
    "x": np.array([[0, 1], [1, 0]], dtype=complex),
    "z": np.diag([1, -1]).astype(complex),
    "s": np.diag([1, 1j]),
    "sdg": np.diag([1, -1j]),
    "t": np.diag([1, np.exp(1j * np.pi / 4)]),
    "tdg": np.diag([1, np.exp(-1j * np.pi / 4)]),
}


def simulate(gates, n, psi):
    """Float statevector simulation (qubit q = axis q). GUARD ONLY — never used to accept a rule."""
    psi = psi.reshape([2] * n).copy()
    for g, qs in gates:
        if g in _M1:
            psi = np.moveaxis(np.tensordot(_M1[g], psi, axes=([1], [qs[0]])), 0, qs[0])
        elif g == "cx":
            c, t = qs
            idx = [slice(None)] * n
            idx[c] = 1
            sub = psi[tuple(idx)]
            tt = t if t < c else t - 1
            psi[tuple(idx)] = np.flip(sub, axis=tt).copy()
        elif g == "cz":
            a, b = qs
            idx = [slice(None)] * n
            idx[a] = 1
            idx[b] = 1
            psi[tuple(idx)] *= -1
        else:
            raise ValueError(g)
    return psi.reshape(-1)


def numeric_guard(gates_a, gates_b, n, n_states: int = 2, seed: int = 0, max_qubits: int = 22) -> dict:
    """Random-statevector check |<A psi|B psi>| == 1 (same global phase across states). A guard, not a proof."""
    if n > max_qubits:
        return dict(ok=None, method="skipped", reason=f"n={n} > {max_qubits}")
    rng = np.random.default_rng(seed)
    phases, worst = [], 0.0
    for _ in range(n_states):
        psi = rng.normal(size=2 ** n) + 1j * rng.normal(size=2 ** n)
        psi /= np.linalg.norm(psi)
        a, b = simulate(gates_a, n, psi), simulate(gates_b, n, psi)
        ov = np.vdot(a, b)
        phases.append(ov / abs(ov) if abs(ov) > 1e-12 else 0)
        worst = max(worst, float(np.linalg.norm(b - ov / max(abs(ov), 1e-300) * a)))
    same_phase = all(abs(p - phases[0]) < 1e-8 for p in phases)
    ok = worst < 1e-8 and same_phase
    return dict(ok=bool(ok), method=f"statevector-{n_states}", distance=worst, certified=False)


def exact_guard(gates_a, gates_b, n, max_qubits: int = 10, time_limit_s: float = 300.0) -> dict:
    """Whole-circuit exact check with the v2 verifier (frozen D[omega] simulator, exhaustive basis inputs)."""
    if n > max_qubits:
        return dict(ok=None, method="skipped", reason=f"n={n} > {max_qubits}")
    from ..verify import Limits, verify
    v = verify((to_ops(gates_b), n), (to_ops(gates_a), n), mode="exact",
               limits=Limits(time_limit_s=time_limit_s))
    return dict(ok=bool(v.ok), method=v.method, certified=bool(v.certified), reason=v.reason)
