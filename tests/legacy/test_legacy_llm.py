"""P4 tests: prompt/parse round trip, blinding, guards (no LLM calls)."""
from circuitevolve.legacy.adder.llm import (BLIND_NAMES, OPEN_NAMES, _rename_prog, build_prompt, llm_search,
                                      parse_programs)
from circuitevolve.legacy.adder.slice import CUCCARO, GIDNEY_A, GIDNEY_B, to_source

LEAKY = ["adder", "carry", "gidney", "cuccaro", "and_compute", "and_uncompute", "temporary"]


def _fenced(p, names):
    return "Reasoning.\n```python\n" + to_source(_rename_prog(p, names)) + "```\n"


def test_round_trip_open_and_blind():
    for p in (CUCCARO, GIDNEY_A, GIDNEY_B):
        for blinded, names in ((False, OPEN_NAMES), (True, BLIND_NAMES)):
            progs, errs = parse_programs(_fenced(p, names), blinded)
            assert errs == [] and progs == [p]


def test_blinded_prompt_has_no_cue_words():
    for tier in ("A", "B"):
        txt = build_prompt(GIDNEY_A if tier == "A" else GIDNEY_B, (4.0, 32, 26, 9, 9), [], [], True, tier, 4).lower()
        assert not [w for w in LEAKY if w in txt]


def test_parser_rejects_code_and_unknown_roles():
    bad = "```python\nimport os\nFWD = (G('cx', 'a', 'q9'),)\nTOP = ()\nBWD = ()\n```"
    progs, errs = parse_programs(bad, False)
    assert progs == [] and errs
    evil = "```python\nFWD = (G(__import__('os').system('true')),)\nTOP=()\nBWD=()\n```"
    progs, errs = parse_programs(evil, False)
    assert progs == [] and errs


def test_llm_search_counts_errors_and_accepts_good():
    def fake(prompts):
        out = []
        for i, _ in enumerate(prompts):
            out.append(RuntimeError("cli: is_error=True") if i == 0 else _fenced(GIDNEY_A, OPEN_NAMES))
        return out
    _, _, stats, best = llm_search(CUCCARO, "A", fake, n_calls=3, batch=3)
    assert stats["llm_error"] == 1 and stats["accepted"] == 1 and stats["duplicate"] == 1
    assert stats["best"][0] == 4.0 and best == GIDNEY_A


# ------------------------------------------------------------------ harness fixes (2026-10-11)
import subprocess
import threading
from collections import Counter

from circuitevolve.legacy.adder.llm import normalise_gate, parse_programs_p4
from circuitevolve.llm_backends import make_api_backend, make_batch_merger, make_cli_backend


def test_parser_skips_hand_traces_and_text_blocks():
    trace = "```\nH(t)\nT\u2020(t)\nCNOT(a, t)\n```\n"
    diagram = "```text\na: --*--\n```\nprose\n"
    resp = "Trace:\n" + trace + diagram + _fenced(GIDNEY_B, OPEN_NAMES)
    c = Counter()
    progs, errs = parse_programs(resp, False, counts=c)
    assert progs == [GIDNEY_B] and errs == [] and c["non_program_block"] == 2
    # the P4 parser counted the trace as a SyntaxError and misaligned on the ```text fence
    _, old_errs = parse_programs_p4(resp, False)
    assert old_errs
    # a response with only traces is one error, not one per block
    progs, errs = parse_programs("x\n" + trace + trace, False, counts=c)
    assert progs == [] and errs == ["no program block in response"]


def test_dagger_and_case_aliases_normalised():
    known = {"t", "tdg", "s", "sdg", "cx", "ccx", "h"}
    for alias, canon in (("T\u2020", "tdg"), ("t^\u2020", "tdg"), ("Tdg", "tdg"), ("tdag", "tdg"),
                         ("S\u2020", "sdg"), ("sdagger", "sdg"), ("CNOT", "cx"), ("H", "h"), ("tdg", "tdg")):
        assert normalise_gate(alias, known) == canon
    assert normalise_gate("rz", known) == "rz" and normalise_gate("x\u2020", known) == "x\u2020"
    src = to_source(GIDNEY_B).replace("'tdg'", "'T\u2020'").replace("'h'", "'H'")
    c = Counter()
    progs, errs = parse_programs("```python\n" + src + "```", False, counts=c)
    assert progs == [GIDNEY_B] and errs == [] and c["normalised_gate"] > 0


def test_single_call_template_and_still_no_exec():
    resp = "```python\nFWD = (G('ccx', 'a', 'b', 'z'))\nTOP = ()\nBWD = ()\n```"
    progs, errs = parse_programs(resp, False)
    assert errs == [] and progs[0].fwd == (("ccx", ("a", "b", "z"), None, None),)
    evil = "```python\nFWD = (G(open('/etc/passwd').read()),)\nTOP=()\nBWD=()\n```"
    assert parse_programs(evil, False)[0] == []


def test_prompt_format_rules_toggle():
    new = build_prompt(CUCCARO, (14.0, 112, 17, 1, 1), [], [], False, "B", 4)
    old = build_prompt(CUCCARO, (14.0, 112, 17, 1, 1), [], [], False, "B", 4, format_rules=False)
    assert new.startswith(old) and "plain text outside code blocks" in new and "plain text outside" not in old


def _fake_llm(script):
    """script: list of per-attempt lists of results, consumed in order."""
    calls = []

    def llm(reqs, max_concurrency=None):
        calls.append(reqs)
        return script[len(calls) - 1][: len(reqs)]
    return llm, calls


def test_api_backend_errors_empty_and_retries():
    ok = {"text": "hello", "stop_reason": "end_turn", "usage": {"input_tokens": 5, "output_tokens": 2}}
    llm, calls = _fake_llm([
        [ok, {"error": "APIConnectionError: connection reset"}, {"text": "", "stop_reason": "max_tokens"},
         {"error": "invalid_request: bad"}],
        [ok, {"text": "  "}],
        [ok],
    ])
    be = make_api_backend(llm, model=lambda: "m1", retries=3, backoff=0, sleep=lambda s: None)
    out = be(["p1", "p2", "p3", "p4"])
    assert out[0] == "hello" and out[1] == "hello" and out[2] == "hello"
    assert isinstance(out[3], RuntimeError) and "invalid_request" in str(out[3])
    assert calls[0][0]["thinking"] == {"type": "disabled"} and calls[0][0]["model"] == "m1"
    assert calls[0][0]["max_tokens"] == 8000
    assert [len(c) for c in calls] == [4, 2, 1]
    s = be.stats
    assert s["calls"] == 4 and s["ok"] == 3 and s["retries"] == 3 and s["failed"] == 1 and s["empty"] == 2


def test_api_backend_whole_batch_exception_and_retry_cap():
    def boom(reqs, max_concurrency=None):
        raise ConnectionError("connection refused")
    be = make_api_backend(boom, retries=2, backoff=0, sleep=lambda s: None)
    out = be(["a", "b"])
    assert all(isinstance(o, RuntimeError) for o in out) and be.stats["retries"] == 4 and be.stats["failed"] == 2

    def ceiling(reqs, max_concurrency=None):
        raise RuntimeError("per-frame token ceiling reached")
    be = make_api_backend(ceiling, retries=3, backoff=0, sleep=lambda s: None)
    be(["a"])
    assert be.stats["retries"] == 0


def test_batch_merger_merges_concurrent_calls():
    seen = []

    def llm(reqs, max_concurrency=None):
        seen.append(len(reqs))
        return [{"text": r["prompt"].upper()} for r in reqs]
    m = make_batch_merger(llm, window=0.3)
    res = {}

    def worker(i):
        res[i] = m([{"prompt": f"p{i}a"}, {"prompt": f"p{i}b"}])
    ts = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    [t.start() for t in ts]
    [t.join(10) for t in ts]
    assert {i: [r["text"] for r in v] for i, v in res.items()} == {i: [f"P{i}A", f"P{i}B"] for i in range(3)}
    assert sum(seen) == 6 and len(seen) <= 2


def test_cli_backend_diagnostics_and_retry():
    class P:
        def __init__(self, rc, out, err=""):
            self.returncode, self.stdout, self.stderr = rc, out, err
    seq = [P(1, '{"type":"result","subtype":"error_during_execution","is_error":true,"result":"API Error: 529 overloaded"}'),
           P(0, '{"type":"result","subtype":"success","is_error":false,"result":"text!"}')]

    def runner(cmd, **kw):
        assert kw["timeout"] == 42 and "--max-turns" in cmd
        return seq.pop(0)
    be = make_cli_backend(binary="claude", timeout=42, workers=1, retries=1, backoff=0, sleep=lambda s: None,
                          extra_args=("--max-turns", "1"), runner=runner)
    assert be(["hi"]) == ["text!"] and be.stats["exit"] == 1 and be.stats["retries"] == 1

    def limit(cmd, **kw):
        return P(1, '{"subtype":"success","is_error":true,"result":"Claude AI usage limit reached"}')
    be = make_cli_backend(binary="claude", workers=1, retries=2, sleep=lambda s: None, runner=limit)
    (e,) = be(["hi"])
    assert "usage limit" in str(e) and "exit 1" in str(e) and be.stats["retries"] == 0

    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw["timeout"])
    be = make_cli_backend(binary="claude", timeout=7, workers=1, retries=1, sleep=lambda s: None, runner=slow)
    (e,) = be(["hi"])
    assert "timeout after 7s" in str(e) and be.stats["timeout"] == 1 and be.stats["retries"] == 0


def test_llm_search_reports_backend_and_non_program_blocks():
    def fake(prompts):
        fake.stats["calls"] += len(prompts)
        return ["```\nH(t)\n```\n" + _fenced(GIDNEY_A, OPEN_NAMES) for _ in prompts]
    fake.stats = Counter(calls=5)          # pre-existing usage must not leak into this run's delta
    _, _, stats, best = llm_search(CUCCARO, "A", fake, n_calls=2, batch=2)
    assert stats["parse_error"] == 0 and stats["non_program_block"] == 2 and stats["backend"] == {"calls": 2}
    assert best == GIDNEY_A
