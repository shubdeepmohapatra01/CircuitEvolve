"""v2 metric: T-count under BQSKit's error convention, plus qubits, ancillas, measurements, T-depth.

    measure(circuit, eps=None, data_qubits=None) -> dict
    t_count(circuit, eps=None) -> int
    fitness_key(m) -> (t_count, qubits, t_depth)        lexicographic (CLAUDE.md invariant 3)

Two paths, chosen by the circuit's content:
* EXACT circuits (ir.Circuit, or op lists whose rz are all multiples of pi/4; may contain ccx/ccz, gadgets,
  measurement, feed-forward): the frozen `circuitevolve.cost.cost` on the Clifford+T expansion (ccx/ccz = 7 T,
  and_compute = 4 T, and_uncompute = 0 T + 1 measurement). No eps needed; T-depth = ASAP T layers (cost.t_depth).
* Clifford+Rz circuits with continuous rotations: `core/metric.BqskitTMetric(eps)` - explicit T/Tdg + 1 per odd
  pi/4 Rz + gridsynth T-count of every remaining Rz at eps_rz = eps / N_Rz (BQSKit `err_per_gate =
  success_threshold / num_rz_gates`; pygridsynth 2.0.0, cached). `eps` is the budget reserved for final rotation
  synthesis (the caller decides the split of the total algorithmic error; see docs/v2/DESIGN.md). T-depth: ASAP
  layers where a synthesized Rz counts as a serial chain of its gridsynth T gates on its qubit (single-qubit
  words are sequential), so it is an upper estimate of the T-depth of the lowered circuit.
Ancillas = qubits - data qubits; data qubits come from `data_qubits` (count, sequence, or a verify.ReferenceSpec),
else from the ir.Circuit registers, else 0.
"""
from __future__ import annotations

from ..cost import cost as _frozen_cost
from ..ir import Circuit as IRCircuit

T_GATES = ("t", "tdg")


def _n_data(c, n_qubits: int, data_qubits) -> int:
    if data_qubits is None:
        if isinstance(c, IRCircuit) and c.registers:
            return n_qubits - len(c.ancillas())
        return n_qubits
    if hasattr(data_qubits, "n_qubits"):        # ReferenceSpec
        return int(data_qubits.n_qubits)
    if isinstance(data_qubits, int):
        return data_qubits
    return len(tuple(data_qubits))


def _ops_t_depth(ops, n: int, weight) -> int:
    qd = [0] * n
    for op in ops:
        qs = op[1]
        d = max(qd[q] for q in qs) + weight(op)
        for q in qs:
            qd[q] = d
    return max(qd) if qd else 0


def measure(c, eps: float | None = None, data_qubits=None) -> dict:
    from .verify import NotExact, _ops_and_n, as_ir
    try:
        ir = as_ir(c)
    except NotExact:
        ir = None
    if ir is not None:
        k = _frozen_cost(ir)
        nd = _n_data(ir if isinstance(c, IRCircuit) else c, ir.n_qubits, data_qubits)
        return dict(t_count=k["t_count"], t_fixed=k["t_count"], t_gs=0, rz=0, eps_rz=None,
                    eps_synth=None if eps is None else float(eps), qubits=ir.n_qubits,
                    ancillas=ir.n_qubits - nd, measurements=k["measurements"], t_depth=k["t_depth"],
                    cx=k["cnot"], gates=k["gates"], path="exact (frozen cost.py)")
    ops, n = _ops_and_n(c)
    from ..core.circuit import normalize
    ops = normalize(ops)
    if eps is None:
        raise ValueError("circuit has rotations that need synthesis: pass eps (synthesis budget)")
    from ..blocks.cost_model import canonical_angle
    from ..core.metric import BqskitTMetric
    met = BqskitTMetric(float(eps))
    k = met.cost(ops)
    angs = [canonical_angle(a) for g, _, a in ops if g == "rz"]
    tmap = dict(zip(map(repr, angs), met.rotation_t(angs, k["eps_rz"]))) if angs else {}

    def w(op):
        if op[0] in T_GATES:
            return 1
        if op[0] == "rz":
            return tmap[repr(canonical_angle(op[2]))]
        return 0
    nd = _n_data(c, n, data_qubits)
    return dict(t_count=k["t"], t_fixed=k["t_fixed"], t_gs=k["t_gs"], rz=k["rz"], eps_rz=k["eps_rz"],
                eps_synth=k["eps_synth"], qubits=n, ancillas=n - nd, measurements=0,
                t_depth=_ops_t_depth(ops, n, w), cx=k["cx"], gates=k["gates"],
                path="bqskit-convention (core/metric.BqskitTMetric)")


def t_count(c, eps: float | None = None) -> int:
    return int(measure(c, eps)["t_count"])


def fitness_key(m: dict) -> tuple:
    """Lexicographic: T-count, then qubits, then T-depth (never a weighted blend)."""
    return (m["t_count"], m["qubits"], m["t_depth"])
