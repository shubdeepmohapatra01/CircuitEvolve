"""Verifier: decides whether a candidate construction meets a specification.

Levels (a candidate is accepted only if every level passes at every tested n):

  L0  well-formed     construct(n) returns a Circuit with the spec's registers, only gates from the
                      allowed vocabulary, valid qubit/cbit indices, within size limits.
  L1  function        on every valid input (ancillas |0>), the output is exactly the expected basis
                      state, ancillas included (so ancillas are returned clean); gadget
                      preconditions hold.
  L2  phase-exact     for every measurement branch m, K_m|x> = c_m |f(x)> with the SAME c_m for all
                      inputs x (otherwise superposition inputs pick up a relative phase), and
                      sum_m |c_m|^2 = 1. Exhaustive over branches when affordable, else sampled.
  L3  generalization  L1 + L2 at every n in the schedule: exhaustive inputs for small n, sampled
                      inputs for larger n.

All amplitudes are exact elements of Z[ω, 1/√2]; there is no floating-point tolerance anywhere.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from .cost import cost
from .ir import ARITY, Circuit
from .ring import D
from .sim import NotClassical, PreconditionViolated, bits_to_ints, n_measurements, run, run_classical

_ONE = D((1, 0, 0, 0))
LEMMA_GATES = frozenset({"x", "cx", "ccx", "and_compute", "and_uncompute"})


@dataclass
class Limits:
    max_qubits: int = 80
    max_gates: int = 20000
    exhaustive_n: int = 4          # exhaustive inputs up to this n
    sampled_inputs: int = 48       # inputs per n above exhaustive_n
    branch_budget: int = 20000     # max (branches x inputs) for exhaustive branch enumeration
    sampled_branches: int = 6
    time_limit_s: float = 120.0
    # Opt-in shortcut for search loops only (default False = full exact L2). If every gate is in
    # LEMMA_GATES and L1 passed (gadget preconditions hold on every input), each gate is a
    # permutation times an input-independent phase, so L2 holds automatically. The gadget facts
    # (and_compute on |0> target: phase 1; and_uncompute on t = a·b: phase 1/√2 per branch) are
    # proven exactly in tests/test_core.py. Winners must be re-verified with this flag off.
    trust_gadget_lemma: bool = False


@dataclass
class Report:
    ok: bool
    level: str                      # "pass" or the first failing level, e.g. "L1"
    n: int | None = None
    reason: str = ""
    costs: dict = field(default_factory=dict)   # n -> cost dict (for every n that passed)

    def __bool__(self):
        return self.ok


class _Fail(Exception):
    def __init__(self, level, reason):
        super().__init__(reason)
        self.level, self.reason = level, reason


# ---------------------------------------------------------------------------------------------
def check_l0(circ, spec, n, vocab, lim: Limits):
    if not isinstance(circ, Circuit):
        raise _Fail("L0", f"construct returned {type(circ).__name__}, not Circuit")
    if circ.n_qubits > lim.max_qubits:
        raise _Fail("L0", f"{circ.n_qubits} qubits > limit {lim.max_qubits}")
    if len(circ.gates) > lim.max_gates:
        raise _Fail("L0", f"{len(circ.gates)} gates > limit {lim.max_gates}")
    sizes = spec.register_sizes(n)
    seen = set()
    for reg, size in sizes.items():
        qs = circ.registers.get(reg)
        if qs is None or len(qs) != size:
            raise _Fail("L0", f"register {reg!r} must have {size} qubits, got {None if qs is None else len(qs)}")
        for q in qs:
            if not (0 <= q < circ.n_qubits) or q in seen:
                raise _Fail("L0", f"register {reg!r} has invalid or repeated qubit {q}")
            seen.add(q)
    written = set()
    for i, g in enumerate(circ.gates):
        if g.name not in vocab:
            raise _Fail("L0", f"gate {i} {g.name!r} not in vocabulary")
        if len(g.qubits) != ARITY[g.name] or len(set(g.qubits)) != len(g.qubits):
            raise _Fail("L0", f"gate {i} {g.name} has bad qubit list {g.qubits}")
        if any(not (0 <= q < circ.n_qubits) for q in g.qubits):
            raise _Fail("L0", f"gate {i} qubit out of range")
        if g.name == "measure":
            if g.cond is not None:
                raise _Fail("L0", "conditional measurement not allowed")
            written.add(g.cbit)
        elif g.cond is not None:
            if g.cond not in written:
                raise _Fail("L0", f"gate {i} conditioned on unwritten cbit {g.cond}")
            if g.name in ("and_compute", "and_uncompute"):
                raise _Fail("L0", "conditional gadgets not allowed")


def _pairs(circ, spec, n, lim, seed):
    if n <= lim.exhaustive_n:
        return spec.inputs(circ, n), True
    return spec.inputs(circ, n, max_inputs=lim.sampled_inputs, seed=seed), False


def check_l1(circ, pairs, rng):
    xs = [x for x, _ in pairs]
    try:
        outs = bits_to_ints(run_classical(circ, xs))
        for (x, y), o in zip(pairs, outs):
            if o != y:
                raise _Fail("L1", f"input {x:#x}: got {o:#x}, expected {y:#x}")
        return
    except PreconditionViolated as e:
        raise _Fail("L1", f"gadget precondition: {e}")
    except NotClassical:
        pass
    M = n_measurements(circ)
    for x, y in pairs:
        outcome = tuple(rng.getrandbits(1) for _ in range(M))
        br = run(circ, x, outcome)
        for st in br.values():
            if set(st) != {y}:
                raise _Fail("L1", f"input {x:#x}: output support {sorted(st)[:4]} != {{{y:#x}}}")


def check_l2(circ, pairs, exhaustive_inputs, lim, rng):
    if lim.trust_gadget_lemma and all(g.name in LEMMA_GATES and g.cond is None for g in circ.gates):
        return
    M = n_measurements(circ)
    exhaustive_branches = (1 << M) * len(pairs) <= lim.branch_budget
    coeff: dict = {}            # branch -> c_m
    if exhaustive_branches:
        for idx, (x, y) in enumerate(pairs):
            br = run(circ, x)
            if idx == 0:
                for m, st in br.items():
                    if set(st) != {y}:
                        raise _Fail("L1", f"input {x:#x}, branch {m}: wrong output support")
                    coeff[m] = st[y]
                continue
            if set(br) != set(coeff):
                diff = sorted(set(br) ^ set(coeff))[0]
                raise _Fail("L2", f"branch {diff} has non-zero amplitude on some inputs only (e.g. {x:#x})")
            for m, st in br.items():
                if set(st) != {y}:
                    raise _Fail("L1", f"input {x:#x}, branch {m}: wrong output support")
                if st[y] != coeff[m]:
                    raise _Fail("L2", f"branch {m}: relative phase differs between inputs "
                                      f"({complex(coeff[m]):.3f} vs {complex(st[y]):.3f} on {x:#x})")
        if exhaustive_inputs:
            total = D()
            for c in coeff.values():
                total = total + c.norm2()
            if total != _ONE:
                raise _Fail("L2", f"branch probabilities sum to {complex(total).real:.6f}, not 1")
    else:
        for _ in range(lim.sampled_branches):
            outcome = tuple(rng.getrandbits(1) for _ in range(M))
            ref = None
            for x, y in pairs:
                br = run(circ, x, outcome)
                c = br.get(outcome, {}).get(y)
                st = br.get(outcome, {})
                if st and set(st) != {y}:
                    raise _Fail("L1", f"input {x:#x}, branch {outcome}: wrong output support")
                c = c if c is not None else D()
                if ref is None:
                    ref = c
                elif c != ref:
                    raise _Fail("L2", f"sampled branch: relative phase differs on input {x:#x}")


def verify(construct, spec, n_values, vocab, limits: Limits | None = None, seed: int = 0) -> Report:
    """Run L0-L3 for `construct` at every n in `n_values`. Returns the first failure or a pass."""
    lim = limits or Limits()
    rng = random.Random(seed)
    t0 = time.time()
    costs = {}
    for n in n_values:
        try:
            try:
                circ = construct(n)
            except Exception as e:  # candidate code crashed
                raise _Fail("L0", f"construct({n}) raised {type(e).__name__}: {e}")
            check_l0(circ, spec, n, vocab, lim)
            pairs, exhaustive = _pairs(circ, spec, n, lim, seed + n)
            check_l1(circ, pairs, rng)
            check_l2(circ, pairs, exhaustive, lim, rng)
            if time.time() - t0 > lim.time_limit_s:
                raise _Fail("L0", f"verification time limit {lim.time_limit_s}s exceeded")
            costs[n] = cost(circ)
        except _Fail as f:
            return Report(False, f.level, n, f.reason, costs)
    return Report(True, "pass", None, "", costs)
