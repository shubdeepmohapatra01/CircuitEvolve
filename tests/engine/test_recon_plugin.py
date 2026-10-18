"""P3.3 gates: the reconstruction plugin (v2/tier1 behind the DomainPlugin contract).

(a) scripted control-route plans through the ENGINE loop reproduce the v2 deterministic-
    control numbers (equal T, qubits) on 4 suite circuits; (b) a zero-accept run returns the
    input unchanged; (d) frozen digests unchanged (test_manifest + integrity, suite-wide).
The cascade e2e gate (c) lives in test_cascade.py."""
from __future__ import annotations

import csv

import pytest

from circuitevolve.blocks import REPO
from circuitevolve.engine.run import optimize
from circuitevolve.v2.tier1.control import control_plans
from circuitevolve.v2.tier1.recognize import load_logical, summarize

MANIFEST = {r["name"]: r for r in csv.DictReader(open(REPO / "benchmarks" / "nam_arith" / "MANIFEST.csv"))}
DEV_CSV = REPO / "results" / "v2" / "tier1" / "dev_results.csv"
BUDGET = 4                     # control ORDER prefix (V1..V4 + pyzx) covers every dev best row


def _circ(name: str):
    row = MANIFEST[name]
    dz = [int(x) for x in str(row.get("zero_init_qubits") or "").split()]
    path = REPO / "benchmarks" / "nam_arith" / row["logical_path"]
    _, lc = load_logical(str(path), name=name)
    return path, lc, summarize(lc, declared_zero=dz, name=name), dz


def _scripted(plans):
    it = iter(plans)

    def complete(prompts):
        return [next(it, "NONE") for _ in prompts]
    return complete


def _v2_best(name: str) -> tuple:
    """Best (t_count, qubits) over the recorded v2 control rows (both contracts)."""
    best = None
    for r in csv.DictReader(open(DEV_CSV)):
        if r["circuit"] == name and r["arm"] == "control" and r.get("ok") == "True":
            key = (int(float(r["t_count"])), int(float(r["qubits"])))
            best = key if best is None or key < best else best
    assert best is not None
    return best


@pytest.mark.parametrize("name", ["cuccaro_4", "rc_adder_6", "tof_5", "barenco_tof_5"])
def test_control_route_reproduces_v2_numbers(name, tmp_path):
    path, lc, s, dz = _circ(name)
    plans = [p.to_json() for _, _, p in control_plans(lc, s, BUDGET)]
    summ = optimize(str(path), 1e-3, _scripted(plans), manifest={"declared_zero": dz,
                                                                 "method": "reconstruction"},
                    runs_dir=tmp_path, n_calls=BUDGET, batch=1)
    t, q = _v2_best(name)
    assert summ["t_after"] == t
    assert summ["after"]["qubits"] == q
    assert summ["contract"] == "relaxed"            # §1.5: relaxed column, never mixed
    assert summ["final_check_vs_original"]["ok"]
    assert summ["ledger"]["window_spent"] == 0      # exact branch-wise: charge 0


def test_zero_accept_returns_input_unchanged(tmp_path):
    path, lc, s, dz = _circ("cuccaro_4")
    summ = optimize(str(path), 1e-3, lambda ps: ["NONE"] * len(ps),
                    manifest={"declared_zero": dz, "method": "reconstruction"},
                    runs_dir=tmp_path, n_calls=2, batch=1)
    assert summ["t_before"] == summ["t_after"] == 56        # naive input cost, untouched
    assert summ["stats"]["accepted"] == 0 and summ["stats"]["declined"] == 2
    assert summ["final_check_vs_original"]["ok"]
    assert "input returned unchanged" in summ["final_check_vs_original"]["reason"]


def test_bad_plan_is_rejected_not_crash(tmp_path):
    path, lc, s, dz = _circ("cuccaro_4")
    bad = '{"target": "relaxed", "decisions": [{"element": "P0", "route": "temporary_and"}], "global_pass": "none"}'
    # P0 in cuccaro_4 is controls_fixed: direct temporary_and (no via_ancilla) must be
    # rejected by compile/verify, never accepted silently
    summ = optimize(str(path), 1e-3, _scripted([bad]),
                    manifest={"declared_zero": dz, "method": "reconstruction"},
                    runs_dir=tmp_path, n_calls=1, batch=1)
    assert summ["stats"]["accepted"] == 0
    assert summ["t_after"] == 56
