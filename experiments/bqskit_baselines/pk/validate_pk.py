"""Correctness gate for the DPF-PK pipeline (upstream's own tests are stale: test_pkac.py calls
ConvertToPKAC(ks=[K]) but the installed signature is (max_k, add_measurements, use_catalyzed_sqrt_t),
so they TypeError before reaching an assertion, independently of the localhost-socket block).

Check: the PKAC-form circuit V on n + a qubits must satisfy, for random |psi> on the n system qubits,
    V (|psi> (x) |0..0>) = e^{i phi} (U|psi>) (x) |0..0>
with the SAME phi for every |psi> (ancillas returned clean, no relative-phase corruption).
BQSKit orders qubit 0 as MSB, so ancillas occupy the low a bits and the clean subspace is
index = x << a.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dpf_pk  # noqa: E402  (installs shims)


def check(circ, error: float, max_k: int, n_probe: int = 4, seed: int = 7, cat_sqrt_t: bool = True):
    from bqskit.qis.unitary.unitarymatrix import UnitaryMatrix
    compiler = dpf_pk.serial_compiler()
    n = circ.num_qudits
    U = circ.get_unitary().numpy
    out, info = dpf_pk.dpf_pk_compile(circ.copy(), compiler, error=error, max_k=max_k,
                                     use_catalyzed_sqrt_t=cat_sqrt_t)
    a = out.num_qudits - n
    res = dict(info=info, n=n, ancillas=a, gates=dpf_pk.gate_histogram(out))
    try:
        V = out.get_unitary().numpy
    except Exception as e:
        res.update(ok=None, reason=f'no unitary: {type(e).__name__}: {e}')
        return res
    rng = np.random.default_rng(seed)
    phis, errs, leaks = [], [], []
    for _ in range(n_probe):
        psi = rng.normal(size=2 ** n) + 1j * rng.normal(size=2 ** n)
        psi /= np.linalg.norm(psi)
        full = np.zeros(2 ** out.num_qudits, dtype=complex)
        full[np.arange(2 ** n) << a] = psi            # |psi> (x) |0..0>
        o = V @ full
        clean = o[np.arange(2 ** n) << a]             # amplitudes with ancillas = 0
        leaks.append(float(np.sqrt(max(0.0, 1.0 - np.vdot(clean, clean).real))))
        tgt = U @ psi
        ov = np.vdot(tgt, clean)
        phis.append(np.angle(ov))
        errs.append(float(np.linalg.norm(clean - np.exp(1j * np.angle(ov)) * tgt)))
    res.update(ok=bool(max(errs) < 1e-6 and max(leaks) < 1e-6),
               max_state_err=max(errs), max_ancilla_leak=max(leaks),
               phase_spread=float(np.ptp(np.unwrap(phis))))
    return res


def small_dyadic(n_q: int, ks: list[int]):
    """H on every qubit, a CNOT ladder, then one Rz(2pi * 1 / 2^k) per k - exactly dyadic."""
    from bqskit.ir.circuit import Circuit
    from bqskit.ir.gates import CNOTGate, HGate, RZGate
    c = Circuit(n_q)
    for q in range(n_q):
        c.append_gate(HGate(), [q])
    for q in range(n_q - 1):
        c.append_gate(CNOTGate(), [q, q + 1])
    for i, k in enumerate(ks):
        c.append_gate(RZGate(), [i % n_q], [2 * np.pi / (2 ** k)])
    return c


if __name__ == '__main__':
    import json
    cases = [
        ('2q k=[3]',     small_dyadic(2, [3]),        3),
        ('2q k=[4]',     small_dyadic(2, [4]),        4),
        ('2q k=[4,4]',   small_dyadic(2, [4, 4]),     4),
        ('3q k=[5]',     small_dyadic(3, [5]),        5),
        ('3q k=[4,5]',   small_dyadic(3, [4, 5]),     5),
    ]
    for name, c, K in cases:
        try:
            r = check(c, error=1e-3, max_k=K)
            print(f'{name:12s} K={K}  ok={r.get("ok")}  anc={r.get("ancillas")}  '
                  f'err={r.get("max_state_err")}  leak={r.get("max_ancilla_leak")}  '
                  f'phase_spread={r.get("phase_spread")}  {r.get("reason","")}', flush=True)
            print(f'              gates={r["gates"]}', flush=True)
        except Exception as e:
            import traceback
            print(f'{name:12s} K={K}  EXC {type(e).__name__}: {e}', flush=True)
            print(traceback.format_exc()[-800:], flush=True)


def check_ntro(circ, error: float, max_k: int, seed: int = 7):
    """Validate ONLY steps 2-5 (CliffordRZ retarget + partition + GreedyNTRO), i.e. the angle-fixing
    stage, which must stay unitary. PKAC lowering (step 6) is measurement-based by construction and
    cannot be checked this way: LogicalAndDgGate is the measured temporary-AND uncompute."""
    import numpy as np
    from bqskit.compiler.compile import compile as bq_compile
    from bqskit.ft.cliffordrz.cliffordrzmodel import CliffordRZModel
    from bqskit.ft.ftpasses.greedy_ntro import GreedyNTROPass
    from bqskit.ft.gates.fractional_rz import FractionalRZGate
    from bqskit.passes.control.foreach import ForEachBlockPass
    from bqskit.passes.util.unfold import UnfoldPass

    compiler = dpf_pk.serial_compiler()
    U = circ.get_unitary().numpy
    eps_pg = error / (circ.num_params + 1)
    rz = bq_compile(circ.copy(), model=CliffordRZModel(circ.num_qudits, epsilon_per_gate=eps_pg),
                    compiler=compiler)
    part = dpf_pk.partition(rz, compiler, 4)
    nb = part.num_operations
    out = compiler.compile(part, [
        ForEachBlockPass([GreedyNTROPass(max_k=max_k, success_threshold=error / nb)]),
        UnfoldPass()])
    V = out.get_unitary().numpy
    N = U.shape[0]
    x = abs(np.trace(U.conj().T @ V)) / N
    frac = {}
    for op in out.operations():
        if isinstance(op.gate, FractionalRZGate):
            frac[op.gate.k] = frac.get(op.gate.k, 0) + 1
    from bqskit.ir.gates import RZGate
    return dict(num_blocks=nb, block_threshold=error / nb,
                hs_cost=float(1 - x), hs_dist=float(np.sqrt(max(0.0, 1 - x * x))),
                op_dist=float(np.linalg.norm(V - np.exp(-1j * np.angle(np.trace(U.conj().T @ V))) * U, 2)),
                fractional_rz_by_k={int(k): int(v) for k, v in sorted(frac.items())},
                residual_rz=out.count(RZGate()), gates=dpf_pk.gate_histogram(out))
