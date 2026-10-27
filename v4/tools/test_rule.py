"""The ONLY command the implementer agent may run. Read-only: the same checks as admission.

    python -m v4.tools.test_rule rules/candidates/<name>.py [--target <label>]    -> JSON on stdout

Runs the TARGET circuit first, then the small circuits, at eps 1e-3, stopping at the first verification
failure. Moves nothing. Counts its own calls per candidate and refuses after 5.
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
        target, args = args[i + 1], args[:i] + args[i + 2:]
    if len(args) != 1:
        sys.exit("usage: python -m v4.tools.test_rule rules/candidates/<name>.py [--target <label>]")
    path = Path(args[0]).resolve()
    if path.parent.name != "candidates":
        sys.exit("test_rule only runs files in v4/rules/candidates/")
    counts = json.loads(COUNTS.read_text()) if COUNTS.exists() else {}
    key = f"{os.environ.get('V4_ATTEMPT_ID', 'manual')}:{path.name}"
    n = counts.get(key, 0)
    if n >= MAX_CALLS:
        print(json.dumps(dict(error=f"refused: test_rule already called {n} times for {path.name} "
                                    f"(max {MAX_CALLS})")))
        sys.exit(2)
    counts[key] = n + 1
    COUNTS.write_text(json.dumps(counts, indent=1))
    rep = evaluate(path, target=target, small_only=True, stop_at_first_failure=True)
    rep["note"] = ("test_rule ran the target + small circuits only; admission runs the full suite. The "
                   "book's own result on each circuit is cached, so your rule was applied to the "
                   "circuit AFTER the book and only your own applications were verified.")
    rep["call"] = n + 1
    print(json.dumps(rep, default=str, indent=1))


if __name__ == "__main__":
    main()
