"""Verifier for window replacements and whole circuits - a thin wrapper around the FROZEN
blocks/verify_block.py (never edited here; integrity.FROZEN hashes it).

verify_window(orig, new, k, allowance)
  1. literal checks: gate set, local qubit range, op count limit (no execution of model text anywhere);
  2. if both windows are Clifford+T after snapping exact pi/4-multiple rz (circuit.normalize), EXACT mode:
     verify_block.verify_exact over Z[omega]/sqrt2^k, charge 0 on success;
  3. otherwise APPROXIMATE mode: verify_block.verify_instance(orig, new, k, eps=allowance) - phase-aligned
     OPERATOR-norm distance d <= allowance; the charge is d. For reference the record also carries BQSKit's
     Hilbert-Schmidt quantities, hs_cost = 1 - |Tr(U^dag V)|/N and hs_dist = sqrt(1 - (|Tr|/N)^2); both are
     <= d, so a window accepted here also passes a BQSKit HS threshold of the same value.
check_circuit(original, candidate, n, bound)
  whole-circuit numerical check against the ORIGINAL qseed circuit (verify_block.circuit_check: dense unitary
  for n <= 10, Haar-random statevectors for n <= 20, skipped above): pass iff dist <= bound + NUMERIC_SLACK.
  For n in 11..20 the statevector distance is a lower bound on the operator distance (it can catch errors,
  not certify the bound). Runs under circuitevolve.locks.NUMERIC_LOCK.
"""
from __future__ import annotations

import math

import numpy as np

from ..blocks import verify_block as vb
from ..locks import NUMERIC_LOCK
from .circuit import CORE_GATES, normalize

NUMERIC_SLACK = 1e-10       # floating-point error of dense simulation (observed ~1e-13 for exact rewrites)
MAX_WINDOW_OPS = 120


def _literal_check(ops, k: int) -> str | None:
    if not ops:
        return None                       # an empty replacement is legal (window was identity)
    if len(ops) > MAX_WINDOW_OPS:
        return f"too many ops ({len(ops)} > {MAX_WINDOW_OPS})"
    for g, qs, a in ops:
        if g not in CORE_GATES:
            return f"gate {g!r} not allowed"
        if len(qs) != (2 if g in ("cx", "cz") else 1) or len(set(qs)) != len(qs):
            return f"bad qubit list {qs} for {g}"
        if any(not 0 <= q < k for q in qs):
            return f"qubit out of range in {g} {qs} (window has {k} qubits)"
        if g == "rz" and not (isinstance(a, float) and math.isfinite(a)):
            return f"rz angle {a!r} is not a finite float"
    return None


def hs_quantities(orig_ops, new_ops, k: int) -> dict:
    U, V = vb.unitary(orig_ops, k), vb.unitary(new_ops, k)
    x = min(1.0, abs(np.trace(U.conj().T @ V)) / U.shape[0])
    return dict(hs_cost=float(1.0 - x), hs_dist=float(math.sqrt(max(0.0, 1.0 - x * x))))


def verify_window(orig_ops, new_ops, k: int, allowance: float) -> dict:
    """-> {ok, mode, dist, charge, reason, ...}. orig/new are LOCAL op lists on k qubits."""
    why = _literal_check(new_ops, k)
    if why:
        return dict(ok=False, mode="literal", reason=why, dist=None, charge=None)
    a, b = normalize(orig_ops), normalize(new_ops)
    with NUMERIC_LOCK:
        if vb.is_exact_block(a) and vb.is_exact_block(b):
            r = vb.verify_exact(a, b, k)
            if r["ok"]:
                return dict(ok=True, mode="exact", dist=0.0, charge=0.0, reason="",
                            phase_omega_power=r.get("phase_omega_power"))
            exact_reason = r.get("reason", "")
        else:
            exact_reason = None
        r = vb.verify_instance(a, b, k, eps=allowance)
        hs = hs_quantities(a, b, k)
    out = dict(ok=bool(r["ok"]), mode="approx", dist=float(r["dist"]), fro=float(r["fro"]),
               charge=float(r["dist"]) if r["ok"] else None, allowance=float(allowance), **hs)
    if not r["ok"]:
        out["reason"] = (f"distance {r['dist']:.3e} > allowance {allowance:.3e}"
                         + (f"; exact check: {exact_reason}" if exact_reason else ""))
    else:
        out["reason"] = ""
    return out


def check_circuit(original_ops, cand_ops, n: int, bound: float, n_states: int = 4, seed: int = 0) -> dict:
    with NUMERIC_LOCK:
        r = vb.circuit_check(original_ops, cand_ops, n, n_states=n_states, seed=seed)
    if r["method"] == "skipped":
        r.update(ok=True, verified=False, bound=bound)
    else:
        r.update(ok=bool(r["dist"] <= bound + NUMERIC_SLACK), verified=True, bound=bound)
    return r
