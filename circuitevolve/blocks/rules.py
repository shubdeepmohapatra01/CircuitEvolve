"""LEGACY compatibility alias. This module moved to `circuitevolve.legacy.blocks_v1.rules`
(block optimizer v1 rule library / proposer, archived 2026-10-13). The alias keeps old commands, notebooks and results/ scripts reproducible: importing
`circuitevolve.blocks.rules` returns the very same module object as `circuitevolve.legacy.blocks_v1.rules`."""
import sys as _sys
from circuitevolve.legacy.blocks_v1 import rules as _m

_sys.modules[__name__] = _m
