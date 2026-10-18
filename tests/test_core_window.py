"""Window core (circuitevolve/core): circuit, mutator parsing, verifier, metric, ledger, loop - fake LLM only.

Planted bad rewrites (wrong angle, dropped gate, exceeding the allowance) must be rejected; good exact and
approximate rewrites accepted with the right ledger charge; the playbook credits only MEASURED improvements.
"""
import builtins
import json
import math

import pytest

from circuitevolve.blocks.cost_model import Gridsynth
from circuitevolve.core.circuit import Circuit, load_input, splice, window_text, windows
from circuitevolve.core.ledger import Ledger
from circuitevolve.core.loop import WindowLoop
from circuitevolve.core.metric import BqskitTMetric, improves
from circuitevolve.core.mutator import (ParseError, WindowTask, build_prompt, extract_candidates, indexed_window_text,
                                        parse_angle, parse_window)
from circuitevolve.core.verifier import check_circuit, verify_window
from circuitevolve.integrity import frozen_digest
from circuitevolve.search.playbook import Playbook

EPS = 1e-3
TINY = 1e-7          # near-identity rotation: distance 2 sin(TINY/4) = 5e-8, well inside the allowance
BIG = 1e-3           # dropping it costs 5e-4 > allowance (eps/2 * 1/4 = 1.25e-4)

# one 3-qubit window; the original circuit is the input itself
ORIG = [("h", (0,), None), ("rz", (0,), 0.3), ("rz", (0,), 0.4), ("cx", (0, 1), None), ("rz", (1,), TINY),
        ("rz", (1,), 0.25), ("cx", (0, 1), None), ("h", (2,), None), ("rz", (2,), 0.9), ("cx", (1, 2), None),
        ("rz", (2,), BIG), ("rz", (2,), 1.1), ("t", (0,), None), ("t", (0,), None)]


def W(ops):
    return "```window\n" + window_text(ops) + "\n```\n"


def without(i, ops=ORIG):
    return ops[:i] + ops[i + 1:]


GOOD_EXACT = [ORIG[0], ("rz", (0,), 0.7)] + ORIG[3:12] + [("s", (0,), None)]       # merge rz, t t -> s
GOOD_APPROX = without(3, GOOD_EXACT)                                                 # ... and drop rz(TINY)
WRONG_ANGLE = [ORIG[0], ("rz", (0,), 0.8)] + ORIG[3:]
DROPPED_GATE = without(6)                                                            # second cx dropped
OVER_ALLOWANCE = without(10)                                                         # drop rz(BIG)


@pytest.fixture
def circ():
    return Circuit(3, list(ORIG), dict(name="synthetic", source="test"))


# ------------------------------------------------------------------ circuit / mutator parsing
def test_parse_literal_formats_and_refusals(monkeypatch):
    assert parse_angle("-3*pi/8") == pytest.approx(-3 * math.pi / 8)
    assert parse_angle("3pi/4") == pytest.approx(0.75 * math.pi) and parse_angle("1.5e-3") == 1.5e-3
    assert parse_window("h q0\ncx q0, q1;\nrz(pi/4) q[1]\ntdag q2  # c") == [
        ("h", (0,), None), ("cx", (0, 1), None), ("rz", (1,), math.pi / 4), ("tdg", (2,), None)]
    for bad in ("ccx q0 q1 q2", "rz(__import__('os').getpid()) q0", "rz(eval(1)) q0", "cx q0", "h q0 q1", "rz q0",
                "u3(1,2,3) q0", "rz(1/0) q0"):
        with pytest.raises(ParseError):
            parse_window(bad)

    def boom(*a, **k):
        raise AssertionError("model text reached eval/exec")
    monkeypatch.setattr(builtins, "eval", boom)
    monkeypatch.setattr(builtins, "exec", boom)
    cands, errs = extract_candidates(W(GOOD_EXACT) + "```window\nrz(exec('x')) q0\n```")
    assert cands == [GOOD_EXACT] and len(errs) == 1
    assert extract_candidates("No merge is possible.\n\nNONE") == ([], ["declined (NONE)"])
    assert extract_candidates("```window\nNONE\n```") == ([], ["declined (NONE)"])
    assert extract_candidates("I think so.") == ([], ["no ```window block in the response"])


def test_windows_reassemble_and_splice_on_tket_input():
    c = load_input("qft_4", prefer_baseline_file=False)
    assert "tket" in c.meta["source"]
    ws, flat = windows(c)
    assert all(w.k <= 4 and len(w.ops) <= 40 for w in ws)
    assert check_circuit(c.ops, flat, c.n, bound=0.0)["ok"]
    w = max(ws, key=lambda w: len(w.ops))
    assert splice(flat, w, w.ops) == flat
    assert Circuit.from_qasm(c.to_qasm()).ops == c.ops


# ------------------------------------------------------------------ verifier
def test_planted_bad_rewrites_rejected_good_ones_accepted():
    allow = Ledger(EPS).allowance()                  # v1: pool cap eps/4, per rewrite 1/4 of it
    assert allow == pytest.approx(6.25e-5)
    r = verify_window(ORIG, WRONG_ANGLE, 3, allow)
    assert not r["ok"] and r["dist"] > 1e-2 and "allowance" in r["reason"]
    r = verify_window(ORIG, DROPPED_GATE, 3, allow)
    assert not r["ok"] and r["dist"] > 0.1
    r = verify_window(ORIG, OVER_ALLOWANCE, 3, allow)
    assert not r["ok"] and r["dist"] == pytest.approx(2 * math.sin(BIG / 4), rel=1e-6) and r["dist"] > allow
    r = verify_window(ORIG, GOOD_EXACT, 3, allow)
    assert r["ok"] and r["mode"] == "approx" and r["charge"] < 1e-12
    r = verify_window(ORIG, GOOD_APPROX, 3, allow)
    assert r["ok"] and r["charge"] == pytest.approx(2 * math.sin(TINY / 4), rel=1e-4)
    assert r["hs_cost"] <= r["dist"] + 1e-15
    r = verify_window(ORIG, [("h", (0,), None), ("cx", (0, 3), None)], 3, allow)
    assert not r["ok"] and r["mode"] == "literal" and "out of range" in r["reason"]


def test_exact_mode_for_clifford_t_windows():
    a = [("t", (0,), None), ("cx", (0, 1), None), ("t", (0,), None)]
    r = verify_window(a, [("s", (0,), None), ("cx", (0, 1), None)], 2, 0.0)
    assert r["ok"] and r["mode"] == "exact" and r["charge"] == 0.0
    r = verify_window(a, [("s", (1,), None), ("cx", (0, 1), None)], 2, 0.0)
    assert not r["ok"] and "exact check" in r["reason"]
    # invariant 1: no floating-point fallback for Clifford+T pairs, even with a huge allowance
    r = verify_window(a, [("s", (0,), None), ("cx", (0, 1), None), ("t", (1,), None)], 2, 10.0)
    assert not r["ok"] and r["mode"] == "exact"


# ------------------------------------------------------------------ metric / ledger
def test_metric_bqskit_convention(tmp_path):
    m = BqskitTMetric(5e-4, cache_dir=tmp_path)
    ops = [("rz", (0,), 0.3), ("rz", (1,), 0.7), ("rz", (0,), math.pi / 4), ("rz", (1,), math.pi / 2), ("t", (0,), None)]
    c = m.cost(ops)
    assert c["rz"] == 2 and c["eps_rz"] == 5e-4 / 2 and c["t_fixed"] == 2       # pi/4 rz = 1 T, pi/2 = 0
    g = Gridsynth(eps=5e-4 / 2, path=tmp_path / "direct.json")
    assert c["t_gs"] == g.t(0.3) + g.t(0.7) and c["t"] == c["t_fixed"] + c["t_gs"]
    assert m.cost(ops[:1])["eps_rz"] == 5e-4        # fewer rotations -> looser eps_rz
    old = dict(t=100, rz=3, t_fixed=0, cx=5, gates=20)
    assert not improves(dict(old, t=96), old)                    # same rotations, angle noise only
    assert improves(dict(old, t=70, rz=2), old) and not improves(dict(old, t=101, rz=2), old)


def test_ledger_v0_rule_and_bound():
    led = Ledger(EPS, rule="v0").with_input(1e-13)
    assert led.window_pool == led.eps_synth == EPS / 2
    led = led.charge(1e-4).charge(1.2e-4)
    assert led.remaining == pytest.approx(EPS / 2 - 1e-13 - 2.2e-4)
    assert led.allowance() == pytest.approx(min(led.remaining, EPS / 8))
    with pytest.raises(ValueError):
        led.charge(led.remaining * 1.01)
    assert led.bound(50) <= EPS and led.bound(50) == pytest.approx(1e-13 + 2.2e-4 + EPS / 2)
    assert led.reclaimed_eps_synth == pytest.approx(EPS - 1e-13 - 2.2e-4)


def test_prompt_contains_window_costs_allowance_rules_feedback():
    t = WindowTask(local_ops=ORIG, k=3, eps_rz=1e-5, allowance=1.25e-4, t_rot=[50] * 7, t_fixed=2,
                   rules=["Merge adjacent rz."], feedback=["rejected: distance 1e-2 > allowance"])
    p = build_prompt(t)
    assert "1.250e-04" in p and "Merge adjacent rz." in p and "rejected: distance" in p
    assert indexed_window_text(ORIG) in p and "352 T" in p  # ORIG angles are already in [-pi, pi]
    assert parse_window(indexed_window_text(ORIG)) == ORIG       # `# op i` comments are ignored by the parser
    assert "FIX-AND-REFIT" in p and "op 1 on q0" in p


# ------------------------------------------------------------------ loop with a fake backend
def make_fake(responses):
    """Each call pops the next response (str or Exception); records prompts."""
    seen = []

    def complete(prompts):
        seen.extend(prompts)
        return [responses.pop(0) if responses else "NONE" for _ in prompts]
    complete.seen = seen
    return complete


def test_loop_rejects_planted_bad_and_accepts_good(circ, tmp_path):
    fake = make_fake([W(WRONG_ANGLE) + W(DROPPED_GATE) + W(OVER_ALLOWANCE),
                      RuntimeError("api: overloaded"),
                      W(ORIG) + W(GOOD_EXACT),              # identical copy passes but is no improvement
                      W(GOOD_APPROX)])
    digest = frozen_digest()
    loop = WindowLoop(circ, list(ORIG), EPS, fake, tag="t1", runs_dir=tmp_path, n_calls=4, batch=1, p_best=1.0)
    s = loop.run()
    st = s["stats"]
    assert st["rejected_verifier"] == 3 and st["llm_errors"] == 1 and st["rejected_metric"] >= 1
    assert st["accepted"] == 2 and st["accepted_t_reduced"] == 2 and st["exact_accepts"] == 0
    assert st["declined"] == 0 and st["parse_errors"] == 0
    assert s["t_after"] < s["t_before"] and s["after"]["rz"] == s["before"]["rz"] - 2
    led = s["ledger"]
    assert led["window_spent"] == pytest.approx(2 * math.sin(TINY / 4), rel=1e-3) and led["bound"] <= EPS
    assert s["t_after_reclaimed"] <= s["t_after"] and s["verifier_digest"] == digest[:16]
    lines = [json.loads(x) for x in (tmp_path / "t1.jsonl").read_text().splitlines()]
    kinds = [x["kind"] for x in lines]
    assert kinds[0] == "start" and kinds[-1] == "end" and kinds.count("propose") == 4
    first = lines[1]
    assert [c["decision"] for c in first["candidates"]] == ["rejected: verifier"] * 3 and not first["accepted"]
    assert "rejected:" in fake.seen[1] or "rejected:" in fake.seen[2]          # verifier feedback reaches prompts
    best = Circuit.from_qasm((tmp_path / "t1_best.qasm").read_text())
    assert check_circuit(ORIG, best.ops, 3, bound=led["d_input"] + led["window_spent"])["ok"]
    with pytest.raises(FileExistsError):                                        # append-only tags
        WindowLoop(circ, list(ORIG), EPS, make_fake([]), tag="t1", runs_dir=tmp_path, n_calls=1).run()


def test_whole_circuit_check_catches_a_bypassed_window_verifier(circ, tmp_path, monkeypatch):
    import circuitevolve.core.loop as L

    def lying_verifier(orig, new, k, allowance):
        return dict(ok=True, mode="approx", dist=0.0, charge=0.0, reason="")
    monkeypatch.setattr(L, "verify_window", lying_verifier)
    loop = WindowLoop(circ, list(ORIG), EPS, make_fake([W(OVER_ALLOWANCE[:1] + OVER_ALLOWANCE[2:])]),
                      runs_dir=tmp_path, n_calls=1, batch=1)
    s = loop.run()
    assert s["stats"]["rejected_whole"] == 1 and s["stats"]["accepted"] == 0 and s["t_after"] == s["t_before"]


def test_playbook_credits_only_measured_improvement(circ, tmp_path):
    pb = Playbook(ab_fraction=1.0)                     # candidates always shown
    pb.add("Merge rotations on the same wire.", 0)
    # call 1: verifier PASS but no improvement (identical window); call 2: real improvement
    fake = make_fake([W(ORIG), W(GOOD_EXACT)])
    refl = make_fake(['```json\n[{"op": "add", "text": "Drop rotations below the allowance."}]\n```'])
    loop = WindowLoop(circ, list(ORIG), EPS, fake, reflect_complete=refl, playbook=pb, runs_dir=tmp_path,
                      tag="pb", n_calls=4, batch=1, reflect_every=2, p_best=1.0)
    s = loop.run()
    r1 = pb.get("R1")
    # prompts 1, 2 and 4 showed R1 (call 3 is the reflector); passes 1 + 1 + 0; ONE measured improvement
    assert r1.with_pass == 2 and r1.with_prompts == 3 and r1.with_improvements == 1
    assert s["stats"]["reflect_calls"] == 1 and s["stats"]["rules_added"] == 1 and len(pb.live()) == 2
    assert "Merge rotations on the same wire." in fake.seen[0]
    assert (tmp_path / "pb_playbook.json").exists() and (tmp_path / "pb_playbook.md").exists()
    assert s["calls"] == 4                              # reflector calls count against the budget


def test_windows_deterministic_regardless_of_process_history():
    from circuitevolve.blocks.partition import partition
    a = [(w.qubits, w.ops) for w in windows(Circuit(3, list(ORIG)))[0]]
    for _ in range(3):                                   # advance QuickPartitioner's global Bin counter
        partition(load_input("qft_4", prefer_baseline_file=False).ops, 4, block_size=2)
    assert [(w.qubits, w.ops) for w in windows(Circuit(3, list(ORIG)))[0]] == a and len(a) == 1
