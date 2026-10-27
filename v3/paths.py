"""Fixed locations used by every v3 tool (repo root, v3 folders, upstream sources)."""
from __future__ import annotations

from pathlib import Path

V3 = Path(__file__).resolve().parent
REPO = V3.parent
SUITE = V3 / "suite"
MANIFEST = SUITE / "manifest.json"
INPUTS = SUITE / "inputs"
BASELINES = V3 / "baselines"
BASELINES_CSV = BASELINES / "baselines.csv"
JUDGE = V3 / "judge"
FROZEN_FILE = JUDGE / "FROZEN.sha256"
RULES = V3 / "rules"
RESULTS = V3 / "results"
REPORT = V3 / "report"
CACHE = V3 / ".cache"

# environments (SPEC section 1.7)
DV_PY = REPO / ".venv" / "bin" / "python"
DPF_PY = REPO / "experiments" / "bqskit_baselines" / ".venv-dpf" / "bin" / "python"
CVDV_PY = Path.home() / ".claude-science" / "conda" / "envs" / "cvdv-opt" / "bin" / "python"
CVDV = REPO / "cvdv"
GENESIS = CVDV / "third_party" / "genesis"
