"""Fix-and-refit: the LLM names rotations of a window and target values; the toolbox re-instantiates the
window's REMAINING rotation angles numerically to minimise the distance to the window's unitary.

This is the dyadic-phase-fixing idea of bqskit-ft's DPFPass (branch algorithmic_error_dpf @
2e99ba614d48970b9afefc0b8c32860c3a3dc9f1, ftpasses/dpf.py: fix one Rz to a multiple of 2*pi/2^k, re-instantiate
all other angles, accept if the block distance is within budget), except that the CHOICE of which rotations to
fix and to what is made by the LLM (one or several at once), not by the greedy "closest to a multiple" rule.

Targets (validated literally, `validate_target`): 0 (= delete the rotation), multiples of pi/4 (exact
Clifford / T gates), or dyadic 2*pi*m/2^k with k <= MAX_K (k = 4: multiples of pi/8; still synthesized by
gridsynth under our metric, so they only help as a stepping stone - the prompt says so).

Numerics: BQSKit's `Minimization` instantiater (Ceres Levenberg-Marquardt on Hilbert-Schmidt residuals, the
bqskit default), starts: the window's current angles; a Pauli-informed start (a fixed rotation's angle change is
moved onto an unfixed rotation with the same Pauli frame and a commuting path, `_merge_start`); `multistarts`
seeded random starts (uniform in [0, 2*pi)). The start with the smallest phase-aligned operator distance wins,
then up to POLISH_ROUNDS restarts from the best point (Ceres stops at its function tolerance, ~1e-7 in
distance, from some starts). The toolbox only
PROPOSES: its output is an ordinary window that goes to the frozen verifier (core/verifier.py) at the
ledger's allowance like any LLM-written window.

Target unitary: computed from the SAME bqskit circuit template with the original angles, so qubit-order
conventions cannot differ between target and fit. The verifier recomputes the distance independently with
the frozen blocks/verify_block.py.
"""
from __future__ import annotations

import math
import re

import numpy as np

from ..blocks.circuit_io import classify_angle
from ..blocks.cost_model import canonical_angle
from ..locks import NUMERIC_LOCK
from .circuit import ParseError, parse_angle

MAX_K = 4                                   # dyadic targets: multiples of 2*pi/2^MAX_K = pi/8
MAX_FIXES = 6
DEFAULT_MULTISTARTS = 8
POLISH_ROUNDS = 3
FIX_FENCE_RE = re.compile(r"```[ \t]*fix[ \t]*\n(.*?)```", re.S | re.I)
FIX_LINE_RE = re.compile(r"^(?:op\s*)?(\d+)\s*(?:->|=|:|to)\s*(.+?)\s*;?$", re.I)


def validate_target(a: float) -> tuple[int, int]:
    """-> (m, k) with a = 2*pi*m/2^k, smallest k <= MAX_K; raises ParseError if not dyadic."""
    unit = 2 * math.pi / 2 ** MAX_K
    m = round(a / unit)
    if abs(a - m * unit) > 1e-9:
        raise ParseError(f"target {a!r} is not 0, a multiple of pi/4, or 2*pi*m/2^k with k <= {MAX_K}")
    k = MAX_K
    m %= 2 ** MAX_K
    while k > 0 and m % 2 == 0:
        m //= 2
        k -= 1
    return m, k


def parse_fix(body: str) -> dict:
    """Literal fix block -> {op_index: target_angle}. Lines `op 12 -> pi/4`, `7 -> 0`, `op 3 = -3*pi/8`."""
    fixes = {}
    lines = [ln.split("#", 1)[0].split("//", 1)[0].strip() for ln in body.splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        raise ParseError("empty fix block")
    for ln in lines:
        m = FIX_LINE_RE.match(ln)
        if not m:
            raise ParseError(f"cannot parse fix line {ln!r}")
        i = int(m.group(1))
        txt = m.group(2).strip().lower()
        txt = re.sub(r"^rz\s*\((.*)\)$", r"\1", txt)
        a = 0.0 if txt in ("0", "0.0", "delete", "drop", "remove", "identity") else parse_angle(txt)
        validate_target(a)
        if i in fixes:
            raise ParseError(f"op {i} fixed twice")
        fixes[i] = a
    if len(fixes) > MAX_FIXES:
        raise ParseError(f"more than {MAX_FIXES} fixes in one block")
    return fixes


def extract_fixes(text: str, max_blocks: int = 3) -> tuple[list, list]:
    out, errs = [], []
    for body in FIX_FENCE_RE.findall(text or "")[:max_blocks]:
        try:
            out.append(parse_fix(body))
        except ParseError as e:
            errs.append(str(e))
    return out, errs


def free_rotations(local_ops) -> list:
    """Indices of rz ops that need synthesis (not multiples of pi/4)."""
    return [i for i, (g, _, a) in enumerate(local_ops) if g == "rz" and classify_angle(a) is None]


def _rz_const(a: float):
    from bqskit.ir.gates import ConstantUnitaryGate
    return ConstantUnitaryGate(np.diag([np.exp(-0.5j * a), np.exp(0.5j * a)]))


_CONST = None


def _const_gates():
    global _CONST
    if _CONST is None:
        from bqskit.ir.gates import CNOTGate, CZGate, HGate, SdgGate, SGate, TdgGate, TGate, XGate, ZGate
        _CONST = {"h": HGate(), "s": SGate(), "sdg": SdgGate(), "x": XGate(), "z": ZGate(), "t": TGate(),
                  "tdg": TdgGate(), "cx": CNOTGate(), "cz": CZGate()}
    return _CONST


def _template(local_ops, k: int, fixes: dict):
    """-> (target unitary, fit circuit, free_idx, perm, x_free).
    target: the ORIGINAL window as a parameter-free bqskit circuit (every rz a constant gate).
    fit: fixed rotations as constants (0-targets removed), free rotations as RZGate parameters.
    BQSKit orders parameters by cycle, not by insertion, so each free RZ is appended with a unique marker
    value and `perm[t]` = position in fit.params of free rotation number t (insertion order)."""
    from bqskit.ir.circuit import Circuit as BCircuit
    from bqskit.ir.gates import RZGate
    const = _const_gates()
    full, fit = BCircuit(k), BCircuit(k)
    free_idx, x_free = [], []
    for i, (g, qs, a) in enumerate(local_ops):
        if g == "rz":
            full.append_gate(_rz_const(float(a)), list(qs))
            if i in fixes:
                if fixes[i] != 0.0:
                    fit.append_gate(_rz_const(float(fixes[i])), list(qs))
            elif classify_angle(a) is not None:
                fit.append_gate(_rz_const(float(a)), list(qs))
            else:
                fit.append_gate(RZGate(), list(qs), [1000.0 + len(free_idx)])
                free_idx.append(i)
                x_free.append(float(a))
        else:
            full.append_gate(const[g], list(qs))
            fit.append_gate(const[g], list(qs))
    markers = [int(round(v - 1000.0)) for v in fit.params]
    perm = [markers.index(t) for t in range(len(free_idx))]
    return np.asarray(full.get_unitary().numpy), fit, free_idx, perm, np.array(x_free)


def _merge_start(local_ops, k: int, fixes: dict, free_idx: list, x_free):
    """Pauli-informed warm start: for each fixed rotation j (angle a_j -> target t_j), if an unfixed free rotation
    i has the same Pauli (mutator.rotation_paulis) and every rotation between them commutes with it, start i at
    x_i +- (a_j - t_j) (the exact merge). None if no fixed rotation has such a partner."""
    from .mutator import rotation_paulis

    def commute(p, q):
        return sum(1 for a, b in zip(p[1:], q[1:]) if a != "I" and b != "I" and a != b) % 2 == 0
    P = rotation_paulis(local_ops, k)
    rot = sorted(P)
    x = np.array(x_free, dtype=float)
    pos = {i: t for t, i in enumerate(free_idx)}
    hit = False
    for j, tj in fixes.items():
        if j not in P:
            continue
        aj = float(local_ops[j][2])
        for i in sorted((i for i in pos if P[i][1:] == P[j][1:]), key=lambda i: abs(i - j)):
            lo, hi = min(i, j), max(i, j)
            if all(commute(P[m], P[j]) for m in rot if lo < m < hi):
                x[pos[i]] += (1 if P[i][0] == P[j][0] else -1) * (aj - tj)
                hit = True
                break
    return x if hit else None


def _opdist(U, V) -> float:
    """Phase-aligned operator-norm distance min_phi ||U - e^{i phi} V||_2 (same quantity as the frozen
    verifier; recomputed there independently)."""
    tr = np.trace(V.conj().T @ U)
    ph = tr / abs(tr) if abs(tr) > 0 else 1.0
    return float(np.linalg.norm(U - ph * V, 2))


def refit(local_ops, k: int, fixes: dict, multistarts: int = DEFAULT_MULTISTARTS, seed: int = 0) -> dict:
    """-> {ok, ops, dist, n_free, fixes, reason}. `ops` is the refitted LOCAL window (fixed rotations at their
    targets, 0-targets removed, free angles re-instantiated). Raises nothing for bad input: returns ok=False."""
    rz_idx = {i for i, (g, _, _) in enumerate(local_ops) if g == "rz"}
    bad = [i for i in fixes if i not in rz_idx]
    if bad:
        return dict(ok=False, ops=None, dist=None, n_free=None, fixes=fixes,
                    reason=f"op index {bad} is not an rz of this window")
    for i, a in fixes.items():
        try:
            validate_target(a)
        except ParseError as e:
            return dict(ok=False, ops=None, dist=None, n_free=None, fixes=fixes, reason=str(e))
    from bqskit.ir.opt.instantiaters.minimization import Minimization
    from bqskit.qis.unitary import UnitaryMatrix

    with NUMERIC_LOCK:
        U, fit, free_idx, perm, x_free = _template(local_ops, k, fixes)
        if not free_idx:
            best = (_opdist(U, fit.get_unitary().numpy), np.zeros(0))
        else:
            inst = Minimization()
            rng = np.random.default_rng(seed)
            starts = [x_free.copy()]
            merged = _merge_start(local_ops, k, fixes, free_idx, x_free)
            if merged is not None:
                starts.append(merged)
            starts += [rng.uniform(0, 2 * math.pi, len(free_idx)) for _ in range(multistarts)]
            target = UnitaryMatrix(U)

            def _run(xs):
                x0 = np.zeros(len(free_idx))
                x0[perm] = xs                                   # insertion order -> bqskit parameter order
                xb = np.asarray(inst.instantiate(fit, target, x0), dtype=float)
                return _opdist(U, fit.get_unitary(xb).numpy), xb[perm]   # back to insertion order
            best = None
            for xs in starts:
                try:
                    cand = _run(xs)
                except Exception:                                # pragma: no cover
                    continue
                if best is None or cand[0] < best[0]:
                    best = cand
            for _ in range(POLISH_ROUNDS):                       # LM stops at its function tolerance; restart
                if best is None or best[0] < 1e-13:              # from the best point to tighten
                    break
                try:
                    cand = _run(best[1])
                except Exception:                                # pragma: no cover
                    break
                if cand[0] >= best[0]:
                    break
                best = cand
            if best is None:
                return dict(ok=False, ops=None, dist=None, n_free=len(free_idx), fixes=fixes,
                            reason="instantiation failed for every start")
    d, xf = best
    # rebuild the local window: fixed -> target (0 removed), free -> refitted angle (reduced to [-pi, pi])
    new_free = {free_idx[t]: canonical_angle(float(xf[t])) for t in range(len(free_idx))}
    ops = []
    for i, (g, qs, a) in enumerate(local_ops):
        if g == "rz":
            if i in fixes:
                if fixes[i] != 0.0:
                    ops.append(("rz", qs, float(fixes[i])))
            elif i in new_free:
                ops.append(("rz", qs, new_free[i]))
            else:
                ops.append((g, qs, a))
        else:
            ops.append((g, qs, a))
    return dict(ok=True, ops=ops, dist=float(d), n_free=len(free_idx), fixes=fixes, reason="")
