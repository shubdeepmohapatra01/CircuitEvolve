"""LEGACY: block optimizer v1 (circuitevolve/legacy/blocks_v1): program format, rule library, proposer loop,
pipeline. Moved from tests/test_blocks.py on 2026-10-13, test bodies unchanged."""
import math

import numpy as np
import pytest

from circuitevolve.blocks import verify_block as vb
from circuitevolve.blocks.circuit_io import bench_path, classify_angle
from circuitevolve.blocks.cost_model import Gridsynth, ops_cost
from circuitevolve.blocks.partition import group, make_block, partition, reassemble
from circuitevolve.blocks.passes import classical_pass, phase_fold, resynth_1q
from circuitevolve.legacy.blocks_v1.program import (ParseError, block_program, eval_expr, extract_programs,
                                          fit_params, parse_expr, parse_program)
from circuitevolve.legacy.blocks_v1.rules import RuleLibrary, check_general, try_rewrite



@pytest.fixture(scope="module")
def gs(tmp_path_factory):
    # shared on-disk cache so repeated test runs do not re-run gridsynth
    return Gridsynth()


@pytest.fixture(scope="module")
def qft4(gs):
    from circuitevolve.blocks.classical import best_classical
    return best_classical("qft_4", gs)


def test_parser_literal_and_whitelisted():
    p = parse_program("qubits 2\ncx q0 q1\nrz(a0 + a1/2 - pi/4) q1  # c\nrz(-p0) q0\nCNOT q1 q0", 2, 2)
    assert p.kind == "parametric" and p.n_params == 1 and p.a_used == {0, 1}
    assert abs(eval_expr(p.ops[1][2], [0.2, 0.6], [0]) - (0.5 - math.pi / 4)) < 1e-15
    assert p.ops[3][0] == "cx" and p.ops[3][1] == (1, 0)
    for bad in ("rz(__import__('os').system('x')) q0", "rz(a0.real) q0", "rz(abs(a0)) q0",
                "rz(a0**2) q0", "rz(b0) q0", "rz(a5) q0", "rz(lambda: 1) q0", "u3(1,2,3) q0",
                "cx q0 q0", "h q2", "rz q0", "h(0.1) q0", "rz([1][0]) q0", "qubits 3"):
        with pytest.raises(ParseError):
            parse_program(bad, 2, 2)
    with pytest.raises(ParseError):
        parse_expr("x" * 300)
    with pytest.raises(ZeroDivisionError):
        eval_expr(parse_expr("a0/(a0-a0)"), [1.0], [])


def test_program_roundtrip_and_extract():
    ops = [("rz", (0,), 0.3), ("cx", (0, 1), None), ("rz", (1,), 0.7)]
    p = block_program(ops, 2)
    q = parse_program(p.to_text(), 2, 2)
    assert q.materialize([0.3, 0.7]) == ops
    txt = "blah\n```block\nh q0\n```\n```python\nx=1\n```\n```\nrz(a0) q1\n```"
    assert extract_programs(txt) == ["h q0", "rz(a0) q1"]
    c = {}
    assert extract_programs("```\n(8, 8)\n```\n```block\nh q0\n```", counts=c) == ["h q0"]
    assert c["non_program_block"] == 1


def test_materialize_snaps_clifford_angles():
    p = parse_program("rz(a0 - a0 + pi/4) q0\nrz(pi/2) q0\nrz(a0) q0", 1, 1)
    assert [g for g, _, _ in p.materialize([0.1])] == ["t", "s", "rz"]


def test_fit_params_recovers_and_snaps():
    target = vb.unitary([("rz", (0,), 0.3), ("cx", (0, 1), None), ("rz", (1,), math.pi / 4 + 1e-13),
                         ("cx", (0, 1), None)], 2)
    prog = parse_program("rz(p0) q0\ncx q0 q1\nrz(p1) q1\ncx q0 q1", 2, 0)
    p, d = fit_params(prog, target, [], seed=1)
    assert d < 1e-10
    assert classify_angle(p[1]) == 1 and abs(p[0] - 0.3) < 1e-8          # snapped to pi/4


def _random_ops(rng, n, m):
    gates = ["h", "s", "sdg", "t", "tdg", "x", "z", "rz", "rz", "rz", "cx", "cx", "cz"]
    ops = []
    for _ in range(m):
        g = gates[rng.integers(len(gates))]
        if g in ("cx", "cz"):
            a, b = rng.choice(n, 2, replace=False)
            ops.append((g, (int(a), int(b)), None))
        else:
            ops.append((g, (int(rng.integers(n)),), float(rng.normal()) if g == "rz" else None))
    return ops


def _blk(i, a, b, c):
    return make_block(i, [("rz", (0,), a), ("cx", (0, 1), None), ("rz", (1,), b), ("cx", (0, 1), None),
                          ("rz", (0,), c), ("h", (1,), None)])


def test_rule_library_apply_and_persist(gs, tmp_path):
    b = _blk(0, 0.3, 0.7, -1.1)
    good = parse_program("rz(a0+a2) q0\ncx q0 q1\nrz(a1) q1\ncx q0 q1\nh q1", 2, 3)
    rec = try_rewrite(b, good, gs)
    assert rec["ok"] and rec["cost"]["rz"] == 2
    g = check_general(b, good)
    assert g["ok"] and g["samples"] >= 32
    lib = RuleLibrary(tmp_path / "rules.json")
    lib.add(b, good, dict(g), True, dict(test=1))
    lib.save()
    lib2 = RuleLibrary(tmp_path / "rules.json")
    other = _blk(5, -0.2, 1.9, 0.4)
    assert other.sig == b.sig
    r = lib2.apply(other, gs)
    assert r and r["ok"] and r["cost"]["rz"] == 2 and r["rule"] == "B1"
    assert "B1" in lib2.to_markdown()


def test_search_structures_with_fake_backend(gs, tmp_path):
    from circuitevolve.blocks.proposer import build_prompt, search_structures
    blocks = [_blk(i, 0.1 * i + 0.05, -0.3 * i + 0.11, 0.2 + 0.07 * i) for i in range(4)]
    groups = group(blocks)
    base = {b.index: ops_cost(b.ops, gs) for b in blocks}
    prompt = build_prompt(blocks[0], blocks, base[0], [], "", 3)
    assert "a0" in prompt and "```block" in prompt
    responses = [
        "```block\nrz(a0-a2) q0\ncx q0 q1\nrz(a1) q1\ncx q0 q1\nh q1\n```\n"      # wrong sign
        "```block\nrz(2*a0) q0\ncx q0 q1\nrz(a1) q1\ncx q0 q1\nh q1\n```\n"       # wrong in general
        "```block\nrz(a0+a2) q0\ncx q0 q1\nrz(a1) q1\ncx q0 q1\nh q1\n```\n"]     # correct
    calls = []

    def fake(prompts):
        calls.append(len(prompts))
        return [responses[0] for _ in prompts]
    lib = RuleLibrary(tmp_path / "r.json")
    res = search_structures(groups, gs, fake, lib, base, max_calls=3, circuit="toy")
    st = res["stats"]
    assert st["calls"] == 1 and st["programs"] == 3 and st["improving"] == 1 and st["rules_added"] == 1
    assert len(res["best"]) == 4 and all(r["cost"]["rz"] == 2 for r in res["best"].values())
    assert lib.rules[0]["general"] and lib.rules[0]["gain"]["toy"]["blocks"] == 4

    def errors(prompts):
        return [RuntimeError("api: overloaded") for _ in prompts]
    res = search_structures(groups, gs, errors, RuleLibrary(tmp_path / "r2.json"), base, max_calls=2)
    assert res["stats"]["llm_errors"] == 2 and not res["best"]


def test_pipeline_no_llm_qft4(gs, tmp_path):
    from circuitevolve.blocks.pipeline import run_pipeline
    r = run_pipeline("qft_4", complete=None, gs=gs, library=RuleLibrary(tmp_path / "x.json"))
    assert r["output_cost"]["t"] <= r["input_cost"]["t"]
    assert r["whole_circuit_check"]["dist"] <= r["error_bound"] + 1e-12
    assert r["whole_circuit_check"]["dist"] < 1e-8


def test_pipeline_global_fold_and_forced_input(gs, tmp_path):
    from circuitevolve.blocks.pipeline import run_pipeline
    r = run_pipeline("qft_4", complete=None, gs=gs, library=RuleLibrary(tmp_path / "y.json"),
                     input_pipeline="tket", global_fold=True)
    assert r["input_pipeline"] == "tket" and r["best_classical_pipeline"] in ("pyzx", "tket")
    assert r["output_cost"]["rz"] <= r["after_global_fold"]["rz"] <= r["input_cost"]["rz"]
    assert r["whole_circuit_check"]["dist"] < 1e-8
