"""Frozen-file check: every v3 tool calls check_frozen() at start.

v3/judge/FROZEN.sha256 lists "<sha256>  <repo-relative path>" for the judge files, the suite manifest and inputs,
baselines.csv, and the upstream modules the judge wraps. A missing, extra-changed or unreadable file raises
FrozenError. Before the freeze at the end of P0 the file does not exist; only the P0 build scripts may run then,
by setting V3_PREFREEZE=1 (check_frozen() then returns without checking).
"""
from __future__ import annotations

import hashlib
import os

from ..paths import FROZEN_FILE, REPO


class FrozenError(RuntimeError):
    pass


def sha256(path) -> str:
    return hashlib.sha256((REPO / path).read_bytes()).hexdigest()


def read_list(path=FROZEN_FILE) -> dict:
    out = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            h, rel = line.split(None, 1)
            out[rel.strip()] = h
    return out


def check_frozen(path=FROZEN_FILE) -> int:
    """Raise FrozenError unless every listed file exists with its recorded hash. Returns #files checked."""
    if not path.exists():
        if os.environ.get("V3_PREFREEZE") == "1":
            return 0
        raise FrozenError(f"{path} missing: the judge is not frozen")
    bad = []
    files = read_list(path)
    for rel, h in files.items():
        p = REPO / rel
        if not p.is_file():
            bad.append(f"missing {rel}")
        elif sha256(rel) != h:
            bad.append(f"changed {rel}")
    if bad:
        raise FrozenError("frozen files modified: " + "; ".join(bad))
    return len(files)
