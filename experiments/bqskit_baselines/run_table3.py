"""Reproduce arXiv:2409.00433 Table 3 'By Gate' T-counts with bqskit-ft (no block resynthesis).

Pipeline per circuit
  1. (shor only) lower cp/ccp/swap/ccx/u1 to {u3, cx}: see --shor-lowering.
  2. bqskit-ft `build_circuit_workflow(optimization_level=1, synthesis_epsilon=EPS_BLOCK,
     decompose_rz=False)` with `CliffordTModel(n)` -> Clifford + RZ circuit. This is the
     library's gate-level path: GroupSingleQudit -> Clifford replacement -> RX/RY->RZ ->
     RoundToDiscreteZ -> QuickPartitioner(2)+ScanningGateRemoval -> ZXZXZ -> Clifford
     replacement -> RoundToDiscreteZ, all inside 3-qubit partition blocks.
  3. every remaining RZ synthesized by pygridsynth at EPS_RZ (= the call bqskit-ft's
     GridSynthPass makes). T-count = T/Tdg already present + sum of gridsynth T-counts.

Run:  .venv/bin/python run_table3.py [--circuits add/add_17 ...] [--tag NAME]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np  # noqa: E402
from bqskit import Circuit  # noqa: E402
from bqskit.ft import CliffordTModel  # noqa: E402
from bqskit.ft.cliffordt.defaultworkflow import build_circuit_workflow  # noqa: E402
from bqskit.ir.gates import RZGate, TGate, TdgGate  # noqa: E402
from bqskit.passes import SetRandomSeedPass  # noqa: E402

from common import EVAL, OUT, PUBLISHED_BYGATE, QASM, gridsynth_summary  # noqa: E402
from serial_runtime import run_passes  # noqa: E402


def lower_shor(path: Path, how: str) -> Circuit:
    """shor_* use cp/ccp/swap/ccx/u1; bqskit-ft's ZXZXZ/RZ passes only touch 1q gates with
    >1 parameter, and its multi-qudit retarget step is not reached (see REPORT.md), so the
    non-native gates must be lowered first."""
    levels = {'qiskit-u3cx': 0, 'qiskit-u3cx-opt1': 1, 'qiskit-u3cx-opt2': 2}
    if how in levels:
        qc = load_shor_qiskit(path)
        from qiskit import transpile
        from qiskit.qasm2 import dumps
        qc2 = transpile(qc, basis_gates=['u3', 'cx'], optimization_level=levels[how])
        tmp = OUT / 'work' / f'{path.stem}_{how}.qasm'
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(dumps(qc2))
        return Circuit.from_file(str(tmp))
    raise ValueError(how)


# Exact identity: CCP(t) = CP(t/2)[b,c] CX[a,b] CP(-t/2)[b,c] CX[a,b] CP(t/2)[a,c]
CCP_DEF = 'gate ccp(t) a,b,c { cp(t/2) b,c; cx a,b; cp(-t/2) b,c; cx a,b; cp(t/2) a,c; }\n'


def load_shor_qiskit(path: Path):
    from qiskit import QuantumCircuit
    txt = path.read_text()
    txt = txt.replace('include "qelib1.inc";\n', 'include "qelib1.inc";\n' + CCP_DEF, 1)
    assert CCP_DEF in txt
    return QuantumCircuit.from_qasm_str(txt)


def unitary_dist(a: Circuit, b: Circuit) -> float:
    ua, ub = a.get_unitary(), b.get_unitary()
    return float(ua.get_distance_from(ub))


def pergate_workflow(eps: float):
    """bqskit-ft's own gate-level passes applied to each 1q gate INDEPENDENTLY: no
    GroupSingleQuditGatePass merging and no QuickPartitioner+ScanningGateRemoval (the two lossy /
    merging steps of build_cliffordt_workflow). Each U3 -> ZXZXZ (RZ SX RZ SX RZ), Clifford
    replacement, RoundToDiscreteZ(eps)."""
    from bqskit.ft.cliffordt.defaultworkflow import (clifford_replace, single_qudit_rx_or_ry,
                                                     single_qudit_u2_or_u3)
    from bqskit.ft.ftpasses.rounding import RoundToDiscreteZPass
    from bqskit.ft.rules.xytoz import XYtoZRotation
    from bqskit.passes import ForEachBlockPass, UnfoldPass
    from bqskit.passes.rules.zxzxz import ZXZXZDecomposition
    return [
        UnfoldPass(),
        clifford_replace(), UnfoldPass(),
        ForEachBlockPass([XYtoZRotation()], collection_filter=single_qudit_rx_or_ry),
        ForEachBlockPass([ZXZXZDecomposition()], collection_filter=single_qudit_u2_or_u3),
        UnfoldPass(),
        clifford_replace(), UnfoldPass(),
        RoundToDiscreteZPass(eps), UnfoldPass(),
    ]


def run_one(name: str, eps_block: float, eps_rz: float, shor_lowering: str, cache: dict, seed: int = 0,
            workflow: str = 'shipped') -> dict:
    path = Path(name) if name.endswith('.qasm') else QASM / f'{name}.qasm'
    circ = Circuit.from_file(str(path))
    in_counts = {str(k).replace('Gate', ''): v for k, v in circ.gate_counts.items()}
    lowering = ''
    if path.stem.startswith('shor_') and 'u3' not in path.stem:
        circ = lower_shor(path, shor_lowering)
        lowering = shor_lowering
    orig = circ.copy()
    t0 = time.time()
    # bqskit-ft's build_cliffordt_workflow overwrites its own `passes` list (`passes =` instead of
    # `passes +=`, defaultworkflow.py:170), dropping SetRandomSeedPass and the retarget step, so
    # we prepend the seed pass ourselves for reproducibility.
    if workflow == 'shipped':
        passes = build_circuit_workflow(optimization_level=1, synthesis_epsilon=eps_block,
                                        decompose_rz=False)
    else:
        passes = pergate_workflow(eps_block)
    out, data = run_passes(circ, [SetRandomSeedPass(seed)] + passes,
        model=CliffordTModel(circ.num_qudits))
    t_stage = time.time() - t0
    counts = {str(k).replace('Gate', ''): v for k, v in out.gate_counts.items()}
    angles = [op.params[0] for op in out if isinstance(op.gate, RZGate)]
    assert len(angles) == out.count(RZGate()) == out.num_params, (len(angles), out.num_params)
    t_fixed = out.count(TGate()) + out.count(TdgGate())
    t1 = time.time()
    gs = gridsynth_summary(angles, eps_rz, cache)
    t_gs = time.time() - t1
    dist = unitary_dist(orig, out) if circ.num_qudits <= 10 else None
    short = path.stem
    pub = PUBLISHED_BYGATE.get(short, {})
    tc = t_fixed + gs['gs_t']
    stem = OUT / 'clifford_rz' / workflow
    stem.mkdir(parents=True, exist_ok=True)
    out.save(str(stem / f'{short}_bqskitft_{workflow}_seed{seed}.qasm'))
    row = dict(circuit=short, seed=seed, pipeline=f'bqskit-ft {workflow}', shor_lowering=lowering,
               eps_block=eps_block, eps_rz=eps_rz, qubits=circ.num_qudits,
               input_gates=sum(in_counts.values()), rz_count=len(angles),
               rz_distinct=gs['distinct_angles'], t_fixed=t_fixed, t_gridsynth=gs['gs_t'],
               t_count=tc, t_per_rz=round(gs['gs_t'] / max(1, len(angles)), 2),
               published_rz=pub.get('rz'), published_t=pub.get('t'),
               rz_diff_pct=round(100 * (len(angles) - pub['rz']) / pub['rz'], 2) if pub else None,
               t_diff_pct=round(100 * (tc - pub['t']) / pub['t'], 2) if pub else None,
               max_gridsynth_dist=gs['gs_max_dist'], cliffordrz_unitary_dist=dist,
               bqskit_error_bound=float(data.error), stage1_s=round(t_stage, 1),
               gridsynth_s=round(t_gs, 1), out_gate_counts=json.dumps(counts),
               in_gate_counts=json.dumps(in_counts))
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--circuits', nargs='*', default=EVAL)
    ap.add_argument('--eps-block', type=float, default=1e-8)
    ap.add_argument('--eps-rz', type=float, default=1e-9)
    ap.add_argument('--shor-lowering', default='qiskit-u3cx')
    ap.add_argument('--tag', default='table3_bygate')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--workflow', choices=['shipped', 'pergate'], default='shipped')
    a = ap.parse_args()
    import pandas as pd
    cache: dict = {}
    rows = []
    for name in a.circuits:
        r = run_one(name, a.eps_block, a.eps_rz, a.shor_lowering, cache, a.seed, a.workflow)
        print(json.dumps({k: r[k] for k in ('circuit', 'rz_count', 'published_rz', 't_count',
                                             'published_t', 't_diff_pct', 'stage1_s')}), flush=True)
        rows.append(r)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f'{a.tag}.csv'
    f.parent.mkdir(parents=True, exist_ok=True)
    assert not f.exists(), f'{f} exists; results are append-only, choose a new --tag'
    pd.DataFrame(rows).to_csv(f, index=False)
    print('wrote', f)


if __name__ == '__main__':
    main()
