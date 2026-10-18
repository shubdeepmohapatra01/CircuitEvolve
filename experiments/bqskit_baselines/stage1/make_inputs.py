"""Produce the ONE shared TKET-pre-optimized input per stage-1 circuit (paper Sec. III step 1).

pytket FullPeepholeOptimise() (defaults, allow_swaps=True) -> replace_implicit_wire_swaps()
(explicit SWAPs so the QASM implements the same unitary) -> AutoRebase{CX, H, Rz} ->
RemoveRedundancies(). Output: CNOT + H + Rz QASM in results/bqskit_baselines/stage1/inputs/.
Angles are written by pytket as multiples of pi with 17 significant digits (checked below by a
statevector comparison with the original qseed circuit).

Run: .venv-dpf/bin/python stage1/make_inputs.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault('XDG_CONFIG_HOME', str(HERE.parent / '.venv-dpf' / 'xdg'))

from s1_common import CIRCUITS, INPUTS, OUT, dump_json, input_path, load_qiskit, orig_path, quarter, short, state_distance  # noqa: E402


def make(name):
    from pytket import OpType
    from pytket.passes import AutoRebase, FullPeepholeOptimise, RemoveRedundancies
    from pytket.qasm import circuit_from_qasm, circuit_to_qasm_str
    c = circuit_from_qasm(str(orig_path(name)))
    n_in = c.n_gates
    t0 = time.time()
    FullPeepholeOptimise().apply(c)
    t_fpo = time.time() - t0
    perm = c.implicit_qubit_permutation()
    nontriv = any(k != v for k, v in perm.items())
    c.replace_implicit_wire_swaps()
    AutoRebase({OpType.CX, OpType.H, OpType.Rz}).apply(c)
    RemoveRedundancies().apply(c)
    t_tot = time.time() - t0
    p = input_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        raise SystemExit(f'{p} exists (append-only); delete deliberately to regenerate')
    p.write_text(circuit_to_qasm_str(c, maxwidth=10**6))
    qc = load_qiskit(p)
    ref = load_qiskit(orig_path(name))
    n_rz = sum(1 for i in qc.data if i.operation.name == 'rz' and quarter(float(i.operation.params[0])) is None)
    t_fixed = sum(quarter(float(i.operation.params[0])) % 2 for i in qc.data
                  if i.operation.name == 'rz' and quarter(float(i.operation.params[0])) is not None)
    d = state_distance(ref, qc, nstates=2)
    ops = qc.count_ops()
    return dict(circuit=short(name), qubits=qc.num_qubits, orig_gates=n_in, cx=ops.get('cx', 0),
                h=ops.get('h', 0), rz_total=ops.get('rz', 0), rz_nonclifford_t=n_rz, t_fixed=t_fixed,
                implicit_perm_made_explicit=nontriv, fpo_s=round(t_fpo, 2), total_s=round(t_tot, 2),
                state_dist_vs_orig=d, file=str(p.relative_to(OUT)))


def main():
    import pandas as pd
    rows = []
    for name in CIRCUITS:
        r = make(name)
        print(r, flush=True)
        rows.append(r)
    f = INPUTS / 'inputs_manifest.csv'
    assert not f.exists()
    pd.DataFrame(rows).to_csv(f, index=False)
    dump_json(rows, INPUTS / 'inputs_manifest.json')


if __name__ == '__main__':
    main()
