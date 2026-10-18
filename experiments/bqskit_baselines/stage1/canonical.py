"""Canonical T recount: re-lower every arm's exact pre-gridsynth Clifford+Rz circuit with pygridsynth 2.0.0
(deterministic) at the SAME per-rotation precision the arm used, then verify the resulting Clifford+T circuit
against the original qseed circuit.

Why: rsgridsynth v1.0.0 (used by bqskit-ft GridSynthPass and by our B0/B1 as-run numbers) is not a pure
function of (theta, eps): its word for a given call depends on earlier calls in the same process, which moves
whole-circuit T-counts by a few percent (hubbard_8, eps 1e-3, identical 84 angles: 4312 vs 4466 vs 4472
depending on call history). The canonical recount removes that noise so arms differ only by what the
compiler did (rotation count, angles, fixed T). Error bounds are unchanged (same N_Rz, same eps per Rz).

Pre-gridsynth circuits:
  B0  the TKET input itself;  B1  pyzx full_reduce of the input (recomputed here, deterministic, and its N_Rz
  checked against the as-run record);  B2/B2ft/B3/B3m/B3g  the circuit handed to GridSynthPass, dumped by
  run_bqskit_arms.py (S1_RUN_VERSION=v2) as outputs_v2/<tag>_pregs.qasm.gz.

Run: S1_RUN_VERSION=v2 .venv-dpf/bin/python stage1/canonical.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import get_context
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault('S1_RUN_VERSION', 'v2')

import s1_common as S  # noqa: E402
from s1_common import (CIRCUITS, EPS, OUT, dump_json, eps_tag, input_path, load_qiskit, orig_path,  # noqa: E402
                       quarter, short, state_distance, write_qasm)

V1_RUNS = OUT / 'runs'
CANON = S.RUNS / 'canonical'
CACHE: dict = {}


def cached_words(angles, prec, procs=None, impl='pyg'):
    assert impl == 'pyg'
    return {float(a): CACHE[(float(a), prec)] for a in set(angles)}


def rotations(qc):
    return [float(i.operation.params[0]) for i in qc.data
            if i.operation.name in ('rz', 'rx', 'p', 'u1') and quarter(float(i.operation.params[0])) is None]


def main():
    from run_b0_b1 import pyzx_reduce
    jobs = []  # (tag, record, pre-gs qiskit circuit, eps_per_rz, name)
    for name in CIRCUITS:
        qin = load_qiskit(input_path(name))
        qzx = None
        for eps in EPS:
            for arm in ['B0', 'B1', 'B2', 'B3', 'B2ft', 'B3m', 'B3g']:
                tag = f'{short(name)}_{arm}_{eps_tag(eps)}'
                src = (V1_RUNS if arm in ('B0', 'B1') else S.RUNS) / f'{tag}.json'
                if not src.exists():
                    print('missing', src)
                    continue
                r = json.loads(src.read_text())
                if r['status'] != 'ok':
                    print('not ok', tag)
                    continue
                if arm == 'B0':
                    pre = qin
                elif arm == 'B1':
                    if qzx is None:
                        qzx, _ = pyzx_reduce(input_path(name))
                        write_qasm(qzx, S.OUTPUTS / f'{short(name)}_B1_pyzx_cliffrz.qasm.gz')
                    pre = qzx
                    assert len(rotations(pre)) == r['n_rz'], (tag, len(rotations(pre)), r['n_rz'])
                else:
                    pre = load_qiskit(S.OUTPUTS / f'{tag}_pregs.qasm.gz')
                jobs.append((tag, r, pre, float(r['eps_per_rz']), name))
    need = sorted({(a, j[3]) for j in jobs for a in rotations(j[2])})
    print('distinct (theta, eps) pairs:', len(need), flush=True)
    t0 = time.time()
    with get_context('spawn').Pool(int(os.environ.get('S1_GS_PROCS', '8'))) as pool:
        for i, (key, res) in enumerate(pool.imap_unordered(_pyg_keyed, need, chunksize=8)):
            a, w, err, dt = res
            if err > key[1] * (1 + 1e-9):
                raise ValueError(f'pygridsynth error {err} > {key[1]} for {a}')
            CACHE[key] = (w, err, dt)
            if i % 2000 == 0:
                print(i, round(time.time() - t0), flush=True)
    print('gridsynth done', round(time.time() - t0), 's', flush=True)
    S.gridsynth_words = cached_words
    CANON.mkdir(parents=True, exist_ok=True)
    refs = {}
    for tag, r, pre, epr, name in jobs:
        f = CANON / f'{tag}.json'
        if f.exists():
            continue
        ct, st = S.lower_clifford_rz(pre, None, impl='pyg', eps_per_rz=epr)
        outp = S.OUTPUTS / f'{tag}_canon.qasm.gz'
        write_qasm(ct, outp)
        if name not in refs:
            refs[name] = load_qiskit(orig_path(name))
        d = state_distance(refs[name], ct)
        rec = dict(circuit=short(name), arm=r['arm'], eps=r['eps'], t_count_canon=st['t_count'],
                   t_fixed_canon=st['t_fixed'], t_gridsynth_canon=st['t_gridsynth'], n_rz_canon=st['n_rz'],
                   n_rz_asrun=r['n_rz'], eps_per_rz=epr, cx_canon=st['cx'], state_dist_vs_orig_canon=d,
                   t_count_asrun=r['t_count'], source_run=str((V1_RUNS if r['arm'] in ('B0', 'B1') else S.RUNS).name),
                   output=outp.name, gridsynth='pygridsynth 2.0.0')
        dump_json(rec, f)
        print({k: rec[k] for k in ('circuit', 'arm', 'eps', 't_count_asrun', 't_count_canon', 'n_rz_canon',
                                   'n_rz_asrun', 'state_dist_vs_orig_canon')}, flush=True)


def _pyg_keyed(key):
    return key, S._gs_one_pyg(key)


if __name__ == '__main__':
    main()
