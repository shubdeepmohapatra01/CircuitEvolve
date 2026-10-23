"""v2 verifier: ONE entry point for both tiers, three labelled modes.

    verify(candidate, reference, mode, eps=0.0, **options) -> Verdict

Modes
-----
'exact'    Unitary equivalence on the SAME qubits, up to one global phase, decided over D[omega] = Z[omega, 1/sqrt2]
           with the FROZEN sparse simulator `circuitevolve.sim.run` (no floating point anywhere). Candidate and
           reference must be Clifford+T or Toffoli-level (x z h s sdg t tdg cx cz ccx ccz; rz only at multiples of
           pi/4). The check runs over basis inputs |x>: for each x the candidate output u_x must equal c * v_x with
           v_x the reference output and ONE c for all x. Exhaustive over all 2^n inputs this is a proof of
           U_cand = c U_ref (linearity); it is the dense exact unitary column by column. For permutation-like
           references (only x/cx/ccx + diagonal gates, or a basis-map function) on many qubits (default > 14) the
           inputs are SAMPLED (edge cases + random) and the Verdict says certified=False.
'approx'   Numerical: phase-aligned operator distance <= eps, through `core/verifier.check_circuit` (which wraps the
           FROZEN `blocks/verify_block.circuit_check`): dense unitary for n <= 10 (certified bound), Haar-random
           statevectors for 11 <= n <= 20 (a LOWER bound on the distance, certified=False), refused above 20.
           invariant 1: if candidate AND reference are both Clifford+T the check is routed to 'exact'
           (floating point never accepts a Clifford+T candidate); the Verdict then has mode='exact',
           requested='approx'.
'relaxed'  Specification semantics of the frozen adder verifier (`circuitevolve/verify.py` L1/L2), generalized to
           any ReferenceSpec: the candidate may use extra CLEAN ancillas (start in |0>, must end in |0>),
           mid-circuit measurements and classically controlled gates (ir.Circuit `measure` / `cond`, and the
           and_compute / and_uncompute gadgets). For every valid input x and every measurement branch m:
           K_m |x, 0_anc> = c_m |f(x), 0_anc> with the SAME c_m for all x, and sum_m |c_m|^2 = 1. Simulated
           branch-wise and exactly with `sim.run`. Exhaustive over branches when 2^M * #inputs <= branch_budget,
           otherwise sampled branches (certified=False).
'auto'     'exact' if both sides are exact, measurement-free and on the same qubits; 'relaxed' if the candidate is
           exact but measures or has extra qubits; otherwise 'approx'.

Every Verdict carries `mode` (the mode actually used) and `unitary_preserving` (True for exact/approx, False for
relaxed) so reports can keep unitary-preserving and relaxed results apart.

Inputs accepted as candidate / reference
----------------------------------------
* `circuitevolve.ir.Circuit` (Toffoli level, gadgets, measurement, feed-forward);
* `circuitevolve.core.circuit.Circuit` (Clifford+Rz op list);
* `(ops, n)` tuples of (name, qubits, angle) ops (blocks/core op format);
* `ReferenceSpec` (reference side only; wraps any of the above, or a basis-map function).

Qubit labelling: sim.py uses bit q of a basis index for qubit q; verify_block matrices use qubit 0 as the most
significant index. Each mode uses ONE convention for both sides, so equivalence does not depend on it.
Basis-map functions passed to `ReferenceSpec.from_function` use the sim.py convention (bit q = qubit q).

Nothing in this module edits or monkey-patches the frozen files; `FROZEN_DIGEST` records their digest at import
and `check_integrity()` re-checks it.
"""
from __future__ import annotations

import math
import random
import re
import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .. import integrity
from ..ir import ARITY, GADGETS, Circuit as IRCircuit, Gate
from ..ring import D
from ..sim import NotClassical, PreconditionViolated, n_measurements, run, run_classical

FROZEN_DIGEST = integrity.frozen_digest()

ZERO = D()
ONE = D((1, 0, 0, 0))
MODES = ("exact", "approx", "relaxed", "auto")
EXACT_OPS = frozenset({"x", "z", "h", "s", "sdg", "t", "tdg", "cx", "cz", "ccx", "ccz"})


def check_integrity() -> None:
    """Raise integrity.IntegrityError if a frozen verifier file changed since this module was imported."""
    integrity.check_unchanged(FROZEN_DIGEST)


# ============================================================================================ results
@dataclass
class Verdict:
    ok: bool
    mode: str                         # mode actually used: 'exact' | 'approx' | 'relaxed'
    distance: float | None = None     # exact/relaxed: 0.0 on pass; approx: measured phase-aligned distance
    bound: float | None = None        # the bound the distance was checked against (eps; 0 for exact/relaxed)
    reason: str = ""                  # "" on pass; a diagnosis on failure (fed back to the LLM)
    method: str = ""                  # 'basis-exhaustive' | 'basis-sampled' | 'branchwise-...' | 'unitary' | ...
    certified: bool = False           # True only if the check is a proof (exhaustive / dense operator norm)
    requested: str = ""               # mode the caller asked for (differs when approx -> exact, or 'auto')
    n_inputs: int = 0
    n_branches: int = 0
    details: dict = field(default_factory=dict)

    @property
    def unitary_preserving(self) -> bool:
        return self.mode in ("exact", "approx")

    def __bool__(self):
        return self.ok

    def to_dict(self) -> dict:
        d = {k: getattr(self, k) for k in ("ok", "mode", "distance", "bound", "reason", "method", "certified",
                                            "requested", "n_inputs", "n_branches")}
        d["unitary_preserving"] = self.unitary_preserving
        d["details"] = dict(self.details)
        return d


class NotExact(ValueError):
    """The circuit has gates with no exact D[omega] semantics (continuous rz, u3, ...)."""


@dataclass
class Limits:
    max_exhaustive_inputs: int = 1 << 14   # exhaustive basis inputs up to this many (else sampled, if allowed)
    sampled_inputs: int = 256              # random inputs when sampling (plus edge cases)
    branch_budget: int = 20000             # max (2^M x #inputs) for exhaustive branch enumeration (as verify.py)
    sampled_branches: int = 8
    max_state: int = 1 << 16               # max non-zero amplitudes of one simulated state
    time_limit_s: float = 300.0
    approx_max_qubits: int = 20


# ============================================================================================ conversions
def _norm_angle_gates(q: int, a: float) -> list:
    from ..blocks.circuit_io import DISCRETE, classify_angle
    k = classify_angle(float(a))
    if k is None:
        raise NotExact(f"rz({a!r}) is not a multiple of pi/4")
    return [(g, (q,)) for g in DISCRETE[k]]


def ops_to_ir(ops, n: int) -> IRCircuit:
    """(name, qubits, angle) ops -> ir.Circuit. rz/u1/p must be multiples of pi/4 (else NotExact)."""
    c = IRCircuit(int(n))
    for op in ops:
        g, qs = op[0], tuple(int(q) for q in op[1])
        a = op[2] if len(op) > 2 else None
        if g in ("rz", "u1", "p"):
            for gg, qq in _norm_angle_gates(qs[0], a):
                c.add(gg, *qq)
        elif g == "swap":
            c.add("cx", qs[0], qs[1]).add("cx", qs[1], qs[0]).add("cx", qs[0], qs[1])
        elif g in EXACT_OPS:
            c.add(g, *qs)
        else:
            raise NotExact(f"gate {g!r} has no exact Clifford+T semantics")
    return c


def ir_to_ops(c: IRCircuit) -> tuple[list, int]:
    """ir.Circuit (measurement-free) -> (ops, n) over verify_block gates (ccx/ccz expanded to Clifford+T)."""
    e = c.expand("clifford_t")
    out = []
    for g in e.gates:
        if g.name == "measure" or g.cond is not None:
            raise ValueError("circuit has measurements / classical control; use mode='relaxed'")
        out.append((g.name, tuple(g.qubits), None))
    return out, c.n_qubits


def _ops_and_n(x):
    """Numeric (ops, n) for approx mode."""
    if isinstance(x, IRCircuit):
        return ir_to_ops(x)
    if hasattr(x, "ops") and hasattr(x, "n"):            # core.circuit.Circuit
        return list(x.ops), int(x.n)
    if isinstance(x, tuple) and len(x) == 2:
        return list(x[0]), int(x[1])
    raise TypeError(f"cannot interpret {type(x).__name__} as a circuit")


def as_ir(x) -> IRCircuit:
    """Exact (ir.Circuit) view of a circuit; raises NotExact for continuous rotations."""
    if isinstance(x, IRCircuit):
        return x
    ops, n = _ops_and_n(x)
    return ops_to_ir(ops, n)


def is_exact(x) -> bool:
    if isinstance(x, ReferenceSpec):
        return x.exact
    try:
        as_ir(x)
        return True
    except NotExact:
        return False


def parse_qasm_ir(text: str) -> IRCircuit:
    """OpenQASM 2 -> ir.Circuit over {x z h s sdg t tdg cx cz ccx ccz swap} plus rz/u1/p at multiples of pi/4
    (e.g. the Nam et al. arithmetic suite). Literal parsing (core.circuit regexes), no eval. Several qregs are
    concatenated in declaration order."""
    from ..core.circuit import ARG_RE, GATE_LINE_RE, QREG_RE, parse_angle
    offs, n, ops = {}, 0, []
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line or line.startswith(("OPENQASM", "include", "creg", "barrier")):
            continue
        m = QREG_RE.match(line)
        if m:
            offs[m.group(1)] = n
            n += int(m.group(2))
            continue
        m = GATE_LINE_RE.match(line)
        if not m:
            raise ValueError(f"cannot parse QASM line {raw!r}")
        g, arg, args = m.groups()
        qs = []
        for a in args.split(","):
            am = ARG_RE.match(a.strip())
            if not am or am.group(1) not in offs:
                raise ValueError(f"bad qubit argument {a!r} in {raw!r}")
            qs.append(offs[am.group(1)] + int(am.group(2)))
        ops.append((g, tuple(qs), _angle(arg, parse_angle) if arg is not None else None))
    return ops_to_ir(ops, n)


_PI_TIMES = re.compile(r"^pi\s*\*\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)$")


def _angle(text: str, parse_angle) -> float:
    """core.circuit.parse_angle plus the quartz form 'pi*-0.25' (literal regex, no eval)."""
    m = _PI_TIMES.match(text.strip())
    if m:
        return float(m.group(1)) * math.pi
    return parse_angle(text)


# ============================================================================================ reference
@dataclass
class ReferenceSpec:
    """What the candidate must implement, on `n_qubits` reference (data) qubits.

    Exactly one of `circuit` (ir.Circuit, measurement-free), `func` (basis map x -> y or x -> {y: D amplitude})
    or `ops` (numeric op list, approx mode only) defines the action. `zero_qubits` are reference qubits PROMISED
    to be |0> on input (e.g. a clean carry-out); this restricts the valid inputs and is allowed only in relaxed
    mode. `registers` (name -> reference qubits) lets relaxed mode map data qubits by register name."""
    n_qubits: int
    circuit: IRCircuit | None = None
    func: Callable | None = None
    ops: list | None = None
    zero_qubits: tuple = ()
    registers: dict = field(default_factory=dict)
    name: str = ""

    # ------------------------------------------------------------------ constructors
    @classmethod
    def from_circuit(cls, circ, zero_qubits=(), name: str = "", registers=None) -> "ReferenceSpec":
        """Toffoli-level / Clifford+T reference (ir.Circuit, core Circuit or (ops, n)); continuous-angle
        circuits are kept as numeric ops (approx mode only)."""
        if isinstance(circ, ReferenceSpec):
            return circ
        if isinstance(circ, IRCircuit):
            if n_measurements(circ):
                raise ValueError("a reference circuit must be measurement-free")
            return cls(circ.n_qubits, circuit=circ, zero_qubits=tuple(zero_qubits), name=name,
                       registers=dict(registers if registers is not None else circ.registers))
        ops, n = _ops_and_n(circ)
        try:
            return cls(n, circuit=ops_to_ir(ops, n), zero_qubits=tuple(zero_qubits), name=name,
                       registers=dict(registers or {}))
        except NotExact:
            return cls(n, ops=ops, zero_qubits=tuple(zero_qubits), name=name, registers=dict(registers or {}))

    from_ops = from_circuit

    @classmethod
    def from_function(cls, n_qubits: int, func: Callable, zero_qubits=(), name: str = "",
                      registers=None) -> "ReferenceSpec":
        """Permutation (or phased permutation) reference: func(x) -> y, or func(x) -> {y: D}. Bit q = qubit q."""
        return cls(int(n_qubits), func=func, zero_qubits=tuple(zero_qubits), name=name,
                   registers=dict(registers or {}))

    # ------------------------------------------------------------------ properties
    @property
    def exact(self) -> bool:
        return self.circuit is not None or self.func is not None

    @property
    def permutation_like(self) -> bool:
        """True if every basis input maps to ONE basis output (so basis-state checks stay sparse)."""
        if self.func is not None:
            return True
        if self.circuit is None:
            return False
        try:
            run_classical(self.circuit, [0])
            return True
        except (NotClassical, PreconditionViolated):
            return False

    @property
    def n_valid_inputs(self) -> int:
        return 1 << (self.n_qubits - len(set(self.zero_qubits)))

    def apply(self, x: int) -> dict:
        """Exact output state {basis: D} of the reference on |x>."""
        if self.func is not None:
            y = self.func(x)
            return dict(y) if isinstance(y, dict) else {int(y): ONE}
        if self.circuit is None:
            raise NotExact("numeric reference has no exact action")
        br = run(self.circuit, x)
        (st,) = br.values()
        return st

    def numeric_ops(self) -> tuple[list, int]:
        if self.ops is not None:
            return list(self.ops), self.n_qubits
        if self.circuit is not None:
            return ir_to_ops(self.circuit)
        n = self.n_qubits
        if n > 10:
            raise ValueError("function reference: numeric form only for n <= 10")
        dim = 1 << n
        M = np.zeros((dim, dim), complex)

        def to_mat(k):   # sim index (bit q = qubit q) -> verify_block matrix index (qubit 0 = MSB)
            return sum(((k >> q) & 1) << (n - 1 - q) for q in range(n))
        for x in range(dim):
            for y, a in self.apply(x).items():
                M[to_mat(y), to_mat(x)] = complex(a)
        return [("unitary", tuple(range(n)), M)], n

    def valid_inputs(self, exhaustive: bool, k: int, rng: random.Random) -> list:
        free = [q for q in range(self.n_qubits) if q not in set(self.zero_qubits)]
        if exhaustive:
            out = []
            for v in range(1 << len(free)):
                x = 0
                for i, q in enumerate(free):
                    if (v >> i) & 1:
                        x |= 1 << q
                out.append(x)
            return out
        full = sum(1 << q for q in free)
        seen, out = set(), []
        for x in [0, full] + [rng.getrandbits(self.n_qubits) & full for _ in range(4 * k)]:
            if x not in seen:
                seen.add(x)
                out.append(x)
            if len(out) >= k:
                break
        return out


def adder_reference(n: int, carry_in: bool = False) -> ReferenceSpec:
    """Reference n-bit in-place adder in the frozen AdderSpec layout of the given circuit family:
    registers a, b, z (z = carry out). carry_in=False: qubits a = 0..n-1, b = n..2n-1, z = 2n, z promised |0>
    (relaxed mode; the contract of spec.AdderSpec). carry_in=True: Cuccaro layout (qubit 0 = carry-in c0,
    b_i = 1 + 2i, a_i = 2 + 2i, z = 2n + 1); the full permutation
        |c0, a, b, z> -> |c0, a, (a + b + c0) mod 2^n, z XOR carry(a + b + c0)>
    on all 2^(2n+2) inputs (exact mode)."""
    if carry_in:
        c0, b, a, z = 0, [1 + 2 * i for i in range(n)], [2 + 2 * i for i in range(n)], 2 * n + 1
        nq = 2 * n + 2
    else:
        a, b, z, c0 = list(range(n)), list(range(n, 2 * n)), 2 * n, None
        nq = 2 * n + 1

    def get(x, qs):
        return sum(((x >> q) & 1) << i for i, q in enumerate(qs))

    def f(x):
        A, B = get(x, a), get(x, b)
        cin = ((x >> c0) & 1) if c0 is not None else 0
        s = A + B + cin
        y = x
        for i, q in enumerate(b):
            y = (y & ~(1 << q)) | (((s >> i) & 1) << q)
        return y ^ (((s >> n) & 1) << z)

    regs = {"a": a, "b": b, "z": [z]}
    return ReferenceSpec.from_function(nq, f, zero_qubits=() if carry_in else (z,),
                                       name=f"adder_{n}{'_cin' if carry_in else ''}", registers=regs)


# ============================================================================================ core check
class _Fail(Exception):
    pass


def _inner(v: dict, u: dict) -> D:
    c = ZERO
    for k, a in v.items():
        b = u.get(k)
        if b is not None:
            c = c + a.conj() * b
    return c


def _diagnose(u: dict, V: dict, c: D, anc_mask: int) -> str:
    if any(k & anc_mask for k in u):
        bad = sorted(k for k in u if k & anc_mask)[:3]
        return f"ancilla not returned to |0> (output support includes {[hex(k) for k in bad]})"
    if set(u) != set(V):
        return (f"wrong output: support {[hex(k) for k in sorted(u)[:4]]} != expected "
                f"{[hex(k) for k in sorted(V)[:4]]}")
    if c.is_zero():
        return "output orthogonal to the reference output"
    return "output amplitudes not proportional to the reference output (relative phase inside the state)"


def _basis_check(cand: IRCircuit, ref: ReferenceSpec, data_map: list, inputs: list, branches,
                 lim: Limits, t0: float) -> dict:
    """branches: None = enumerate all branches exhaustively; else a list of outcome tuples to follow."""
    nc = cand.n_qubits
    dm = list(data_map)
    anc_mask = sum(1 << q for q in range(nc) if q not in set(dm))

    def embed(k):
        K = 0
        for i, q in enumerate(dm):
            if (k >> i) & 1:
                K |= 1 << q
        return K

    coeff: dict = {}
    first_x = None
    for idx, x in enumerate(inputs):
        if time.time() - t0 > lim.time_limit_s:
            raise _Fail(f"time limit {lim.time_limit_s}s exceeded after {idx} inputs")
        v = ref.apply(x)
        V = {embed(y): a for y, a in v.items()}
        X = embed(x)
        if branches is None:
            br = run(cand, X)
        else:
            br = {}
            for m in branches:
                st = run(cand, X, m).get(m)
                br[m] = st if st else {}
        for m, u in br.items():
            if len(u) > lim.max_state:
                raise _Fail(f"state size {len(u)} > max_state {lim.max_state}")
            c = _inner(V, u) if u else ZERO
            if u:
                keys = set(u) | set(V)
                if any(not (u.get(k, ZERO) - c * V.get(k, ZERO)).is_zero() for k in keys):
                    raise _Fail(f"input {x:#x}" + (f", branch {m}" if m else "") + ": "
                                + _diagnose(u, V, c, anc_mask))
            if idx == 0:
                coeff[m] = c
            elif m not in coeff:
                raise _Fail(f"branch {m} has non-zero amplitude on input {x:#x} but not on input {first_x:#x}")
            elif coeff[m] != c:
                raise _Fail(("relative phase differs between inputs" if not c.is_zero() and not coeff[m].is_zero()
                             else "branch probability differs between inputs")
                            + f" (branch {m or '()'}: {complex(coeff[m]):.4f} on {first_x:#x} vs "
                              f"{complex(c):.4f} on {x:#x})")
        if idx == 0:
            first_x = x
        elif branches is None and set(br) != set(coeff):
            m = sorted(set(coeff) - set(br))[0]
            raise _Fail(f"branch {m} has non-zero amplitude on input {first_x:#x} but not on input {x:#x}")
    return coeff


def _default_data_map(cand: IRCircuit, ref: ReferenceSpec) -> list:
    if ref.registers and cand.registers and all(r in cand.registers for r in ref.registers):
        dm = [None] * ref.n_qubits
        for r, qs in ref.registers.items():
            cq = cand.registers[r]
            if len(cq) != len(qs):
                raise _Fail(f"register {r!r}: candidate has {len(cq)} qubits, reference {len(qs)}")
            for rq, q in zip(qs, cq):
                dm[rq] = q
        # reference qubits outside every register (e.g. Cuccaro's carry-in) take the unused candidate qubits
        # in increasing order
        spare = [q for q in range(cand.n_qubits) if q not in set(x for x in dm if x is not None)]
        for i in range(len(dm)):
            if dm[i] is None and spare:
                dm[i] = spare.pop(0)
        if None not in dm:
            return dm
    return list(range(ref.n_qubits))


def _check_exact_like(cand, ref: ReferenceSpec, mode: str, data_map, lim: Limits, seed: int) -> Verdict:
    t0 = time.time()
    rng = random.Random(seed)
    try:
        c = as_ir(cand)
    except NotExact as e:
        return Verdict(False, mode, reason=f"candidate not exact: {e}", method="literal")
    if not ref.exact:
        return Verdict(False, mode, reason="reference has continuous rotations; use mode='approx'", method="literal")
    for g in c.gates:
        if len(g.qubits) != ARITY.get(g.name, -1) or len(set(g.qubits)) != len(g.qubits) or \
                any(not 0 <= q < c.n_qubits for q in g.qubits):
            return Verdict(False, mode, reason=f"bad gate {g}", method="literal")
    M = n_measurements(c)
    try:
        dm = list(data_map) if data_map is not None else _default_data_map(c, ref)
    except _Fail as f:
        return Verdict(False, mode, reason=str(f), method="literal")
    if len(dm) != ref.n_qubits or len(set(dm)) != len(dm) or any(not 0 <= q < c.n_qubits for q in dm):
        return Verdict(False, mode, reason=f"bad data_map {dm}", method="literal")
    if mode == "exact":
        if M or any(g.cond is not None or g.name in GADGETS for g in c.gates):
            return Verdict(False, mode, reason="exact mode: candidate measures / uses gadgets or feed-forward; "
                                               "use mode='relaxed'", method="literal")
        if c.n_qubits != ref.n_qubits:
            return Verdict(False, mode, reason=f"exact mode: candidate has {c.n_qubits} qubits, reference "
                                               f"{ref.n_qubits}; extra ancillas need mode='relaxed'",
                           method="literal")
        if ref.zero_qubits:
            return Verdict(False, mode, reason="exact mode needs an unrestricted reference (zero_qubits given); "
                                               "use mode='relaxed'", method="literal")
    n_valid = ref.n_valid_inputs
    exhaustive = n_valid <= lim.max_exhaustive_inputs
    if not exhaustive and not ref.permutation_like:
        return Verdict(False, mode, reason=f"{n_valid} inputs > max_exhaustive_inputs and reference is not "
                                           f"permutation-like: exact check infeasible", method="infeasible")
    inputs = ref.valid_inputs(exhaustive, lim.sampled_inputs, rng)
    branches = None
    if M and (1 << M) * len(inputs) > lim.branch_budget:
        branches = sorted({tuple(rng.getrandbits(1) for _ in range(M)) for _ in range(lim.sampled_branches)})
    kind = "basis" if mode == "exact" else "branchwise"
    method = f"{kind}-{'exhaustive' if exhaustive else 'sampled'}" + ("" if branches is None else "+sampled-branches")
    certified = exhaustive and branches is None
    try:
        coeff = _basis_check(c, ref, dm, inputs, branches, lim, t0)
        if certified:
            total = ZERO
            for v in coeff.values():
                total = total + v.norm2()
            if total != ONE:
                raise _Fail(f"branch probabilities sum to {complex(total).real:.6f}, not 1")
    except _Fail as f:
        return Verdict(False, mode, reason=str(f), method=method, certified=certified, n_inputs=len(inputs),
                       details=dict(data_map=dm, seconds=round(time.time() - t0, 3)))
    except PreconditionViolated as e:
        return Verdict(False, mode, reason=f"gadget precondition: {e}", method=method, n_inputs=len(inputs))
    nb = len(coeff)
    det = dict(data_map=dm, ancillas=[q for q in range(c.n_qubits) if q not in set(dm)], measurements=M,
               seconds=round(time.time() - t0, 3))
    if mode == "exact" and nb == 1:
        (ph,) = coeff.values()
        det["global_phase"] = complex(ph)
    return Verdict(True, mode, distance=0.0, bound=0.0, method=method, certified=certified,
                   n_inputs=len(inputs), n_branches=nb, details=det)


def _check_approx(cand, ref: ReferenceSpec, eps: float, lim: Limits, seed: int, n_states: int) -> Verdict:
    from ..core.verifier import check_circuit
    try:
        a_ops, na = ref.numeric_ops()
        b_ops, nb = _ops_and_n(cand)
    except ValueError as e:
        return Verdict(False, "approx", reason=str(e), method="literal", bound=eps)
    if na != nb:
        return Verdict(False, "approx", reason=f"qubit counts differ ({nb} vs reference {na})", method="literal",
                       bound=eps)
    if ref.zero_qubits:
        return Verdict(False, "approx", reason="approx mode needs an unrestricted reference", method="literal",
                       bound=eps)
    if na > lim.approx_max_qubits:
        return Verdict(False, "approx", reason=f"n={na} > {lim.approx_max_qubits}: not numerically verifiable",
                       method="skipped", bound=eps)
    r = check_circuit(a_ops, b_ops, na, eps, n_states=n_states, seed=seed)
    ok = bool(r["ok"]) and bool(r.get("verified", False))
    cert = r["method"] == "unitary"
    reason = "" if ok else f"distance {r.get('dist', float('nan')):.3e} > eps {eps:.3e}"
    det = {k: v for k, v in r.items() if k not in ("ok", "dist", "bound")}
    if not cert and ok:
        det["note"] = "statevector distance is a lower bound on the operator distance"
    return Verdict(ok, "approx", distance=float(r["dist"]), bound=float(eps), reason=reason, method=r["method"],
                   certified=cert, details=det)


# ============================================================================================ entry point
def verify(candidate, reference, mode: str = "exact", eps: float = 0.0, *, data_map=None,
           limits: Limits | None = None, seed: int = 0, n_states: int = 4) -> Verdict:
    """Check `candidate` against `reference` (a ReferenceSpec or anything ReferenceSpec.from_circuit accepts).

    mode: 'exact' | 'approx' | 'relaxed' | 'auto' (see module docstring). eps: approx-mode bound (phase-aligned
    operator distance). data_map[i] = candidate qubit carrying reference qubit i (relaxed / exact; default: by
    register names when both sides have them, else identity)."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    lim = limits or Limits()
    ref = reference if isinstance(reference, ReferenceSpec) else ReferenceSpec.from_circuit(reference)
    requested = mode
    if mode == "auto":
        if is_exact(candidate) and ref.exact:
            c = as_ir(candidate)
            plain = (not n_measurements(c) and c.n_qubits == ref.n_qubits and not ref.zero_qubits
                     and not any(g.cond is not None or g.name in GADGETS for g in c.gates))
            mode = "exact" if plain else "relaxed"
        else:
            mode = "approx"
    if mode == "approx":
        if is_exact(candidate) and ref.exact:
            v = _check_exact_like(candidate, ref, "exact", data_map, lim, seed)
            v.details["routed"] = "approx requested; both circuits Clifford+T -> exact (invariant 1)"
        else:
            v = _check_approx(candidate, ref, float(eps), lim, seed, n_states)
    else:
        v = _check_exact_like(candidate, ref, mode, data_map, lim, seed)
    v.requested = requested
    return v
