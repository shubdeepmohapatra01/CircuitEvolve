"""G2 graduation gates: AND-preserving Toffoli pairing (discovered by the LLM on rc_adder_6
in recon_campaign1, graduated into the deterministic recognizer as exact code).

Soundness frame: the extension is PROPOSAL-side (recognize/control are not in the frozen set);
every plan built on an extended pair still passes through the frozen verifier. Default OFF —
the no-flag path stays bit-exact (also pinned by tests/engine/test_recon_bench.py)."""
from __future__ import annotations

import csv

from circuitevolve.blocks import REPO
from circuitevolve.v2.tier1.compile import evaluate
from circuitevolve.v2.tier1.control import control_plans, variant_decisions
from circuitevolve.v2.tier1.recognize import _and_preserving_ok, load_logical, summarize

MANIFEST = {r["name"]: r for r in csv.DictReader(open(REPO / "benchmarks" / "nam_arith" / "MANIFEST.csv"))}


def _summ(name, flag):
    row = MANIFEST[name]
    dz = [int(x) for x in str(row.get("zero_init_qubits") or "").split()]
    _, lc = load_logical(REPO / "benchmarks" / "nam_arith" / row["logical_path"], name=name)
    return lc, summarize(lc, declared_zero=dz, name=name, and_preserving=flag)


def _best_relaxed_control(lc, s):
    pc, vc = {}, {}
    best = None
    for v, gp, plan in control_plans(lc, s, 4):
        rec = evaluate(lc, s, plan, pc, vc)
        if rec.get("ok") and rec.get("verdict_mode") == "relaxed":
            best = rec["t_count"] if best is None else min(best, rec["t_count"])
    return best


def test_default_off_is_bit_exact():
    _, s = _summ("rc_adder_6", False)
    assert len(s.pairs) == 1 and all(p["cls"] != "and_preserving" for p in s.pairs)


def test_rc_adder_6_pairs_and_control_reach_llm_result():
    lc, s = _summ("rc_adder_6", True)
    ap = [p for p in s.pairs if p["cls"] == "and_preserving"]
    assert len(s.pairs) == 5 and len(ap) == 4
    assert _best_relaxed_control(lc, s) == 24      # == the LLM's recon_campaign1 dev result


def test_mod_red_21_control_reaches_frozen_llm_result():
    lc, s = _summ("mod_red_21", True)
    assert _best_relaxed_control(lc, s) == 44      # == the LLM's frozen held-out result


def test_exact_v3_excludes_and_preserving_pairs():
    lc, s = _summ("rc_adder_6", True)
    v3 = variant_decisions(lc, s, "V3")
    ap_ids = {p["id"] for p in s.pairs if p["cls"] == "and_preserving"}
    assert all(d.element not in ap_ids for d in v3)


def test_helper_rejects_non_preserving_rewrite():
    # x on a control flips AND(c0,c1) whenever the other control is 1: must refuse
    _, lc = load_logical(
        'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[4];\n'
        "ccx q[0],q[1],q[2];\nx q[1];\nccx q[0],q[1],q[2];\n", name="neg")
    s = summarize(lc, name="neg", and_preserving=True)
    assert not _and_preserving_ok(lc.gates, 0, 2, (0, 1))
    assert all(p["cls"] != "and_preserving" for p in s.pairs)
    # the canonical preserving rewrite c -> NOT(c xor a) IS admitted
    _, lc2 = load_logical(
        'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[4];\n'
        "ccx q[0],q[1],q[2];\ncx q[0],q[1];\nx q[1];\nccx q[0],q[1],q[2];\n", name="pos")
    s2 = summarize(lc2, name="pos", and_preserving=True)
    assert any(p["cls"] == "and_preserving" for p in s2.pairs)