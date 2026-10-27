"""Driver for BQSKit's DPF Synth (phase-kickback) arm, run with the bqskit-ft venv
(experiments/bqskit_baselines/.venv-pk, Python 3.12). Reads OPENQASM 2 (circuitevolve's
gate set) on stdin, runs CliffordRZ retarget -> partition -> GreedyNTRO -> ConvertToPKAC
-> UnfoldPass at the given (eps, k, seed) via dpf_pk.dpf_pk_compile, lowers the result into
circuitevolve's gate set, and prints one JSON line to stdout:
{"qasm": ..., "eps_used": eps, "unlowered": {gate_class: count}, "seconds": ..., "info": {...}}.
Called from circuitevolve/dpf.py; unrecognised ops are reported in "unlowered" instead of
crashing, per that module's contract.

LogicalAndDgGate (bqskit-ft's AND-UNCOMPUTE, see dpf_pk.py's module docstring) is coded
upstream as an exact 8x8 permutation unitary -- numerically identical to Toffoli/ccx on
(q0, q1, q2) = (control, control, target holding q0 AND q1), verified with np.allclose --
but our T-count metric (circuitevolve/metric.py) charges 7 T for every surviving ccx/ccz,
so lowering it to ccx would add ~7 T of PHANTOM cost for a gate whose real (Gidney 2018)
implementation is a 0-T measured uncomputation. It is therefore lowered to that measured
protocol instead, on a fresh classical bit c[k] per gadget:
    h t;  measure t -> c[k];  if(c[k]==1) cz c0,c1;  if(c[k]==1) x t
(h puts the AND-target into the X basis where c0 AND c1 shows up as a relative phase;
measuring and classically applying cz only when the outcome is 1, then resetting t with an
x conditioned the same way, is exactly Gidney's 0-T AND-uncompute.)

LogicalAndGate (the AND-COMPUTE direction) is a CircuitGate that UnfoldPass() always
expands into CNOT/CNOT/CNOT/CNOT/Tdg/Tdg/T/CNOT/CNOT/H/S (its own generate_circuit, 3
explicit T/Tdg) before we ever see it. Its docstring requires the 3rd qubit to ALREADY
hold |A> = T H |0> going in -- but bqskit-ft's own `ConstantGidneyAdder.generate_circuit`
(bqskit/ft/gates/gidney_adder.py), which is supposed to supply that prep, has an off-by-one
in its init loop (`for q in range(n + start_ind + 1, 2 * n - 1)`): it skips local ancilla
index `n + start_ind`, which is exactly the ancilla consumed by the adder's LAST
LogicalAndGate. Traced end-to-end on validate_pk.py's own small_dyadic(3, [5]) case: that
ancilla gets no H/T at all before being used as an AND target, starting from the default
|0> instead of |A>. This is a genuine upstream state-prep bug (confirmed via
bqskit.ir.circuit.Circuit.operations() gate-by-gate trace), independent of either
LogicalAndDgGate lowering choice. match_and_prepare_logical_and() below detects the
unfolded LogicalAndGate pattern per occurrence and, if its target was not immediately
preceded (on that qubit) by h;t, inserts the missing h;t from |0> right there -- i.e. it
patches the state in OUR lowered output, not the upstream pass.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'stage1'))

import numpy as np  # noqa: E402
import midmeasure_shim  # noqa: E402
import u12rz_shim  # noqa: E402

midmeasure_shim.install()
u12rz_shim.install()

GATE_MAP = {
    'HGate': 'h', 'XGate': 'x', 'YGate': 'y', 'ZGate': 'z',
    'SGate': 's', 'SdgGate': 'sdg', 'TGate': 't', 'TdgGate': 'tdg',
    'SXGate': 'sx', 'SqrtXGate': 'sx', 'SXdgGate': 'sxdg', 'SqrtXdgGate': 'sxdg',
    'CNOTGate': 'cx', 'CXGate': 'cx', 'CZGate': 'cz', 'SwapGate': 'swap',
    'CCXGate': 'ccx', 'ToffoliGate': 'ccx', 'CCZGate': 'ccz',
    # LogicalAndDgGate is handled separately in lower() -- measured 0-T uncompute, not ccx.
}
DAGGER_MAP = {'SXGate': 'sxdg', 'SGate': 'sdg', 'TGate': 'tdg', 'SqrtXGate': 'sxdg'}


def _logical_and_ops(q):
    """CNOT CNOT CNOT CNOT Tdg Tdg T CNOT CNOT H S on (q0,q1,q2): LogicalAndGate's own
    generate_circuit (bqskit/ft/gates/logical_and.py), for the rare un-unfolded case."""
    a, b, t = q
    return [('cx', (a, t)), ('cx', (b, t)), ('cx', (t, a)), ('cx', (t, b)),
            ('tdg', (a,)), ('tdg', (b,)), ('t', (t,)), ('cx', (t, b)), ('cx', (t, a)),
            ('h', (t,)), ('s', (t,))]


def _and_dg_ops(q, k):
    """Gidney 2018's 0-T measured AND-uncompute for LogicalAndDgGate(c0, c1, t), t holding
    c0 AND c1 (see module docstring), on a fresh classical bit c[k]."""
    c0, c1, t = q
    return [('h', (t,), None, None, None),
            ('measure', (t,), None, k, None),
            ('cz', (c0, c1), None, None, k),
            ('x', (t,), None, None, k)]


_AND_SIG = ('CNOTGate', 'CNOTGate', 'CNOTGate', 'CNOTGate', 'TdgGate', 'TdgGate', 'TGate',
            'CNOTGate', 'CNOTGate', 'HGate', 'SGate')
_AND_LOOKAHEAD = 60


def _try_match_logical_and(ops_raw, i):
    """Try to match LogicalAndGate's unfolded 11-gate circuit (_AND_SIG) starting at
    ops_raw[i], tolerating OTHER-qubit ops interleaved in between -- bqskit's topological
    scheduler freely reorders commuting ops from elsewhere into the gaps (empirically
    confirmed: the AND-uncompute's own X(anc) landed between two of our pattern's steps).
    Returns (a, b, c, consumed_indices) with c the AND target, or None. Aborts (returns
    None) the moment a non-pattern op touches qubit c -- c carries the AND's actual payload,
    so anything else touching it mid-pattern means this isn't a clean, isolated instance.
    a/b MAY be touched by unrelated, commuting ops in between (empirically confirmed: the
    AND-uncompute's own X(anc) is scheduled into the middle of a forward AND's unfold) --
    those are passed through untouched, since they act on different qubits than our pattern
    steps at that point and therefore commute with them."""
    if type(ops_raw[i].gate).__name__ != 'CNOTGate':
        return None
    a, c = ops_raw[i].location
    consumed, step, b = [i], 1, None
    j, end = i + 1, min(len(ops_raw), i + _AND_LOOKAHEAD)
    while step < 11 and j < end:
        op = ops_raw[j]
        name, loc = type(op.gate).__name__, tuple(op.location)
        if step == 1 and name == 'CNOTGate' and loc[1] == c and loc[0] != a:
            b = loc[0]; consumed.append(j); step += 1; j += 1; continue
        if step > 1:
            want = {2: (c, a), 3: (c, b), 4: (a,), 5: (b,), 6: (c,),
                    7: (c, b), 8: (c, a), 9: (c,), 10: (c,)}[step]
            if name == _AND_SIG[step] and loc == want:
                consumed.append(j); step += 1; j += 1; continue
        if c in loc:
            return None
        j += 1
    return (a, b, c, consumed) if step == 11 else None


def lower(circ):
    """bqskit Circuit -> (ops, unlowered, nc, missing_prep). ops is
    [(name, qubits, theta, cbit, cond), ...] in circuitevolve's gate set; unlowered is
    {gate_class_name: count} for anything left out; nc is the number of fresh classical
    bits used (one per LogicalAndDgGate); missing_prep is the number of LogicalAndGate
    targets we had to prepare ourselves because ConstantGidneyAdder's own init loop missed
    them (see module docstring)."""
    from bqskit.ir.gates import DaggerGate, RZGate
    from bqskit.ft.gates.fractional_rz import FractionalRZGate
    from bqskit.ft.gates.logical_and import LogicalAndGate

    ops_raw = list(circ.operations())
    history: dict = {}          # qubit -> list of our gate names applied to it, in order
    ops, unlowered = [], {}
    counters = dict(nc=0, missing_prep=0)

    def emit(name, qubits, theta=None, cbit=None, cond=None):
        ops.append((name, qubits, theta, cbit, cond))
        for qq in qubits:
            history.setdefault(qq, []).append(name)

    def lower_one(op):
        g, q = op.gate, tuple(op.location)
        gname = type(g).__name__
        if isinstance(g, RZGate):
            emit('rz', q, theta=float(op.params[0]))
        elif isinstance(g, FractionalRZGate):
            emit('rz', q, theta=float(2 * np.pi * g.numerator / (2 ** g.k)))
        elif gname == 'LogicalAndDgGate':
            for name, qq, theta, cbit, cond in _and_dg_ops(q, counters['nc']):
                emit(name, qq, theta, cbit, cond)
            counters['nc'] += 1
        elif gname in GATE_MAP:
            emit(GATE_MAP[gname], q)
        elif isinstance(g, DaggerGate) and type(g.gate).__name__ in DAGGER_MAP:
            emit(DAGGER_MAP[type(g.gate).__name__], q)
        elif isinstance(g, LogicalAndGate):   # defensive: should never fire, see docstring
            for name, qq in _logical_and_ops(q):
                emit(name, qq)
        elif gname == 'IdentityGate':
            pass
        else:
            unlowered[gname] = unlowered.get(gname, 0) + 1

    i = 0
    while i < len(ops_raw):
        m = _try_match_logical_and(ops_raw, i)
        if m is not None:
            a, b, c, consumed = m
            consumed_set, last = set(consumed), consumed[-1]
            for k in range(i, last + 1):          # pass through interleaved unrelated ops
                if k not in consumed_set:
                    lower_one(ops_raw[k])
            if history.get(c, [])[-2:] != ['h', 't']:   # target not freshly prepared: BQSKit-FT bug
                emit('h', (c,)); emit('t', (c,))
                counters['missing_prep'] += 1
            for name, qq in _logical_and_ops((a, b, c)):
                emit(name, qq)
            i = last + 1
            continue
        lower_one(ops_raw[i])
        i += 1
    return ops, unlowered, counters['nc'], counters['missing_prep']


def to_qasm(n_qubits, ops, nc):
    out = ['OPENQASM 2.0;', 'include "qelib1.inc";', f'qreg q[{n_qubits}];']
    if nc:
        out.append(f'creg c[{nc}];')
    for name, qs, theta, cbit, cond in ops:
        qstr = ','.join(f'q[{i}]' for i in qs)
        if name == 'measure':
            stmt = f'measure {qstr} -> c[{cbit}];'
        elif name == 'rz':
            stmt = f'rz({theta!r}) {qstr};'
        else:
            stmt = f'{name} {qstr};'
        out.append(f'if(c[{cond}]==1) {stmt}' if cond is not None else stmt)
    return '\n'.join(out) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--k', type=int, required=True)
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--eps', type=float, required=True)
    args = ap.parse_args()

    qasm_in = sys.stdin.read()
    import dpf_pk
    from bqskit.ir.lang.qasm2.qasm2 import OPENQASM2Language

    np.random.seed(args.seed)                 # GreedyNTRO instantiation is stochastic
    circ = OPENQASM2Language().decode(qasm_in)
    compiler = dpf_pk.serial_compiler()
    t0 = time.time()
    out, info = dpf_pk.dpf_pk_compile(circ, compiler, error=args.eps, max_k=args.k)
    seconds = round(time.time() - t0, 2)
    ops, unlowered, nc, missing_prep = lower(out)
    payload = dict(
        qasm=to_qasm(out.num_qudits, ops, nc), eps_used=args.eps, k=args.k, seed=args.seed,
        qubits_in=circ.num_qudits, qubits_out=out.num_qudits,
        ancillas=out.num_qudits - circ.num_qudits, and_uncomputes=nc,
        state_preps_added=missing_prep, unlowered=unlowered, seconds=seconds, info=info,
    )
    print(json.dumps(payload, default=str))


if __name__ == '__main__':
    main()
