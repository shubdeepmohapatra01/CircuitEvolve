"""Acceptance tests for the frozen cvdv_fast judge (run in env cvdv-opt): QuTiP cross-check, Hermiticity at the
truncation edge, planted bugs rejected, exact seeds accepted."""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import qutip as qt
from cvdv_fast import paths, runner  # noqa
from cvdv.qasm import Op
from cvdv import terms
from cvdv_fast.judge.enr import Space
from cvdv_fast.judge import verify as V


def test_norm_preserved_at_edge():
    S = Space([("q", 0)], [("qm", 0), ("qm", 1), ("qm", 2)], 6)
    rng = np.random.default_rng(1)
    psi = rng.normal(size=(S.D, S.Q, 3)) + 1j * rng.normal(size=(S.D, S.Q, 3))
    psi /= np.linalg.norm(psi.reshape(-1, 3), axis=0)
    for op in [Op("BS", (math.pi, 0.3), (("qm", 1), ("qm", 0))), Op("CBS", (1.1, 0.2), (("q", 0), ("qm", 2), ("qm", 0))),
               Op("D", (0.5j,), (("qm", 1),)), Op("CD", (0.4,), (("q", 0), ("qm", 2))), Op("RB", (0.3,), (("q", 0), ("qm", 0)))]:
        psi = S.apply(psi, op)
        assert np.allclose(np.linalg.norm(psi.reshape(-1, 3), axis=0), 1, atol=1e-10), op


def test_qutip_bs():
    N = 12; a = qt.tensor(qt.destroy(N), qt.qeye(N)); b = qt.tensor(qt.qeye(N), qt.destroy(N))
    S = Space([], [("qm", 0), ("qm", 1)], 10)
    v = np.zeros((S.D, 1, 1), complex); v[S.idx[(2, 1)], 0, 0] = 1
    out = S.apply(v, Op("BS", (0.7, 0.3), (("qm", 0), ("qm", 1))))[:, 0, 0]
    U = (-1j * 0.35 * (np.exp(0.3j) * a.dag() * b + np.exp(-0.3j) * a * b.dag())).expm()
    ref = (U * qt.tensor(qt.basis(N, 2), qt.basis(N, 1))).full()[:, 0]
    assert max(abs(out[S.idx[(i, j)]] - ref[i * N + j]) for i in range(4) for j in range(4) if i + j <= 3) < 1e-12


def _hop():
    return terms.Poly({((), ((0, 1, 0), (1, 0, 1))): 0.7, ((), ((0, 0, 1), (1, 1, 0))): 0.7})


def test_exact_accepted_and_planted_rejected():
    H = _hop()  # exp(-i 0.7 (a^+b + b^+a)) = BS(1.4, 0)
    ok = V.window_check(H, [Op("BS", (1.4, 0.0), (("qm", 0), ("qm", 1)))])["dist"]
    bad_angle = V.window_check(H, [Op("BS", (0.7, 0.0), (("qm", 0), ("qm", 1)))])["dist"]
    bad_phase = V.window_check(H, [Op("BS", (1.4, math.pi), (("qm", 0), ("qm", 1)))])["dist"]
    assert ok < 1e-10 and bad_angle > 0.1 and bad_phase > 0.1


def test_planted_dropped_displacement_phase_and_ancilla_garbage():
    # D(a)D(b) merge is exact up to GLOBAL phase -> accepted; CD on an ancilla left displaced -> rejected
    old = [Op("D", (0.3,), (("qm", 0),)), Op("D", (0.2j,), (("qm", 0),))]
    d = V.rewrite_check(old, [Op("D", (0.3 + 0.2j,), (("qm", 0),))]); print("D-merge dist per K", {k: v["dist"] for k, v in d["per_K"].items()}); assert d["dist"] < runner.EXACT_TOL
    assert V.rewrite_check(old, [Op("D", (0.3 - 0.2j,), (("qm", 0),))])["dist"] > 0.1
    Hz = terms.Poly({((( 0, "Z"),), ()): 0.4})
    garb = [Op("rz", (0.8,), (("q", 0),)), Op("CD", (0.5,), (("q", 0), ("qm", 7)))]
    assert V.window_check(Hz, garb)["dist"] > 0.1
    assert V.window_check(Hz, garb[:1])["dist"] < 1e-10


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("PASS", k)
