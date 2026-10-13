"""LEGACY compatibility alias. This module moved to `circuitevolve.legacy.adder.slice`
(P3/P4 adder slice search, archived 2026-10-13). The alias keeps old commands, notebooks and results/ scripts reproducible: importing
`circuitevolve.search.slice` returns the very same module object as `circuitevolve.legacy.adder.slice`."""
import sys as _sys
from circuitevolve.legacy.adder import slice as _m

_sys.modules[__name__] = _m
