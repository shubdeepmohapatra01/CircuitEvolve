"""optimize() cvdv wire-up (PLAN_P1 P1.3): routed terms input, zero accepts reproduce the
current rulebook compile. Runs in the cvdv acceptance env (cvdv-opt, marked by qutip) like
tests/engine/test_cvdv_plugin.py."""
from __future__ import annotations

import pytest

pytest.importorskip("qutip")

from circuitevolve.engine.run import optimize  # noqa: E402


def test_optimize_cvdv_zero_accepts_reproduce_rulebook_compile(tmp_path):
    s = optimize({"benchmark": "boseHubbard_small"}, 1e-3,
                 lambda prompts: ["NONE"] * len(prompts), runs_dir=tmp_path, n_calls=1, batch=1)
    assert s["routing"]["family"] == "cvdv.bosonic" and s["routing"]["contract"] == "certified_subspace"
    assert s["stats"]["accepted"] == 0 and s["stats"]["declined"] == 1
    assert s["t_after"] == s["t_before"]                       # duration unchanged, zero accepts
    assert s["ledger"]["window_spent"] == 0.0
    assert s["final_check_vs_original"]["ok"] is True
