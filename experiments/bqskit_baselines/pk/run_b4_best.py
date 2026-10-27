"""B4 best-of-N-seeds. GreedyNTROPass re-instantiates angles numerically (multistarts=4), so the arm
is STOCHASTIC: measured spread on qft_8 eps=1e-3 over 5 runs is 2 T at K=3 (0.1%) but 104 T at K=8
(9.8%). Single runs are therefore not reportable. We take best-of-5 seeds per (circuit, eps, K) and
then the best over K, mirroring SPEC section 3c's Genesis convention ("5 seeds and keep the best").

IMPORTANT: each worker seeds numpy explicitly. Without that, spawned processes all start from the
same default RNG state and would return five identical "seeds".

K range per circuit comes from the exhaustive single-run sweep in ../b4/ (K=3..10 everywhere):
circuits whose T rises monotonically with K only need the low-K end re-run with seeds.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'stage1'))

SEEDS = [0, 1, 2, 3, 4]
KS_BY_CIRCUIT = {           # from the b4/ single-run sweep
    'qft/qft_8':             [3, 4, 5, 6, 7, 8, 9, 10],
    'qae/qae_13':            [3, 4, 5, 6, 7, 8, 9, 10],
    'tfim/tfim_6':           [3, 4, 5, 6, 7, 8, 9, 10],
    'heisenberg/heisenberg_6': [3, 4, 5, 6, 7, 8, 9, 10],
    'hubbard/hubbard_8':     [3, 4, 5, 6, 7, 8, 9, 10],
    'qml/qml_13':            [3, 4, 5, 6, 7, 8, 9, 10],
    'qpe/qpe_8':             [3, 4, 5],      # T rises monotonically for K >= 5
    'hhl/hhl_8':             [3, 4],         # T rises monotonically for K >= 4
}


def out_dir():
    from s1_common import OUT
    d = OUT / 'b4_best'
    d.mkdir(parents=True, exist_ok=True)
    return d


def cell(name: str, eps: float, K: int, seed: int):
    import numpy as np
    from s1_common import eps_tag, short
    d = out_dir()
    f = d / f'{short(name)}_B4k{K}_s{seed}_{eps_tag(eps)}.json'
    if f.exists() and json.loads(f.read_text()).get('status') == 'ok':
        return json.loads(f.read_text())
    np.random.seed(seed)                       # see module docstring
    import dpf_pk
    t0 = time.time()
    try:
        r = dpf_pk.run_arm(name, eps, K)
        r.update(status='ok', seed=seed)
    except BaseException as e:
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        r = dict(input=name, eps=eps, max_k=K, seed=seed, arm='B4', status='error',
                 error=f'{type(e).__name__}: {e}'[:400],
                 traceback=traceback.format_exc()[-1500:], wall_s=round(time.time() - t0, 1))
    f.write_text(json.dumps(r, indent=1, default=str))
    print(f"  {short(name):12s} eps={eps:g} K={K} s={seed} -> "
          + (f"T={r['t_count']} anc={r['ancillas']} ({r['seconds_total']}s)"
             if r['status'] == 'ok' else f"ERROR {str(r['error'])[:70]}"), flush=True)
    return r


def main():
    from multiprocessing import get_context
    from s1_common import EPS
    cells = [(n, e, K, s) for n, Ks in KS_BY_CIRCUIT.items()
             for e in EPS for K in Ks for s in SEEDS]
    # longest circuits first so the tail does not serialise
    order = {'hhl/hhl_8': 0, 'qpe/qpe_8': 1}
    cells.sort(key=lambda c: order.get(c[0], 9))
    print(f'{len(cells)} cells', flush=True)
    ctx = get_context('spawn')
    with ctx.Pool(processes=12) as pool:
        pool.starmap(cell, cells, chunksize=1)
    print('done', flush=True)


if __name__ == '__main__':
    main()
