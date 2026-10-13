"""Self-tests for bygate_exact (run: .venv/bin/python -m pytest -q test_bygate_exact.py)."""
import math, numpy as np
from bygate_exact import decompose_1q, cliffords, rz, H, S, phase_eq

def _prod(seq):
    M = np.eye(2, dtype=complex)
    G = {'h': H, 's': S}
    for kind, v in seq:
        if kind == 'C':
            for g in v: M = G[g] @ M
        else:
            M = rz(v) @ M
    return M

def test_random_unitaries():
    rng = np.random.default_rng(0)
    for _ in range(200):
        X = rng.normal(size=(2, 2)) + 1j * rng.normal(size=(2, 2))
        U, _ = np.linalg.qr(X)
        k, seq = decompose_1q(U)
        assert k == 3 and phase_eq(_prod(seq), U, 1e-8)

def test_structured():
    rng = np.random.default_rng(1)
    C = cliffords()
    for _ in range(300):
        A, B, M = (C[i][1] for i in rng.integers(0, 24, 3))
        a, b = rng.uniform(-3, 3, 2)
        for U, kk in ((B @ A, 0), (B @ rz(a) @ A, 1), (B @ rz(b) @ H @ rz(a) @ A, 2)):
            k, seq = decompose_1q(U)
            assert k <= kk and phase_eq(_prod(seq), U, 1e-8)

def test_small_angles_not_dropped():
    for d in (1e-3, 1e-5, 1e-6, 1e-7, 1e-8):
        U = S @ rz(d) @ H
        k, seq = decompose_1q(U)
        assert k == 1, (d, k)
        assert phase_eq(_prod(seq), U, 1e-12)
