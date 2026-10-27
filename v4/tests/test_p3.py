"""P3: the new API primitives, and the re-expressed rules decide exactly what v3's files decided.

The gate (V4_README section 11, P3) is that the v3 rules re-expressed against `v4.api` verify
identically. These tests compare v4's rule files against **v3's actual rule files, loaded and run**, not
against a remembered number: same matches, rotation for rotation, on every angle circuit.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from v4.api import angles as A, blocks as BL, dv, fermion as F, pauli as P, phasepoly as PP, refit as R, \
    sim as S
from v4.judge import dv as J

ANGLE = ("qft_8", "qpe_8", "hhl_8", "qae_13", "tfim_6")
REEXPRESSED = ("pauli_frame_rotation_merge", "pauli_exponential_commutation_merge")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("name", REEXPRESSED)
@pytest.mark.parametrize("label", ANGLE)
def test_reexpressed_rules_match_v3_exactly(name, label):
    """The v4 rule, written on `pauli.frames`, must return the SAME match list as v3's own file."""
    v3 = _load(Path(f"v3/rules/accepted/{name}.py"), f"v3_{name}")
    v4 = _load(Path(f"v4/rules/floor/{name}.py"), f"v4_{name}")
    c = J.load(label)
    assert v4.RULE.trigger(c) == v3.RULE.trigger(c)


@pytest.mark.parametrize("name", REEXPRESSED)
def test_reexpressed_rules_ignore_the_other_family(name):
    v4 = _load(Path(f"v4/rules/floor/{name}.py"), f"v4b_{name}")
    assert v4.RULE.trigger(J.load("adder_6")) == []


# ------------------------------------------------------------------------------------------ primitives
@pytest.mark.parametrize("label", ANGLE)
def test_blocks_partition_round_trips(label):
    c = J.load(label)
    flat = []
    for b in BL.partition(c, 4):
        assert b.k <= 4
        flat += b.to_global(list(b.local_ops))
    assert flat == list(c.ops)


def test_splice_is_a_valid_rewrite():
    c = J.load("qft_8")
    b = BL.partition(c, 4)[3]
    same = BL.splice(list(c.ops), b, list(b.local_ops))
    assert same == list(c.ops)


@pytest.mark.parametrize("label", ANGLE)
def test_phasepoly_witness_accepts_identity_and_rejects_perturbation(label):
    """On every Hadamard-free segment: the witness passes against itself and fails if an angle moves."""
    ops = list(J.load(label).ops)
    seen = 0
    for lo, hi in dv.segments(ops, cut=("h",)):
        seg = ops[lo:hi]
        if not PP.is_hadamard_free(seg):
            continue
        qs = sorted(dv.touched(seg))
        if not qs:
            continue
        loc = {q: i for i, q in enumerate(qs)}
        local = [(g, tuple(loc[q] for q in qq), a) for g, qq, a in seg]
        n = len(qs)
        ok, why = PP.witness(local, local, n)
        assert ok, why
        rots = [i for i, op in enumerate(local) if dv.rotation(op) is not None]
        if rots:
            bad = list(local)
            i = rots[0]
            bad[i] = ("rz", bad[i][1], (dv.rotation(bad[i]) or 0.0) + 0.3)
            assert not PP.witness(local, bad, n)[0]
            seen += 1
    assert seen > 0, f"no Hadamard-free segment with a rotation on {label}"


def test_phasepoly_witness_agrees_with_the_numeric_check():
    """Where the witness applies, it must agree with the judge's numeric distance - and be exact."""
    old = [("cx", (0, 1), None), ("rz", (1,), 0.3), ("rz", (1,), 0.4), ("cx", (0, 1), None)]
    new = [("cx", (0, 1), None), ("rz", (1,), 0.7), ("cx", (0, 1), None)]
    bad = [("cx", (0, 1), None), ("rz", (1,), 0.8), ("cx", (0, 1), None)]
    assert PP.witness(old, new, 2)[0] and S.distance(old, new, 2)["op"] < 1e-12
    assert not PP.witness(old, bad, 2)[0] and S.distance(old, bad, 2)["op"] > 1e-3


def test_phasepoly_witness_declines_outside_its_class():
    assert not PP.witness([("h", (0,), None)], [("h", (0,), None)], 1)[0]


def test_angles_rz_distance_is_what_the_judge_measures():
    """`angles.rz_distance(d)` must equal the judge's phase-aligned distance for a one-rotation window.

    Compared RELATIVELY: the judge's number comes from a numerical operator 2-norm after dividing out
    the aligning phase, so it carries ~1e-8 relative floating-point noise even on a 2x2."""
    for th, d in ((0.3, 1e-3), (1.7, 0.05), (-2.2, 1e-5)):
        got = S.distance([("rz", (0,), th)], [("rz", (0,), th + d)], 1)["op"]
        want = A.rz_distance(d)
        assert abs(got - want) <= 1e-6 * max(want, 1e-12), (th, d, got, want)


def test_angles_dyadic_and_greedy_fix_respect_the_budget():
    d = A.dyadic(0.7853981, 2)
    assert d.m == 2 and abs(d.angle - math.pi / 4) < 1e-12
    out, spent, fixed = A.greedy_fix([0.1, math.pi / 4, 0.7853, 1.23], kmax=6, budget=1e-3)
    assert spent <= 1e-3 and len(fixed) >= 1
    assert all(A.on_grid(a) or not A.on_grid(a) for a in out)


def test_fermion_detects_tfim_and_not_qft():
    """Lever (c): tfim_6 is Gaussian, which is why the project's one large win is there."""
    t = J.load("tfim_6")
    q = J.load("qft_8")
    assert F.is_gaussian(t.ops, t.n)
    assert not F.is_gaussian(q.ops, q.n)


def test_fermion_givens_reconstructs_the_orthogonal_exactly():
    c = J.load("tfim_6")
    Rm = F.orthogonal_of(c.ops, c.n)
    assert np.allclose(Rm @ Rm.T, np.eye(Rm.shape[0]))
    rots, signs = F.givens(Rm)
    assert len(rots) <= c.n * (2 * c.n - 1)
    Q = np.diag(np.array(signs, dtype=float))
    for a, b, th in rots:
        Q = F.plane_rotation(a, b, th, c.n) @ Q
    assert float(np.abs(Q - Rm).max()) < 1e-12


def test_refit_recovers_pinned_and_free_angles():
    pat = [("rz", (0,)), ("h", (0,)), ("rz", (0,)), ("h", (0,)), ("rz", (0,))]
    tpl = R.euler_template(1, pat)
    tgt = S.unitary(tpl([0.3, 1.1, -0.4]), 1)
    f = R.least_squares(tpl, tgt, [0.1, 0.1, 0.1], n=1)
    assert f.distance < 1e-9
    g = R.least_squares(tpl, tgt, [0.1, 0.1, 0.1], n=1, pinned={0: 0.3})
    assert g.distance < 1e-9 and abs(g.angles[0] - 0.3) < 1e-15


def test_refit_closure_gives_the_right_algebra_dimension():
    X = np.array([[0, 1], [1, 0]], dtype=complex)
    Z = np.diag([1, -1]).astype(complex)
    assert len(R.closure([X, Z])) == 3            # su(2)
    assert len(R.closure([Z])) == 1


# ------------------------------------------------------------------------------------------ budget
def test_budget_is_installed_by_the_runner_and_zero_outside_it():
    from v4.api import budget
    from v4.ledger import Ledger
    assert budget.remaining() == 0.0 and budget.draw(1e-9) is False
    L = Ledger(1e-3)
    with budget.installed(L, "r"):
        assert budget.remaining() == 5e-4
        assert budget.draw(1e-5) and abs(budget.remaining() - 4.9e-4) < 1e-15
    assert budget.remaining() == 0.0
    assert L.report()["draws"] == {"r": 1e-05}


def test_dpf_card_draws_only_what_it_spends_and_nothing_outside_a_runner():
    """The DPF card is the first rule that is MEANT to spend error. Outside a runner it must not."""
    from v4 import book as B
    r = B.load_rule(Path("v4/rules/floor/dpf_dyadic_angle_fixing.py"))
    c = J.load("qft_8")
    assert r.trigger(c) == []                     # no budget installed -> nothing to spend -> no matches
    assert r.error_class == "approx" and r.resource_class == "unitary"
