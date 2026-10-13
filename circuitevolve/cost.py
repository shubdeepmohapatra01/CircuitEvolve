"""Fault-tolerant cost proxies, computed on the fully expanded (Clifford+T) circuit."""
from __future__ import annotations

from .ir import Circuit

T_GATES = {"t", "tdg"}


def t_count(circ: Circuit) -> int:
    return sum(1 for g in circ.expand("clifford_t").gates if g.name in T_GATES)


def t_depth(circ: Circuit) -> int:
    """Number of T layers in an ASAP schedule (all gates create dependencies)."""
    c = circ.expand("clifford_t")
    qd = [0] * c.n_qubits
    cd = [0] * max(c.n_cbits, 1)
    for g in c.gates:
        deps = [qd[q] for q in g.qubits]
        if g.cond is not None:
            deps.append(cd[g.cond])
        d = max(deps) + (1 if g.name in T_GATES else 0)
        for q in g.qubits:
            qd[q] = d
        if g.name == "measure":
            cd[g.cbit] = d
    return max(qd) if qd else 0


def cost(circ: Circuit) -> dict:
    c = circ.expand("clifford_t")
    counts = c.count()
    return {
        "t_count": sum(counts.get(g, 0) for g in T_GATES),
        "t_depth": t_depth(circ),
        "qubits": circ.n_qubits,
        "cnot": counts.get("cx", 0),
        "measurements": counts.get("measure", 0),
        "gates": len(c),
    }
