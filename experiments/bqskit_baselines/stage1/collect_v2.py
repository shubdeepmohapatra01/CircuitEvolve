"""Final stage-1 table: results/bqskit_baselines/stage1/stage1_baselines_v2.csv (append-only).

Rows: B0/B1 from runs/ (deterministic compilers), B2/B3/B2ft/B3m/B3g from runs_v2/ (re-run with the
pre-gridsynth dump), joined with runs_v2/canonical/ (pygridsynth recount) and, for BQSKit arms, the first-pass
as-run T from runs/ (shows run-to-run variation of the stochastic BQSKit instantiation + rsgridsynth).

Primary comparison column: t_count_canon (pygridsynth, same N_Rz and per-Rz eps as the arm used).
Run: .venv-dpf/bin/python stage1/collect_v2.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pandas as pd  # noqa: E402

from collect import ARMS, bounds  # noqa: E402
from s1_common import CIRCUITS, DPF_COMMIT, EPS, INPUTS, OUT, eps_tag, short  # noqa: E402

R1, R2 = OUT / 'runs', OUT / 'runs_v2'


def main():
    man = pd.read_csv(INPUTS / 'inputs_manifest.csv').set_index('circuit')
    rows = []
    for name in CIRCUITS:
        c = short(name)
        for eps in EPS:
            for arm in ARMS:
                tag = f'{c}_{arm}_{eps_tag(eps)}'
                src = (R1 if arm in ('B0', 'B1') else R2) / f'{tag}.json'
                r = json.loads(src.read_text())
                assert r['status'] == 'ok', tag
                can = json.loads((R2 / 'canonical' / f'{tag}.json').read_text())
                br, bd, bg, bt, note = bounds(arm, eps, r)
                after = (r.get('stages') or {}).get('after_dpf') or {}
                desc, primary = ARMS[arm]
                row = dict(circuit=c, qubits=int(man.loc[c, 'qubits']), eps_total=eps, arm=arm, primary_arm=primary,
                           t_count_canon=can['t_count_canon'], t_count_asrun=r['t_count'],
                           nonclifford_rotations=can['n_rz_canon'], gridsynth_calls_asrun=r['n_rz'],
                           rz_after_dpf=after.get('rz'), cx=int(r['cx']), eps_per_rz=r['eps_per_rz'],
                           bound_round=br, bound_dpf=bd, bound_gs=bg, err_bound_total=bt, bound_over_eps=bt / eps,
                           state_dist_vs_orig_canon=can['state_dist_vs_orig_canon'],
                           state_dist_vs_orig_asrun=r['state_dist_vs_orig'],
                           measured_within_eps=bool(max(can['state_dist_vs_orig_canon'], r['state_dist_vs_orig']) <= eps),
                           runtime_s=r['runtime_s'], source_run=src.parent.name)
                if arm not in ('B0', 'B1'):
                    f1 = R1 / f'{tag}.json'
                    if f1.exists():
                        r1 = json.loads(f1.read_text())
                        if r1['status'] == 'ok':
                            row['t_count_asrun_firstpass'] = r1['t_count']
                            row['gridsynth_calls_firstpass'] = r1['n_rz']
                pr = (r.get('log') or {}).get('gridsynth_panic_retries')
                if pr:
                    note += f'; rsgridsynth panic x{len(pr)} resolved by identical call in fresh process'
                row['bound_note'] = note
                row['arm_desc'] = desc
                rows.append(row)
    df = pd.DataFrame(rows)
    for (c, e), g in df.groupby(['circuit', 'eps_total'], sort=False):
        t = g.set_index('arm')['t_count_canon']
        idx = (df.circuit == c) & (df.eps_total == e)
        best = t[['B0', 'B1', 'B2', 'B3']].min()
        df.loc[idx, 'best_B0_B3_canon'] = best
        df.loc[idx, 'best_B0_B3_arm'] = t[['B0', 'B1', 'B2', 'B3']].idxmin()
        df.loc[idx, 'canon_vs_B2_pct'] = (100 * (df.loc[idx, 't_count_canon'] / t['B2'] - 1)).round(1)
        df.loc[idx, 'canon_vs_best_B0_B3_pct'] = (100 * (df.loc[idx, 't_count_canon'] / best - 1)).round(1)
    df['gridsynth_asrun'] = 'rsgridsynth v1.0.0 (bff24e2)'
    df['gridsynth_canon'] = 'pygridsynth 2.0.0'
    df['bqskit_ft_commit'] = DPF_COMMIT
    f = OUT / 'stage1_baselines_v2.csv'
    assert not f.exists(), f'{f} exists (append-only)'
    df.to_csv(f, index=False)
    print(f, len(df))


if __name__ == '__main__':
    main()
