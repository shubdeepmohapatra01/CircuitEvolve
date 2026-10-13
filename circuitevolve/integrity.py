"""Integrity guard for the frozen verifier (CLAUDE.md invariant 4).

Self-evolving parts of the harness (the playbook, and later any evolved search code) may change
between runs. The files that decide ACCEPT may not. `frozen_digest()` hashes them; search loops record
the digest at start and assert it is unchanged at the end, so a run in which anything edited the
verifier is detected rather than silently reported.
"""
from __future__ import annotations

import hashlib
import pathlib

PKG = pathlib.Path(__file__).resolve().parent
FROZEN = ("ir.py", "ring.py", "sim.py", "spec.py", "verify.py", "cost.py", "acceptance.py",
          # approximate verification mode for continuous-angle blocks (CLAUDE.md invariant 1)
          "blocks/verify_block.py")


def frozen_digest() -> str:
    h = hashlib.sha256()
    for name in FROZEN:
        h.update(name.encode())
        h.update((PKG / name).read_bytes())
    return h.hexdigest()


class IntegrityError(RuntimeError):
    pass


def check_unchanged(digest_at_start: str) -> None:
    now = frozen_digest()
    if now != digest_at_start:
        raise IntegrityError("frozen verifier files changed during the run; results are invalid")
