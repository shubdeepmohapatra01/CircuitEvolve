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
    evidence: str = ""        # measured support (z-promotion stats OR documented override)


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


def load_callable(rule: GraduatedRule):
    """Hash-checked import of a graduated pass module -> its apply_pass callable. The file was
    already re-hashed by load_graduated; re-check here so a direct caller cannot skip it."""
    import importlib.util

    f = REPO / rule.path
    if _sha256(f) != rule.sha256:
        raise RuntimeError(f"graduated rule {rule.id}: file {rule.path} changed since freeze — refuse to load")
    spec = importlib.util.spec_from_file_location(f"graduated_{rule.id}", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.apply_pass


def apply_graduated(state, rules: list[GraduatedRule], n: int | None = None):
    """Pre-optimization application -> (state, reports). kind='pass': hash-checked import, call
    apply_pass(state, n); the pass itself re-verifies every application through the frozen
    verifier. Other kinds land with their first graduation."""
    reports = []
    for r in rules:
        if r.kind == "pass":
            assert n is not None, "kind='pass' needs the qubit count"
            state, rep = load_callable(r)(state, n)
            rep["id"] = r.id
            reports.append(rep)
        else:
            raise NotImplementedError(f"graduated kind {r.kind!r}: applier lands with its first graduation")
    return state, reports


def promote(family: str, provenance_rule_id: str, kind: str, path: str, verified_by: str,
            evidence: str, rule_status: str, index_path: Path | None = None) -> GraduatedRule:
    """Freeze an executable rule into the graduated index (PLAN_P2 P2.3).

    Normal route: the prose rule earned status='active' (z-promotion) in a campaign. A rule
    still 'candidate' may ONLY be promoted with a non-empty `evidence` string documenting
    independent measured support (e.g. the ablation control arm) — the override is recorded
    verbatim in the entry; silent promotion of unproven rules is refused."""
    assert kind in KINDS, f"unknown graduated kind {kind!r}"
    if rule_status != "active" and not evidence.strip():
        raise ValueError("refusing to graduate a non-active rule without documented evidence")
    p = Path(index_path or INDEX)
    idx = load_index(p)
    fams = idx["families"]
    entries = fams.setdefault(family, [])
    gid = f"G{sum(len(v) for v in fams.values()) + 1}"
    entry = GraduatedRule(id=gid, family=family, kind=kind, path=path,
                          sha256=_sha256(REPO / path), provenance_rule_id=provenance_rule_id,
                          verified_by=verified_by, evidence=evidence)
    entries.append(dict(entry.__dict__))
    idx["index_sha256_of_entries"] = hashlib.sha256(json.dumps(fams, sort_keys=True).encode()).hexdigest()
    p.write_text(json.dumps(idx, indent=1) + "\n")
    return entry
