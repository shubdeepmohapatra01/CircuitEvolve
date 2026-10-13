"""Tests for the shared block infrastructure (circuitevolve/blocks/): import, best-classical input, partition,
passes, cost model, reassembly. Dev circuits only (no evaluation circuits). The v1 rule library / proposer /
pipeline tests are in tests/legacy/test_legacy_blocks_v1.py."""
import math

import numpy as np
import pytest

from circuitevolve.blocks import verify_block as vb
from circuitevolve.blocks.circuit_io import bench_path, classify_angle
from circuitevolve.blocks.cost_model import Gridsynth, ops_cost
from circuitevolve.blocks.partition import group, make_block, partition, reassemble
from circuitevolve.blocks.passes import classical_pass, phase_fold, resynth_1q



@pytest.fixture(scope="module")
def gs(tmp_path_factory):
    # shared on-disk cache so repeated test runs do not re-run gridsynth
    return Gridsynth()


@pytest.fixture(scope="module")
def qft4(gs):
    from circuitevolve.blocks.classical import best_classical
    return best_classical("qft_4", gs)


def test_eval_circuits_refused():
    for nm in ("add_17", "add_9", "hhl_6", "mult_16", "qft_32", "shor_16", "qft/qft_32"):
        with pytest.raises(PermissionError):
            bench_path(nm)
    assert bench_path("qft_5").exists() and bench_path("hhl_8").exists()


def test_best_classical_qft4(qft4):
    c = qft4["candidates"]
    assert qft4["best"] in ("pyzx", "tket")
    for k in ("minrz", "pyzx", "tket"):
        assert c[k]["check"]["dist"] < 1e-9, k
    b = c[qft4["best"]]["cost"]
    assert b["t"] <= min(c["pyzx"]["cost"]["t"], c["tket"]["cost"]["t"])
    assert set(g for g, _, _ in c[qft4["best"]]["ops"]) <= {"h", "x", "z", "s", "sdg", "t", "tdg", "cx", "cz", "rz"}


@pytest.mark.parametrize("bs", [2, 3])
def test_partition_reassembles_exactly(qft4, bs):
    ops = qft4["candidates"][qft4["best"]]["ops"]
    n = qft4["n"]
    bl = partition(ops, n, block_size=bs, max_gates=5)
    assert all(len(b.ops) <= 5 and b.n <= bs for b in bl)
    assert vb.circuit_check(ops, reassemble(bl), n)["dist"] < 1e-13
    assert sorted(g for b in bl for g, _, _ in b.ops) == sorted(g for g, _, _ in ops)


def test_structure_signature_abstracts_angles():
    a = make_block(0, [("rz", (3,), 0.1), ("cx", (3, 5), None), ("rz", (5,), 0.2)])
    b = make_block(1, [("rz", (0,), -0.7), ("cx", (0, 1), None), ("rz", (1,), 1.3)])
    c = make_block(2, [("rz", (0,), -0.7), ("cx", (1, 0), None), ("rz", (1,), 1.3)])
    assert a.sig == b.sig != c.sig
    assert a.angles == [0.1, 0.2] and a.qubits == (3, 5)
    assert len(group([a, b, c])) == 2


def _random_ops(rng, n, m):
    gates = ["h", "s", "sdg", "t", "tdg", "x", "z", "rz", "rz", "rz", "cx", "cx", "cz"]
    ops = []
    for _ in range(m):
        g = gates[rng.integers(len(gates))]
        if g in ("cx", "cz"):
            a, b = rng.choice(n, 2, replace=False)
            ops.append((g, (int(a), int(b)), None))
        else:
            ops.append((g, (int(rng.integers(n)),), float(rng.normal()) if g == "rz" else None))
    return ops


def test_phase_fold_and_resynth_exact_on_random_blocks():
    rng = np.random.default_rng(0)
    for _ in range(40):
        n = int(rng.integers(2, 4))
        ops = _random_ops(rng, n, int(rng.integers(1, 30)))
        for f in (phase_fold, resynth_1q, classical_pass):
            new = f(ops, n)
            assert vb.verify_instance(ops, new, n)["ok"], (f.__name__, ops)


def test_phase_fold_merges_through_cnots():
    ops = [("rz", (1,), 0.3), ("cx", (0, 1), None), ("rz", (1,), 0.2), ("cx", (0, 1), None),
           ("rz", (1,), 0.5), ("x", (1,), None), ("rz", (1,), 0.1)]
    new = phase_fold(ops, 2)
    assert sum(g == "rz" for g, _, _ in new) == 2
    assert vb.verify_instance(ops, new, 2)["ok"]
    # pi/4 merge becomes a T gate; H blocks merging
    ops2 = [("rz", (0,), 0.1), ("t", (0,), None), ("rz", (0,), math.pi / 4 - 0.1)]
    assert [g for g, _, _ in phase_fold(ops2, 1)] == ["s"]
    ops3 = [("rz", (0,), 0.1), ("h", (0,), None), ("rz", (0,), 0.2)]
    assert sum(g == "rz" for g, _, _ in phase_fold(ops3, 1)) == 2


def test_cost_model_counts(gs):
    ops = [("t", (0,), None), ("tdg", (1,), None), ("rz", (0,), 3 * math.pi / 4), ("rz", (0,), 0.3),
           ("cx", (0, 1), None)]
    c = ops_cost(ops, gs)
    assert c["t_fixed"] == 3 and c["rz"] == 1 and c["cx"] == 1
    assert 60 < c["t_gs"] < 130 and c["t_gs"] == gs.t(0.3)
    assert gs.data[repr(0.3)][2] <= 1e-9


def _blk(i, a, b, c):
    return make_block(i, [("rz", (0,), a), ("cx", (0, 1), None), ("rz", (1,), b), ("cx", (0, 1), None),
                          ("rz", (0,), c), ("h", (1,), None)])


def test_improves_rejects_gridsynth_angle_noise_and_mod_2pi(gs):
    from circuitevolve.blocks.cost_model import canonicalize, improves
    base = dict(t=190, t_fixed=0, rz=2, cx=2, gates=6)
    assert not improves(dict(base, t=186), base)                       # same rz, cheaper angles only
    assert improves(dict(base, t=95, rz=1), base)
    assert not improves(dict(base, t=200, rz=1), base)                 # fewer rz but more T
    assert improves(dict(base, cx=1, gates=5), base)
    assert not improves(dict(base), base)
    ops = [("rz", (0,), 11.0105), ("cx", (0, 1), None)]
    can = canonicalize(ops)
    assert -math.pi <= can[0][2] <= math.pi and vb.verify_instance(ops, can, 2)["ok"]
    assert ops_cost(ops, gs)["t"] == ops_cost(can, gs)["t"]            # canonical counting is mod-2pi invariant
