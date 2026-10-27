"""Fixed locations for v4. The suite, the inputs and the frozen upstream modules stay where v3 put them."""
from __future__ import annotations

from pathlib import Path

from v3.paths import (BASELINES_CSV, CVDV_PY, DV_PY, FROZEN_FILE, INPUTS, MANIFEST, REPO,  # noqa: F401
                      SUITE, V3)

V4 = Path(__file__).resolve().parent
RULES = V4 / "rules"
FLOOR = RULES / "floor"
ACCEPTED = RULES / "accepted"
CANDIDATES = RULES / "candidates"
RESULTS = V4 / "results"
CACHE = V4 / ".cache"
AGENT = V4 / "agent"
BOOK_MD = RULES / "BOOK.md"
B4_CSV = REPO / "b4_baseline.csv"          # the DPF Synth arm (section 3)
PK_DIR = REPO / "experiments" / "bqskit_baselines" / "pk"

for d in (RESULTS, CACHE):
    d.mkdir(parents=True, exist_ok=True)
