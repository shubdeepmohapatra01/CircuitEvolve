"""P5 control arms: repair-only loop respects the evaluation budget and verifier integrity (no LLM)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from experiments.p5_controls import repair_only_search  # noqa: E402
from circuitevolve.legacy.adder.slice import CUCCARO


def test_repair_only_matched_budget():
    arch, traj, stats, best = repair_only_search(CUCCARO, "B", eval_budget=400, rng_seed=1, repair_budget=50)
    assert 400 <= stats["evals"] <= 401 and stats["best"][0] <= 14.0
    assert stats["proposals"] >= 1 and traj[-1][1] == stats["evals"]
    a2 = repair_only_search(CUCCARO, "B", eval_budget=400, rng_seed=1, repair_budget=50)[2]
    assert {k: v for k, v in a2.items() if k != "seconds"} == {k: v for k, v in stats.items() if k != "seconds"}
