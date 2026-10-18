"""B0 (TKET + gridsynth) and B1 (pyzx full_reduce + gridsynth) on the shared TKET inputs.

B0: the TKET input itself (FullPeepholeOptimise -> {CX,H,Rz}); every Rz that is not a multiple of
    pi/4 is gridsynth'd at eps / N_Rz (rsgridsynth); pi/4-multiples are emitted exactly.
B1: pyzx 0.10.7 full_reduce -> extract_circuit -> to_basic_gates -> basic_optimization on the
    same input (float_to_fraction_max_denominator raised to 1e15, see run_reference.py), then the
    same gridsynth lowering at eps / N_Rz.
Total error bound (operator norm, triangle inequality): N_Rz * eps/N_Rz = eps (+ ~1e-13 input).

Run: .venv-dpf/bin/python stage1/run_b0_b1.py [--circuits qft/qft_8 ...]
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from s1_common import (CIRCUITS, EPS, OUTPUTS, RUNS, dump_json, eps_tag, input_path, load_qiskit,  # noqa: E402
                       lower_clifford_rz, orig_path, short, state_distance, write_qasm)


def pyzx_reduce(path: Path):
    import pyzx as zx
    from qiskit import QuantumCircuit
    zx.settings.float_to_fraction_max_denominator = 10 ** 15
    txt = re.sub(r'(?<![\w.])-?\d+\.?\d*[eE][-+]?\d+', lambda m: format(float(m.group(0)), '.25f'),
                 path.read_text())
    # pyzx 0.10.7 turns `creg c[n]` into n extra graph wires; inputs have no measurements -> drop it
    assert 'measure' not in txt
    txt = re.sub(r'^creg .*;\n', '', txt, flags=re.M)
    c_in = zx.Circuit.from_qasm(txt)
    t0 = time.time()
    g = c_in.to_graph()
    zx.full_reduce(g)
    c = zx.extract_circuit(g.copy())
    c = zx.basic_optimization(c.to_basic_gates())
    dt = time.time() - t0
    return QuantumCircuit.from_qasm_str(c.to_qasm()), dt


def run(name, arm, ref, cache_in):
    rows = []
    t0 = time.time()
    if arm == 'B0':
        qc, pre_s = cache_in, 0.0
    else:
        qc, pre_s = pyzx_reduce(input_path(name))
    for eps in EPS:
        f = RUNS / f'{short(name)}_{arm}_{eps_tag(eps)}.json'
        if f.exists():
            print('skip', f.name)
            continue
        t1 = time.time()
        ct, st = lower_clifford_rz(qc, eps)
        low_s = time.time() - t1
        outp = OUTPUTS / f'{short(name)}_{arm}_{eps_tag(eps)}.qasm.gz'
        write_qasm(ct, outp)
        tv = time.time()
        d_orig = state_distance(ref, ct)
        d_in = state_distance(load_qiskit(input_path(name)), ct)
        r = dict(circuit=short(name), arm=arm, eps=eps, status='ok', **st,
                 err_bound_total=st['err_bound_gridsynth'], pre_s=round(pre_s, 2),
                 runtime_s=round(pre_s + low_s, 2), verify_s=round(time.time() - tv, 1),
                 state_dist_vs_orig=d_orig, state_dist_vs_input=d_in, output=str(outp.name))
        dump_json(r, f)
        print({k: r[k] for k in ('circuit', 'arm', 'eps', 'n_rz', 't_count', 'cx', 'state_dist_vs_orig')}, flush=True)
        rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--circuits', nargs='*', default=CIRCUITS)
    ap.add_argument('--arms', nargs='*', default=['B0', 'B1'])
    a = ap.parse_args()
    for name in a.circuits:
        ref = load_qiskit(orig_path(name))
        qin = load_qiskit(input_path(name))
        for arm in a.arms:
            run(name, arm, ref, qin)


if __name__ == '__main__':
    main()
