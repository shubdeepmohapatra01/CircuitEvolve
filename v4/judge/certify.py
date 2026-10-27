"""Certificate dispatch - V4_README section 6.2. What check a rewrite can actually PROVE.

| certificate     | check                                                   | cost            | proof? |
|-----------------|---------------------------------------------------------|-----------------|--------|
| `algebraic`     | the rule's class supplies a witness; this module        | O(ops),         | yes    |
|                 | re-derives it                                           | no matrices     |        |
| `exact_ring`    | D[omega] equality over Z[omega, 1/sqrt2]                | sparse          | yes (sampled above 2^14) |
| `numeric_block` | phase-aligned operator norm, width-bounded              | ops * 4**n      | bound; certified n <= 10 |
| `branch_kraus`  | K_m|x,0> = c_m|f(x),0>, same c_m for all x, sum|c_m|^2=1| branch-wise     | yes within the branch budget |

The one that matters is the first. **Every** admitted angle rule in v3 was in the phase-folding class,
and today each of its rewrites costs a full-width dense matrix build: on qft_8, 120 of 190 checks, at
roughly 48 ms each, and at 11-20 qubits the matrix check is a Haar-statevector LOWER BOUND rather than a
certified one. The algebraic witness for that class is an exact identity on the phase polynomial: a
Hadamard-free Clifford+Rz circuit acts as

    U|x> = e^{i phi(x)} |A x + b>

so it is determined completely by its affine part (A, b) and its phase polynomial phi. Both are
re-derived here in O(ops) with no matrices, by the frozen update rules `cx a,b: p[b] ^= p[a]` and
`x a: c[a] ^= 1`. That is ~100x cheaper AND upgrades the hot path from uncertified to a proof.

SOUNDNESS. The witness compares the per-label angle sums individually, modulo 2 pi. Since every label's
indicator v_L(x) = <p_L, x> xor c_L takes values in {0, 1}, equal angles mod 2 pi give equal phases, and
matching every label individually implies matching phi. It is therefore sound (it can never accept an
inequivalent pair) and deliberately conservative (it can decline a pair that is in fact equivalent, e.g.
when angle mass moves between the labels (p, 0) and (p, 1), whose indicators differ by a constant). A
declined witness falls through to the numeric check, so conservatism costs time, never correctness.

Because this is new code that can ACCEPT a rewrite, it carries its own planted-bug suite
(`v4/tests/test_p4.py`): nine mutations of a correct rewrite - wrong sign, wrong angle, dropped cx,
swapped control and target, extra x, a phase moved to the wrong label - each of which it must reject.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..api import pauli, phasepoly
from . import dv as J, kraus

KINDS = ("algebraic", "exact_ring", "numeric_block", "branch_kraus")
STATS: dict = dict(algebraic_applied=0, algebraic_declined=0, algebraic_merge=0,
                   algebraic_phasepoly=0, exact_ring=0, numeric_block=0, branch_kraus=0,
                   algebraic_seconds=0.0, other_seconds=0.0)


@dataclass
class Certificate:
    """The verdict of one check.

    THREE outcomes, not two. `ok=True` is a pass; `ok=False` with `unverifiable=False` is a REFUTATION;
    `ok=False` with `unverifiable=True` means the check could not RUN - too wide, or refused - and must
    never be read as a rejection. A rule that cannot be checked at this width is not a rule that failed
    a check. v3 collapsed the two: its `relaxed` mode returned `method='skipped'` and the harness
    recorded a verification FAILURE, which is the same category error that lost eight of its rules to
    `rz(...) is not a multiple of pi/4`. The application is still NOT kept either way - nothing
    unverified is ever accepted - but the rule is not branded wrong, and the feedback says what to
    change: make the construction narrower.
    """

    kind: str
    ok: bool
    certified: bool                 # True only when the check is a PROOF
    distance: float | None = None
    bound: float | None = None
    reason: str = ""
    method: str = ""
    witness: dict = field(default_factory=dict)
    seconds: float = 0.0
    unverifiable: bool = False      # the check could not RUN (too wide, refused), not "the rule is wrong"

    def __bool__(self):
        return self.ok

    def to_verdict_fields(self) -> dict:
        return dict(verified=self.ok, mode=("exact" if self.kind in ("algebraic", "exact_ring")
                                            else ("relaxed" if self.kind == "branch_kraus" else "approx")),
                    distance=self.distance, reason=self.reason, method=self.method,
                    certified=self.certified, certificate=self.kind,
                    unverifiable=self.unverifiable)


def _local(ops):
    """(local ops, n) for an op list or a (ops, n) pair, re-indexed from 0."""
    if isinstance(ops, tuple) and len(ops) == 2 and isinstance(ops[1], int):
        return list(ops[0]), int(ops[1])
    if hasattr(ops, "ops") and hasattr(ops, "n"):
        return list(ops.ops), int(ops.n)
    return None, None


def algebraic(old, new) -> Certificate:
    """The algebraic certificate: two witnesses, tried in order, or a DECLINE.

    1. **Pauli merge** (`pauli.merge_witness`). This is the class every admitted angle rule in v3 belongs
       to: one rotation deleted, one earlier rotation's angle changed by the signed deleted angle, the
       Clifford skeleton untouched, and every rotation in between commuting with the moved axis. It works
       straight through Hadamards, because the axes are front-frame Paulis.
    2. **Phase polynomial** (`phasepoly.witness`). Covers any rewrite of a Hadamard-free segment, not
       just a merge - a reordering, a re-association, a different CNOT tree - by comparing the affine
       part and the phase polynomial.

    `method='declined'` means neither class applies and the caller must fall through to a numeric check.
    A `False` with any other method is a REFUTATION, and is certified.
    """
    t0 = time.perf_counter()
    a_ops, na = _local(old)
    b_ops, nb = _local(new)
    if a_ops is None or b_ops is None or na != nb:
        STATS["algebraic_declined"] += 1
        return Certificate("algebraic", False, False, reason="not two op lists on the same qubits",
                           method="declined", seconds=time.perf_counter() - t0)
    ok, why, det = pauli.merge_witness(a_ops, b_ops)
    if ok:
        dt = time.perf_counter() - t0
        STATS["algebraic_applied"] += 1
        STATS["algebraic_merge"] += 1
        STATS["algebraic_seconds"] += dt
        return Certificate("algebraic", True, True, distance=0.0, bound=0.0, method="pauli-merge",
                           witness=dict(det, ops=len(a_ops), qubits=na), seconds=dt)
    merge_refuted = not why.startswith("class does not apply")
    if phasepoly.is_hadamard_free(a_ops) and phasepoly.is_hadamard_free(b_ops):
        ok2, why2 = phasepoly.witness(a_ops, b_ops, na)
        dt = time.perf_counter() - t0
        STATS["algebraic_applied"] += 1
        STATS["algebraic_seconds"] += dt
        if ok2:
            STATS["algebraic_phasepoly"] += 1
            pa = phasepoly.polynomial(a_ops, na)
            return Certificate("algebraic", True, True, distance=0.0, bound=0.0,
                               method="phase-polynomial",
                               witness=dict(labels=len(pa[0]),
                                            affine=dict(p=list(pa[1].p), c=list(pa[1].c)),
                                            ops=len(a_ops), qubits=na), seconds=dt)
        return Certificate("algebraic", False, True, method="phase-polynomial", reason=why2, seconds=dt)
    dt = time.perf_counter() - t0
    STATS["algebraic_seconds"] += dt
    if merge_refuted:
        STATS["algebraic_applied"] += 1
        return Certificate("algebraic", False, True, method="pauli-merge", reason=why, seconds=dt)
    STATS["algebraic_declined"] += 1
    return Certificate("algebraic", False, False, method="declined",
                       reason=f"no algebraic class applies ({why})", seconds=dt)


def certify_relaxed_window(old_local, new_local, data_wires, anc_wires, rule,
                           allowance: float, exact_tol: float = 1e-8) -> Certificate:
    """`branch_kraus` on a WINDOW of an ancilla / measurement rewrite (see runner.relaxed_window).

    The window carries its own ancillas, so the data register is `data_wires` and everything in
    `anc_wires` must start and end in |0>. This is what makes the phase-gradient family checkable: the
    whole candidate has 34 qubits on qft_8, the window has far fewer."""
    t0 = time.perf_counter()
    n = len(data_wires) + len(anc_wires)
    STATS["branch_kraus"] += 1
    if n > kraus.MAX_QUBITS:
        return Certificate("branch_kraus", False, False, method="too-wide", bound=allowance,
                           unverifiable=True,
                           reason=f"NOT VERIFIABLE (not a rejection): the window has {n} qubits > "
                                  f"{kraus.MAX_QUBITS}, and a dense branch-wise check needs "
                                  f"2^{n} amplitudes per state. Make the construction narrower - fewer "
                                  f"register bits, or one group at a time instead of a whole cascade.",
                           seconds=time.perf_counter() - t0)
    allow = min(exact_tol, allowance) if rule.error_class == "exact" else allowance
    ref = kraus.reference_state_of(list(old_local), len(data_wires)) \
        if _measurement_free(old_local) else None
    if ref is None:
        return Certificate("branch_kraus", False, False, method="declined", bound=allowance,
                           reason="the window's OLD side measures; it cannot define a state map",
                           seconds=time.perf_counter() - t0)
    cand = _ops_to_ir_numeric(new_local, n)
    kv = kraus.check(cand, ref, len(data_wires), allow, data_map=list(data_wires))
    dt = time.perf_counter() - t0
    STATS["other_seconds"] += dt
    return Certificate("branch_kraus", kv.ok, kv.certified, distance=kv.distance, bound=kv.bound,
                       reason=kv.reason, method=kv.method + "-window",
                       witness=dict(leak=kv.leak, phase_spread=kv.phase_spread,
                                    prob_error=kv.prob_error, n_inputs=kv.n_inputs,
                                    n_branches=kv.n_branches, data_qubits=len(data_wires),
                                    ancillas=len(anc_wires)), seconds=dt)


def _measurement_free(ops) -> bool:
    return not any((op[0] in ("measure", "and_uncompute")) for op in ops)


def certify(old, new, rule, allowance: float, exact_tol: float = 1e-8) -> Certificate:
    """The verdict on `new` vs `old` under `rule`'s two tags, by the cheapest certificate that applies.

    Order: `algebraic` (if the rule allows it and the class applies) -> `exact_ring` (both Clifford+T)
    -> `branch_kraus` (ancillas / measurement) -> `numeric_block`.
    """
    want = getattr(rule, "certificate", "auto")
    if want in ("auto", "algebraic") and rule.resource_class == "unitary":
        c = algebraic(old, new)
        if c.method != "declined":
            if c.ok or want == "algebraic":
                return c
            # the witness proved them different: no cheaper check can rescue that, and for an `exact`
            # rule it is the answer. An `approx` rule may still be inside its allowance, so fall through.
            if rule.error_class == "exact":
                return c
    t0 = time.perf_counter()
    if rule.resource_class != "unitary":
        STATS["branch_kraus"] += 1
        kind = "branch_kraus"
        if kraus.is_exact_angles(new) and kraus.is_exact_angles(old):
            # both sides Clifford+T: the FROZEN exact relaxed check decides it, so floating point never
            # accepts a Clifford+T candidate (CLAUDE.md invariant 1)
            v = J.verify_memo(new, old, mode="relaxed")
        else:
            # ancillas TOGETHER WITH continuous angles - what the frozen `relaxed` mode cannot express
            # at all, and the one thing P5 unfreezes. See v4/judge/kraus.py.
            allow = min(exact_tol, allowance) if rule.error_class == "exact" else allowance
            kv = _kraus(old, new, allow)
            dt = time.perf_counter() - t0
            STATS["other_seconds"] += dt
            if kv.method == "skipped":
                return Certificate("branch_kraus", False, False, method="too-wide", bound=kv.bound,
                                   unverifiable=True,
                                   reason=f"NOT VERIFIABLE (not a rejection): {kv.reason}. Make the "
                                          f"construction narrower, or rewrite one group at a time "
                                          f"instead of a whole cascade.", seconds=dt)
            return Certificate("branch_kraus", kv.ok, kv.certified, distance=kv.distance,
                               bound=kv.bound, reason=kv.reason, method=kv.method,
                               witness=dict(leak=kv.leak, phase_spread=kv.phase_spread,
                                            prob_error=kv.prob_error, n_inputs=kv.n_inputs,
                                            n_branches=kv.n_branches), seconds=dt)
    elif J.is_exact(new) and J.is_exact(old):
        STATS["exact_ring"] += 1
        v = J.verify_memo(new, old, mode="exact")
        kind = "exact_ring"
    else:
        STATS["numeric_block"] += 1
        allow = min(exact_tol, allowance) if rule.error_class == "exact" else allowance
        v = J.verify_memo(new, old, mode="approx", eps=allow)
        kind = "numeric_block"
    dt = time.perf_counter() - t0
    STATS["other_seconds"] += dt
    return Certificate(kind, bool(v.ok), bool(v.certified), distance=v.distance, bound=v.bound,
                       reason=v.reason, method=v.method, seconds=dt)


def _kraus(old, new, allowance: float):
    """`branch_kraus` on (reference = old, candidate = new). The data qubits are the reference's own;
    every extra candidate qubit is a clean ancilla and must come back to |0>."""
    from circuitevolve.v2.verify import _ops_and_n
    cand = new if isinstance(new, kraus.IRCircuit) else None
    if cand is None:
        ops, n = _ops_and_n(new)
        cand = _ops_to_ir_numeric(ops, n)
    n_data = old.n_qubits if isinstance(old, kraus.IRCircuit) else _ops_and_n(old)[1]
    ref = kraus.reference_state_from_circuit(old, n_data)
    return kraus.check(cand, ref, n_data, float(allowance))


def _ops_to_ir_numeric(ops, n: int):
    """An op list with CONTINUOUS angles as an IRCircuit-shaped object the branch simulator can run.

    `v2.verify.ops_to_ir` refuses this (it is `_norm_angle_gates` that raises NotExact), which is
    precisely the limitation P5 removes. The gates are carried with their angles instead of being
    rewritten into Clifford+T."""
    from circuitevolve.ir import Circuit as IRC, Gate

    class _G(Gate):
        pass

    c = IRC(int(n))
    for op in ops:
        g, qs = op[0], tuple(int(q) for q in op[1])
        a = op[2] if len(op) > 2 else None
        gate = Gate(g, qs) if a is None else Gate(g, qs)
        object.__setattr__(gate, "angle", a) if a is not None else None
        c.gates.append(gate)
    return c


def stats() -> dict:
    tot = STATS["algebraic_applied"] + STATS["exact_ring"] + STATS["numeric_block"] + STATS["branch_kraus"]
    return dict(STATS, total=tot,
                algebraic_share=(STATS["algebraic_applied"] / tot) if tot else 0.0)


def reset() -> None:
    for k in STATS:
        STATS[k] = 0 if isinstance(STATS[k], int) else 0.0
