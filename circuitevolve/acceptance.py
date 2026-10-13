"""Verifier acceptance suite: known-good constructions and planted-bug mutants.

The verifier is trusted only if it classifies every case correctly (verdict AND failing level).
Each mutant isolates one failure mode the search could exploit if the verifier missed it.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .baselines import cuccaro, gidney, pyzx_opt
from .ir import TIER_A, TIER_B, Circuit, Gate

N_SCHEDULE = (1, 2, 3, 4, 6)


@dataclass(frozen=True)
class Case:
    name: str
    construct: object
    vocab: frozenset
    expect_ok: bool
    expect_level: str          # "pass" for accepts
    what: str
    n_values: tuple = N_SCHEDULE


def _edit(base, fn):
    def construct(n):
        c = base(n)
        out = fn(c, n)
        return c if out is None else out
    return construct


def _drop(pred, first_only=False):
    def fn(c: Circuit, n):
        keep, dropped = [], False
        for i, g in enumerate(c.gates):
            if pred(g, i, c, n) and not (first_only and dropped):
                dropped = True
                continue
            keep.append(g)
        c.gates = keep
    return fn


def _map(pred, f, first_only=False):
    def fn(c: Circuit, n):
        done = False
        for i, g in enumerate(c.gates):
            if pred(g, i, c, n) and not (first_only and done):
                c.gates[i] = f(g, c, n)
                done = True
    return fn


def _bug_dirty_ancilla_target(c: Circuit, n):
    if n < 2:
        return
    for i, g in enumerate(c.gates):
        if g.name == "and_compute":
            c.gates[i] = replace(g, qubits=(g.qubits[0], g.qubits[1], c.registers["a"][1]))
            return


def _bug_only_large_n(c: Circuit, n):
    if n < 6:
        return
    a5, b5 = c.registers["a"][5], c.registers["b"][5]
    for i, g in enumerate(c.gates):
        if g.name == "cx" and g.qubits[1] == b5 and g.qubits[0] != a5:
            del c.gates[i]
            return


def _bug_odd_n(c: Circuit, n):
    if n % 2 == 0:
        return
    a, b = c.registers["a"][-1], c.registers["b"][-1]
    for i in range(len(c.gates) - 1, -1, -1):
        g = c.gates[i]
        if g.name == "cx" and g.qubits == (a, b):
            del c.gates[i]
            return


def _swap_ab(c: Circuit, n):
    c.registers["a"], c.registers["b"] = c.registers["b"], c.registers["a"]


def _uncompute_before_carry_fix(c: Circuit, n):
    # move each "cx c, nxt" that precedes an and_uncompute to after it -> t != a·b at uncompute
    g = c.gates
    for i in range(len(g) - 1):
        if g[i].name == "cx" and g[i + 1].name == "and_uncompute" and g[i].qubits[1] == g[i + 1].qubits[2]:
            g[i], g[i + 1] = g[i + 1], g[i]
            return


def cases() -> list:
    A, B, AB = frozenset(TIER_A), frozenset(TIER_B), frozenset(TIER_A | TIER_B)
    is_cond = lambda name: (lambda g, i, c, n: g.name == name and g.cond is not None)
    return [
        # ---- must accept ----------------------------------------------------------------------
        Case("cuccaro", cuccaro.construct, AB, True, "pass", "naive ripple-carry adder"),
        Case("gidney_tierA", gidney.construct, A, True, "pass", "temporary-AND adder, gadget form"),
        Case("gidney_tierB", gidney.construct_tier_b, B, True, "pass", "temporary-AND adder, primitives"),
        Case("gidney_global_phase", _edit(gidney.construct_tier_b,
             lambda c, n: setattr(c, "gates", [Gate("x", (0,)), Gate("z", (0,)), Gate("x", (0,)), Gate("z", (0,))] + c.gates)),
             B, True, "pass", "global phase -1 inserted (unobservable; must be accepted)"),
        Case("pyzx_cuccaro", lambda n: pyzx_opt.optimize(cuccaro.construct(n)), B, True, "pass",
             "pyzx full_reduce output (dense; small n only)", (1, 2, 3)),
        # ---- must reject ----------------------------------------------------------------------
        Case("wrong_carry_wiring", _edit(cuccaro.construct, _map(lambda g, i, c, n: i == 1,
             lambda g, c, n: replace(g, qubits=(g.qubits[0], c.registers["b"][0])), first_only=True)),
             AB, False, "L1", "first MAJ targets the wrong qubit"),
        Case("ancilla_left_dirty", _edit(gidney.construct, _drop(lambda g, i, c, n: g.name == "and_uncompute", True)),
             A, False, "L1", "one carry ancilla never uncomputed"),
        Case("missing_cz_correction", _edit(gidney.construct_tier_b, _drop(is_cond("cz"))),
             B, False, "L2", "measurement-based uncompute without the CZ fix-up"),
        Case("unconditional_cz", _edit(gidney.construct_tier_b, _map(is_cond("cz"), lambda g, c, n: replace(g, cond=None))),
             B, False, "L2", "CZ fix-up applied on both branches"),
        Case("cz_wrong_qubits", _edit(gidney.construct_tier_b, _map(is_cond("cz"),
             lambda g, c, n: replace(g, qubits=(g.qubits[0], c.registers["z"][0])), first_only=True)),
             B, False, "L2", "CZ fix-up on the wrong pair of qubits"),
        Case("z_instead_of_cz", _edit(gidney.construct_tier_b, _map(is_cond("cz"),
             lambda g, c, n: Gate("z", (g.qubits[0],), None, g.cond), first_only=True)),
             B, False, "L2", "single-qubit Z instead of CZ in the fix-up"),
        Case("missing_ancilla_reset", _edit(gidney.construct_tier_b, _drop(is_cond("x"))),
             B, False, "L1", "measured ancilla not reset to |0> on outcome 1"),
        Case("relative_phase_bug", _edit(gidney.construct, lambda c, n: c.add("t", c.registers["a"][0])),
             A | {"t"}, False, "L2", "correct on basis states, wrong relative phase (T on a_0)"),
        Case("measures_data_qubit", _edit(gidney.construct_tier_b, lambda c, n: (c.measure(c.registers["a"][0]), None)[1]),
             B, False, "L2", "measures a data qubit (collapses superpositions)"),
        Case("dirty_target_assumed_clean", _edit(gidney.construct, _bug_dirty_ancilla_target),
             A, False, "L1", "and_compute into a data qubit (n >= 2)"),
        Case("uncompute_precondition", _edit(gidney.construct, _uncompute_before_carry_fix),
             A, False, "L1", "and_uncompute while t != a·b"),
        Case("sum_into_wrong_register", _edit(cuccaro.construct, _swap_ab),
             AB, False, "L1", "sum written into a instead of b"),
        Case("missing_carry_out", _edit(cuccaro.construct, _drop(lambda g, i, c, n: g.name == "cx"
             and g.qubits[1] == c.registers["z"][0])), AB, False, "L1", "carry-out never written"),
        Case("correct_only_even_n", _edit(gidney.construct, _bug_odd_n),
             A, False, "L1", "top sum bit dropped for odd n"),
        Case("bug_only_n_ge_6", _edit(gidney.construct, _bug_only_large_n),
             A, False, "L1", "carry propagation broken at bit 5 (caught only by sampled n = 6)"),
        Case("gadget_outside_vocab", gidney.construct, B, False, "L0", "tier-B candidate uses a tier-A gadget"),
    ]
