"""Compute (and verify) every worked-example number quoted in docs/v2/cards/. Writes
results/v2/cards_worked_examples.json (refuses to overwrite).

    .venv/bin/python experiments/v2_bench_cards_check.py
"""
from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_bench_common import ROOT, check, counts, expand, pyzx_arm  # noqa: E402

import numpy as np  # noqa: E402

from circuitevolve.blocks import verify_block as vb  # noqa: E402
from circuitevolve.ir import _AND_COMPUTE, _CCX  # noqa: E402

OUT = os.path.join(ROOT, "results", "v2", "cards_worked_examples.json")


def U(ops, n):
    return vb.unitary(expand(ops), n)


def mat_ccx():
    return U([("ccx", (0, 1, 2), None)], 3)


def ops_from(seq, qmap=(0, 1, 2)):
    return [(g[0], tuple(qmap[i] for i in g[1:]), None) for g in seq]


def qiskit_ops(gate, n):
    from qiskit import QuantumCircuit, transpile
    qc = QuantumCircuit(n)
    qc.append(gate, list(range(n)))
    t = transpile(qc, basis_gates=["h", "t", "tdg", "s", "sdg", "cx", "x", "z"], optimization_level=0)
    out = []
    for ins in t.data:
        out.append((ins.operation.name, tuple(t.find_bit(q).index for q in ins.qubits), None))
    return out


def diag_relative(A, B):
    """True if A = D B with D diagonal unitary (relative phase)."""
    M = A @ B.conj().T
    return bool(np.allclose(M, np.diag(np.diag(M)), atol=1e-10))


def main():
    if os.path.exists(OUT):
        sys.exit(f"{OUT} exists")
    R = {}
    # standard 7-T Toffoli (frozen ir.py table)
    std = ops_from(_CCX)
    R["toffoli_7T"] = dict(t=counts(std)["t"], cx=counts(std)["cx"],
                           dist_vs_ccx=vb.distance(U(std, 3), mat_ccx())["op"])
    # relative-phase Toffoli (qiskit RCCX = Margolus-type) and RC3X
    from qiskit.circuit.library import RC3XGate, RCCXGate
    rccx = qiskit_ops(RCCXGate(), 3)
    R["rccx"] = dict(t=counts(rccx)["t"], cx=counts(rccx)["cx"],
                     equals_ccx_up_to_diagonal=diag_relative(U(rccx, 3), mat_ccx()),
                     dist_vs_ccx=vb.distance(U(rccx, 3), mat_ccx())["op"])
    rc3x = qiskit_ops(RC3XGate(), 4)
    from qiskit.circuit.library import C3XGate
    c3 = qiskit_ops(C3XGate(), 4)
    R["rc3x"] = dict(t=counts(rc3x)["t"], cx=counts(rc3x)["cx"],
                     equals_c3x_up_to_diagonal=diag_relative(U(rc3x, 4), U(c3, 4)))
    R["qiskit_c3x_default"] = dict(t=counts(c3)["t"], cx=counts(c3)["cx"], rz_other=counts(c3)["rz_other"])
    # compute / uncompute pair of RCCX around a CX equals the exact sequence ccx . cx . ccx
    pair = rccx + [("cx", (2, 3), None)] + [(g, q, a) for g, q, a in reversed(_inverse(rccx))]
    ref = [("ccx", (0, 1, 2), None), ("cx", (2, 3), None), ("ccx", (0, 1, 2), None)]
    R["rccx_pair_around_cx"] = dict(t=counts(pair)["t"], t_exact_version=7 * 2,
                                    dist=vb.distance(U(pair, 4), U(ref, 4))["op"])
    # Gidney temporary AND / Jones: compute with 4 T, uncompute by X-measurement + CZ fix-up
    andc = ops_from(_AND_COMPUTE)
    Ua = U(andc, 3)
    ok = True
    for a in (0, 1):
        for b in (0, 1):
            e = np.zeros(8, complex)
            e[(a << 2) | (b << 1)] = 1   # qubit 0 = MSB, target qubit 2 starts in |0>
            out = Ua @ e
            k = int(np.argmax(abs(out)))
            ok &= bool(abs(abs(out[k]) - 1) < 1e-12 and k == ((a << 2) | (b << 1) | (a & b)))
    # uncompute: H on target, measure m; if m = 1 apply CZ(a, b); phases must be independent of (a, b)
    psi = np.random.default_rng(1).normal(size=4) + 1j * np.random.default_rng(2).normal(size=4)
    psi /= np.linalg.norm(psi)
    st = np.zeros(8, complex)
    for a in (0, 1):
        for b in (0, 1):
            st[(a << 2) | (b << 1) | (a & b)] = psi[2 * a + b]
    st = U([("h", (2,), None)], 3) @ st
    branch_ok = []
    for m in (0, 1):
        proj = np.array([st[(a << 2) | (b << 1) | m] for a in (0, 1) for b in (0, 1)])
        if m == 1:
            proj = proj * np.array([1, 1, 1, -1])
        c = proj / psi
        branch_ok.append(bool(np.allclose(c, c[0], atol=1e-12)) and abs(abs(c[0]) ** 2 - 0.5) < 1e-12)
    R["temporary_and"] = dict(t_compute=counts(andc)["t"], computes_ab_on_basis=ok, t_uncompute=0,
                              uncompute_branches_phase_consistent=branch_ok)
    # Jones Toffoli: AND into ancilla (4 T), CX ancilla -> target, measurement uncompute
    R["jones_toffoli"] = dict(t=4, ancilla=1, measurements=1, derived_from="temporary_and above")
    # Selinger T-depth-1 CCZ with 4 ancillas (phase polynomial on 7 parities)
    par = [(0,), (1,), (2,), (0, 1), (0, 2), (1, 2), (0, 1, 2)]
    sign = [+1, +1, +1, -1, -1, -1, +1]
    wires = [0, 1, 2, 3, 4, 5, 6]  # parity j lives on wire j (3 inputs + 4 ancillas)
    comp = []
    for j in range(3, 7):
        for q in par[j]:
            comp.append(("cx", (q, wires[j]), None))
    layer = [("t" if s > 0 else "tdg", (wires[j],), None) for j, s in enumerate(sign)]
    sel = comp + layer + list(reversed(comp))
    Us = U(sel, 7)
    Uz = U([("ccz", (0, 1, 2), None)], 7)
    idx = [x << 4 for x in range(8)]  # ancillas (qubits 3..6, least significant) in |0>
    sub = Us[np.ix_(idx, idx)]
    subz = Uz[np.ix_(idx, idx)]
    leak = float(np.linalg.norm(Us[:, idx]) ** 2 - np.linalg.norm(sub) ** 2)
    R["selinger_tdepth1_ccz"] = dict(t=counts(sel)["t"], t_depth=1, ancillas=4, cx=counts(sel)["cx"],
                                     dist_on_clean_ancilla_subspace=vb.distance(sub, subz)["op"],
                                     ancilla_leakage=leak)
    # phase folding: two T on the same parity x0^x1, computed on different wires -> one S (Clifford)
    pf = [("cx", (0, 1), None), ("t", (1,), None), ("cx", (0, 1), None),
          ("cx", (1, 0), None), ("t", (0,), None), ("cx", (1, 0), None)]
    p = pyzx_arm(pf, 2)
    R["phase_folding_parity"] = dict(t_before=counts(pf)["t"], t_after_pyzx=counts(p["ops"])["t"],
                                     verify=check(pf, p["ops"], 2))
    # approximate QFT on n = 8: drop controlled phases with angle < 2 pi / 2^(m+1) (keep |j-k| < m)
    n = 8
    R["aqft_n8"] = {}
    full = None
    for m in list(range(1, n)) + [n]:
        Uq = _qft(n, m)
        if m == n:
            full = Uq
        R["aqft_n8"][m] = dict(kept_cphases=sum(min(m - 1, n - 1 - i) for i in range(n)), U=Uq)
    for m, d in R["aqft_n8"].items():
        d["op_dist_vs_qft"] = vb.distance(d.pop("U"), full)["op"]
    # gridsynth T-count for a dyadic and a near-dyadic angle (pygridsynth via the project's cached wrapper)
    from circuitevolve.blocks.cost_model import Gridsynth
    gs = Gridsynth(eps=1e-3 / 4)
    gs.ensure([math.pi / 8, math.pi / 16, 0.39])
    R["gridsynth_eps_2.5e-4"] = {"pi/8": gs.t(math.pi / 8), "pi/16": gs.t(math.pi / 16), "0.39": gs.t(0.39)}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(R, open(OUT, "w"), indent=1, default=float)
    print(json.dumps(R, indent=1, default=float))


def _inverse(ops):
    inv = {"t": "tdg", "tdg": "t", "s": "sdg", "sdg": "s"}
    return [(inv.get(g, g), q, a) for g, q, a in ops]


def _qft(n, m):
    """QFT (no final swaps) keeping controlled phases R_k (angle 2 pi / 2^k) with k <= m; m = n is exact."""
    ops = []
    for i in range(n):
        ops.append(("h", (i,), None))
        for j in range(i + 1, n):
            k = j - i + 1
            if k <= m:
                th = 2 * math.pi / 2 ** k
                # controlled phase(th) on (j, i) = rz(th/2) on both, cx, rz(-th/2), cx (up to global phase)
                ops += [("rz", (i,), th / 2), ("cx", (j, i), None), ("rz", (i,), -th / 2), ("cx", (j, i), None),
                        ("rz", (j,), th / 2)]
    return vb.unitary(ops, n)


if __name__ == "__main__":
    main()
