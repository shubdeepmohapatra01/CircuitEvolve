"""Exact gate-level Clifford+T baseline (see bygate_exact.py) + gridsynth at eps_rz.

Run: .venv/bin/python run_bygate_exact.py --tag NAME [--circuits add/add_17 ... | path.qasm]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd  # noqa: E402

from bygate_exact import lower_circuit, lower_circuit_paramzsx, lower_to_u3cx, ops_to_qasm, ops_unitary, tcount_ops  # noqa: E402
from common import EVAL, OUT, PUBLISHED_BYGATE, QASM, gridsynth_summary  # noqa: E402


def run_one(name, eps_rz, cache, method='minrz'):
    path = Path(name) if name.endswith('.qasm') else QASM / f'{name}.qasm'
    t0 = time.time()
    circ, lowering = lower_to_u3cx(path, OUT / 'work')
    ops, st = lower_circuit(circ) if method == 'minrz' else lower_circuit_paramzsx(circ)
    t_stage = time.time() - t0
    n = circ.num_qudits
    dist = None
    if n <= 10:
        import numpy as np
        A, B = np.asarray(ops_unitary(ops, n)), np.asarray(circ.get_unitary())
        tr = np.trace(B.conj().T @ A)
        dist = float(np.linalg.norm(A - tr / abs(tr) * B, 2))  # phase-aligned operator norm
    t_fixed, angles = tcount_ops(ops)
    t1 = time.time()
    gs = gridsynth_summary(angles, eps_rz, cache)
    short = path.stem
    (OUT / 'clifford_rz').mkdir(parents=True, exist_ok=True)
    (OUT / 'clifford_rz' / f'{short}_bygate_{method}.qasm').write_text(ops_to_qasm(ops, n))
    pub = PUBLISHED_BYGATE.get(short, {})
    tc = t_fixed + gs['gs_t']
    return dict(circuit=short, pipeline={'minrz': 'gate-level, min RZ per merged 1q run', 'paramzsx': 'gate-level, per-U3 parameter ZSX (paper convention)'}[method], lowering=lowering,
                eps_rz=eps_rz, qubits=n, cx=sum(1 for g, _, _ in ops if g == 'cx'),
                rz_count=len(angles), rz_distinct=gs['distinct_angles'], t_fixed=t_fixed,
                t_gridsynth=gs['gs_t'], t_count=tc,
                t_per_rz=round(gs['gs_t'] / max(1, len(angles)), 2),
                published_rz=pub.get('rz'), published_t=pub.get('t'),
                rz_diff_pct=round(100 * (len(angles) - pub['rz']) / pub['rz'], 2) if pub else None,
                t_diff_pct=round(100 * (tc - pub['t']) / pub['t'], 2) if pub else None,
                eps_total_bound=len(angles) * eps_rz, k_hist=json.dumps(st.get('k_hist')),
                rounded_angles=st['rounded_angles'], max_gridsynth_dist=gs['gs_max_dist'],
                cliffordrz_unitary_dist=dist, stage1_s=round(t_stage, 1),
                gridsynth_s=round(time.time() - t1, 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--circuits', nargs='*', default=EVAL)
    ap.add_argument('--eps-rz', type=float, default=1e-9)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--method', choices=['minrz', 'paramzsx'], default='minrz')
    a = ap.parse_args()
    f = OUT / f'{a.tag}.csv'
    assert not f.exists(), f'{f} exists; results are append-only'
    cache: dict = {}
    rows = []
    for name in a.circuits:
        r = run_one(name, a.eps_rz, cache, a.method)
        print(json.dumps({k: r[k] for k in ('circuit', 'rz_count', 'published_rz', 't_count',
                                             'published_t', 't_diff_pct', 'cliffordrz_unitary_dist')}),
              flush=True)
        rows.append(r)
    f.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(f, index=False)
    print('wrote', f)


if __name__ == '__main__':
    main()
