"""Tier 2: commutation table, rule DSL, one-time exact rule verification, matching, fixpoint, library hashing."""
import itertools
import json
import random

import numpy as np
import pytest

from circuitevolve.v2.tier2.apply import (apply_library, cost, exact_guard, find_match, numeric_guard, _qpos,
                                          simulate)
from circuitevolve.v2.tier2.commute import GATES, ONE_Q, commute
from circuitevolve.v2.tier2.enumerate_ids import enumerate_identities, gate_matrix
from circuitevolve.v2.tier2.rules import Library, Rule, RuleError, parse_rules, parse_seq, verify_rule


def R(name, p, r, side="commute"):
    return Rule(name, parse_seq(p), parse_seq(r), side, "test")


def _concrete_gates(n):
    out = [(g, (q,)) for g in ONE_Q for q in range(n)]
    out += [("cx", (a, b)) for a, b in itertools.permutations(range(n), 2)]
    out += [("cz", (a, b)) for a, b in itertools.permutations(range(n), 2)]
    return out


def _dense(g, n):
    vs = "abcd"
    return gate_matrix((g[0], tuple(vs[q] for q in g[1])), n)


# ----------------------------------------------------------------------------------------------- commutation
def test_commutation_table_sound_on_3_qubits():
    gs = _concrete_gates(3)
    n_comm = 0
    for g1, g2 in itertools.product(gs, gs):
        A, B = _dense(g1, 3), _dense(g2, 3)
        really = np.allclose(A @ B, B @ A)
        if commute(g1, g2):
            n_comm += 1
            assert really, (g1, g2)
    assert n_comm > len(gs) ** 2 // 2          # table is not trivially conservative


def test_commutation_examples():
    assert commute(("t", (0,)), ("cx", (0, 1)))          # phase on control
    assert not commute(("t", (1,)), ("cx", (0, 1)))      # phase on target
    assert commute(("x", (1,)), ("cx", (0, 1)))          # X on target
    assert commute(("cx", (0, 1)), ("cx", (0, 2)))       # shared control
    assert commute(("cx", (0, 2)), ("cx", (1, 2)))       # shared target
    assert not commute(("cx", (0, 1)), ("cx", (1, 2)))   # target of one = control of other
    assert not commute(("h", (0,)), ("t", (0,)))
    assert commute(("cz", (0, 1)), ("cz", (1, 0)))


# ----------------------------------------------------------------------------------------------- DSL + verification
def test_tt_to_s_rule_verifies():
    v = verify_rule(R("tt", "t a; t a", "s a"))
    assert v["ok"] and v["certified"] and v["method"] == "basis-exhaustive"


def test_wrong_sign_rule_rejected():
    v = verify_rule(R("bad", "t a; t a", "sdg a"))
    assert not v["ok"]
    v = verify_rule(R("bad2", "cx a b; t b; cx a b", "t b"))           # needs cx-conjugated parity, false
    assert not v["ok"]


def test_true_multiqubit_identity_and_global_phase():
    # X T X = e^{i pi/4} Tdg: a true identity only up to global phase; (T, gates) drops (1,3) -> (1,1)
    v = verify_rule(R("xtx", "x a; t a; x a", "tdg a"))
    assert v["ok"] and v["global_phase"] != [1.0, 0.0]
    v = verify_rule(R("xtx_bad", "x a; t a; x a", "t a"))
    assert not v["ok"]
    v = verify_rule(R("xtxt", "x a; t a; x a; t a", "id"))           # = e^{i pi/4} I
    assert v["ok"]
    v = verify_rule(R("cxcx", "cx a b; cx a b", ""))
    assert v["ok"]


def test_malformed_rules():
    assert not verify_rule(R("same", "s a", "s a"))["ok"]                     # not decreasing
    with pytest.raises(RuleError):
        parse_seq("ccx a b c")                                                 # gate set
    with pytest.raises(RuleError):
        parse_seq("cx a a")
    assert not verify_rule(R("disc", "t a; t b", "t a; t b"))["ok"]
    assert "not connected" in verify_rule(R("disc3", "h a; h b; h a; h b", "id"))["reason"]
    assert verify_rule(R("conn", "h a; h a", "id"))["ok"]


def test_parse_rules_block():
    text = """some prose
RULE merge_tt
PATTERN: t a; t a
REPLACE: s a
MEANING: two T on one wire make S
END
RULE broken
PATTERN: ccx a b c
REPLACE: id
END
"""
    rules, errs = parse_rules(text, "llm")
    assert [r.name for r in rules] == ["merge_tt"] and rules[0].meaning.startswith("two T")
    assert errs and errs[0][0] == "broken"


# ----------------------------------------------------------------------------------------------- matching
def test_matching_crosses_commuting_gate_only():
    tt = R("tt", "t a; t a", "s a")
    g = [("t", (0,)), ("cx", (0, 1)), ("t", (0,))]
    assert find_match(g, _qpos(g, 2), 0, tt) is not None
    g = [("t", (0,)), ("h", (0,)), ("t", (0,))]
    assert find_match(g, _qpos(g, 1), 0, tt) is None
    g = [("t", (1,)), ("cx", (0, 1)), ("t", (1,))]
    assert find_match(g, _qpos(g, 2), 0, tt) is None
    g = [("t", (0,)), ("cx", (0, 1)), ("t", (0,))]
    assert find_match(g, _qpos(g, 2), 0, R("tt_c", "t a; t a", "s a", "contiguous")) is None


def test_matching_right_placement():
    # cx a b ; x b ; cx a b with x b in between: x on target commutes with both cx -> cancel to x b
    r = R("cxcx", "cx a b; cx a b", "")
    g = [("cx", (0, 1)), ("x", (1,)), ("cx", (0, 1))]
    res = apply_library(g, 2, [r])
    assert res["gates"] == [("x", (1,))]


def test_fixpoint_terminates_and_preserves_unitary():
    rng = random.Random(1)
    lib = Library([R("tt", "t a; t a", "s a"), R("ttdg", "t a; tdg a", ""), R("tdgt", "tdg a; t a", ""),
                   R("ss", "s a; s a", "z a"), R("hh", "h a; h a", ""), R("cxcx", "cx a b; cx a b", ""),
                   R("zz", "z a; z a", ""), R("xx", "x a; x a", ""), R("czcz", "cz a b; cz a b", ""),
                   R("tdgtdg", "tdg a; tdg a", "sdg a")])
    for r in lib.rules:
        assert verify_rule(r)["ok"], r.name
    for trial in range(30):
        n = rng.randint(2, 4)
        gs = _concrete_gates(n)
        g = [rng.choice(gs) for _ in range(rng.randint(5, 60))]
        res = apply_library(g, n, lib)
        assert res["fixpoint"]
        assert cost(res["gates"]) <= cost(g)
        assert numeric_guard(g, res["gates"], n, seed=trial)["ok"]
        if trial < 6:
            assert exact_guard(g, res["gates"], n)["ok"]
        # idempotent at the fixpoint
        assert apply_library(res["gates"], n, lib)["gates"] == res["gates"]


def test_simulator_guard_detects_difference():
    g1 = [("h", (0,)), ("cx", (0, 1))]
    g2 = [("h", (0,)), ("cx", (1, 0))]
    assert not numeric_guard(g1, g2, 2)["ok"]
    psi = np.zeros(4, complex)
    psi[0] = 1
    out = simulate(g1, 2, psi)
    assert np.allclose(np.abs(out) ** 2, [0.5, 0, 0, 0.5])


# ----------------------------------------------------------------------------------------------- library
def test_library_hash_save_load(tmp_path):
    v0 = Library([], "v0")
    assert v0.sha256 == Library([], "other").sha256
    v1 = v0.extended([R("tt", "t a; t a", "s a")], "v1")
    assert v1.parent_sha == v0.sha256 and v1.sha256 != v0.sha256
    p = tmp_path / "lib.json"
    v1.save(p)
    assert Library.load(p).sha256 == v1.sha256
    d = json.loads(p.read_text())
    d["rules"][0]["replacement"] = "sdg a"
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        Library.load(p)
    # variable renaming does not change the content hash
    assert Library([R("x", "t b; t b", "s b")]).sha256 == Library([R("y", "t a; t a", "s a")]).sha256


def test_enumeration_finds_tt_and_verifies():
    e = enumerate_identities(1, 3)
    found = {(tuple(s), tuple(r)) for s, r in e["identities"]}
    assert ((("t", ("a",)), ("t", ("a",))), (("s", ("a",)),)) in found
    for s, r in e["identities"][:40]:
        assert verify_rule(Rule("e", tuple(s), tuple(r)))["ok"]
