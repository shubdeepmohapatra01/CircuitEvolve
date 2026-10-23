"""A call stopped by --max-budget-usd aborts its attempt (aborted_budget) and never enters a retry path.

The agent CLI is mocked with the JSON it really returns for a budget stop (observed 2026-10-20):
subtype error_max_budget_usd, terminal_reason budget_exhausted, exit code 1.
"""
from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import v3.agent.run as R

BUDGET_STOP = dict(type="result", subtype="error_max_budget_usd", is_error=True, terminal_reason="budget_exhausted",
                   total_cost_usd=4.01, num_turns=7, result="", errors=["Reached maximum budget ($4)"], usage={})
CARD = dict(name="test_card_rule", domain="dv", kind="rewrite", contract="exact", identity="x", correctness="x",
            trigger="x", expected_effect="x", source="x")


def run_with(monkeypatch, tmp_path, responses):
    calls = []
    real = subprocess.run
    monkeypatch.setattr(R, "AGENT_CLI", "agent-cli")
    monkeypatch.setattr(R, "SCOUT_MODEL", "scout-model")
    monkeypatch.setattr(R, "IMPL_MODEL", "implementer-model")

    def fake(cmd, *a, **k):
        if cmd and cmd[0] == R.AGENT_CLI:
            calls.append(cmd[cmd.index("--model") + 1])
            d = responses[len(calls) - 1]
            return SimpleNamespace(stdout=json.dumps(d), stderr="", returncode=1 if d.get("is_error") else 0)
        if "v3.tools.admit" in " ".join(map(str, cmd)):
            raise AssertionError("admission must not run after a budget abort")
        return real(cmd, *a, **k)
    monkeypatch.setattr(R.subprocess, "run", fake)
    monkeypatch.setattr(R, "P2", tmp_path)
    rec = R.attempt("qft_8", 1, {})
    return rec, calls


def test_scout_budget_stop_aborts_attempt(monkeypatch, tmp_path):
    rec, calls = run_with(monkeypatch, tmp_path, [BUDGET_STOP])
    assert rec["decision"] == "aborted_budget" and "scout" in rec["reason"]
    assert calls == [R.SCOUT_MODEL]                               # no scout retry, no implementer
    rows = [json.loads(l) for l in (tmp_path / "tokens.jsonl").read_text().splitlines()]
    assert rows[0]["subtype"] == "error_max_budget_usd" and rows[0]["cost_usd"] == 4.01


def test_implementer_budget_stop_aborts_attempt_without_retry(monkeypatch, tmp_path):
    scout_ok = dict(type="result", subtype="success", is_error=False, result=json.dumps(CARD), total_cost_usd=0.5,
                    num_turns=3, usage={})
    rec, calls = run_with(monkeypatch, tmp_path, [scout_ok, BUDGET_STOP])
    assert rec["decision"] == "aborted_budget" and "implementer" in rec["reason"]
    assert calls == [R.SCOUT_MODEL, R.IMPL_MODEL]                 # no implementer retry, no scout retry
