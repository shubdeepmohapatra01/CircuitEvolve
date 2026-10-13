"""LEGACY compatibility alias for circuitevolve.legacy.evolve_opt (optimizer-program evolution, archived 2026-10-13).

Every submodule name circuitevolve.evolve_opt.<m> is registered in sys.modules as the SAME module object
as circuitevolve.legacy.evolve_opt.<m> (one NUMERIC_LOCK, one cache), so old commands and results/ scripts
still run unchanged. New code should import circuitevolve.legacy.evolve_opt.
"""
import importlib as _il
import sys as _sys

from circuitevolve.legacy.evolve_opt import *  # noqa: F401,F403
from circuitevolve.legacy.evolve_opt import EPS_RZ, ERROR_BUDGET, NUMERIC_SLACK, TOOLBOX_VERSION  # noqa: F401

for _s in ('split', 'toolbox', 'sandbox', 'evaluate', 'programs', 'evolve', 'control'):
    _m = _il.import_module("circuitevolve.legacy.evolve_opt." + _s)
    _sys.modules[__name__ + "." + _s] = _m
    globals()[_s] = _m
