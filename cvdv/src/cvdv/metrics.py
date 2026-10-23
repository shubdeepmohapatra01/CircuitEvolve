"""Genesis' cost metrics (Chen et al., ISCA'25, §4.1), re-implemented independently.

    1-op gates  : instructions with one operand
    2-op gates  : instructions with >= 2 operands (qubit-qumode, qumode-qumode, CBS)
    duration    : critical-path length with latency 1 per 1-op gate and 20 per multi-operand gate
                  (Genesis `Node.get_latecy`, `Circuit.depths`), on the physical circuit.

Genesis reports duration under the name "depth".  `pauli` placeholder ops (logical circuits only)
are rejected: metrics are defined on fully synthesised circuits.
"""
from __future__ import annotations

from collections import defaultdict

LAT_1OP = 1
LAT_MULTI = 20


def latency(op) -> int:
    return LAT_MULTI if len(op.wires) > 1 else LAT_1OP


def metrics(circ) -> dict:
    ops = circ.ops if hasattr(circ, "ops") else list(circ)
    if any(o.name == "pauli" for o in ops):
        raise ValueError("unsynthesised pauli op present")
    one = sum(1 for o in ops if len(o.wires) <= 1)
    depth = defaultdict(int)
    for o in ops:
        d = max(depth[w] for w in o.wires) + latency(o)
        for w in o.wires:
            depth[w] = d
    return {"one_op": one, "two_op": len(ops) - one, "total": len(ops),
            "duration": max(depth.values()) if depth else 0}


def key(m: dict, error_ok: bool = True):
    """Lexicographic order used by the selector: valid, duration, 2-op, 1-op."""
    return (0 if error_ok else 1, m["duration"], m["two_op"], m["one_op"])
