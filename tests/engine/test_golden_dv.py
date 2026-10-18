"""P1.2 equivalence gate: the engine path must reproduce the pre-refactor loop byte-for-byte.

golden_dv.json was generated at phase P1.0 with the original core/loop.py. This test re-runs the
identical scripted scenario through whatever core.loop.WindowLoop now is (post-P1.2: a shim over
circuitevolve.engine) and requires an identical behavior record — accept sequence, charges,
costs, ledger, stats, log structure, prompt hashes, verifier digest.
"""
from __future__ import annotations

import json

from .dv_golden_scenario import GOLDEN, run_scenario


def test_engine_reproduces_golden_run():
    assert GOLDEN.exists(), "golden fixture missing — see dv_golden_scenario.write_golden()"
    golden = json.loads(GOLDEN.read_text())
    now = json.loads(json.dumps(run_scenario(), sort_keys=True))  # normalize types like the fixture
    mismatches = {k: (golden[k], now[k]) for k in golden if golden[k] != now.get(k)}
    assert not mismatches, f"behavior drift vs pre-refactor golden run: {list(mismatches)}"
