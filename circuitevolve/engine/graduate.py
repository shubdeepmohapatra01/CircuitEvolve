"""Graduated-rule library: formats, provenance schema, hash-checked loader (PLAN_P1 P1.4).

A graduated rule is a playbook rule that earned z-promotion and was reissued as EXECUTABLE code
(tier-2 DSL pattern for Clifford+T, a Python pass for parametric rules, a rulebook function for
CV-DV), verified ONCE by the frozen verifier, replayed on all dev circuits (kept iff the total
primary metric drops and no circuit rises), then frozen: the index and every referenced file are
hash-checked at load time. Authoring (the graduator LLM call) is point 2; in P1 the library is
EMPTY and loading it is a verified no-op.

Provenance chain (append-only): playbook rule id -> graduated entry -> this index.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ..blocks import REPO

INDEX = REPO / "playbooks" / "graduated" / "index.json"
KINDS = ("dsl", "pass", "cvdv_rule")


@dataclass(frozen=True)
class GraduatedRule:
    id: str
    family: str
    kind: str                 # one of KINDS
    path: str                 # repo-relative file holding the executable form
    sha256: str               # hash of that file at freeze time
    provenance_rule_id: str   # the playbook rule this graduated from
    verified_by: str          # frozen-verifier digest (16 hex) at verification time


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_index(path: Path | None = None) -> dict:
    p = Path(path or INDEX)
    idx = json.loads(p.read_text())
    assert idx["format"].startswith("circuitevolve.engine.graduated/"), "unknown graduated-index format"
    recorded = idx["index_sha256_of_entries"]
    actual = hashlib.sha256(json.dumps(idx["families"], sort_keys=True).encode()).hexdigest()
    if recorded != actual:
        raise RuntimeError("graduated index entries do not match their recorded hash — library tampered or corrupt")
    return idx


def load_graduated(family: str, path: Path | None = None) -> list[GraduatedRule]:
    """Hash-checked load of a family's graduated rules (empty list in P1)."""
    idx = load_index(path)
    rules = []
    for e in idx["families"].get(family, []):
        r = GraduatedRule(**e)
        assert r.kind in KINDS, f"unknown graduated kind {r.kind!r}"
        f = REPO / r.path
        if _sha256(f) != r.sha256:
            raise RuntimeError(f"graduated rule {r.id}: file {r.path} changed since freeze — refuse to load")
        rules.append(r)
    return rules


def apply_graduated(state, rules: list[GraduatedRule]):
    """Pre-optimization application. P1: the library is empty and this is the identity; the
    per-kind appliers (DSL matcher = v2/tier2 apply, pass import, cvdv rulebook) land with the
    first graduation (point 2)."""
    if rules:
        raise NotImplementedError("graduated-rule application lands with the first graduation (point 2)")
    return state
