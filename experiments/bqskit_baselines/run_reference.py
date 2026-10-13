"""Classical reference pipelines (no LLM): RZ count + T-count after gridsynth at eps_rz.

tket : pytket FullPeepholeOptimise() (defaults) -> AutoRebase{CX,H,Rz} -> RemoveRedundancies.
       Rz angles that are multiples of pi/4 count as Clifford/T; the rest go to gridsynth.
       Also reported: 'tket+minrz' = TKET's optimised circuit re-lowered with the exact
       minimal-RZ-per-1q-run decomposition of bygate_exact.py (same CX skeleton).
pyzx : input = exact Clifford+Rz form (bygate_exact 'minrz' lowering of the benchmark), then
       full_reduce -> extract_circuit -> to_basic_gates -> basic_optimization.
       pyzx.settings.float_to_fraction_max_denominator is raised from 2**20 to 10**15 because the
       default silently rounds angles to multiples of pi/2**20 (drops |theta| < ~3e-6 rad).

Each (pipeline, circuit) runs in a subprocess with a wall-clock limit (default 30 min).
Run: .venv/bin/python run_reference.py --pipeline tket|pyzx --tag NAME [--circuits ...]
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import sys
import time
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault('XDG_CONFIG_HOME', str(HERE / '.venv' / 'xdg'))  # pytket writes a config file

from common import EVAL, OUT, PUBLISHED_BYGATE, QASM, gridsynth_summary  # noqa: E402

CCP_DEF_CU1 = 'gate ccp(t) a,b,c { cu1(t/2) b,c; cx a,b; cu1(-t/2) b,c; cx a,b; cu1(t/2) a,c; }\n'


def _bench_path(name):
    return Path(name) if name.endswith('.qasm') else QASM / f'{name}.qasm'


def _quarter(halfturns: float, tol=1e-10):
    """pytket angle (half-turns) -> k if multiple of 1/4 (pi/4 rad), else None."""
    x = halfturns * 4
    r = round(x)
    return int(r) % 8 if abs(x - r) * math.pi / 4 <= tol else None


# ------------------------------------------------------------------------------------- TKET
def tket_job(name):
    from pytket import OpType
    from pytket.passes import AutoRebase, DecomposeBoxes, FullPeepholeOptimise, RemoveRedundancies
    from pytket.qasm import circuit_from_qasm_str, circuit_to_qasm_str
    path = _bench_path(name)
    txt = path.read_text()
    if 'ccp' in txt or 'cp(' in txt:
        import re
        txt = re.sub(r'(?<![a-z])cp\(', 'cu1(', txt)
        txt = txt.replace('include "qelib1.inc";\n', 'include "qelib1.inc";\n' + CCP_DEF_CU1, 1)
    c = circuit_from_qasm_str(txt)
    DecomposeBoxes().apply(c)
    c_in = c.copy()
    t0 = time.time()
    FullPeepholeOptimise().apply(c)
    t_opt = time.time() - t0
    AutoRebase({OpType.CX, OpType.H, OpType.Rz}).apply(c)
    RemoveRedundancies().apply(c)
    t_total = time.time() - t0
    angles, t_fixed, cx = [], 0, 0
    for cmd in c:
        if cmd.op.type == OpType.Rz:
            a = float(cmd.op.params[0])
            k = _quarter(a)
            if k is None:
                angles.append(math.pi * a)
            else:
                t_fixed += k % 2
        elif cmd.op.type == OpType.CX:
            cx += 1
    dist = None
    if c.n_qubits <= 10:
        import numpy as np
        A, B = c.get_unitary(), c_in.get_unitary()
        tr = np.trace(B.conj().T @ A)
        dist = float(np.linalg.norm(A - tr / abs(tr) * B, 2))
    # also emit the optimised circuit for the minrz re-lowering
    stem = OUT / 'clifford_rz'
    stem.mkdir(parents=True, exist_ok=True)
    qasm_out = stem / f'{path.stem}_tket.qasm'
    c2 = c.copy()
    c2.replace_implicit_wire_swaps()  # make FullPeepholeOptimise's implicit permutation explicit
    AutoRebase({OpType.CX, OpType.U3}).apply(c2)
    qasm_out.write_text(circuit_to_qasm_str(c2))
    return dict(rz_angles=angles, t_fixed=t_fixed, cx=cx, opt_s=t_opt, total_s=t_total,
                unitary_dist=dist, implicit_perm=bool(c.implicit_qubit_permutation() and any(
                    k != v for k, v in c.implicit_qubit_permutation().items())),
                tket_qasm=str(qasm_out), qubits=c.n_qubits)


def tket_minrz_job(qasm_path):
    from bqskit import Circuit
    from bygate_exact import lower_circuit, tcount_ops
    c = Circuit.from_file(qasm_path)
    t0 = time.time()
    ops, st = lower_circuit(c)
    t_fixed, angles = tcount_ops(ops)
    return dict(rz_angles=angles, t_fixed=t_fixed, cx=sum(1 for g, _, _ in ops if g == 'cx'),
                total_s=time.time() - t0, unitary_dist=None, qubits=c.num_qudits)


# ------------------------------------------------------------------------------------- pyzx
def pyzx_job(name):
    import pyzx as zx
    zx.settings.float_to_fraction_max_denominator = 10 ** 15
    short = _bench_path(name).stem
    src = OUT / 'clifford_rz' / f'{short}_bygate_minrz.qasm'
    assert src.exists(), f'run run_bygate_exact.py --method minrz first ({src})'
    import re
    # pyzx's phase parser reads '9.5e-05' as an expression with a free variable 'e': rewrite
    # scientific-notation literals in fixed point (exact to 1e-25 absolute)
    txt = re.sub(r'(?<![\w.])-?\d+\.?\d*[eE][-+]?\d+', lambda m: format(float(m.group(0)), '.25f'),
                 src.read_text())
    c_in = zx.Circuit.from_qasm(txt)
    t0 = time.time()
    g = c_in.to_graph()
    zx.full_reduce(g)
    t_red = time.time() - t0
    c = zx.extract_circuit(g.copy())
    c = zx.basic_optimization(c.to_basic_gates())
    t_total = time.time() - t0
    angles, t_fixed, cx, other = [], 0, 0, {}
    for gate in c.gates:
        nm = gate.name
        if nm in ('ZPhase', 'XPhase'):
            ph = Fraction(gate.phase)
            if (ph * 4).denominator == 1:
                t_fixed += int(ph * 4) % 2
            else:
                angles.append(float(ph) * math.pi)
            if nm == 'XPhase':
                other['XPhase'] = other.get('XPhase', 0) + 1
        elif nm in ('T', 'T*'):
            t_fixed += 1
        elif nm == 'CNOT':
            cx += 1
        elif nm in ('HAD', 'S', 'S*', 'Z', 'NOT', 'CZ', 'SWAP'):
            if nm == 'CZ':
                other['CZ'] = other.get('CZ', 0) + 1
        else:
            other[nm] = other.get(nm, 0) + 1
    dist = None
    if c_in.qubits <= 10:
        dist = 0.0 if zx.compare_tensors(c_in, c, preserve_scalar=False) else 1.0
    (OUT / 'clifford_rz' / f'{short}_pyzx.qasm').write_text(c.to_qasm())
    return dict(rz_angles=angles, t_fixed=t_fixed, cx=cx, reduce_s=t_red, total_s=t_total,
                unitary_dist=dist, other_gates=other, qubits=c_in.qubits, zx_tcount=c.tcount())


JOBS = dict(tket=tket_job, pyzx=pyzx_job)


def _runner(fn, arg, q):
    try:
        q.put(('ok', fn(arg)))
    except Exception as e:  # pragma: no cover
        import traceback
        q.put(('err', f'{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}'))


def run_limited(fn, arg, limit_s):
    ctx = mp.get_context('spawn')
    q = ctx.Queue()
    p = ctx.Process(target=_runner, args=(fn, arg, q))
    t0 = time.time()
    p.start()
    p.join(limit_s)
    if p.is_alive():
        p.terminate()
        p.join()
        return 'timeout', None, time.time() - t0
    status, res = q.get() if not q.empty() else ('err', 'no result')
    return status, res, time.time() - t0


def row_from(pipeline, short, status, res, wall, eps_rz, cache):
    pub = PUBLISHED_BYGATE.get(short, {})
    row = dict(circuit=short, pipeline=pipeline, status=status, eps_rz=eps_rz, wall_s=round(wall, 1))
    if status != 'ok':
        row['error'] = str(res)[:500] if res else f'exceeded limit ({wall:.0f}s)'
        return row
    gs = gridsynth_summary(res['rz_angles'], eps_rz, cache)
    tc = res['t_fixed'] + gs['gs_t']
    row.update(qubits=res['qubits'], cx=res['cx'], rz_count=len(res['rz_angles']),
               rz_distinct=gs['distinct_angles'], t_fixed=res['t_fixed'], t_gridsynth=gs['gs_t'],
               t_count=tc, eps_total_bound=len(res['rz_angles']) * eps_rz,
               published_bygate_rz=pub.get('rz'), published_bygate_t=pub.get('t'),
               t_vs_published_bygate_pct=round(100 * (tc - pub['t']) / pub['t'], 2) if pub else None,
               opt_s=round(res.get('opt_s', res.get('reduce_s', res['total_s'])), 1),
               pipeline_s=round(res['total_s'], 1), unitary_dist=res.get('unitary_dist'),
               extra=json.dumps({k: v for k, v in res.items() if k in ('implicit_perm', 'other_gates', 'zx_tcount')}))
    return row


def main():
    import pandas as pd
    ap = argparse.ArgumentParser()
    ap.add_argument('--pipeline', choices=list(JOBS), required=True)
    ap.add_argument('--circuits', nargs='*', default=EVAL)
    ap.add_argument('--eps-rz', type=float, default=1e-9)
    ap.add_argument('--limit-s', type=float, default=1800)
    ap.add_argument('--tag', required=True)
    a = ap.parse_args()
    f = OUT / f'{a.tag}.csv'
    assert not f.exists(), f'{f} exists; results are append-only'
    cache: dict = {}
    rows = []
    for name in a.circuits:
        short = _bench_path(name).stem
        status, res, wall = run_limited(JOBS[a.pipeline], name, a.limit_s)
        rows.append(row_from(a.pipeline, short, status, res, wall, a.eps_rz, cache))
        if a.pipeline == 'tket' and status == 'ok':
            s2, r2, w2 = run_limited(tket_minrz_job, res['tket_qasm'], a.limit_s)
            r = row_from('tket+minrz', short, s2, r2, w2 + wall, a.eps_rz, cache)
            rows.append(r)
        print(json.dumps({k: rows[-1].get(k) for k in ('circuit', 'pipeline', 'status', 'rz_count',
                                                       't_count', 'wall_s', 'unitary_dist')}), flush=True)
    f.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(f, index=False)
    print('wrote', f)


if __name__ == '__main__':
    main()
