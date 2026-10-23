"""Candidate rule: re-bill a maximal single-wire run (>= 2 non-pi/4 rz) as ONE SU(2) element emitted as an
explicit Clifford+T word (grid search over Z[omega] + Giles-Selinger/KMM exact synthesis)."""
import math

import numpy as np

from v3.api import Rule
from v3.api import dv

DELTA = 1e-6
C_RZ = 35
MAX_RUNS_TRIED = 30
MAX_ACCEPT = 300
U_SAMPLES = 150
T_SAMPLES = 150
RUN_GATES = ("h", "s", "sdg", "x", "z", "t", "tdg", "rz")
_W = np.exp(1j * np.pi / 4)
_MATS = {"h": np.array([[1, 1], [1, -1]]) / math.sqrt(2), "s": np.diag([1, 1j]), "sdg": np.diag([1, -1j]),
         "x": np.array([[0, 1], [1, 0]], dtype=complex), "z": np.diag([1, -1]).astype(complex),
         "t": np.diag([1, _W]), "tdg": np.diag([1, np.conj(_W)])}


# ---- Z[omega] elements as 4-tuples (a, b, c, d) = a + b w + c w^2 + d w^3 -------------------------------------
def _add(x, y):
    return tuple(i + j for i, j in zip(x, y))


def _sub(x, y):
    return tuple(i - j for i, j in zip(x, y))


def _mulw(x, j):
    a, b, c, d = x
    for _ in range(j % 8):
        a, b, c, d = -d, a, b, c
    return (a, b, c, d)


def _conj(x):
    a, b, c, d = x
    return (a, -d, -c, -b)


def _val(x):
    return x[0] + x[1] * _W + x[2] * _W ** 2 + x[3] * _W ** 3


def _norm_parts(x):
    a, b, c, d = x
    return a * a + b * b + c * c + d * d, a * b + b * c + c * d - d * a      # |x|^2 = A + B sqrt2


def _run_matrix(ops):
    U = np.eye(2, dtype=complex)
    for g, _, ang in ops:
        M = np.diag([1, np.exp(1j * float(ang))]) if g == "rz" else _MATS[g]
        U = M @ U
    return U


def _is_grid(theta):
    r = theta / (math.pi / 4)
    return abs(r - round(r)) < 1e-9


# ---- (3a) approximate: find (u, t) near the target column -------------------------------------------------------
def _search_vt(U, k):
    """V = [[u,-t*],[t,u*]]/sqrt2^k within DELTA of U (SU(2)); returns (u, t) or None. Bounded enumeration."""
    s = math.sqrt(2.0) ** k
    r = DELTA * s
    tu, tt = s * U[0, 0], s * U[1, 0]
    two_k = 1 << k
    inv = 1 / math.sqrt(2.0)

    def near(target, count):
        out = []
        for idx in range(count):
            p = (idx // 2) * (1 if idx % 2 == 0 else -1)
            for q in (p, p + 2):
                if (p - q) % 2:
                    continue
                b, d = (p + q) // 2, (q - p) // 2
                a = round(target.real - p * inv)
                c = round(target.imag - q * inv)
                e = (a, b, c, d)
                if abs(_val(e) - target) <= r:
                    out.append(e)
        return out

    for u in near(tu, U_SAMPLES):
        Au, Bu = _norm_parts(u)
        S, Bt = two_k - Au, -Bu
        if S < 0:
            continue
        for t in near(tt, T_SAMPLES):
            At, Bt2 = _norm_parts(t)
            if At == S and Bt2 == Bt:
                V = np.array([[_val(u), -np.conj(_val(t))], [_val(t), np.conj(_val(u))]]) / s
                if min(np.linalg.norm(U - V, 2), np.linalg.norm(U + V, 2)) <= DELTA:
                    return u, t
    return None


# ---- (3b) exact synthesis (denominator reduction) ----------------------------------------------------------------
def _t_word(p):
    p %= 8
    return [(), ("t",), ("s",), ("s", "t"), ("z",), ("z", "t"), ("sdg",), ("tdg",)][p]


def _exact_word(u, t, k):
    M = [[u, _neg(_conj(t))], [t, _conj(u)]]      # numerators over sqrt2^k, rows x columns
    steps = []
    guard = 0
    while k > 0:
        guard += 1
        if guard > 400:
            return None
        for j in range(4):
            new = [[None, None], [None, None]]
            for col in range(2):
                r1 = _mulw(M[1][col], j)
                new[0][col] = _add(M[0][col], r1)
                new[1][col] = _sub(M[0][col], r1)
            if all(all(c % 2 == 0 for c in e) for row in new for e in row):
                M = [[tuple(c // 2 for c in e) for e in row] for row in new]
                steps.append(j)
                k -= 1
                break
        else:
            return None
    # k == 0: M monomial with entries +-w^m
    def expo(e):
        nz = [(i, c) for i, c in enumerate(e) if c]
        if len(nz) != 1 or abs(nz[0][1]) != 1:
            return None
        return nz[0][0] + (4 if nz[0][1] < 0 else 0)

    ex = [[expo(M[i][j]) if any(M[i][j]) else None for j in range(2)] for i in range(2)]
    word = []
    if ex[0][0] is not None and ex[1][1] is not None and ex[0][1] is None and ex[1][0] is None:
        word += list(_t_word(ex[1][1] - ex[0][0]))
    elif ex[0][1] is not None and ex[1][0] is not None and ex[0][0] is None and ex[1][1] is None:
        word += ["x"] + list(_t_word(ex[1][0] - ex[0][1]))     # [[0,w^a],[w^b,0]] = diag(w^a,w^b) X    else:
        return None
    for j in reversed(steps):
        word += ["h"] + list(_t_word(-j))
    return word


def _neg(e):
    return tuple(-c for c in e)


def _word_unitary(word):
    U = np.eye(2, dtype=complex)
    for g in word:
        U = _MATS[g] @ U
    return U


def _phase_dist(A, B):
    ph = np.trace(B.conj().T @ A)
    if abs(ph) < 1e-12:
        return 2.0
    return float(np.linalg.norm(A - B * (ph / abs(ph)), 2))


def _synthesise(U):
    """gate-name word W (h s sdg x z t tdg) within DELTA of the SU(2) matrix U, or None."""
    for k in (math.ceil(3 * math.log2(1 / DELTA)), math.ceil(3 * math.log2(1 / DELTA)) + 1):
        hit = _search_vt(U, k)
        if hit is None:
            continue
        word = _exact_word(hit[0], hit[1], k)
        if word is None:
            continue
        if _phase_dist(_word_unitary(word), U) <= DELTA * 1.0001:
            return tuple(word)
    return None


# ---- rule ---------------------------------------------------------------------------------------------------------
def find_matches(c):
    if not dv.is_angle_circuit(c):
        return []
    ops = c.ops
    runs = []
    for q in range(c.n):
        cur = []
        for i, op in enumerate(ops):
            g, qs, _ = op
            if q not in qs:
                continue
            if len(qs) == 1 and g in RUN_GATES:
                cur.append(i)
            else:
                if cur:
                    runs.append((q, tuple(cur)))
                cur = []
        if cur:
            runs.append((q, tuple(cur)))
    cand = []
    for q, idxs in runs:
        nrz = sum(1 for i in idxs if ops[i][0] == "rz" and not _is_grid(ops[i][2]))
        nt = sum(1 for i in idxs if ops[i][0] in ("t", "tdg"))
        if nrz >= 2:
            cand.append((-(C_RZ * nrz + nt), q, idxs, nrz, nt))
    cand.sort(key=lambda x: (x[0], x[1], x[2]))
    out = []
    for neg, q, idxs, nrz, nt in cand[:MAX_RUNS_TRIED]:
        U = _run_matrix([ops[i] for i in idxs])
        det = np.linalg.det(U)
        U = U / np.sqrt(det)
        W = _synthesise(U)
        if W is None:
            continue
        tw = sum(1 for g in W if g in ("t", "tdg"))
        if tw + 2 <= C_RZ * nrz + nt:
            out.append((q, idxs, W, tuple(ops[i] for i in idxs)))
        if len(out) >= MAX_ACCEPT:
            break
    return out


def apply_match(c, m):
    q, idxs, W, sig = m
    ops = c.ops
    if not dv.is_angle_circuit(c) or max(idxs) >= len(ops) or tuple(ops[i] for i in idxs) != sig:
        return c
    drop = set(idxs)
    new = []
    for i, op in enumerate(ops):
        if i == idxs[0]:
            new.extend((g, (q,), None) for g in W)
        if i not in drop:
            new.append(op)
    return dv.with_ops(c, new)


RULE = Rule(
    name="single_qubit_run_unitary_clifford_t_synthesis",
    domain="dv",
    kind="procedure",
    contract="approx",
    source="Ross-Selinger 2016; Kliuchnikov-Maslov-Mosca 2013/2016; Giles-Selinger 2013",
    idea="A maximal single-wire run of h/s/x/z/t/rz ops is one SU(2) element. Approximate it at delta=1e-6 by an "
         "exactly representable [[u,-t*],[t,u*]]/sqrt2^k over Z[omega], read off a literal Clifford+T word by "
         "denominator reduction, and replace the run by it when its T-count beats the per-rotation pricing.",
    trigger=find_matches,
    apply=apply_match,
)
