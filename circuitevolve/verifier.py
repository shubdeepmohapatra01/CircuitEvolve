"""The verifier: is `new` an allowed replacement for `old` under requirement `req`?

One check covers every rule tag. Let S be the qubits touched where old and new differ (common prefix and suffix are
stripped, so only the changed segment is simulated). Qubits of `old` are DATA: the segment must act the same on every
data input. Qubits that exist only in `new` are FRESH ANCILLAS: they start in |0> and must end in a state that does not
depend on the input (back to |0>, or e.g. a kept phase-gradient register). Measurements split the simulation into
branches; every branch must produce the same data output (up to a phase/amplitude, i.e. a deterministic protocol).

Tags (Req) only say what the rule is ALLOWED to use; the verifier measures what it actually does:
    exact      eps = 0            distance must be <= TOL
    approx     eps > 0            distance must be <= eps (measured, not declared, eps is what the budget is charged)
    ancilla    ancillas > 0       new may have that many extra qubits
    measure    measure = True     new may contain measure / reset / classically controlled gates
    (dirty ancilla = borrowing an existing qubit: needs no tag, existing qubits are DATA and checked on every input)
Distance = phase-invariant operator-norm distance of the data maps, plus the non-determinism residual of each side.
For small supports (<= DENSE_MAX data qubits) the check uses every basis input (exact up to float precision); for larger
supports it uses N_SAMPLES random input states and the verdict is marked mode="sampled".

zero_init (benchmark spec): qubits of `old` that are clean ancillas, i.e. |0> at the START of the circuit. Inside a
changed segment such a qubit is taken to be |0> on input if no earlier gate touched it; its output is still compared
like a data qubit (so a rewrite may rely on it being |0> before first use, never on anything else).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from .circuit import Circuit, Gate, matrix

TOL = 1e-8
DENSE_MAX = 8          # data qubits for the all-basis-inputs check
STATE_MAX = 22         # data + ancilla qubits we are willing to simulate
N_SAMPLES = 8
MAX_BRANCHES = 4096
MAX_AMPLITUDES = 2 ** 26   # ~1 GB of complex128 per simulated state block
MAX_WORK = 2 ** 31         # branches x amplitudes we are willing to simulate for one segment
TIME_LIMIT = 60.0          # seconds for one check(); beyond that the application is refused (never accepted)


@dataclass(frozen=True)
class Req:
    eps: float = 0.0
    ancillas: int = 0
    measure: bool = False

    @property
    def kind(self) -> str:
        tags = ["approx" if self.eps > 0 else "exact"]
        tags += ["ancilla"] * (self.ancillas > 0) + ["measure"] * self.measure
        return "+".join(tags)


@dataclass
class Verdict:
    ok: bool
    dist: float          # measured distance (charge this to the error budget)
    mode: str            # "nochange" | "dense" | "sampled" | "refused"
    support: int = 0
    reason: str = ""


# ---- simulation ---------------------------------------------------------------------------------
def _apply(state, g: Gate, pos: dict):
    """state: array of shape (2,)*m + (K,). Apply unitary gate g (qubits mapped through pos)."""
    axes = [pos[q] for q in g.qubits]
    k = len(axes)
    u = matrix(g).reshape((2,) * 2 * k)
    out = np.tensordot(u, state, axes=(list(range(k, 2 * k)), axes))
    return np.moveaxis(out, list(range(k)), axes)


def _branches(gates, state, pos, cbits, i=0, count=None):
    """Depth-first over measurement outcomes. Yields final (unnormalised) states, one per branch."""
    count = count if count is not None else [0]
    while i < len(gates):
        g = gates[i]
        if g.cond is not None:
            if g.cond not in cbits:
                raise ValueError(f"gate {i} conditioned on bit c[{g.cond}] not measured inside the segment")
            if cbits[g.cond]:
                state = _apply(state, g, pos)
        elif g.name in ("measure", "reset"):
            for o in (0, 1):
                s = state.copy()
                idx = [slice(None)] * s.ndim
                idx[pos[g.qubits[0]]] = 1 - o
                s[tuple(idx)] = 0
                if np.vdot(s, s).real < 1e-24:
                    continue
                if g.name == "reset" and o == 1:
                    s = _apply(s, Gate("x", g.qubits), pos)
                cb = dict(cbits) | ({g.cbit: o} if g.name == "measure" else {})
                yield from _branches(gates, s, pos, cb, i + 1, count)
            return
        else:
            state = _apply(state, g, pos)
        i += 1
    count[0] += 1
    if count[0] > MAX_BRANCHES:
        raise ValueError(f"more than {MAX_BRANCHES} measurement branches")
    yield state


def _data_map(gates, data, fresh, inputs, zinit=()):
    """Run `gates` on inputs (2^d x K, data qubits) with zero-init qubits and fresh ancillas in |0>.
    Returns (W, residual): W is the 2^(d+z) x K output on data + zero-init qubits (common to all branches, up to
    phase); residual measures how far fresh ancillas/branches are from factoring out (0 for a valid protocol)."""
    order = list(data) + list(zinit) + list(fresh)
    pos = {q: i for i, q in enumerate(order)}
    d, z, a, K = len(data), len(zinit), len(fresh), inputs.shape[1]
    init = np.zeros((2 ** d, 2 ** z, 2 ** a, K), complex)
    init[:, 0, 0, :] = inputs
    init = init.reshape((2,) * (d + z + a) + (K,))
    d += z
    w_ref, resid2, rows = None, 0.0, []
    for s in _branches(gates, init, pos, {}):
        R = s.reshape(2 ** d, 2 ** a, K).transpose(1, 0, 2).reshape(2 ** a, -1)   # ancilla x (data out, input)
        if w_ref is None:
            ev, evec = np.linalg.eigh(R @ R.conj().T)
            u1 = evec[:, -1]
            w_ref = u1.conj() @ R
            w_ref /= np.linalg.norm(w_ref)
        alpha = R @ w_ref.conj()
        resid2 += np.linalg.norm(R - np.outer(alpha, w_ref)) ** 2
    W = (w_ref * np.sqrt(K)).reshape(2 ** d, K)
    return W, np.sqrt(resid2 / K)


def _segment(old: Circuit, new: Circuit):
    """Lengths (p, s) of the common prefix and suffix of the two gate lists."""
    a, b = old.gates, new.gates
    p = 0
    while p < min(len(a), len(b)) and a[p] == b[p]:
        p += 1
    s = 0
    while s < min(len(a), len(b)) - p and a[-1 - s] == b[-1 - s]:
        s += 1
    return p, s


def _phase_invariant_dist(A, B, dense: bool):
    """min over phase of ||A - e^{i phi} B|| (phase from the overlap; an upper bound on the true minimum).
    dense: operator 2-norm over all basis inputs; sampled: worst sampled input state."""
    ov = np.vdot(B, A)
    ph = ov / abs(ov) if abs(ov) > 1e-15 else 1.0
    D = A - ph * B
    return float(np.linalg.norm(D, 2)) if dense else float(np.max(np.linalg.norm(D, axis=0)))


def verify(old: Circuit, new: Circuit, req: Req = Req(), seed: int = 0, zero_init=()) -> Verdict:
    if new.n - old.n > req.ancillas:
        return Verdict(False, np.inf, "refused", reason=f"uses {new.n - old.n} extra qubits, req allows {req.ancillas}")
    if new.n < old.n:
        return Verdict(False, np.inf, "refused", reason="removes qubits")
    if not req.measure and not new.is_unitary() and old.is_unitary():
        return Verdict(False, np.inf, "refused", reason="non-unitary ops but req.measure is False")
    p, sfx = _segment(old, new)
    if p == len(old.gates) - sfx and p == len(new.gates) - sfx:
        return Verdict(True, 0.0, "nochange")
    zset = set(zero_init)
    while True:   # a clean ancilla used by the segment but touched by the shared prefix: start the segment earlier
        seg_q = {q for g in old.gates[p:len(old.gates) - sfx] + new.gates[p:len(new.gates) - sfx] for q in g.qubits}
        first = [i for i, g in enumerate(old.gates[:p]) if zset & seg_q & set(g.qubits)]
        if not first:
            break
        p = first[0]
    om, nm = old.gates[p:len(old.gates) - sfx], new.gates[p:len(new.gates) - sfx]
    touched = sorted({q for g in om + nm for q in g.qubits})
    zinit = [q for q in touched if q in zset]                                     # |0> at segment start
    data = [q for q in touched if q < old.n and q not in zinit]  # prefix/suffix are shared with old: no fresh qubits
    fresh = [q for q in touched if q >= old.n]
    seg_bits = {g.cbit for g in om + nm if g.name == "measure"}
    outside = new.gates[:p] + new.gates[len(new.gates) - sfx:]
    if any(g.cond in seg_bits or (g.name == "measure" and g.cbit in seg_bits) for g in outside):
        return Verdict(False, np.inf, "refused", reason="a bit measured in the changed segment is used outside it")
    if len(data) + len(fresh) > STATE_MAX:
        return Verdict(False, np.inf, "refused", support=len(touched), reason=f"support {len(touched)} > {STATE_MAX}")
    d, a = len(data), len(fresh) + len(zinit)
    m = sum(g.name in ("measure", "reset") for g in om) + sum(g.name in ("measure", "reset") for g in nm)
    if 2 ** m > MAX_BRANCHES or 2 ** m * 2 ** (d + a) * (2 ** d if d <= DENSE_MAX else N_SAMPLES) > MAX_WORK and \
            2 ** m * 2 ** (d + a) * N_SAMPLES > MAX_WORK:
        return Verdict(False, np.inf, "refused", support=len(touched), reason=f"segment too expensive ({m} measurements, {d}+{a} qubits)")
    if 2 ** (d + a) * N_SAMPLES > MAX_AMPLITUDES:
        return Verdict(False, np.inf, "refused", support=len(touched), reason=f"segment too large to simulate ({d}+{a} qubits)")
    if d <= DENSE_MAX and 2 ** (2 * d + a) <= MAX_AMPLITUDES and 2 ** m * 2 ** (2 * d + a) <= MAX_WORK:
        inputs, mode = np.eye(2 ** d, dtype=complex), "dense"
    else:
        rng = np.random.default_rng(seed)
        inputs = rng.normal(size=(2 ** d, N_SAMPLES)) + 1j * rng.normal(size=(2 ** d, N_SAMPLES))
        inputs /= np.linalg.norm(inputs, axis=0)
        mode = "sampled"
    try:
        W_old, r_old = _data_map(om, data, [], inputs, zinit)
        W_new, r_new = _data_map(nm, data, fresh, inputs, zinit)
    except ValueError as e:
        return Verdict(False, np.inf, "refused", support=len(touched), reason=str(e))
    dist = _phase_invariant_dist(W_new, W_old, mode == "dense") + r_old + r_new
    allowed = max(req.eps, TOL)
    ok = dist <= allowed
    why = "" if ok else f"distance {dist:.3e} > allowed {allowed:.1e} (ancilla/branch residual {r_new:.1e})"
    return Verdict(bool(ok), float(dist), mode, len(touched), why)


def check(old: Circuit, new: Circuit, req: Req = Req(), zero_init=()) -> Verdict:
    """Main entry point. A rule may change many places of a circuit. Align the two gate lists, then verify each
    changed block in turn on the circuit with the earlier blocks already replaced (each step is a local segment
    replacement, so it is sound, and distances add). If that fails (e.g. the alignment split a valid change badly),
    fall back to one verify() over the whole changed span."""
    import difflib
    ops = [o for o in difflib.SequenceMatcher(None, old.gates, new.gates, autojunk=False).get_opcodes() if o[0] != "equal"]
    t0 = time.monotonic()
    if len(ops) > 1:
        cur, total, worst, shift = old, 0.0, None, 0
        for _, i1, i2, j1, j2 in ops:
            if time.monotonic() - t0 > TIME_LIMIT:
                return Verdict(False, np.inf, "refused", reason=f"verification exceeded {TIME_LIMIT:.0f} s")
            gates = cur.gates[: i1 + shift] + new.gates[j1:j2] + cur.gates[i2 + shift:]
            shift += (j2 - j1) - (i2 - i1)
            used = max((q for g in gates for q in g.qubits), default=-1) + 1
            nxt = Circuit(max(cur.n, used), gates, max(cur.nc, new.nc))
            v = verify(cur, nxt, Req(eps=max(req.eps - total, 0.0), ancillas=new.n - cur.n, measure=req.measure),
                       zero_init=zero_init)
            if not v.ok:
                worst = v
                break
            total += v.dist
            cur = nxt
        else:
            assert cur.gates == new.gates
            if new.n - old.n <= req.ancillas and total <= max(req.eps, TOL):
                return Verdict(True, total, "blockwise", reason=f"{len(ops)} blocks")
    if time.monotonic() - t0 > TIME_LIMIT:
        return Verdict(False, np.inf, "refused", reason=f"verification exceeded {TIME_LIMIT:.0f} s")
    whole = verify(old, new, req, zero_init=zero_init)
    if whole.ok or len(ops) <= 1:
        return whole
    return worst if worst is not None and whole.mode == "refused" else whole
