"""Best-classical pre-optimisation (the block pipeline's INPUT): pyzx and TKET, keep the lower T-count.

Same pipelines as phase 0 (experiments/bqskit_baselines/run_reference.py):
  pyzx : exact Clifford+Rz minrz lowering -> full_reduce -> extract_circuit -> to_basic_gates ->
         basic_optimization (float_to_fraction_max_denominator = 1e15; scientific literals rewritten).
  tket : FullPeepholeOptimise() -> replace_implicit_wire_swaps -> AutoRebase{CX,H,Rz} ->
         RemoveRedundancies (from the U3+CX benchmark).
Both outputs are converted to ops over {h,x,z,s,sdg,t,tdg,cx,cz,rz} and checked against the original
qseed circuit with verify_block.circuit_check.
"""
from __future__ import annotations

import math
import re
from fractions import Fraction

from . import verify_block as vb
from .circuit_io import bqskit_to_ops, emit_rz, load_u3cx, lower_minrz, ops_to_qasm
from .cost_model import Gridsynth, cost_key, ops_cost


def pyzx_optimise(ops_in, n: int) -> list:
    import pyzx as zx
    zx.settings.float_to_fraction_max_denominator = 10 ** 15
    txt = re.sub(r"(?<![\w.])-?\d+\.?\d*[eE][-+]?\d+", lambda m: format(float(m.group(0)), ".25f"),
                 ops_to_qasm(ops_in, n))
    c_in = zx.Circuit.from_qasm(txt)
    g = c_in.to_graph()
    zx.full_reduce(g)
    c = zx.basic_optimization(zx.extract_circuit(g.copy()).to_basic_gates())
    ops = []
    for gate in c.gates:
        nm = gate.name
        if nm in ("ZPhase", "XPhase"):
            ph = Fraction(gate.phase)
            q = gate.target
            if nm == "XPhase":
                ops.append(("h", (q,), None))
            emit_rz(ops, q, float(ph) * math.pi)
            if nm == "XPhase":
                ops.append(("h", (q,), None))
        elif nm in ("T", "T*", "S", "S*", "Z", "NOT", "HAD"):
            q = gate.target
            name = {"T": "tdg" if getattr(gate, "adjoint", False) else "t", "T*": "tdg",
                    "S": "sdg" if getattr(gate, "adjoint", False) else "s", "S*": "sdg",
                    "Z": "z", "NOT": "x", "HAD": "h"}[nm]
            ops.append((name, (q,), None))
        elif nm == "CNOT":
            ops.append(("cx", (gate.control, gate.target), None))
        elif nm == "CZ":
            ops.append(("cz", (gate.control, gate.target), None))
        elif nm == "SWAP":
            a, b = gate.control, gate.target
            ops.extend([("cx", (a, b), None), ("cx", (b, a), None), ("cx", (a, b), None)])
        else:
            raise ValueError(f"unexpected pyzx gate {nm}")
    return ops


def tket_optimise(u3cx_circ) -> list:
    from pytket import OpType
    from pytket.passes import AutoRebase, FullPeepholeOptimise, RemoveRedundancies
    from pytket.qasm import circuit_from_qasm_str
    n = u3cx_circ.num_qudits
    c = circuit_from_qasm_str(ops_to_qasm(bqskit_to_ops(u3cx_circ), n))
    FullPeepholeOptimise().apply(c)
    c.replace_implicit_wire_swaps()
    AutoRebase({OpType.CX, OpType.H, OpType.Rz}).apply(c)
    RemoveRedundancies().apply(c)
    idx = {q: i for i, q in enumerate(c.qubits)}
    ops = []
    for cmd in c:
        qs = tuple(idx[q] for q in cmd.qubits)
        t = cmd.op.type
        if t == OpType.Rz:
            emit_rz(ops, qs[0], math.pi * float(cmd.op.params[0]))
        elif t == OpType.H:
            ops.append(("h", qs, None))
        elif t == OpType.CX:
            ops.append(("cx", qs, None))
        else:
            raise ValueError(f"unexpected tket op {t}")
    return ops


def best_classical(name: str, gs: Gridsynth | None = None, check: bool = True) -> dict:
    """Load qseed circuit, run pyzx and TKET, return both and the lower-T one ('best')."""
    gs = gs or Gridsynth()
    circ, note = load_u3cx(name)
    n = circ.num_qudits
    original = bqskit_to_ops(circ)
    minrz = lower_minrz(circ)
    cands = {"minrz": minrz, "pyzx": pyzx_optimise(minrz, n), "tket": tket_optimise(circ)}
    out = dict(name=name, n=n, note=note, original=original, candidates={})
    for k, ops in cands.items():
        rec = dict(ops=ops, cost=ops_cost(ops, gs), cost_raw=ops_cost(ops, gs, canonical=False))
        if check:
            rec["check"] = vb.circuit_check(original, ops, n)
        out["candidates"][k] = rec
    # best = lower T under either counting (phase-0 raw angles, or angles reduced to [-pi, pi])
    best = min(("pyzx", "tket"), key=lambda k: (min(out["candidates"][k]["cost"]["t"],
                                                     out["candidates"][k]["cost_raw"]["t"]),
                                                 cost_key(out["candidates"][k]["cost"]), k))
    out["best"] = best
    return out
