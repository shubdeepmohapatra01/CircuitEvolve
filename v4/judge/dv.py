"""DV judge for v4: the v3 judge surface plus the three caches V4_README section 6.4 asks for.

Re-exported unchanged from v3 (frozen): `load`, `manifest_entry`, `parse_logical`, `measure`, `verify_window`,
`is_ir`, `canonical_angle`. Everything added here only *reorders* calls to the same frozen primitives:

  reference(c)          memoised `v2.verify.ReferenceSpec` (v3 rebuilt it per call)
  check_circuit(...)    whole-circuit numeric check with the REFERENCE side cached. v3's `circuit_check`
                        rebuilt both sides every call; the reference is the same original circuit every time
                        (110 ms of qpe_8's 283 ms = 39%). Same frozen arithmetic, same numbers - asserted
                        bit-for-bit against the frozen `core.verifier.check_circuit` in tests/test_p0.py.
  verify(...)           v2 verify with the cached reference.
  verify_window_memo()  window check memoised on (normalise(old), normalise(new), k, allowance bucket).

Nothing here decides acceptance differently from v3; it decides the same thing fewer times.
"""
from __future__ import annotations

import math

import numpy as np

from circuitevolve.blocks import verify_block as _vb
from circuitevolve.core import verifier as _core_verifier
from circuitevolve.core.circuit import normalize
from circuitevolve.ir import Circuit as IRCircuit
from circuitevolve.locks import NUMERIC_LOCK
from circuitevolve.v2 import verify as _v2_verify
from v3.judge.dv import (CCZ_DEF, canonical_angle, is_ir, load, manifest_entry,  # noqa: F401
                         measure, parse_logical, verify_window)

from .frozen import check_frozen

NUMERIC_SLACK = _core_verifier.NUMERIC_SLACK
is_exact = _v2_verify.is_exact
Limits = _v2_verify.Limits
ReferenceSpec = _v2_verify.ReferenceSpec
NotExact = _v2_verify.NotExact
Verdict = _v2_verify.Verdict

STATS: dict = dict(reference_hits=0, reference_misses=0, ref_side_hits=0, ref_side_misses=0,
                   window_hits=0, window_misses=0, whole_checks=0)
_REFS: dict = {}
_REF_SIDE: dict = {}
_WINDOWS: dict = {}


# ------------------------------------------------------------------------------------------ keys
def ckey(c) -> tuple:
    """Stable, cheap, collision-free key of a circuit (its literal op/gate sequence)."""
    if isinstance(c, IRCircuit):
        return ("ir", c.n_qubits, c.n_cbits,
                tuple((g.name, tuple(g.qubits), g.cbit, g.cond) for g in c.gates))
    if hasattr(c, "ops") and hasattr(c, "n"):
        return ("ops", int(c.n), tuple((g, tuple(q), a) for g, q, a in c.ops))
    if isinstance(c, tuple) and len(c) == 2:
        return ("ops", int(c[1]), tuple((g, tuple(q), a) for g, q, a in c[0]))
    raise TypeError(f"cannot key {type(c).__name__}")


# ------------------------------------------------------------------------------------------ reference
def reference(ref):
    """Memoised ReferenceSpec. Same construction as v3.judge.dv.reference (incl. the from_function fallback
    for non-permutation-like Toffoli circuits above 2^14 inputs), built once per distinct circuit."""
    if isinstance(ref, ReferenceSpec):
        return ref
    k = ckey(ref)
    hit = _REFS.get(k)
    if hit is not None:
        STATS["reference_hits"] += 1
        return hit
    STATS["reference_misses"] += 1
    from v3.judge.dv import reference as _v3_reference
    spec = _v3_reference(ref)
    _REFS[k] = spec
    return spec


# ------------------------------------------------------------------------------------------ whole circuit
def _ref_side(ops, n: int, n_states: int, seed: int):
    """The cached reference side of the frozen `circuit_check`: the dense unitary (n <= 10) or the Haar
    probe states together with the reference's images (11 <= n <= 20). Built with the frozen primitives."""
    k = (tuple((g, tuple(q), a) for g, q, a in ops), n, n_states, seed)
    hit = _REF_SIDE.get(k)
    if hit is not None:
        STATS["ref_side_hits"] += 1
        return hit
    STATS["ref_side_misses"] += 1
    if n <= 10:
        val = ("unitary", _vb.unitary(ops, n), None)
    elif n > 20:
        val = ("skipped", None, None)
    else:
        rng = np.random.default_rng(seed)
        dim = 1 << n
        psi = rng.normal(size=(dim, n_states)) + 1j * rng.normal(size=(dim, n_states))
        psi /= np.linalg.norm(psi, axis=0)
        st = psi.reshape((2,) * n + (n_states,))
        A = _vb.apply_ops(st.copy(), ops, n).reshape(dim, n_states)
        val = ("statevector", psi, A)
    _REF_SIDE[k] = val
    return val


def circuit_check(ref_ops, cand_ops, n: int, n_states: int = 4, seed: int = 0) -> dict:
    """Frozen `blocks.verify_block.circuit_check(ref_ops, cand_ops, n)` with the reference side cached.
    Returns the identical dict (tested bit-for-bit)."""
    STATS["whole_checks"] += 1
    method, a, A = _ref_side(list(ref_ops), int(n), int(n_states), int(seed))
    if method == "skipped":
        return dict(method="skipped", n=n)
    with NUMERIC_LOCK:
        if method == "unitary":
            d = _vb.distance(a, _vb.unitary(cand_ops, n))
            return dict(method="unitary", n=n, dist=d["op"], fro=d["fro"])
        dim = 1 << n
        st = a.reshape((2,) * n + (n_states,))
        B = _vb.apply_ops(st.copy(), cand_ops, n).reshape(dim, n_states)
    ov = np.einsum("ij,ij->j", A.conj(), B)
    vd = [float(np.linalg.norm(A[:, j] - (ov[j].conj() / abs(ov[j])) * B[:, j])) for j in range(n_states)]
    return dict(method="statevector", n=n, n_states=n_states,
                one_minus_overlap=float(max(1 - abs(o) for o in ov)), dist=max(vd))


def check_circuit(ref_ops, cand_ops, n: int, bound: float, n_states: int = 4, seed: int = 0) -> dict:
    """As `core.verifier.check_circuit`, cached reference side."""
    r = circuit_check(ref_ops, cand_ops, n, n_states=n_states, seed=seed)
    if r["method"] == "skipped":
        r.update(ok=True, verified=False, bound=bound)
    else:
        r.update(ok=bool(r["dist"] <= bound + NUMERIC_SLACK), verified=True, bound=bound)
    return r


# ------------------------------------------------------------------------------------------ verify
def _check_approx_cached(cand, ref: ReferenceSpec, eps: float, lim: Limits, seed: int, n_states: int) -> Verdict:
    """`v2.verify._check_approx` with the reference unitary / probe images cached."""
    try:
        a_ops, na = ref.numeric_ops()
        b_ops, nb = _v2_verify._ops_and_n(cand)
    except ValueError as e:
        return Verdict(False, "approx", reason=str(e), method="literal", bound=eps)
    if na != nb:
        return Verdict(False, "approx", reason=f"qubit counts differ ({nb} vs reference {na})",
                       method="literal", bound=eps)
    if ref.zero_qubits:
        return Verdict(False, "approx", reason="approx mode needs an unrestricted reference",
                       method="literal", bound=eps)
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
    return Verdict(ok, "approx", distance=float(r["dist"]), bound=float(eps), reason=reason,
                   method=r["method"], certified=cert, details=det)


def verify(candidate, ref, mode: str = "exact", eps: float = 0.0, **kw) -> Verdict:
    """v2 verify with the cached reference (and the cached reference unitary on the approx path)."""
    check_frozen()
    spec = reference(ref)
    if mode == "approx" and not (is_exact(candidate) and spec.exact):
        lim = kw.get("limits") or Limits()
        v = _check_approx_cached(candidate, spec, float(eps), lim, kw.get("seed", 0), kw.get("n_states", 4))
        v.requested = "approx"
        return v
    return _v2_verify.verify(candidate, spec, mode=mode, eps=eps, **kw)


# ------------------------------------------------------------------------------------------ verdict memo
_VERDICTS: dict = {}


def verify_memo(candidate, ref, mode: str = "exact", eps: float = 0.0, **kw) -> Verdict:
    """`verify` memoised on (candidate, reference, mode).

    This is the mechanism that makes V4_README 5.1 cheap. `order='best'` runs the book 2 + len(book)
    times over the same circuit (gain order, book order, one solo run per rule), and every one of those
    re-verifies the SAME (old window, new window) pairs and the same whole-circuit check against the same
    original. The frozen check is a pure function of its inputs, so its verdict is cached.

    `mode='approx'` verdicts carry a MEASURED distance, so a hit is re-decided against the caller's
    current allowance: a cached pass can never become a pass at a tighter budget, and a cached fail
    becomes a pass only if the measured distance really fits. Exact and relaxed verdicts do not depend on
    eps at all.
    """
    key = (ckey(candidate) if not isinstance(candidate, ReferenceSpec) else None,
           ckey(ref) if not isinstance(ref, ReferenceSpec) else None, mode,
           kw.get("seed", 0), kw.get("n_states", 4))
    if None in key[:2]:                                    # un-keyable input: do not cache
        return verify(candidate, ref, mode=mode, eps=eps, **kw)
    hit = _VERDICTS.get(key)
    if hit is None:
        STATS["window_misses"] += 1
        hit = verify(candidate, ref, mode=mode, eps=eps, **kw)
        _VERDICTS[key] = hit
        return hit
    STATS["window_hits"] += 1
    if hit.mode != "approx" or hit.distance is None:
        return hit
    out = Verdict(**{f: getattr(hit, f) for f in hit.__dataclass_fields__})
    out.details = dict(hit.details)
    out.bound = float(eps)
    out.ok = bool(hit.distance <= float(eps))
    out.reason = "" if out.ok else f"distance {hit.distance:.3e} > eps {float(eps):.3e}"
    return out


# ------------------------------------------------------------------------------------------ windows
def _wkey(old, new, k: int, allowance: float) -> tuple:
    """Windows are keyed on their NORMALISED op lists. The allowance enters only as the value it is
    compared against, so an exact-mode hit (distance 0) is reusable at any allowance; an approx hit is
    reusable at any allowance >= the measured distance (handled by the caller)."""
    return (tuple((g, tuple(q), (None if a is None else round(float(a), 15))) for g, q, a in normalize(old)),
            tuple((g, tuple(q), (None if a is None else round(float(a), 15))) for g, q, a in normalize(new)),
            int(k))


def verify_window_memo(orig_ops, new_ops, k: int, allowance: float) -> dict:
    """`verify_window` memoised on the normalised window pair. The frozen check reports a measured distance,
    so the memo stores the distance and re-decides against the current allowance (no stale accepts)."""
    key = _wkey(orig_ops, new_ops, k, allowance)
    hit = _WINDOWS.get(key)
    if hit is None:
        STATS["window_misses"] += 1
        hit = verify_window(orig_ops, new_ops, k, allowance)
        _WINDOWS[key] = hit
        return dict(hit)
    STATS["window_hits"] += 1
    out = dict(hit)
    if out.get("mode") == "approx":
        # the frozen check measured a distance; re-decide it against THIS allowance
        d = out.get("dist")
        if d is None:                        # literal reject or a failed measurement: nothing to reuse
            return out
        out["allowance"] = float(allowance)
        out["ok"] = bool(d <= allowance)
        out["charge"] = float(d) if out["ok"] else None
        out["reason"] = "" if out["ok"] else f"distance {d:.3e} > allowance {allowance:.3e}"
    return out


def cache_stats() -> dict:
    return dict(STATS, references=len(_REFS), ref_sides=len(_REF_SIDE), windows=len(_WINDOWS),
                verdicts=len(_VERDICTS))


def clear_caches() -> None:
    _REFS.clear()
    _REF_SIDE.clear()
    _WINDOWS.clear()
    _VERDICTS.clear()
    for k in STATS:
        STATS[k] = 0


def grid_multiple(theta: float, tol: float = 1e-9) -> bool:
    """True if theta is a multiple of pi/4 within tol (the frozen metric prices these exactly)."""
    r = float(theta) / (math.pi / 4)
    return abs(r - round(r)) * (math.pi / 4) < tol
