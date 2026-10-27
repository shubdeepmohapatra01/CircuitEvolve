"""BQSKit's DPF Synth (phase-kickback, the "B4 / DPF Synth" arm): CliffordRZ retarget ->
partition -> GreedyNTRO -> ConvertToPKAC -> UnfoldPass, stopped BEFORE the final gridsynth
of the residual rz gates. Runs in experiments/bqskit_baselines/.venv-pk (bqskit-ft,
separate Python 3.12) via subprocess; QASM in, QASM (+ metadata) out through
experiments/bqskit_baselines/pk/dpf_pre_gridsynth.py.

Error budget: eps_total is split eps_used = DPF_FRACTION * eps_total for the
DPF/GreedyNTRO/PKAC retarget stage (the fraction the paper's B4 script itself gives that
stage, see dpf_pk.py's run_arm); the caller still owes gridsynth(eps_total - eps_used) on
the rz gates this function leaves behind, so the two stages fully account eps_total (no
slack dropped, unlike the original B4 script's 20% unaccounted margin).

k / seed defaults: looked up in baselines/b4_dpf_synth.csv (the stored best-of-5-seeds
sweep) by `label` at the nearest eps, when a label is given and k is not; else k falls
back to the k_reg of that file's lowest-t_count row at the nearest eps. `seed` has no
"unset" sentinel in the given signature, so seed=0 (its default) is treated as "use the
file's seed_best when label matches" -- pass an explicit seed to override.
"""
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

from circuitevolve.circuit import Circuit, from_qasm, to_qasm

REPO = Path(__file__).resolve().parent.parent
DRIVER = REPO / 'experiments' / 'bqskit_baselines' / 'pk' / 'dpf_pre_gridsynth.py'
PK_PYTHON = REPO / 'experiments' / 'bqskit_baselines' / '.venv-pk' / 'bin' / 'python'
CSV_PATH = REPO / 'baselines' / 'b4_dpf_synth.csv'
DPF_FRACTION = 0.4


def _defaults(label: str | None, eps_total: float) -> tuple[int, int | None]:
    """(k, seed_best) from b4_dpf_synth.csv: match `label` at the nearest eps, else fall
    back to k_reg of the file's lowest-t_count row at that eps (seed left as None)."""
    if not CSV_PATH.exists():
        return 7, None
    with open(CSV_PATH) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return 7, None
    rows.sort(key=lambda r: abs(float(r['eps']) - eps_total))
    near_eps = float(rows[0]['eps'])
    pool = [r for r in rows if float(r['eps']) == near_eps]
    if label:
        for r in pool:
            if r['label'] == label:
                return int(r['k_reg']), int(r['seed_best'])
    best = min(pool, key=lambda r: int(r['t_count']))
    return int(best['k_reg']), None


def dpf(c: Circuit, eps_total: float, k: int | None = None, seed: int = 0,
        label: str | None = None, timeout: float = 600.0) -> tuple[Circuit, float]:
    """Run the DPF Synth arm on `c`, stopping just before the final gridsynth of the
    residual rz gates. Returns (circuit_in_our_gate_set, eps_used): eps_used is the error
    budget consumed by the DPF/GreedyNTRO/PKAC retarget; gridsynth(eps_total - eps_used)
    on the surviving rz gates is still owed by the caller."""
    k_default, seed_default = _defaults(label, eps_total)
    k = k if k is not None else k_default
    if seed == 0 and seed_default is not None:
        seed = seed_default
    eps_used = DPF_FRACTION * eps_total

    proc = subprocess.run(
        [str(PK_PYTHON), str(DRIVER), '--k', str(k), '--seed', str(seed), '--eps', str(eps_used)],
        input=to_qasm(c), capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f'dpf driver failed (rc={proc.returncode}):\n{proc.stderr[-4000:]}')
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    if payload['unlowered']:
        raise RuntimeError(f"dpf output has gates outside our gate set: {payload['unlowered']}")
    return from_qasm(payload['qasm']), eps_used
