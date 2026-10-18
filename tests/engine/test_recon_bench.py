"""P3.1 gate: the recon_bench suite reproduces deterministically from its committed inputs.

Re-runs the v2 recognizer on two suite circuits and compares the feature evidence byte-for-
byte with results/engine/recon_bench/MANIFEST.json; checks twin files against their recorded
sha256; checks baselines.csv shape. The whole-repo no-modification guard is
tests/engine/test_manifest.py (unchanged).
"""
from __future__ import annotations

import csv
import hashlib
import json

from circuitevolve.blocks import REPO

RB = REPO / "results" / "engine" / "recon_bench"
MANIFEST = json.loads((RB / "MANIFEST.json").read_text())
BY_NAME = {e["name"]: e for e in MANIFEST["circuits"]}


def _features(name: str) -> dict:
    import sys
    sys.path.insert(0, str(REPO / "experiments"))
    from engine_recon_bench import features_from_summary
    from circuitevolve.v2.tier1.recognize import load_logical, summarize
    rows = list(csv.DictReader(open(REPO / "benchmarks" / "nam_arith" / "MANIFEST.csv")))
    row = next(r for r in rows if r["name"] == name)
    dz = [int(x) for x in str(row.get("zero_init_qubits") or "").split()]
    _, lc = load_logical(REPO / "benchmarks" / "nam_arith" / row["logical_path"], name=name)
    return features_from_summary(summarize(lc, declared_zero=dz, name=name))


def test_features_reproduce_cuccaro_4():
    assert _features("cuccaro_4") == BY_NAME["cuccaro_4"]["features"]


def test_features_reproduce_rc_adder_6():
    assert _features("rc_adder_6") == BY_NAME["rc_adder_6"]["features"]


def test_suite_membership_and_split():
    kept = [e["name"] for e in MANIFEST["circuits"] if e["kept"]]
    assert sorted(kept) == sorted(MANIFEST["dev"] + MANIFEST["held_out"])
    for e in MANIFEST["circuits"]:
        if e["kept"]:
            assert e["fires"], e["name"]
            assert e["split"] in ("dev", "held-out")


def test_twins_exist_and_match_sha256():
    for e in MANIFEST["circuits"]:
        if not e["kept"]:
            continue
        tw = REPO / e["twin"]["path"]
        assert tw.exists(), e["name"]
        assert hashlib.sha256(tw.read_bytes()).hexdigest() == e["twin"]["sha256"], e["name"]
        assert e["twin"]["sparse_check_ok"] is True, e["name"]


def test_sources_match_sha256():
    for e in MANIFEST["circuits"]:
        src = REPO / e["source"]
        assert hashlib.sha256(src.read_bytes()).hexdigest() == e["source_sha256"], e["name"]


def test_baselines_rows():
    rows = list(csv.DictReader(open(RB / "baselines.csv")))
    for name in ("cuccaro_4", "adder_8"):
        arms = {r["arm"] for r in rows if r["circuit"] == name}
        assert {"naive_T", "B0_tket", "B1_pyzx", "control_exact", "control_relaxed"} <= arms, name
    # the relaxed column is separate: every control_relaxed row says so
    for r in rows:
        if r["arm"] == "control_relaxed":
            assert r["contract"] == "relaxed"
        if r["arm"] in ("naive_T", "B0_tket", "B1_pyzx", "control_exact"):
            assert r["contract"] == "exact"
