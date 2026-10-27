"""Frozen-file check, ONCE PER PROCESS (V4_README section 6.4).

v3 called `check_frozen()` inside every `optimize()` and every `verify()`: it re-reads and SHA-256s 52 files,
299 KB, measured at 3.303 ms per call, against 0.421 ms for the window comparison it guards. The files cannot
change inside one process without something having already imported them, so once at process start plus once at
the end of a run is the same guarantee at 1/N the cost.

    check_frozen()          -> #files checked (0 on the 2nd..nth call in this process)
    recheck_frozen()        -> force a re-read (call at the END of a run, before writing results)
    frozen_state()          -> {'checked': bool, 'files': int, 'seconds': float}
"""
from __future__ import annotations

import time

from v3.judge.frozen import FrozenError, check_frozen as _v3_check_frozen, read_list, sha256  # noqa: F401

_STATE: dict = dict(checked=False, files=0, seconds=0.0, calls=0)


def check_frozen(path=None) -> int:
    """Check the frozen list once per process. Later calls are free and return 0."""
    _STATE["calls"] += 1
    if _STATE["checked"]:
        return 0
    t0 = time.perf_counter()
    n = _v3_check_frozen() if path is None else _v3_check_frozen(path)
    _STATE.update(checked=True, files=n, seconds=time.perf_counter() - t0)
    return n


def recheck_frozen(path=None) -> int:
    """Force a fresh check (end of a run, or after anything that could have touched the tree)."""
    _STATE["checked"] = False
    return check_frozen(path)


def frozen_state() -> dict:
    return dict(_STATE)
