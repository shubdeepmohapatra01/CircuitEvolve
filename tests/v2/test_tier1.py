"""Tier 1 (compilation strategy): recognizer, plan parser, compiler, verifier wiring, fake-LLM loop, control arm."""
import json
from collections import Counter

import pytest

from circuitevolve.blocks import REPO
from circuitevolve.v2 import verify as V
from circuitevolve.v2.tier1.compile import evaluate
from circuitevolve.v2.tier1.control import control_plans
from circuitevolve.v2.tier1.loop import run_control_arm, run_llm_arm
from circuitevolve.v2.tier1.plan import PlanError, parse_dsl_gate, parse_plan
from circuitevolve.v2.tier1.prompt import build_prompt, resolve_card, select_cards
from circuitevolve.v2.tier1.recognize import load_logical, summarize

BENCH = REPO / "benchmarks" / "nam_arith"


def _load(name, dz, sub="logical"):
    orig, lc = load_logical(BENCH / sub / f"{name}.qasm")
    return orig, lc, summarize(lc, dz, name)


@pytest.fixture(scope="module")
def cuccaro():
    return _load("cuccaro_4", [0], "generated")


@pytest.fixture(scope="module")
def tof3():
    return _load("tof_3", [4])


# ------------------------------------------------------------------------------------------------ recognizer
def test_normalization_is_exact(tof3):
    orig, lc, _ = tof3
    v = V.verify(lc.to_ir(), orig, "exact")
    assert v.ok and v.certified
    assert [g.name for g in lc.gates] == ["ccx"] * 3


def test_recognize_tof3(tof3):
    _, lc, s = tof3
    assert [t["target"] for t in s.toffolis] == [4, 3, 4]
    assert len(s.pairs) == 1 and s.pairs[0]["cls"] == "clean" and s.pairs[0]["target"] == 4
    assert s.unpaired == ["T1"]
    assert s.mcx and s.mcx[0]["controls"] == [0, 1, 2] and s.mcx[0]["target"] == 3 and s.mcx[0]["work_clean"]
    roles = {r["q"]: r["role"] for r in s.qubits}
    assert roles[4] == "ancilla(clean)" and roles[3] == "data"
    assert "P0 = T0+T2" in s.text(lc)


def test_recognize_cuccaro(cuccaro):
    _, lc, s = cuccaro
    assert len(s.toffolis) == 8 and len(s.pairs) == 4 and not s.unpaired
    assert [p["cls"] for p in s.pairs] == ["controls_fixed"] * 3 + ["mirror"]
    assert s.repeated, "MAJ/UMA blocks should repeat"
    assert s.digest == summarize(lc, [0], "cuccaro_4").digest          # deterministic


# ------------------------------------------------------------------------------------------------ plans
def test_cuccaro_temporary_and_passes_relaxed_4T_per_pair(cuccaro):
    _, lc, s = cuccaro
    plan = {"decisions": [{"element": p["id"], "route": "temporary_and", "via_ancilla": True} for p in s.pairs],
            "global_pass": "none"}
    r = evaluate(lc, s, json.dumps(plan))
    assert r["ok"], r["reason"]
    assert r["verdict_mode"] == "relaxed" and not r["unitary_preserving"] and r["certified"]
    assert r["t_count"] == 4 * len(s.pairs) == 16
    assert r["measurements"] == 4


def test_lone_relative_phase_toffoli_rejected(cuccaro):
    _, lc, s = cuccaro
    r = evaluate(lc, s, '{"decisions": [{"element": "T0", "route": "relative_phase_toffoli"}]}')
    assert not r["ok"] and "partner" in r["reason"]
    # the same RCCX written as a custom single-Toffoli construction is caught by the verifier
    rccx = ["h q2", "t q2", "cx q1, q2", "tdg q2", "cx q0, q2", "t q2", "cx q1, q2", "tdg q2", "h q2"]
    r = evaluate(lc, s, {"decisions": [{"element": "T0", "route": "custom", "gates": rccx}]})
    assert not r["ok"] and r["mode"] == "exact" and "phase" in r["reason"]


def test_relative_phase_pair_exact(tof3):
    _, lc, s = tof3
    r = evaluate(lc, s, {"decisions": [{"element": "P0", "route": "relative_phase_toffoli"}], "global_pass": "none"})
    assert r["ok"] and r["verdict_mode"] == "exact" and r["certified"] and r["t_count"] == 8 + 7


def test_temporary_and_on_dirty_target_rejected(cuccaro):
    _, lc, s = cuccaro
    r = evaluate(lc, s, {"decisions": [{"element": "P0", "route": "temporary_and"}], "global_pass": "none"})
    assert not r["ok"] and r["mode"] == "relaxed"
    assert r["zero_qubits"] == []                 # target q2 is not a declared zero-init qubit: nothing promised


def test_temporary_and_clean_target_and_mcx(tof3):
    _, lc, s = tof3
    r = evaluate(lc, s, {"decisions": [{"element": "P0", "route": "temporary_and"}], "global_pass": "none"})
    assert r["ok"] and r["zero_qubits"] == [4] and r["t_count"] == 4 + 7 and r["qubits"] == 5
    r = evaluate(lc, s, {"decisions": [{"element": "M0", "route": "ancilla_mcx"}]})
    assert r["ok"] and r["t_count"] == 8 and r["ancillas"] == 1


def test_custom_dsl_jones_with_measurement(tof3):
    _, lc, s = tof3
    g = ["h a0", "t a0", "cx q2, a0", "cx q4, a0", "cx a0, q2", "cx a0, q4", "tdg q2", "tdg q4", "t a0",
         "cx a0, q2", "cx a0, q4", "h a0", "s a0", "cx a0, q3",
         "h a0", "measure a0 -> c0", "if(c0) cz q2, q4", "if(c0) x a0"]
    r = evaluate(lc, s, {"decisions": [{"element": "T1", "route": "custom", "gates": g},
                                       {"element": "P0", "route": "temporary_and"}]})
    assert r["ok"], r["reason"]
    assert r["t_count"] == 8 and r["measurements"] == 2 and r["verdict_mode"] == "relaxed"


@pytest.mark.parametrize("bad", [
    "", "no json here", '{"decisions": [', '{"decisions": "x"}',
    '{"decisions": [{"element": "T0", "route": "magic"}]}',
    '{"decisions": [{"element": "Q1", "route": "toffoli_7T"}]}',
    '{"decisions": [], "global_pass": "quantum_annealing"}',
    '{"decisions": [{"element": "T0", "route": "custom", "gates": ["__import__(\'os\').system(\'ls\')"]}]}',
    '{"decisions": [{"element": "T0", "route": "custom", "gates": ["ccx q0 q1 q2"]}]}',
    '{"decisions": [{"element": "T9", "route": "toffoli_7T"}]}',
    '{"decisions": [{"element": "T0", "route": "toffoli_7T"}, {"element": "P0", "route": "temporary_and"}]}',
])
def test_malformed_plans_handled(tof3, bad):
    _, lc, s = tof3
    r = evaluate(lc, s, bad)
    assert not r["ok"] and r["reason"].startswith("plan rejected")


def test_plan_parses_fenced_json():
    p = parse_plan('Sure:\n```json\n{"target":"exact","decisions":[{"element":"P0","route":"relative_phase_toffoli"}],'
                   '"global_pass":"pyzx","request_cards":["07"]}\n```\nthanks')
    assert p.global_pass == "pyzx" and p.decisions[0].route == "relative_phase_toffoli" and p.request_cards == ["07"]
    assert parse_dsl_gate("if(c1) cz q[2], q[4]").cond == 1
    with pytest.raises(PlanError):
        parse_dsl_gate("cx q1, q1")


def test_global_pass_keeps_verification(tof3):
    _, lc, s = tof3
    for gp in ("pyzx", "tket", "pyzx_then_tket"):
        r = evaluate(lc, s, {"decisions": [{"element": "M0", "route": "barenco_mcx"}], "global_pass": gp})
        assert r["ok"] and r["verdict_mode"] == "exact" and r["t_count"] <= 15, (gp, r["reason"])


# ------------------------------------------------------------------------------------------------ loop + control
def _fake_backend(replies):
    it = iter(replies)

    def complete(prompts):
        complete.stats["calls"] += len(prompts)
        complete.stats["input_tokens"] += 100
        complete.stats["output_tokens"] += 10
        return [next(it) for _ in prompts]
    complete.stats = Counter()
    return complete


def test_fake_llm_loop(tmp_path, tof3):
    _, lc, s = tof3
    replies = ["garbage",
               '{"target":"relaxed","decisions":[{"element":"M0","route":"ancilla_mcx"}],"global_pass":"none"}',
               '{"target":"exact","decisions":[{"element":"P0","route":"relative_phase_toffoli"}],'
               '"global_pass":"pyzx","request_cards":["07_phase_folding_tpar"]}',
               RuntimeError("api down")]
    log = tmp_path / "log.jsonl"
    res = run_llm_arm(lc, s, _fake_backend(replies), 4, log, "15 (pyzx_fr)")
    assert res.evaluations == 4 and res.tokens["input_tokens"] == 400
    assert res.best["relaxed"]["t_count"] == 8 and res.best["exact"]["t_count"] <= 15
    lines = [json.loads(l) for l in log.read_text().splitlines()]
    assert len(lines) == 4 and lines[0]["ok"] is False and lines[3]["stage"] == "llm"
    assert "07_phase_folding_tpar" in lines[3]["cards"]          # requested card included in the next prompt
    assert "NEW BEST" in lines[3]["prompt"]


def test_control_arm_budget(tmp_path, tof3):
    _, lc, s = tof3
    assert len(control_plans(lc, s, 5)) == 5
    res = run_control_arm(lc, s, 8, tmp_path / "c.jsonl")
    assert res.evaluations == 8
    assert res.best["relaxed"]["t_count"] == 8          # V2: temporary_and pair + jones middle
    assert res.best["exact"]["t_count"] <= 15


def test_prompt_cards(tof3):
    _, lc, s = tof3
    cards = select_cards(s, ["10"])
    assert "01_gidney_temporary_and" in cards and "10_dyadic_phase_fixing" in cards
    assert resolve_card("relative_phase") == "03_relative_phase_toffoli"
    p = build_prompt(s, lc, "exact", {}, [], cards, "15")
    assert "THIS CALL TARGETS: EXACT" in p and "temporary_and" in p and "P0 = T0+T2" in p
