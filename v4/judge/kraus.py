"""`branch_kraus` with an error allowance - V4_README section 6.3, the one unfreeze.

THE PROBLEM. `circuitevolve/v2/verify.py::relaxed` routes through `_norm_angle_gates`, which raises
`NotExact` for any angle off the pi/4 grid. So **ancillas together with continuous rotations cannot be
verified at all**, and 8 of the 9 verification failures in v3's P2 were exactly that. It structurally
forbids the phase-gradient / PKAC family, which is the one lever that closes the gap to DPF Synth on
qft_8 and qae_13 (V4_README 4.2b).

WHAT THIS MODULE IS, AND WHY IT IS NOT AN EDIT TO A FROZEN FILE. CLAUDE.md invariant 4 forbids modifying
the frozen verifier files, and v3's `FROZEN.sha256` hashes `circuitevolve/v2/verify.py` and is checked at
the start of every run. So the new capability is NEW CODE here, in v4, which composes the frozen
primitives rather than changing them: `v2.verify` keeps its exact behaviour and keeps its hash, and
nothing that v3 ever decided changes.

THE CHECK. The specification contract of CLAUDE.md invariant 2, generalised to continuous angles. For a
candidate with `A` clean ancillas (|0> in, |0> out) and `M` mid-circuit measurements, and a reference on
the data qubits:

    for every basis input x and every measurement branch m:
        K_m |x, 0_anc>  =  c_m |U_ref x, 0_anc>  +  (error <= allowance)
        with the SAME c_m for every x, and sum_m |c_m|^2 = 1.

`K_m` is the (non-unitary) Kraus operator of branch m: the circuit simulated with measurement outcomes
forced to m, with no renormalisation, so `|c_m|^2` is that branch's probability. Three things are
checked, each with an explicit tolerance drawn from the SAME allowance:

  1. **function**, per input and branch: the normalised output state agrees with the reference's output
     on the data qubits to within `allowance`;
  2. **ancilla return**, per input and branch: the population left outside |0_anc> is at most
     `allowance**2` in probability. This is the check that catches the leak our own measurement of the
     BQSKit PKAC construction found - exact at k = 3 (state error 2.6e-16, zero leak) but 1/sqrt(2) at
     k = 4 and ~1.0 at k = 5, because the temporary-AND uncompute is measurement-based by construction;
  3. **phase consistency**, across inputs: `c_m` is the same for all x to within `allowance`, and the
     branch probabilities sum to 1 to within `allowance`. Relative phase between inputs IS observable
     (CLAUDE.md invariant 6), so this is not optional.

`certified` is True only when every basis input and every branch was enumerated. Above the budgets the
inputs and/or branches are sampled, exactly as the frozen checker does, and `certified` is False.

Simulation is numeric (numpy), because the whole point is to admit continuous angles. For a candidate
whose angles are all on the pi/4 grid this module is not needed and the frozen exact `relaxed` mode is
used instead - so floating point never decides a Clifford+T case, and CLAUDE.md invariant 1 holds.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from circuitevolve.blocks.verify_block import gate_matrix
from circuitevolve.ir import Circuit as IRCircuit
from circuitevolve.locks import NUMERIC_LOCK

MAX_QUBITS = 22                  # 2^22 complex128 = 64 MB per state vector
MAX_EXHAUSTIVE_INPUTS = 1 << 12
SAMPLED_INPUTS = 64
MAX_EXHAUSTIVE_BRANCHES = 1 << 8
SAMPLED_BRANCHES = 8


class NotApplicable(ValueError):
    """The candidate is not in the form this check handles (used to fall through, not to reject)."""


@dataclass
class KrausVerdict:
    ok: bool
    certified: bool
    distance: float = 0.0            # worst per-input, per-branch state distance
    leak: float = 0.0                # worst ancilla population left outside |0>
    phase_spread: float = 0.0        # worst |c_m(x) - c_m(x0)|
    prob_error: float = 0.0          # |sum_m |c_m|^2 - 1|
    bound: float = 0.0
    reason: str = ""
    method: str = ""
    n_inputs: int = 0
    n_branches: int = 0
    coeffs: dict = field(default_factory=dict)
    seconds: float = 0.0


# ------------------------------------------------------------------------------------------ plumbing
def _gates(c: IRCircuit) -> list:
    return list(c.gates)


def _measured_qubits(c: IRCircuit) -> list:
    return [g.qubits[0] for g in c.gates if g.name == "measure"]


def _apply(state: np.ndarray, M: np.ndarray, qubits, n: int) -> np.ndarray:
    """Apply a 2^k x 2^k gate to `qubits` of an n-qubit state. Qubit 0 is the most significant index,
    the same convention the frozen `verify_block` uses."""
    k = len(qubits)
    st = state.reshape((2,) * n)
    axes = [int(q) for q in qubits]
    st = np.tensordot(M.reshape((2,) * (2 * k)), st, axes=(list(range(k, 2 * k)), axes))
    st = np.moveaxis(st, list(range(k)), axes)
    return st.reshape(-1)


_PROJ = (np.array([[1.0, 0.0], [0.0, 0.0]]), np.array([[0.0, 0.0], [0.0, 1.0]]))


def _and_compute_matrix() -> np.ndarray:
    """The temporary-AND gadget as a 3-qubit unitary on (x, y, target): target ^= x AND y, i.e. a
    Toffoli. Costs 4 T; the frozen IR treats it as a gadget with a |0> precondition on the target."""
    U = np.eye(8)
    U[[6, 7]] = U[[7, 6]]
    return U


def run_branch(c: IRCircuit, x: int, outcomes, n: int) -> tuple:
    """(unnormalised state of branch `outcomes`, number of measurements consumed).

    Measurement outcomes are FORCED, with no renormalisation, so the returned state's squared norm is
    that branch's probability - which is what `|c_m|^2` must sum to 1 over. `and_uncompute` is the
    measurement-based Gidney uncompute: it measures its target in the X basis and applies a corrective
    CZ on the outcome, which is exactly a measurement plus a classically controlled gate."""
    state = np.zeros(1 << n, dtype=complex)
    state[int(x)] = 1.0
    cbits: dict = {}
    k = 0
    for g in _gates(c):
        name, qs = g.name, tuple(int(q) for q in g.qubits)
        if g.cond is not None:
            bit, val = g.cond
            if cbits.get(bit, 0) != val:
                continue
        if name == "measure":
            o = int(outcomes[k]) if k < len(outcomes) else 0
            cbits[g.cbit if g.cbit is not None else k] = o
            k += 1
            state = _apply(state, _PROJ[o], qs, n)
            continue
        if name == "and_compute":
            state = _apply(state, _and_compute_matrix(), qs, n)
            continue
        if name == "and_uncompute":
            # H on the target, then measure it; on outcome 1 a CZ on the two controls
            t = qs[-1]
            state = _apply(state, gate_matrix("h"), (t,), n)
            o = int(outcomes[k]) if k < len(outcomes) else 0
            cbits[("and", k)] = o
            k += 1
            state = _apply(state, _PROJ[o], (t,), n)
            if o == 1 and len(qs) >= 3:
                state = _apply(state, gate_matrix("cz"), (qs[0], qs[1]), n)
            continue
        if name in ("ccx", "ccz"):
            U = np.eye(8)
            if name == "ccx":
                U[[6, 7]] = U[[7, 6]]
            else:
                U[7, 7] = -1.0
            state = _apply(state, U, qs, n)
            continue
        ang = None
        for attr in ("angle", "param", "theta"):
            if hasattr(g, attr):
                ang = getattr(g, attr)
                break
        state = _apply(state, gate_matrix(name, ang), qs, n)
    return state, k


def n_branch_points(c: IRCircuit) -> int:
    return sum(1 for g in _gates(c) if g.name in ("measure", "and_uncompute"))


# ------------------------------------------------------------------------------------------ the check
def check(candidate: IRCircuit, reference_state, n_data: int, allowance: float, data_map=None,
          seed: int = 0, limits: dict | None = None) -> KrausVerdict:
    """`candidate` against `reference_state(x) -> normalised numpy state on n_data qubits`.

    `data_map[i]` = the candidate qubit carrying reference qubit i (default: identity). Every other
    candidate qubit is a clean ancilla and must come back to |0>.
    """
    t0 = time.perf_counter()
    lim = dict(max_inputs=MAX_EXHAUSTIVE_INPUTS, sampled_inputs=SAMPLED_INPUTS,
               max_branches=MAX_EXHAUSTIVE_BRANCHES, sampled_branches=SAMPLED_BRANCHES, **(limits or {}))
    n = candidate.n_qubits
    if n > MAX_QUBITS:
        return KrausVerdict(False, False, reason=f"n={n} > {MAX_QUBITS}: not numerically verifiable",
                            method="skipped", bound=allowance, seconds=time.perf_counter() - t0)
    dm = list(range(n_data)) if data_map is None else list(data_map)
    if len(dm) != n_data or len(set(dm)) != len(dm) or any(not 0 <= q < n for q in dm):
        return KrausVerdict(False, False, reason=f"bad data_map {dm}", method="literal", bound=allowance)
    anc = [q for q in range(n) if q not in set(dm)]
    M = n_branch_points(candidate)

    rng = np.random.default_rng(seed)
    n_in = 1 << n_data
    exhaustive_in = n_in <= lim["max_inputs"]
    if exhaustive_in:
        inputs = list(range(n_in))
    else:
        edge = [0, n_in - 1] + [1 << i for i in range(n_data)]
        inputs = sorted(set(edge + [int(rng.integers(0, n_in)) for _ in range(lim["sampled_inputs"])]))
    exhaustive_br = (1 << M) <= lim["max_branches"]
    if exhaustive_br:
        branches = [tuple((i >> b) & 1 for b in range(M)) for i in range(1 << M)]
    else:
        branches = sorted({tuple(int(rng.integers(0, 2)) for _ in range(M))
                           for _ in range(lim["sampled_branches"])})
    certified = exhaustive_in and exhaustive_br
    method = (f"branch-kraus-{'exhaustive' if exhaustive_in else 'sampled'}"
              f"{'' if exhaustive_br else '+sampled-branches'}")

    # masks for reading the data register out of the full state
    anc_zero = np.zeros(n, dtype=bool)
    idx = np.arange(1 << n)
    # bit q of the basis index, with qubit 0 the MOST significant (verify_block convention)
    def bit(i, q):
        return (i >> (n - 1 - q)) & 1
    anc_ok = np.ones(1 << n, dtype=bool)
    for q in anc:
        anc_ok &= (((idx >> (n - 1 - q)) & 1) == 0)
    data_index = np.zeros(1 << n, dtype=np.int64)
    for j, q in enumerate(dm):
        data_index |= (((idx >> (n - 1 - q)) & 1) << (n_data - 1 - j))

    worst_d = worst_leak = worst_phase = 0.0
    coeff: dict = {}
    with NUMERIC_LOCK:
        for ii, x in enumerate(inputs):
            # the reference's input index in the FULL register (ancillas in |0>)
            full_x = 0
            for j, q in enumerate(dm):
                if (x >> (n_data - 1 - j)) & 1:
                    full_x |= 1 << (n - 1 - q)
            ref = np.asarray(reference_state(x), dtype=complex).reshape(-1)
            if ref.size != n_in:
                return KrausVerdict(False, False, reason=f"reference state has {ref.size} amplitudes, "
                                                         f"expected {n_in}", method="literal",
                                    bound=allowance)
            for m in branches:
                st, _k = run_branch(candidate, full_x, m, n)
                p = float(np.vdot(st, st).real)
                leak = float(np.vdot(st[~anc_ok], st[~anc_ok]).real)
                worst_leak = max(worst_leak, math.sqrt(max(0.0, leak)))
                if p <= allowance ** 2:
                    coeff.setdefault(m, 0.0 + 0j)
                    continue
                # the data-register state of this branch, with the ancillas projected onto |0>
                kept = st[anc_ok]
                data = np.zeros(n_in, dtype=complex)
                np.add.at(data, data_index[anc_ok], kept)
                ov = complex(np.vdot(ref, data))
                c_m = ov                                  # K_m|x,0> = c_m |ref> + residual
                resid = data - c_m * ref
                d = float(np.linalg.norm(resid)) + math.sqrt(max(0.0, leak))
                worst_d = max(worst_d, d)
                if m not in coeff or abs(coeff[m]) <= allowance:
                    coeff[m] = c_m
                else:
                    worst_phase = max(worst_phase, abs(c_m - coeff[m]))
        total = float(sum(abs(v) ** 2 for v in coeff.values()))
    prob_err = abs(total - 1.0)

    reasons = []
    if worst_d > allowance:
        reasons.append(f"branch state distance {worst_d:.3e} > allowance {allowance:.3e}")
    if worst_leak > allowance:
        reasons.append(f"ancilla population left outside |0>: {worst_leak:.3e} > {allowance:.3e}")
    if worst_phase > allowance:
        reasons.append(f"branch coefficient differs between inputs by {worst_phase:.3e} > "
                       f"{allowance:.3e} (relative phase is observable)")
    if certified and prob_err > max(allowance, 1e-9):
        reasons.append(f"branch probabilities sum to {total:.6f}, not 1")
    return KrausVerdict(not reasons, certified, distance=worst_d, leak=worst_leak,
                        phase_spread=worst_phase, prob_error=prob_err, bound=allowance,
                        reason="; ".join(reasons), method=method, n_inputs=len(inputs),
                        n_branches=len(coeff), coeffs={str(k): complex(v) for k, v in coeff.items()},
                        seconds=time.perf_counter() - t0)


def reference_state_of(ops, n_data: int):
    """A `reference_state(x)` built from a measurement-free op list: the column of its unitary."""
    from circuitevolve.blocks.verify_block import unitary
    U = unitary(list(ops), int(n_data))

    def f(x):
        return U[:, int(x)]
    return f


def reference_state_from_circuit(ref, n_data: int):
    """A `reference_state(x)` for any measurement-free reference circuit, simulated numerically.

    Used instead of `reference_state_of` when the reference has continuous angles or more qubits than a
    dense unitary is worth: one state simulation per input, not one 2^n x 2^n build."""
    from circuitevolve.v2.verify import _ops_and_n
    if isinstance(ref, IRCircuit):
        c = ref
        if any(g.name == "measure" or g.cond is not None for g in c.gates):
            raise NotApplicable("the reference measures; it cannot define a state map")

        def f(x):
            st, _ = run_branch(c, int(x), (), c.n_qubits)
            return st
        return f
    ops, n = _ops_and_n(ref)
    if n != n_data:
        raise NotApplicable(f"reference has {n} qubits, expected {n_data}")

    def g(x):
        state = np.zeros(1 << n, dtype=complex)
        state[int(x)] = 1.0
        for op in ops:
            a = op[2] if len(op) > 2 else None
            state = _apply(state, gate_matrix(op[0], a), tuple(int(q) for q in op[1]), n)
        return state
    return g


def is_exact_angles(c) -> bool:
    """True if every rotation of `c` is a multiple of pi/4, so the FROZEN exact relaxed check applies and
    floating point must not decide it (CLAUDE.md invariant 1)."""
    from circuitevolve.v2.verify import is_exact
    return bool(is_exact(c))
