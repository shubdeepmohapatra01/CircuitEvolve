"""Float statevector spot-check that pipeline outputs (Clifford+RZ / U3+CX, BEFORE gridsynth)
implement the benchmark unitary, for circuits with <= MAXQ qubits (n <= 10 also get a full
unitary check inside the pipelines). For each pair we evolve NSTATES Haar-random input states
through reference and candidate and report min |<a|b>| (1.0 = equal up to global phase).
This is a floating-point sanity check of the baselines, not the repo's exact verifier.

Run: .venv/bin/python verify_equiv.py --tag NAME
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np  # noqa: E402

from common import EVAL, OUT, QASM  # noqa: E402

MAXQ = 20


def load_qiskit(path: Path):
    from qiskit import QuantumCircuit
    from bygate_exact import CCP_DEF
    txt = path.read_text()
    if re.search(r'^ccp\(', txt, re.M):
        txt = txt.replace('include "qelib1.inc";\n', 'include "qelib1.inc";\n' + CCP_DEF, 1)
    return QuantumCircuit.from_qasm_str(txt)


def overlap(ref, cand, nstates, seed=0):
    from qiskit.quantum_info import Statevector, random_statevector
    out = []
    for i in range(nstates):
        psi = random_statevector(2 ** ref.num_qubits, seed=seed + i)
        a = psi.evolve(ref).data
        b = psi.evolve(cand).data
        out.append(abs(np.vdot(a, b)))
    return min(out)


def main():
    import pandas as pd
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', required=True)
    ap.add_argument('--circuits', nargs='*', default=EVAL)
    ap.add_argument('--suffixes', nargs='*', default=['bygate_paramzsx', 'bygate_minrz', 'tket', 'pyzx'])
    ap.add_argument('--nstates', type=int, default=2)
    a = ap.parse_args()
    rows = []
    for name in a.circuits:
        ref_path = QASM / f'{name}.qasm'
        ref = load_qiskit(ref_path)
        if ref.num_qubits > MAXQ:
            rows.append(dict(circuit=ref_path.stem, candidate='*', status=f'skipped (n={ref.num_qubits} > {MAXQ})'))
            continue
        for suf in a.suffixes:
            cp = OUT / 'clifford_rz' / (suf.format(stem=ref_path.stem) if '{stem}' in suf
                                         else f'{ref_path.stem}_{suf}.qasm')
            if not cp.exists():
                rows.append(dict(circuit=ref_path.stem, candidate=suf, status='missing'))
                continue
            t0 = time.time()
            cand = load_qiskit(cp)
            ov = overlap(ref, cand, a.nstates)
            rows.append(dict(circuit=ref_path.stem, candidate=suf, status='ok', qubits=ref.num_qubits,
                             min_overlap=ov, one_minus_overlap=1 - ov, nstates=a.nstates,
                             seconds=round(time.time() - t0, 1)))
            print(rows[-1], flush=True)
    f = OUT / f'{a.tag}.csv'
    assert not f.exists()
    pd.DataFrame(rows).to_csv(f, index=False)
    print('wrote', f)


if __name__ == '__main__':
    main()
