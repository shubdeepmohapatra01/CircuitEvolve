"""The ONLY command the implementer agent may run (SPEC section 7). Read-only: same checks as admission.

    python -m v3.tools.test_rule rules/candidates/<name>.py [--target <label>]     -> JSON report on stdout

Runs the TARGET circuit first, then the small circuits (qft_8, adder_6, mult_4, modred_21), at eps 1e-3, and
stops at the first verification failure. The full suite runs only in admission (once per attempt).

Per circuit: fired?, #applications, #verified, first failure (circuit, match, method, distance), cost before /
after, qubits before / after, error bound; plus the decision admission would take. Moves nothing. Counts its own
calls per candidate (v3/results/test_rule_calls.json) and refuses after 5.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from ..paths import RESULTS
from .evaluate import evaluate

MAX_CALLS = 5
COUNTS = RESULTS / "test_rule_calls.json"


def main():
    args = sys.argv[1:]
    target = None
    if "--target" in args:
        i = args.index("--target")
        target = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        sys.exit("usage: python -m v3.tools.test_rule rules/candidates/<name>.py [--target <label>]")
    path = Path(args[0]).resolve()
    if path.parent.name != "candidates":
        sys.exit("test_rule only runs files in v3/rules/candidates/")
    counts = json.loads(COUNTS.read_text()) if COUNTS.exists() else {}
    key = f"{os.environ.get('V3_ATTEMPT_ID', 'manual')}:{path.name}"      # 5 calls per attempt step and file
    n = counts.get(key, 0)
    if n >= MAX_CALLS:
        print(json.dumps(dict(error=f"refused: test_rule already called {n} times for {path.name} (max {MAX_CALLS})")))
        sys.exit(2)
    counts[key] = n + 1
    RESULTS.mkdir(parents=True, exist_ok=True)
    COUNTS.write_text(json.dumps(counts, indent=1))
    rep = evaluate(path, eps=1e-3, target=target, small_only=True, stop_at_first_failure=True)
    rep["note"] = ("test_rule ran the target + small circuits only; admission runs the full suite and may still "
                   "find failures or improvements elsewhere")
    rep["call"] = n + 1
    print(json.dumps(rep, default=str, indent=1))


if __name__ == "__main__":
    main()
