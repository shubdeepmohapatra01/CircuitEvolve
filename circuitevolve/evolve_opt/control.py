"""LEGACY compatibility alias (never imported directly: circuitevolve/evolve_opt/__init__.py registers
circuitevolve.legacy.evolve_opt.control under this name)."""
import sys as _sys
from circuitevolve.legacy.evolve_opt import control as _m

_sys.modules[__name__] = _m
