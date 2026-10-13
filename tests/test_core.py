"""P0 tests: exact ring, IR expansions, simulators, pyzx cross-checks."""
import numpy as np
import pytest

from circuitevolve.baselines import cuccaro, pyzx_opt
from circuitevolve.cost import cost, t_count
from circuitevolve.ir import Circuit, to_qasm3
from circuitevolve.ring import D, INV_SQRT2, ONE
from circuitevolve.sim import bits_to_ints, run, run_classical, unitary
from circuitevolve.spec import AdderSpec


def _eq_up_to_phase(U, V):
    i = np.unravel_index(np.argmax(abs(V)), V.shape)
    ph = U[i] / V[i]
    return abs(abs(ph) - 1) < 1e-12 and np.allclose(U, ph * V, atol=1e-12)


def _big_endian(M, nq):
    perm = [int(format(i, f"0{nq}b")[::-1], 2) for i in range(1 << nq)]
    return M[np.ix_(perm, perm)]


# ring ---------------------------------------------------------------------------------------
def test_ring_identities():
    assert D.omega_pow(8) == ONE
    assert D.omega_pow(4) == -ONE
    assert INV_SQRT2 * INV_SQRT2 + INV_SQRT2 * INV_SQRT2 == ONE
    w = D.omega_pow(1)
    assert w * w.conj() == ONE
    sqrt2 = D((0, 1, 0, -1))
    assert sqrt2 * INV_SQRT2 == ONE          # canonical form reduces k
    assert (INV_SQRT2 - INV_SQRT2).is_zero()


# expansions ---------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["ccx", "ccz"])
def test_native_expansion_exact(name):
    c = Circuit(3).add(name, 0, 1, 2)
    e = c.expand("clifford_t")
    assert _eq_up_to_phase(unitary(e), unitary(c))
    assert t_count(c) == 7


def test_and_compute_on_clean_target():
    c = Circuit(3).add("and_compute", 0, 1, 2)
    amps = set()
    for x in range(4):  # t = 0 inputs only
        (st,) = run(c, x).values()
        assert list(st) == [x | (4 if x == 3 else 0)]
        amps.add(st[next(iter(st))])
    assert len(amps) == 1                     # same phase on every input
    assert t_count(c) == 4


def test_and_uncompute_restores_clean_ancilla():
    c = Circuit(3).add("and_compute", 0, 1, 2).add("and_uncompute", 0, 1, 2)
    assert t_count(c) == 4
    for outcome in [(0,), (1,)]:
        amps = set()
        for x in range(4):
            br = run(c, x, outcome)
            (st,) = br.values()
            assert list(st) == [x]
            amps.add(st[x])
        assert len(amps) == 1


def test_qasm_export_mentions_measure_and_condition():
    c = Circuit(3).add("and_compute", 0, 1, 2).add("and_uncompute", 0, 1, 2)
    q = to_qasm3(c)
    assert "measure" in q and "if (c[0])" in q


# simulators vs pyzx -------------------------------------------------------------------------
@pytest.mark.parametrize("n", [1, 2, 3])
def test_cuccaro_matches_pyzx_tensor(n):
    c = cuccaro.construct(n)
    zm = pyzx_opt.to_pyzx(c).to_matrix()
    assert np.allclose(unitary(c), _big_endian(zm, c.n_qubits))


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_classical_agrees_with_sparse_and_adds(n):
    c = cuccaro.construct(n)
    pairs = AdderSpec().inputs(c, n)
    cl = bits_to_ints(run_classical(c, [x for x, _ in pairs]))
    sp = [next(iter(run(c, x)[()])) for x, _ in pairs]
    assert cl == sp == [y for _, y in pairs]


@pytest.mark.parametrize("n", [1, 2, 3])
def test_pyzx_baseline_equivalent_and_8n(n):
    c = cuccaro.construct(n)
    o = pyzx_opt.optimize(c)
    assert _eq_up_to_phase(unitary(o), unitary(c))
    assert cost(c)["t_count"] == 14 * n and cost(o)["t_count"] == 8 * n
