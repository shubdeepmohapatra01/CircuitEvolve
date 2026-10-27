"""Differential fuzz test: verifier.check must agree with a deliberately naive reference on thousands of random cases.

The reference shares NOTHING with the verifier's shortcuts: it simulates both WHOLE circuits from gate 0 with full
2^N matrices built gate by gate, enumerates every measurement branch, and applies the definition directly:
    for every input (data qubits: any basis state; zero-init qubits: |0>; fresh ancillas: |0>), every branch of `new`
    must give old's output on the old qubits, with the fresh ancillas in a state that does not depend on the input.
No prefix/suffix stripping, no blocks, no segment logic. Any disagreement is a verifier bug.
"""
import itertools

import numpy as np
import pytest

from circuitevolve.circuit import Circuit, Gate, matrix
from circuitevolve.verifier import TOL, Req, check

# ---- naive reference ----------------------------------------------------------------------------
def _full(g: Gate, n: int) -> np.ndarray:
    m, k = matrix(g), len(g.qubits)
    U = np.zeros((2 ** n, 2 ** n), complex)
    for x in range(2 ** n):
        bits = [(x >> (n - 1 - q)) & 1 for q in range(n)]
        sub = int("".join(str(bits[q]) for q in g.qubits), 2)
        for y in range(2 ** k):
            nb = list(bits)
            for j, q in enumerate(g.qubits):
                nb[q] = (y >> (k - 1 - j)) & 1
            U[int("".join(map(str, nb)), 2), x] += m[y, sub]
    return U


def _run(c: Circuit, n: int, S: np.ndarray):
    """All final branch states (columns = inputs) of c on n qubits, starting from S."""
    branches = [(S, {})]
    for g in c.gates:
        nxt = []
        for s, bits in branches:
            if g.name in ("measure", "reset"):
                q = g.qubits[0]
                for o in (0, 1):
                    P = np.diag([1.0 if ((x >> (n - 1 - q)) & 1) == o else 0.0 for x in range(2 ** n)])
                    t = P @ s
                    if np.linalg.norm(t) < 1e-12:
                        continue
                    if g.name == "reset" and o == 1:
                        t = _full(Gate("x", (q,)), n) @ t
                    nxt.append((t, bits | ({g.cbit: o} if g.name == "measure" else {})))
            elif g.cond is not None and not bits.get(g.cond, 0):
                nxt.append((s, bits))
            else:
                nxt.append((_full(Gate(g.name, g.qubits, g.theta), n) @ s, bits))
        branches = nxt
    return [s for s, _ in branches]


def _factor(states, n_keep: int, n_total: int, K: int):
    """Rows (branch, extra qubits) x cols (kept-qubit output, input). Rank-1 => (W, residual)."""
    rows = [s.reshape(2 ** n_keep, 2 ** (n_total - n_keep), K).transpose(1, 0, 2).reshape(2 ** (n_total - n_keep), -1)
            for s in states]
    R = np.vstack(rows)
    u, sv, vh = np.linalg.svd(R, full_matrices=False)
    W = (sv[0] * vh[0]).reshape(2 ** n_keep, K)
    return W, float(np.sqrt(np.sum(sv[1:] ** 2) / K))


def reference(old: Circuit, new: Circuit, req: Req, zero_init=()) -> bool:
    if new.n < old.n or new.n - old.n > req.ancillas:
        return False
    if not req.measure and not new.is_unitary() and old.is_unitary():
        return False
    n, N = old.n, new.n
    xs = [x for x in range(2 ** n) if all(((x >> (n - 1 - q)) & 1) == 0 for q in zero_init)]
    S_old = np.zeros((2 ** n, len(xs)), complex)
    S_new = np.zeros((2 ** N, len(xs)), complex)
    for k, x in enumerate(xs):
        S_old[x, k] = 1
        S_new[x << (N - n), k] = 1                      # fresh ancillas (the last N - n qubits) start in |0>
    W_old, r_old = _factor(_run(old, n, S_old), n, n, len(xs))
    W_new, r_new = _factor(_run(new, N, S_new), n, N, len(xs))
    ov = np.vdot(W_old, W_new)
    ph = ov / abs(ov) if abs(ov) > 1e-15 else 1.0
    dist = np.linalg.norm(W_new - ph * W_old, 2) + r_old + r_new
    return bool(dist <= max(req.eps, TOL))


# ---- random cases ---------------------------------------------------------------------------------
ONE = ["h", "x", "z", "s", "sdg", "t", "tdg"]
IDENTITY_PAIRS = [("h", "h"), ("x", "x"), ("s", "sdg"), ("t", "tdg"), ("z", "z")]
CCX_7T = [("h", 2), ("cx", 1, 2), ("tdg", 2), ("cx", 0, 2), ("t", 2), ("cx", 1, 2), ("tdg", 2), ("cx", 0, 2),
          ("t", 1), ("t", 2), ("h", 2), ("cx", 0, 1), ("t", 0), ("tdg", 1), ("cx", 0, 1)]


def G(name, *q, theta=None, cbit=None, cond=None):
    return Gate(name, tuple(q), theta=theta, cbit=cbit, cond=cond)


def gidney_and(a, b, t):
    return [G("h", t), G("t", t), G("cx", a, t), G("cx", b, t), G("cx", t, a), G("cx", t, b), G("tdg", a),
            G("tdg", b), G("t", t), G("cx", t, a), G("cx", t, b), G("h", t), G("s", t)]


def measured_uncompute(a, b, t, bit):
    return [G("h", t), G("measure", t, cbit=bit), G("cz", a, b, cond=bit), G("x", t, cond=bit)]


def rand_gate(rng, qubits):
    r = rng.random()
    if r < 0.45:
        return G(ONE[rng.integers(len(ONE))], int(rng.choice(qubits)))
    if r < 0.55:
        return G("rz", int(rng.choice(qubits)), theta=float(rng.uniform(-np.pi, np.pi)))
    if r < 0.85 and len(qubits) >= 2:
        a, b = rng.choice(qubits, 2, replace=False)
        return G("cx" if rng.random() < 0.7 else "cz", int(a), int(b))
    if len(qubits) >= 3:
        a, b, c = rng.choice(qubits, 3, replace=False)
        return G("ccx" if rng.random() < 0.5 else "ccz", int(a), int(b), int(c))
    return G("h", int(qubits[0]))


def correct_rewrite(rng, old: Circuit, new: Circuit, state):
    """Apply one equivalence-preserving rewrite to `new` (in place). Returns the permissions it needs."""
    gates = new.gates
    kind = rng.integers(7)
    if kind == 0:                                                     # insert an identity pair
        a, b = IDENTITY_PAIRS[rng.integers(len(IDENTITY_PAIRS))]
        q, i = int(rng.integers(old.n)), int(rng.integers(len(gates) + 1))
        gates[i:i] = [G(a, q), G(b, q)]
        return Req()
    idx = [i for i, g in enumerate(gates) if g.name in ("ccx", "ccz") and g.cond is None]
    if kind == 1 and idx:                                             # ccx -> 7 T decomposition (ccz via h-ccx-h)
        i = int(rng.choice(idx)); g = gates[i]; a, b, c = g.qubits
        m = {0: a, 1: b, 2: c}
        seq = [G(s[0], *[m[x] for x in s[1:]]) for s in CCX_7T]
        gates[i:i + 1] = ([G("h", c)] + seq + [G("h", c)]) if g.name == "ccz" else seq
        return Req()
    if kind == 2:                                                     # swap two adjacent commuting (disjoint) gates
        pairs = [i for i in range(len(gates) - 1) if not set(gates[i].qubits) & set(gates[i + 1].qubits)
                 and gates[i].cond is None and gates[i + 1].cond is None
                 and gates[i].name != "measure" and gates[i + 1].name != "measure"]
        if pairs:
            i = int(rng.choice(pairs)); gates[i], gates[i + 1] = gates[i + 1], gates[i]
        return Req()
    if kind == 3:                                                     # merge or split an rz
        idx = [i for i, g in enumerate(gates) if g.name == "rz"]
        if idx:
            i = int(rng.choice(idx)); g = gates[i]; a = float(rng.uniform(-1, 1))
            gates[i:i + 1] = [G("rz", g.qubits[0], theta=a), G("rz", g.qubits[0], theta=g.theta - a)]
        return Req()
    if kind in (4, 5) and [i for i in idx if gates[i].name == "ccz"]:  # ccz via a fresh ancilla (+ Gidney AND)
        i = int(rng.choice([i for i in idx if gates[i].name == "ccz"])); a, b, c = gates[i].qubits
        anc, bit = new.n, new.nc
        new.n += 1; new.nc += 1
        compute = gidney_and(a, b, anc) if kind == 5 else [G("ccx", a, b, anc)]
        gates[i:i + 1] = compute + [G("cz", anc, c)] + measured_uncompute(a, b, anc, bit)
        return Req(ancillas=1, measure=True)
    if kind == 6:                                                     # approximate: perturb an rz angle
        idx = [i for i, g in enumerate(gates) if g.name == "rz"]
        if idx:
            i = int(rng.choice(idx)); g = gates[i]; d = float(rng.choice([1e-3, -1e-3]))
            gates[i] = G("rz", g.qubits[0], theta=g.theta + d)
            state["eps"] += abs(d)          # |delta|/2 is the true distance, so eps=|delta| is a clear accept
        return Req(eps=1.0)                 # the real eps is set by the caller from state
    return Req()


def ladder_case(rng):
    """The clean-ancilla pattern that broke the verifier: t is a zero-init qubit, h t; ccz(a,b,t); h t ... used ...
    same Toffoli again. Random gates on OTHER qubits around it. Correct rewrite: Gidney AND + measured uncompute."""
    n = int(rng.integers(4, 6))
    a, b, t, u = rng.choice(n, 4, replace=False).tolist()
    others = [q for q in range(n) if q != t]
    pre = [rand_gate(rng, others) for _ in range(rng.integers(0, 4))]
    mid = [G("cx", t, u)] + [rand_gate(rng, [q for q in others if q not in (a, b)] or [u]) for _ in range(rng.integers(0, 3))]
    post = [rand_gate(rng, others) for _ in range(rng.integers(0, 4))]
    tof = [G("h", t), G("ccz", a, b, t), G("h", t)]
    old = Circuit(n, pre + tof + mid + tof + post)
    new = Circuit(n, pre + gidney_and(a, b, t) + mid + measured_uncompute(a, b, t, 0) + post, nc=1)
    return old, new, Req(measure=True), (t,)


def mutate(rng, new: Circuit):
    """Plant a bug somewhere in new (may occasionally still be equivalent: the reference decides)."""
    gates = new.gates
    i = int(rng.integers(len(gates)))
    g = gates[i]
    flip = {"t": "tdg", "tdg": "t", "s": "sdg", "sdg": "s", "h": "x", "x": "h", "z": "s"}
    if g.name in flip:
        gates[i] = Gate(flip[g.name], g.qubits, cond=g.cond)
    elif g.name == "cx":
        gates[i] = Gate("cx", g.qubits[::-1], cond=g.cond)
    elif g.name == "rz":
        gates[i] = Gate("rz", g.qubits, theta=g.theta + 0.5)
    elif g.cond is not None:
        gates[i] = Gate(g.name, g.qubits, theta=g.theta)          # drop the classical condition
    else:
        del gates[i]


def make_case(seed):
    rng = np.random.default_rng(seed)
    if rng.random() < 0.25:
        old, new, req, zinit = ladder_case(rng)
    else:
        n = int(rng.integers(3, 6))
        old = Circuit(n, [rand_gate(rng, list(range(n))) for _ in range(rng.integers(4, 14))])
        new, state, reqs = old.copy(), {"eps": 0.0}, []
        for _ in range(rng.integers(1, 4)):
            reqs.append(correct_rewrite(rng, old, new, state))
        req = Req(eps=state["eps"] * (1.0 if any(r.eps for r in reqs) else 0.0),
                  ancillas=new.n - old.n, measure=any(r.measure for r in reqs))
        zinit = ()
    if rng.random() < 0.4:
        mutate(rng, new)
    return old, new, req, zinit


N_CASES = 3000


def test_verifier_agrees_with_naive_reference():
    false_accepts, false_rejects, refused, accepted = [], [], 0, 0
    for seed in range(N_CASES):
        old, new, req, zinit = make_case(seed)
        v = check(old, new, req, zero_init=zinit)
        ref = reference(old, new, req, zinit)
        if v.mode == "refused" and ref:
            refused += 1
        if v.ok and not ref:
            false_accepts.append((seed, v))
        elif ref and not v.ok and v.mode != "refused":
            false_rejects.append((seed, v))
        accepted += v.ok
    assert not false_accepts, f"FALSE ACCEPTS (unsound): {false_accepts[:5]}"
    assert not false_rejects, f"false rejects: {len(false_rejects)}, e.g. {false_rejects[:5]}"
    assert refused == 0, f"{refused} valid cases refused"
    assert 0.3 * N_CASES < accepted < 0.9 * N_CASES          # the generator exercises both outcomes
