"""P0 gate: baselines.csv reproduces every expected baseline number below exactly; an empty-book run
returns the inputs unchanged with error 0; the judge hash check works.

    .venv/bin/python -m pytest -q v3/tests/test_p0.py
"""
from __future__ import annotations

import csv
import json
import subprocess

import pytest

from v3.judge import dv as J
from v3.judge.frozen import FrozenError, check_frozen, read_list, sha256
from v3.paths import BASELINES, BASELINES_CSV, CACHE, CVDV_PY, FROZEN_FILE, MANIFEST, REPO, V3
from v3.runner import optimize

# ---------------------------------------------------------------------------- expected baseline numbers, verbatim
ANGLE = {  # (label, eps): (TKET, pyzx, BQSKit-FT, BQSKit-DPF)
    ("qft_8", 1e-3): (2391, 1577, 2391, 2029), ("qft_8", 1e-5): (3299, 2219, 3299, 2866),
    ("qpe_8", 1e-3): (14761, 11485, 14761, 8020), ("qpe_8", 1e-5): (19853, 15651, 19853, 10391),
    ("hhl_8", 1e-3): (35450, 29205, 35450, 19443), ("hhl_8", 1e-5): (47228, 38987, 47228, 25043),
    ("qae_13", 1e-3): (7821, 4527, 7821, 6909), ("qae_13", 1e-5): (11017, 6361, 11017, 9237),
    ("tfim_6", 1e-3): (8560, 8560, 8560, 9600), ("tfim_6", 1e-5): (11840, 11840, 11840, 12400),
}
RECON = {"adder_8": (24, 361, 173), "adder_6": (14, 59, 47), "mult_4": (12, 96, 68), "mcx_10": (19, 192, 100),
         "modred_21": (11, 107, 73)}  # qubits, TKET (tket_fpo_logical), pyzx (pyzx_fr)
METHODS = ("TKET", "pyzx", "BQSKit-FT", "BQSKit-DPF")


@pytest.fixture(scope="module")
def rows():
    return list(csv.DictReader(open(BASELINES_CSV)))


def manifest():
    return json.loads(MANIFEST.read_text())["circuits"]


def bench(c, key):
    """The copy of a suite file in benchmarks/ (same bytes, named by label)."""
    fam = {"dv_angle": "dv_angle", "dv_recon": "dv_reconstruction/logical", "cvdv": "cvdv"}[c["family"]]
    if key == "bqskit_input":
        return f"benchmarks/dv_reconstruction/cliffordt/{c['label']}.qasm"
    if key == "spec":
        return f"benchmarks/cvdv/{c['label']}.ir.cvdvqasm"
    return f"benchmarks/{fam}/{c['label']}{'.ham' if c['family'] == 'cvdv' else '.qasm'}"


def test_manifest_inputs_match_hashes_and_benchmarks_folder():
    """Suite inputs match the manifest hashes (recorded from the original sources) and the benchmarks/ copies."""
    for c in manifest():
        assert sha256(V3.relative_to(REPO) / c["input"]) == c["sha256"] == sha256(bench(c, "input"))
        if "spec" in c:
            assert sha256(V3.relative_to(REPO) / c["spec"]) == c["spec_sha256"] == sha256(bench(c, "spec"))
        if "bqskit_input" in c:
            assert sha256(V3.relative_to(REPO) / c["bqskit_input"]) == c["bqskit_input_sha256"] == \
                sha256(bench(c, "bqskit_input"))
    assert len(manifest()) == 15


def test_dv_angle_baselines_exact(rows):
    for (lab, eps), want in ANGLE.items():
        for meth, w in zip(METHODS, want):
            hit = [r for r in rows if r["label"] == lab and r["method"] == meth and float(r["eps"]) == eps]
            assert len(hit) == 1 and int(hit[0]["t_count"]) == w, (lab, eps, meth, hit)


def test_dv_recon_baselines_exact(rows):
    for lab, (nq, tket, pyzx) in RECON.items():
        got = {r["method"]: r for r in rows if r["label"] == lab}
        assert int(got["TKET"]["t_count"]) == tket and int(got["pyzx"]["t_count"]) == pyzx, lab
        assert set(got) == set(METHODS), lab
        for m in METHODS:
            assert int(got[m]["qubits"]) == nq, (lab, m)
        for m in ("BQSKit-FT", "BQSKit-DPF"):     # new runs: valid Clifford+T outputs, recorded
            assert int(got[m]["t_count"]) > 0, (lab, m)


@pytest.mark.parametrize("c", [c for c in manifest() if c["domain"] == "dv"], ids=lambda c: c["label"])
def test_empty_book_returns_input_unchanged(c):
    circ = J.load(c["label"])
    before = circ.to_qasm() if hasattr(circ, "to_qasm") else repr(circ.gates)
    for eps in c["eps"]:
        r = optimize(circ, [], eps)
        assert r.circuit is circ and r.err_rules == 0.0 and r.log == [] and r.passes == 0
        assert (circ.to_qasm() if hasattr(circ, "to_qasm") else repr(circ.gates)) == before


def test_judge_metric_reproduces_tket_column():
    """Judge T-count of the unchanged TKET input == the TKET (B0) baseline, every angle circuit and eps."""
    for (lab, eps), want in ANGLE.items():
        assert J.measure(J.load(lab), eps)["t_count"] == want[0], (lab, eps)


def test_empty_book_cvdv_returns_spec():
    for c in manifest():
        if c["domain"] == "cvdv":
            from v3.api.cvdv import n_terms, start_circuit
            start = start_circuit(c["label"])           # ours starts from the spec: every IR term, in IR order
            assert start["ops"] == [{"term": k} for k in range(n_terms(c["label"]))]
            r = optimize(start, [], 0.0, domain="cvdv")
            assert r.circuit is start and r.err_rules == 0.0


# ---------------------------------------------------------------------------- hash check
def test_frozen_check_passes_and_covers_judge_suite_baselines():
    n = check_frozen()
    listed = read_list()
    assert n == len(listed) > 30
    for must in ("v3/judge/dv.py", "v3/judge/cvdv_worker.py", "v3/judge/frozen.py", "v3/suite/manifest.json",
                 "v3/baselines/baselines.csv", "circuitevolve/v2/verify.py", "cvdv/src/cvdv/sim.py"):
        assert must in listed, must


def test_frozen_check_detects_change_and_missing(tmp_path):
    work = CACHE / "frozen_selftest"
    work.mkdir(parents=True, exist_ok=True)
    f = work / "x.txt"
    f.write_text("original")
    lst = tmp_path / "FROZEN.sha256"
    lst.write_text(f"{sha256(f.relative_to(REPO))}  {f.relative_to(REPO)}\n")
    assert check_frozen(lst) == 1
    f.write_text("tampered")
    with pytest.raises(FrozenError, match="changed"):
        check_frozen(lst)
    f.unlink()
    with pytest.raises(FrozenError, match="missing"):
        check_frozen(lst)
    with pytest.raises(FrozenError, match="not frozen"):
        check_frozen(tmp_path / "absent.sha256")


def test_tools_refuse_when_judge_tampered(monkeypatch, tmp_path):
    """The runner (and everything calling check_frozen) refuses to run against a modified frozen list."""
    bad = tmp_path / "FROZEN.sha256"
    bad.write_text(FROZEN_FILE.read_text().replace(read_list()["v3/judge/dv.py"], "0" * 64))
    import v3.judge.frozen as F
    monkeypatch.setattr(F, "FROZEN_FILE", bad)
    monkeypatch.setattr(F.check_frozen, "__defaults__", (bad,))
    with pytest.raises(FrozenError):
        optimize(J.load("mult_4"), [], 1e-3)


# ---------------------------------------------------------------------------- CV-DV judge sanity
@pytest.mark.skipif(not CVDV_PY.exists() or not (REPO / "experiments" / "common.py").exists(),
                    reason="CV-DV is deferred: needs the cvdv-opt env and the cvdv compiler (experiments/), not shipped")
def test_cvdv_judge_positive_control():
    """A circuit known to implement the Trotter step (cvdv certified compiler, kerr_small) scores ~0."""
    out = CACHE / "control" / "kerr_small.cvdvqasm"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(CVDV_PY), str(V3 / "tests" / "cvdv_judge_control.py"), "kerr_small", str(out)], check=True,
                   capture_output=True)
    from v3.judge.cvdv_judge import judge
    r = judge("kerr_small", out, what=("errors",))
    assert r["cutoffs_agree"] and abs(r["err_trotter"]) < 1e-10 and abs(r["err_exact"]) < 1e-10
