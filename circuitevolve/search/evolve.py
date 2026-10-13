"""LEGACY compatibility alias. This module moved to `circuitevolve.legacy.adder.evolve`
(P3/P4 adder slice search, archived 2026-10-13). The alias keeps old commands, notebooks and results/ scripts reproducible: importing
`circuitevolve.search.evolve` returns the very same module object as `circuitevolve.legacy.adder.evolve`."""
import sys as _sys
from circuitevolve.legacy.adder import evolve as _m

_sys.modules[__name__] = _m
