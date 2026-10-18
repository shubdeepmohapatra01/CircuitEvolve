"""Permanent guard: no refactor step may change a baseline file (PLAN_P1 phase P1.0).

Re-hashes every file recorded in results/engine/BASELINE_MANIFEST.json and re-checks the
frozen-verifier digests of both stacks. If this test goes red, a baseline result was touched
and must be restored from git — never regenerated.
"""
from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = REPO / "results" / "engine" / "BASELINE_MANIFEST.json"


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="module")
def manifest() -> dict:
    assert MANIFEST.exists(), "baseline manifest missing — run experiments/engine_baseline_manifest.py"
    return json.loads(MANIFEST.read_text())


def test_manifest_format(manifest):
    assert manifest["format"] == "circuitevolve.engine.baseline_manifest/1"
    assert manifest["n_files"] == len(manifest["files"]) > 100


def test_every_baseline_file_unchanged(manifest):
    missing, changed = [], []
    for rel, entry in manifest["files"].items():
        p = REPO / rel
        if not p.is_file():
            missing.append(rel)
        elif _sha256(p) != entry["sha256"]:
            changed.append(rel)
    assert not missing, f"baseline files MISSING ({len(missing)}): {missing[:10]}"
    assert not changed, f"baseline files CHANGED ({len(changed)}): {changed[:10]}"


def test_dv_frozen_digest_unchanged(manifest):
    from circuitevolve import integrity

    assert integrity.frozen_digest() == manifest["dv_frozen_digest"]


def test_cvdv_frozen_list_unchanged(manifest):
    assert _sha256(REPO / "cvdv" / "FROZEN.sha256") == manifest["cvdv_frozen_sha256_file"]
    # verify the listed hashes themselves (same check as cvdv/scripts/check_frozen.sh, in-process)
    for line in (REPO / "cvdv" / "FROZEN.sha256").read_text().splitlines():
        digest, _, rel = line.strip().partition("  ")
        assert _sha256(REPO / "cvdv" / rel) == digest, f"cvdv frozen file changed: {rel}"
