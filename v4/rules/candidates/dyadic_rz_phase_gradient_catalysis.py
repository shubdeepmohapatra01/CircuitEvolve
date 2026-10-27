"""Phase-gradient catalysis: every dyadic rz(k pi / 2^m) becomes a q-controlled constant addition into one
shared phase-gradient register |g> = 2^(-M/2) sum_y e^(-2 pi i y / 2^M) |y>, built from m measurement-uncomputed
AND gadgets (4 m T) instead of a gridsynth word.

Adding c mod 2^M to |g> multiplies it by e^(2 pi i c / 2^M); controlled on q that is diag(1, e^(i theta)) with
theta = 2 pi c / 2^M, i.e. rz(theta) up to a global phase. With c = k 2^(M-m-1) (k odd) the addition touches only
the top m+1 register bits, and the ripple carry needs m AND gadgets (one per bit but the last).

The circuit is returned as an IRCircuit: rz gates (the 2 x (M-3)-ish catalyst preparation / unpreparation
rotations that stay off the pi/4 grid) carry their angle in a `.angle` attribute, the form `v4.judge.kraus`
simulates. That simulator is exponential in width (hard cap 22 qubits, but a 21-qubit check did not finish in
10 minutes), so the deepest level covered is L = (KRAUS_QUBITS - 1 - n) // 2 (n data + (L+1) gradient + L carry
ancillas); 17 qubits and L = 4 on qft_8.
"""
import math

from v4.api import Precondition, Rule
from v4.api import angles, budget, dv

MIN_ROTATIONS = 8
MIN_LEVEL = 3
MAX_LEVEL = 8
KRAUS_QUBITS = 18                               # width the branch simulator can check in reasonable time
DRAW = 0.00015
TOL = 1e-12


def _level_cap(n):
    return min(MAX_LEVEL, (KRAUS_QUBITS - 1 - n) // 2)


def find_matches(c):
    if not dv.is_angle_circuit(c) or c.n < 2 or c.n > 20:
        return []
    cap = _level_cap(c.n)
    if cap < MIN_LEVEL:
        return []
    hits = []                                   # (position, k mod 2^(m+1), m)
    for pos, op in enumerate(c.ops):
        if op[0] != "rz" or dv.on_grid(op[2]):
            continue
        d = angles.nearest(float(op[2]), kmax=cap)
        if abs(d.delta) > TOL or not MIN_LEVEL <= d.m <= cap:
            continue
        hits.append((pos, d.k % (1 << (d.m + 1)), d.m))
    if len(hits) < MIN_ROTATIONS:
        return []
    return [tuple(hits)]


def _emit_rz(out, q, theta):
    """Prep / unprep rotations as Clifford+T when on the grid, else as an angle-carrying rz gate."""
    for g, qs, a in dv.normalize([("rz", (q,), theta)]):
        if g == "rz":
            gate = dv.IRGate("rz", tuple(qs))
            object.__setattr__(gate, "angle", float(a))
            out.gates.append(gate)
        else:
            out.add(g, *qs)


def _const_add(out, q, reg, anc, m, M, k):
    """q-controlled addition of c = k * 2^(M-m-1) into reg (bit i has weight 2^i), carries on anc[:m]."""
    s = M - m - 1
    cbit = lambda i: ((k << s) >> i) & 1
    top = M - 1
    t = {}                                      # carry-out ancilla of bit i
    # forward: carries
    out.add("and_compute", reg[s], q, anc[0])   # bit s: c_s = 1 (k odd), no carry in
    t[s] = anc[0]
    for j, i in enumerate(range(s + 1, top), start=1):
        cin, ti = t[i - 1], anc[j]
        if cbit(i):
            out.add("cx", cin, reg[i])
            out.add("cx", cin, q)
            out.add("and_compute", reg[i], q, ti)
            out.add("cx", cin, ti)
            out.add("cx", cin, q)
        else:
            out.add("and_compute", cin, reg[i], ti)
        t[i] = ti
    # top bit: sum = x ^ carry ^ a
    out.add("cx", t[top - 1], reg[top])
    if cbit(top):
        out.add("cx", q, reg[top])
    # backward: uncompute carries, finalize sum bits
    for i in range(top - 1, s, -1):
        cin, ti = t[i - 1], t[i]
        if cbit(i):
            out.add("cx", cin, ti)
            out.add("cx", cin, q)
            out.add("and_uncompute", reg[i], q, ti)
            out.add("cx", cin, q)
            out.add("cx", q, reg[i])
        else:
            out.add("and_uncompute", cin, reg[i], ti)
            out.add("cx", cin, reg[i])
    out.add("and_uncompute", reg[s], q, t[s])
    out.add("cx", q, reg[s])


def apply_match(c, match):
    if not budget.draw(DRAW):
        return c
    hit = {pos: (kk, m) for pos, kk, m in match}
    M = max(m for _, _, m in match) + 1
    A = max(m for _, _, m in match)
    n = c.n
    reg = list(range(n, n + M))
    anc = list(range(n + M, n + M + A))
    out = dv.IRCircuit(n + M + A, 0, [], {"data": list(range(n))})
    prep = [(reg[j], -2 * math.pi * (1 << j) / (1 << M)) for j in range(M)]
    for q, th in prep:
        out.add("h", q)
        _emit_rz(out, q, th)
    for pos, op in enumerate(c.ops):
        if pos in hit:
            kk, m = hit[pos]
            _const_add(out, op[1][0], reg, anc, m, M, kk)
        elif op[0] == "rz":
            _emit_rz(out, op[1][0], float(op[2]))
        else:
            out.add(op[0], *op[1])
    for q, th in reversed(prep):
        _emit_rz(out, q, -th)
        out.add("h", q)
    return out


RULE = Rule(
    name="dyadic_rz_phase_gradient_catalysis",
    domain="dv",
    kind="resource",
    error_class="approx",
    resource_class="measured",
    source="Kitaev-Shen-Vyalyi 2002; Gidney, Quantum 2, 74 (2018); Gidney-Ekera, Quantum 5, 433 (2021) App. C",
    idea="Every rz(k pi/2^m) becomes a q-controlled constant addition into a shared phase-gradient register, "
         "which is an eigenvector of addition: the phase kicks back onto q. The addition touches m+1 bits and "
         "uses m measurement-uncomputed AND gadgets (4m T); the catalyst's few off-grid prep rotations are "
         "paid once instead of one gridsynth word per rotation.",
    trigger=find_matches,
    apply=apply_match,
    precondition=Precondition(families=("dv_angle",), needs=("nonclifford_rz", "ancilla_room"),
                              min_qubits=2, max_qubits=20,
                              note="needs >= 8 exactly-dyadic off-grid rz"),
)
