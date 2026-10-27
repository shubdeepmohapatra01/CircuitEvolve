"""Loop plumbing with a stub LLM: scout -> implementer -> run in subprocess -> verify -> metric -> playbook -> test."""
import glob
import json
import os

import pytest

from circuitevolve import loop
from circuitevolve.circuit import Circuit, Gate

GIDNEY_RULE = '''"""Replace every ccz(a,b,c) by a Gidney temporary AND into a fresh ancilla, cz onto c, and
measurement-based uncomputation (4 T instead of 7). Exact: verified per site."""
from circuitevolve.circuit import Circuit, Gate
from circuitevolve.verifier import Req

def _and(a, b, t):
    return [Gate("h", (t,)), Gate("t", (t,)), Gate("cx", (a, t)), Gate("cx", (b, t)), Gate("cx", (t, a)),
            Gate("cx", (t, b)), Gate("tdg", (a,)), Gate("tdg", (b,)), Gate("t", (t,)), Gate("cx", (t, a)),
            Gate("cx", (t, b)), Gate("h", (t,)), Gate("s", (t,))]

def rewrite(c):
    out, n, nc = [], c.n, c.nc
    for g in c.gates:
        if g.name == "ccz" and g.cond is None:
            a, b, t = g.qubits
            out += _and(a, b, n) + [Gate("cz", (n, t)), Gate("h", (n,)), Gate("measure", (n,), cbit=nc),
                                    Gate("cz", (a, b), cond=nc), Gate("x", (n,), cond=nc)]
            n, nc = n + 1, nc + 1
        else:
            out.append(g)
    return Circuit(n, out, nc), Req(ancillas=n - c.n, measure=n > c.n)
'''

BROKEN_RULE = GIDNEY_RULE.replace('Gate("cz", (a, b), cond=nc), ', "")


def stub_ask(rule_src):
    def ask(prompt):
        if "(scout)" in prompt:
            return json.dumps([{"name": "measured_and_ccz", "idea": "x", "where": "ccz", "needs": "ancilla+measure",
                                "expected_t_saving": 3}])
        return "```python\n" + rule_src + "```"
    return ask


def _circ(sites, n):
    return Circuit(n, [g for s in sites for g in (Gate("h", (s[2],)), Gate("ccz", s), Gate("h", (s[2],)))])


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(loop, "ROOT", str(tmp_path))
    circuits = {"a": _circ([(0, 1, 2), (2, 3, 4), (1, 3, 5)], 6), "b": _circ([(0, 2, 4), (1, 2, 3)], 5)}
    monkeypatch.setattr(loop, "prepare", lambda e, arm: (circuits[e["name"]].copy(), 0.0))
    return tmp_path


def test_train_accepts_verified_improving_rule_then_test_applies_it(sandbox):
    loop.train("L0", [{"name": "a", "family": "rotation"}], stub_ask(GIDNEY_RULE), ideas=1, attempts=1)
    rules = glob.glob(str(sandbox / "playbook" / "L0" / "001_*.py"))
    assert len(rules) == 1
    log = [json.loads(l) for l in open(sandbox / "playbook" / "L0" / "log.jsonl")]
    att = [r for r in log if r["phase"] == "attempt"][0]
    assert att["accepted"] and att["t_before"] == 21 and att["t_after"] == 12
    rows = loop.test("L0", [{"name": "b", "family": "rotation"}])
    assert rows[0]["t"] == 8 and rows[0]["t_no_playbook"] == 14 and rows[0]["e2e_check"] == "ok"


def test_train_rejects_non_equivalent_rule(sandbox):
    loop.train("L0", [{"name": "a", "family": "rotation"}], stub_ask(BROKEN_RULE), ideas=1, attempts=2)
    assert not glob.glob(str(sandbox / "playbook" / "L0" / "0*.py"))
    log = [json.loads(l) for l in open(sandbox / "playbook" / "L0" / "log.jsonl")]
    atts = [r for r in log if r["phase"] == "attempt"]
    assert len(atts) == 2 and all(r["verdict"] == "rejected" for r in atts)
    assert not glob.glob(str(sandbox / ".cache" / "candidates" / "*.py"))      # no rejected code left as files
