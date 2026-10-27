"""B4 = R-DPF-PK sweep over (circuit, eps, K). One process per (circuit, eps); K run sequentially
inside it. Writes one JSON per cell to results/bqskit_baselines/stage1/b4/ (append-only: an existing
ok record is never overwritten)."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'stage1'))

KS = [3, 4, 5, 6, 7, 8, 9, 10]


def out_dir():
    from s1_common import OUT
    d = OUT / 'b4'
    d.mkdir(parents=True, exist_ok=True)
    return d


def job(name: str, eps: float):
    import dpf_pk
    from s1_common import eps_tag, short
    d = out_dir()
    res = []
    for K in KS:
        f = d / f'{short(name)}_B4k{K}_{eps_tag(eps)}.json'
        if f.exists() and json.loads(f.read_text()).get('status') == 'ok':
            res.append(json.loads(f.read_text()))
            continue
        t0 = time.time()
        try:
            r = dpf_pk.run_arm(name, eps, K)
            r['status'] = 'ok'
        except BaseException as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            r = dict(input=name, eps=eps, max_k=K, arm='B4', status='error',
                     error=f'{type(e).__name__}: {e}'[:400],
                     traceback=traceback.format_exc()[-2000:], wall_s=round(time.time() - t0, 1))
        f.write_text(json.dumps(r, indent=1, default=str))
        res.append(r)
        print(f'  {short(name):12s} eps={eps:g} K={K} -> '
              + (f"T={r['t_count']} anc={r['ancillas']} ({r['seconds_total']}s)"
                 if r['status'] == 'ok' else f"ERROR {r['error'][:80]}"), flush=True)
    ok = [r for r in res if r.get('status') == 'ok']
    if ok:
        b = min(ok, key=lambda r: r['t_count'])
        print(f'BEST {short(name)} eps={eps:g}: K={b["max_k"]} T={b["t_count"]} anc={b["ancillas"]}',
              flush=True)
    return res


def main():
    from multiprocessing import get_context
    from s1_common import CIRCUITS, EPS
    cells = [(n, e) for n in CIRCUITS for e in EPS]
    ctx = get_context('spawn')
    with ctx.Pool(processes=min(12, len(cells))) as pool:
        pool.starmap(job, cells)
    print('done', flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        job(sys.argv[1], float(sys.argv[2]))
    else:
        main()
