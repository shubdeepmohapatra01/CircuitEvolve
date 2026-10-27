"""CV-DV judge client (FROZEN): runs v3/judge/cvdv_worker.py in env cvdv-opt via subprocess (SPEC 1.7).

    judge(label, circuit_path, mapping=None, what=("metrics",)) -> dict

`metrics` = Genesis metrics (1-op, 2-op, total, duration); `errors` = err_trotter / err_exact per cutoff
(see cvdv_worker.py for the exact definitions and probe protocol).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..paths import CVDV_PY
from .frozen import check_frozen

WORKER = Path(__file__).resolve().parent / "cvdv_worker.py"


def judge(label: str, circuit, mapping=None, what=("metrics",), timeout: float | None = None,
          reference=None) -> dict:
    """reference: optional circuit file; then errors = err_ref (circuit vs reference on the probe subspace of the
    reference's wires, probe parameters of `label`) instead of err_trotter / err_exact."""
    check_frozen()
    req = dict(label=label, circuit=str(Path(circuit).resolve()), what=list(what))
    if reference is not None:
        req["reference"] = str(Path(reference).resolve())
    if mapping is not None and Path(mapping).exists():
        req["mapping"] = str(Path(mapping).resolve())
    p = subprocess.run([str(CVDV_PY), str(WORKER), json.dumps(req)], capture_output=True, text=True,
                       timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"cvdv judge failed ({p.returncode}): {p.stderr[-2000:]}")
    return json.loads(p.stdout.strip().splitlines()[-1])
