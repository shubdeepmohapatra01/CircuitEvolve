"""Collect runs/*.json -> results/bqskit_baselines/stage1/stage1_baselines.csv (append-only: refuses
to overwrite; pass --tag to write stage1_baselines_<tag>.csv).

Error-bound columns follow the BQSKit convention (sum of per-stage bounds, each in the metric that
stage uses; see ERROR_ACCOUNTING.md):
  bound_round   rounding of near-Clifford+T Rz angles (RoundToDiscreteZPass), nominal (#events <= P+1)
  bound_dpf     Dyadic Phase Fixing acceptance thresholds summed over blocks (HS-type distance)
  bound_gs      gridsynth: N_Rz * per-Rz precision (operator norm)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pandas as pd  # noqa: E402

from s1_common import CIRCUITS, DPF_COMMIT, INPUTS, OUT, RUNS, short  # noqa: E402

ARMS = {
    'B0': ('TKET FullPeepholeOptimise + gridsynth (eps/N_Rz)', True),
    'B1': ('pyzx full_reduce on TKET input + gridsynth (eps/N_Rz)', True),
    'B2': ('BQSKit-FT CliffordRZ retarget (eps/(P+1)) + GridSynthPass (eps/N_Rz); paper "Baseline", no DPF', True),
    'B3': ('published alg_err_workflow.py (DPF k=3) as written; Clifford+T stage uses fixed 1e-4', True),
    'B2ft': ('[suppl.] branch default CliffordTModel(algorithmic_error=eps) compile (contains DPF k=3, ZXZXZ)', False),
    'B3m': ('[suppl.] alg_err_workflow functions, budget split 0.4/0.2 eps so code-accounted total <= eps', False),
    'B3g': ('[suppl.] alg_err_workflow.full_rz_compile(0.4 eps) then GridSynthPass(0.4 eps); no 2nd CliffordTModel stage', False),
}


def bounds(arm, eps, r):
    """(bound_round, bound_dpf, bound_gs, total, note)."""
    gs_ae = r.get('gridsynth_algorithmic_error')
    if arm in ('B0', 'B1'):
        gs = r['n_rz'] * r['eps_per_rz'] if r['n_rz'] else 0.0
        return 0.0, 0.0, gs, gs, 'operator norm; triangle inequality over N_Rz gridsynth approximations'
    if arm == 'B2':
        rd = 0.5 * eps
        return rd, 0.0, gs_ae, rd + gs_ae, 'rounding nominal (realized ~1e-14, see state_dist_input_vs_cliffrz)'
    if arm == 'B2ft':
        ae = r['log']['assign_errors'][-1]['algorithmic_error'] if r['log']['assign_errors'] else eps
        return float('nan'), ae, gs_ae, ae + gs_ae, ('+ per-block rounding (threshold eps/B per event, '
                                                       'count not bounded by code); DPF bound is HS-type')
    if arm == 'B3':
        aeC = r['log']['assign_errors'][-1]['algorithmic_error']
        rd = 0.5 * eps
        return rd, eps + aeC, gs_ae, rd + eps + aeC + gs_ae, (
            f'stage-C (CliffordTModel) uses its default algorithmic_error={aeC:g} regardless of eps '
            '(err_per_gate argument is ignored); + stage-C rounding (count not bounded)')
    if arm == 'B3m':
        aeC = r['log']['assign_errors'][-1]['algorithmic_error']
        rd = 0.5 * 0.4 * eps
        return rd, 0.4 * eps + aeC, gs_ae, rd + 0.4 * eps + aeC + gs_ae, '+ stage-C rounding (count not bounded)'
    if arm == 'B3g':
        rd = 0.5 * 0.4 * eps
        return rd, 0.4 * eps, gs_ae, rd + 0.4 * eps + gs_ae, 'rounding nominal'
    raise ValueError(arm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', default='')
    a = ap.parse_args()
    man = pd.read_csv(INPUTS / 'inputs_manifest.csv').set_index('circuit')
    rows = []
    for f in sorted(RUNS.glob('*.json')):
        if '.failed_' in f.name:
            continue
        r = json.loads(f.read_text())
        arm, eps = r['arm'], float(r['eps'])
        desc, primary = ARMS[arm]
        row = dict(circuit=r['circuit'], qubits=int(man.loc[r['circuit'], 'qubits']), eps_total=eps, arm=arm,
                   primary_arm=primary, status=r['status'])
        if r['status'] == 'ok':
            br, bd, bg, bt, note = bounds(arm, eps, r)
            after = (r.get('stages') or {}).get('after_dpf') or {}
            row.update(t_count=int(r['t_count']), nonclifford_rotations=r['n_rz'],
                       rz_after_dpf=after.get('rz'), cx=int(r['cx']), eps_per_rz=r['eps_per_rz'],
                       bound_round=br, bound_dpf=bd, bound_gs=bg, err_bound_total=bt,
                       bound_over_eps=bt / eps, state_dist_vs_orig=r['state_dist_vs_orig'],
                       state_dist_vs_input=r['state_dist_vs_input'],
                       measured_within_eps=bool(r['state_dist_vs_orig'] <= eps),
                       runtime_s=r['runtime_s'], bound_note=note)
            if 'log' in r and r['log'].get('gridsynth_panic_retries'):
                row['bound_note'] += f"; rsgridsynth panic retried mod 2pi x{len(r['log']['gridsynth_panic_retries'])}"
        else:
            row['error'] = r.get('error')
        row['arm_desc'] = desc
        rows.append(row)
    df = pd.DataFrame(rows)
    order = {short(c): i for i, c in enumerate(CIRCUITS)}
    arm_order = {k: i for i, k in enumerate(ARMS)}
    df = df.sort_values(by=['circuit', 'eps_total', 'arm'], key=lambda s: s.map(order) if s.name == 'circuit'
                        else (s.map(arm_order) if s.name == 'arm' else -s)).reset_index(drop=True)
    ok = df[df.status == 'ok']
    for (c, e), g in ok.groupby(['circuit', 'eps_total']):
        t = g.set_index('arm')['t_count']
        best = t[[k for k in ('B0', 'B1', 'B2', 'B3') if k in t.index]].min()
        idx = (df.circuit == c) & (df.eps_total == e)
        df.loc[idx, 't_vs_B0_pct'] = 100 * (df.loc[idx, 't_count'] / t['B0'] - 1) if 'B0' in t else None
        df.loc[idx, 't_vs_B2_pct'] = 100 * (df.loc[idx, 't_count'] / t['B2'] - 1) if 'B2' in t else None
        df.loc[idx, 'best_B0_B3_t'] = best
    df['gridsynth'] = 'rsgridsynth v1.0.0 (bff24e2)'
    df['bqskit_ft_commit'] = DPF_COMMIT
    f = OUT / (f'stage1_baselines_{a.tag}.csv' if a.tag else 'stage1_baselines.csv')
    assert not f.exists(), f'{f} exists (append-only)'
    df.to_csv(f, index=False)
    print(f, len(df), 'rows;', (df.status == 'ok').sum(), 'ok')


if __name__ == '__main__':
    main()
