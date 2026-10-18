"""Stage-1 additions to the window core (2026-10-13): ledger v1 (unspent window budget returns to synthesis),
regression against B0, and the fix-and-refit mutation action (core/refit.py). Fake LLM only."""
import builtins
import csv
import json
import math

import pytest

from circuitevolve.blocks import REPO
from circuitevolve.core.circuit import Circuit, load_input, original_ops, window_text, windows
from circuitevolve.core.ledger import QUANTUM, Ledger
from circuitevolve.core.loop import WindowLoop
from circuitevolve.core.mutator import ParseError, extract_proposals, is_declined
from circuitevolve.core.refit import parse_fix, refit, validate_target
from circuitevolve.core.verifier import verify_window

EPS = 1e-3
B0_CSV = REPO / "results" / "bqskit_baselines" / "stage1" / "stage1_baselines_v2.csv"


def W(ops):
    return "```window\n" + window_text(ops) + "\n```\n"


def F(lines):
    return "```fix\n" + "\n".join(lines) + "\n```\n"


def nones(_n=None):
    def complete(prompts):
        return ["NONE" for _ in prompts]
    return complete


# ------------------------------------------------------------------ ledger v1
def test_ledger_v1_returns_unspent_budget_to_synthesis():
    led = Ledger(EPS).with_input(2e-13)
    assert led.rule == "v1" and led.window_pool == pytest.approx(EPS / 4)
    assert led.eps_synth == EPS - 2e-13                       # nothing spent: everything goes to synthesis
    assert led.allowance() == pytest.approx(EPS / 16)
    q = EPS * QUANTUM
    led2 = led.charge(1e-14)
    assert led2.spent_rounded == pytest.approx(q) and led2.eps_synth == pytest.approx(EPS - 2e-13 - q)
    led3 = led2.charge(3.1 * q)
    assert led3.spent_rounded == pytest.approx(4 * q)       # ceil((1e-14 + 3.1 q) / q) = 4
    assert led3.eps_synth <= EPS - led3.d_input - led3.spent # rounding is conservative
    for n_rz in (1, 10, 500):
        assert led3.bound(n_rz) <= EPS
    with pytest.raises(ValueError):                          # pool cap eps/4
        led.charge(EPS / 4 + q)
    assert not led.can_charge(EPS / 4 + q) and led.can_charge(EPS / 4 - q)


@pytest.mark.parametrize("name", ["qft_8", "tfim_6"])
def test_zero_accepted_rewrites_equal_b0_exactly(name, tmp_path):
    """With nothing accepted, our T (v1 ledger) equals B0's t_count_canon (TKET + gridsynth at eps/N_Rz)."""
    rows = {(r["circuit"], float(r["eps_total"]), r["arm"]): r for r in csv.DictReader(B0_CSV.open())}
    b0 = int(rows[(name, EPS, "B0")]["t_count_canon"])
    orig, n = original_ops(name)
    loop = WindowLoop(load_input(name), orig, EPS, nones(), runs_dir=tmp_path, n_calls=1, batch=1)
    s = loop.run()
    assert s["stats"]["accepted"] == 0
    assert s["t_before"] == s["t_after"] == b0
    assert s["ledger"]["bound"] <= EPS and s["ledger"]["eps_synth"] == pytest.approx(EPS, rel=1e-9)
    assert s["final_check_vs_original"]["ok"]


# ------------------------------------------------------------------ fix block parsing
def test_parse_fix_literal_and_targets(monkeypatch):
    assert parse_fix("op 7 -> pi/4\nop 12 -> 0\n3 = -3*pi/8") == {7: math.pi / 4, 12: 0.0, 3: -3 * math.pi / 8}
    assert parse_fix("op 2 -> rz(pi/2)  # snap") == {2: math.pi / 2}
    assert parse_fix("op 4 -> delete") == {4: 0.0}
    assert validate_target(math.pi / 4) == (1, 3) and validate_target(0.0) == (0, 0)
    assert validate_target(3 * math.pi / 8) == (3, 4)
    for bad in ("op 1 -> 0.3", "op 1 -> pi/16", "op x -> 0", "op 1 -> __import__('os')", "", "op 1 -> 0\nop 1 -> pi"):
        with pytest.raises(ParseError):
            parse_fix(bad)

    def boom(*a, **k):
        raise AssertionError("model text reached eval/exec")
    monkeypatch.setattr(builtins, "eval", boom)
    monkeypatch.setattr(builtins, "exec", boom)
    ops = [("h", (0,), None)]
    props, errs = extract_proposals(W(ops) + F(["op 3 -> pi/4"]) + F(["op 1 -> eval(1)"]))
    assert props == [("window", ops), ("fix", {3: math.pi / 4})] and len(errs) == 1
    assert not is_declined(F(["op 1 -> 0"]) + "NONE") and is_declined("nothing\nNONE")
    assert extract_proposals("NONE") == ([], ["declined (NONE)"])


# ------------------------------------------------------------------ refit numerics
# rz(a) on the control commutes with cx, so the two q0 rotations merge: rz(0.3) cx rz(0.4) == rz(0.7) cx.
# Listed in the order windows() emits it (one 2-qubit window), so op indices match the prompt's.
ABSORB = [("rz", (0,), 0.3), ("h", (1,), None), ("cx", (0, 1), None), ("rz", (0,), 0.4), ("rz", (1,), 0.5),
          ("cx", (0, 1), None), ("h", (1,), None)]
# lone rotation: nothing can absorb it
LONE = [("h", (0,), None), ("rz", (0,), 0.3), ("h", (0,), None), ("cx", (0, 1), None), ("rz", (1,), 0.9)]


def test_refit_absorbs_redundant_rotation_and_verifier_agrees():
    r = refit(ABSORB, 2, {3: 0.0})
    assert r["ok"] and r["n_free"] == 2 and r["dist"] < 1e-9
    assert sum(g == "rz" for g, _, _ in r["ops"]) == 2
    v = verify_window(ABSORB, r["ops"], 2, 1e-9)
    assert v["ok"] and v["mode"] == "approx" and v["dist"] < 1e-9
    # fixing op 0 to pi/4: op 3 refits to 0.7 - pi/4 (the merged phase must be preserved)
    r = refit(ABSORB, 2, {0: math.pi / 4})
    a4 = [a for i, (g, q, a) in enumerate(r["ops"]) if g == "rz" and q == (0,) and i > 2][0]
    assert r["dist"] < 1e-9 and math.remainder(a4 - (0.7 - math.pi / 4), 2 * math.pi) == pytest.approx(0, abs=1e-7)


def test_refit_cannot_absorb_lone_rotation_and_bad_indices():
    r = refit(LONE, 2, {1: 0.0})
    assert r["ok"] and r["dist"] == pytest.approx(2 * math.sin(0.3 / 4), rel=1e-6)
    assert not verify_window(LONE, r["ops"], 2, 1e-4)["ok"]
    assert not refit(LONE, 2, {0: 0.0})["ok"]                 # op 0 is an h
    assert not refit(LONE, 2, {1: 0.3})["ok"]                 # not a dyadic target


def test_refit_parameter_order_is_insertion_order():
    """BQSKit orders parameters by cycle; a later-inserted rotation on another wire can sit in an earlier
    cycle. The refit must map parameters back to the right ops."""
    ops = [("cx", (0, 1), None), ("rz", (0,), 0.2), ("rz", (1,), 0.6), ("cx", (0, 1), None), ("rz", (2,), 1.0),
           ("rz", (0,), 0.25)]
    r = refit(ops, 3, {5: 0.0}, multistarts=0)               # warm start only
    assert r["dist"] < 1e-9
    got = {i: a for i, (g, q, a) in enumerate(r["ops"]) if g == "rz"}
    assert got[1] == pytest.approx(0.45, abs=1e-7) and got[2] == pytest.approx(0.6, abs=1e-7)
    assert got[4] == pytest.approx(1.0, abs=1e-7)


# ------------------------------------------------------------------ loop with the fix action
def test_loop_fix_action_accepts_absorbable_rejects_others(tmp_path):
    circ = Circuit(2, list(ABSORB), dict(name="absorb", source="test"))
    fake_seen = []

    def fake(prompts):
        fake_seen.extend(prompts)
        return [F(["op 0 -> 0.3"]) + F(["op 4 -> 0"]) + F(["op 3 -> 0"])]
    loop = WindowLoop(circ, list(ABSORB), EPS, fake, tag="fx", runs_dir=tmp_path, n_calls=1, batch=1)
    s = loop.run()
    st = s["stats"]
    assert "op 3 on q0" in fake_seen[0] and "# op 3" in fake_seen[0]
    assert len(windows(circ)[0]) == 1 and windows(circ)[0][0].ops == ABSORB
    assert st["fix_proposals"] == 2 and st["parse_errors"] == 1   # "0.3" is not a dyadic target
    assert st["rejected_verifier"] == 1                             # op 4 (lone rz(0.5) on q1) cannot be absorbed
    assert st["accepted_fix"] == 1 and st["rotations_removed_fix"] == 1 and s["after"]["rz"] == 2
    led = s["ledger"]
    assert led["bound"] <= EPS and led["window_spent"] < 1e-9
    assert s["after"]["eps_rz"] == pytest.approx(led["eps_synth"] / 2)
    assert s["final_check_vs_original"]["ok"]
    rec = [json.loads(x) for x in (tmp_path / "fx.jsonl").read_text().splitlines() if '"propose"' in x][0]
    assert rec["accepted"] and rec["action"] == "fix"
    assert [c["action"] for c in rec["candidates"]] == ["fix", "fix"]


# ------------------------------------------------------------------ Pauli-frame column and merge start
def test_rotation_paulis_frame():
    from circuitevolve.core.mutator import rotation_paulis
    assert rotation_paulis(ABSORB, 2) == {0: "+ZI", 3: "+ZI", 4: "+ZX"}
    ops = [("h", (0,), None), ("rz", (0,), 0.3), ("s", (0,), None), ("rz", (0,), 0.2), ("cx", (1, 0), None),
           ("rz", (0,), 0.1), ("t", (1,), None), ("x", (1,), None), ("rz", (1,), 0.4)]
    assert rotation_paulis(ops, 2) == {1: "+XI", 3: "+XI", 5: "+XZ", 6: "+IZ", 8: "-IZ"}
    # the claim the prompt makes: same P + commuting path -> merging the angles is exact (opposite sign subtracts)
    merged = ops[:6] + [("t", (1,), None), ("x", (1,), None)]
    merged[6] = ("rz", (1,), math.pi / 4 - 0.4)
    assert verify_window(ops, merged, 2, 1e-12)["ok"]


def test_refit_merge_start_is_exact_from_warm_start_only():
    from circuitevolve.core.mutator import rotation_paulis
    # same Pauli XI for ops 1 and 10, rotations in between (XZ, XX) commute with it -> exact merge
    ok = [("h", (0,), None), ("rz", (0,), 0.3), ("cx", (0, 1), None), ("rz", (1,), 0.7), ("cx", (0, 1), None),
          ("h", (1,), None), ("cx", (1, 0), None), ("rz", (0,), 1.1), ("cx", (1, 0), None), ("h", (1,), None),
          ("rz", (0,), 1.9)]
    assert rotation_paulis(ok, 2) == {1: "+XI", 3: "+XZ", 7: "+XX", 10: "+XI"}
    r = refit(ok, 2, {10: 0.0}, multistarts=0)
    assert r["dist"] < 1e-12 and sum(g == "rz" for g, _, _ in r["ops"]) == 3
    # same Pauli XI, but the rotation between them has P = YZ (anticommutes) -> no merge, refit cannot absorb
    bad = [("h", (0,), None), ("rz", (0,), 0.3), ("s", (0,), None), ("h", (0,), None), ("s", (0,), None),
           ("cx", (0, 1), None), ("rz", (1,), 0.7), ("cx", (0, 1), None), ("sdg", (0,), None), ("h", (0,), None),
           ("sdg", (0,), None), ("rz", (0,), 1.9)]
    assert rotation_paulis(bad, 2) == {1: "+XI", 6: "+YZ", 11: "+XI"}
    assert refit(bad, 2, {11: 0.0})["dist"] > 0.1
