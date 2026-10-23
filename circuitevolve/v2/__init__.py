"""CircuitEvolve v2: two-tier LLM-assisted fault-tolerant compilation (see circuitevolve/v2/README.md,
docs/v2/DESIGN.md).

Tier 1 (compilation strategy): recognize subroutines of a LOGICAL circuit and pick or write the best known
construction for each (e.g. Gidney's measurement-based adder), verified against the logical circuit.
Tier 2 (optimization): executable rewrite rules applied wherever they match, every application verified, a
versioned rule library kept only when a version beats the previous one.

Isolation: v2 only IMPORTS the existing code (frozen exact stack ir/ring/sim/spec/verify/cost,
blocks/verify_block.py, core/verifier.py, core/metric.py, core/circuit.py) and never edits it. New results go
to results/v2/, new docs to docs/v2/.

Shared interface (Scaffold track):
  verify.verify(candidate, reference, mode, eps) -> Verdict      modes 'exact' | 'approx' | 'relaxed' | 'auto'
  metric.measure(circuit, eps=..., data_qubits=...) -> dict      T-count (BQSKit convention), qubits, ...
  baselines.best_classical(circuit, eps) / baselines.table()     reused baseline numbers, never recomputed

Submodules are imported lazily so that importing `circuitevolve.v2` stays cheap (no BQSKit / pytket import).
"""
from __future__ import annotations

import importlib as _importlib

__all__ = ["verify", "metric", "baselines"]


def __getattr__(name):           # lazy submodule access: circuitevolve.v2.verify etc.
    if name in __all__:
        return _importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(name)
