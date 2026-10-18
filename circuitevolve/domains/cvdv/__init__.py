"""CV-DV certified-compiler domain (PLAN_P1 phase P1.3): package shim + plugin re-export.

Import mechanics (documented choice): the cvdv stack is a standalone sub-project at
<repo>/cvdv/src/cvdv and is deliberately NOT installed into the repo venv (it is frozen via
cvdv/FROZEN.sha256 and runs in its own conda env, cvdv-opt). Rather than packaging it — which
would mean touching the frozen sub-project — this package prepends <repo>/cvdv/src to sys.path
when `cvdv.evolve` is not already resolvable, the same shim cvdv/tests/test_acceptance.py and
cvdv/experiments/common.py use. The probe is for the SUBMODULE (not `import cvdv`): with the
repo root on sys.path, <repo>/cvdv is itself importable as an empty namespace-package portion
that would shadow a plain `import cvdv` probe; namespace `__path__` recomputation then picks up
the src portion once it is inserted. The cvdv modules themselves are imported UNCHANGED.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

CVDV_ROOT = Path(__file__).resolve().parents[3] / "cvdv"

try:  # pragma: no cover - trivial path shim
    _spec = importlib.util.find_spec("cvdv.evolve")
except Exception:  # noqa: BLE001 - any resolution failure means "not importable here"
    _spec = None
if _spec is None:
    sys.path.insert(0, str(CVDV_ROOT / "src"))
    importlib.invalidate_caches()

from .plugin import CvdvRulesPlugin, KindTask, benchmark_plugin  # noqa: E402,F401
