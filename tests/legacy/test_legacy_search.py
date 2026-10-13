"""P3 tests: slice representation reproduces the baselines; search machinery behaves."""
import random

import pytest

from circuitevolve.ir import TIER_A, TIER_B
from circuitevolve.legacy.adder.evolve import TIERS, Evaluator, map_elites, mutate
from circuitevolve.legacy.adder.slice import CUCCARO, GIDNEY_A, GIDNEY_B, TOFFOLI_CARRY, SliceProgram, build
from circuitevolve.spec import AdderSpec
from circuitevolve.verify import verify


@pytest.mark.parametrize("prog,vocab,slope", [(CUCCARO, TIER_A, 14), (TOFFOLI_CARRY, TIER_A, 14),
                                              (GIDNEY_A, TIER_A, 4), (GIDNEY_B, TIER_B, 4)])
def test_slice_programs_verify_with_expected_slope(prog, vocab, slope):
    r = verify(lambda n: build(prog, n), AdderSpec(), [1, 2, 3, 4, 8], vocab)
    assert r.ok, r.reason
    assert r.costs[8]["t_count"] - r.costs[4]["t_count"] == 4 * slope


def test_mutate_stays_in_vocab():
    rng = random.Random(0)
    p = CUCCARO
    for _ in range(200):
        p = mutate(p, TIERS["A"], rng)
        assert isinstance(p, SliceProgram)
        assert all(g[0] in TIER_A for t in (p.fwd, p.top, p.bwd) for g in t)


def test_evaluator_rejects_and_caches():
    ev = Evaluator("A")
    broken = SliceProgram(CUCCARO.fwd[:-1], CUCCARO.top, CUCCARO.bwd)
    ok, fit, rep = ev(broken)
    assert not ok and fit is None
    ev(broken)
    assert ev.calls == 1


def test_search_improves_toffoli_carry_seed():
    _, traj, stats = map_elites(TOFFOLI_CARRY, "A", budget=600, rng_seed=0)
    assert stats["best"][0] < 14
