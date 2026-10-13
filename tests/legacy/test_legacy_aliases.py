"""Old import paths of the archived stacks are aliases of circuitevolve.legacy.* (same module objects), so
existing commands, notebooks and results/ scripts reproduce unchanged."""
import importlib

import pytest

PAIRS = [("circuitevolve.search.slice", "circuitevolve.legacy.adder.slice"),
         ("circuitevolve.search.evolve", "circuitevolve.legacy.adder.evolve"),
         ("circuitevolve.search.llm", "circuitevolve.legacy.adder.llm"),
         ("circuitevolve.blocks.program", "circuitevolve.legacy.blocks_v1.program"),
         ("circuitevolve.blocks.rules", "circuitevolve.legacy.blocks_v1.rules"),
         ("circuitevolve.blocks.proposer", "circuitevolve.legacy.blocks_v1.proposer"),
         ("circuitevolve.blocks.pipeline", "circuitevolve.legacy.blocks_v1.pipeline")] + [
    (f"circuitevolve.evolve_opt.{m}", f"circuitevolve.legacy.evolve_opt.{m}")
    for m in ("split", "toolbox", "sandbox", "evaluate", "programs", "evolve", "control")]


@pytest.mark.parametrize("old,new", PAIRS)
def test_old_path_is_same_module(old, new):
    assert importlib.import_module(old) is importlib.import_module(new)


def test_shared_backend_and_single_numeric_lock():
    from circuitevolve.evolve_opt.sandbox import NUMERIC_LOCK as a
    from circuitevolve.legacy.evolve_opt.sandbox import NUMERIC_LOCK as b
    from circuitevolve.llm_backends import make_api_backend
    from circuitevolve.search.llm import make_api_backend as old
    assert a is b and old is make_api_backend
    from circuitevolve.evolve_opt import ERROR_BUDGET, evaluate
    assert ERROR_BUDGET == 1e-6 and evaluate is importlib.import_module("circuitevolve.legacy.evolve_opt.evaluate")
