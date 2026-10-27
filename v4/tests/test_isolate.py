"""The supervisor that keeps a runaway candidate from taking the harness down.

These three tests exist because the absence of this supervision cost a whole overnight run on
2026-10-27: `Loop._evaluate` and `admit_one` called `evaluate` in-process with no wall clock and no
memory cap, `LoopConfig.subprocess_limit_s` was declared and never read, and two different wide
`ancilla`-class candidates killed their parent with no traceback and no row - the training loop after 2
of 60 attempts, and the batch admission after 3 of 4 rules. Every failure here must come back as
`not_evaluated`, which neither admits nor rejects (V4_README 5.3)."""
from __future__ import annotations

import pytest

from v4 import book as B
from v4.isolate import book_paths, evaluate_isolated, supervise


def test_a_normal_child_returns_its_output():
    r = supervise("print('@@@hello')", limit_s=60, rss_gb=4, poll_s=0.2)
    assert r["status"] == "ok" and "@@@hello" in r["stdout"] and r["returncode"] == 0


def test_a_child_that_overruns_the_wall_clock_is_killed():
    r = supervise("import time; time.sleep(120)", limit_s=3, rss_gb=4, poll_s=0.2)
    assert r["status"] == "timeout", r
    assert r["seconds"] < 30, "the kill must not wait for the child to finish on its own"


def test_a_child_that_eats_memory_is_killed_before_it_takes_the_parent_with_it():
    """The overnight failure mode. 0.25 GB cap against a child allocating 100 MB a step, so the breach is
    detected in well under a second of real allocation and the machine is never at risk."""
    code = ("x = []\n"
            "import time\n"
            "for _ in range(200):\n"
            "    x.append(bytearray(100 * 1024 * 1024))\n"
            "    time.sleep(0.05)\n")
    r = supervise(code, limit_s=60, rss_gb=0.25, poll_s=0.1)
    assert r["status"] == "memory", r
    assert r["peak_rss_gb"] >= 0.25, r


def test_a_killed_child_is_not_evaluated_rather_than_rejected():
    """The category error that lost v3 eight rules: "could not check" must never read as "failed"."""
    rep = evaluate_isolated("v4/rules/handwritten/same_pauli_merge.py", bk=B.book(),
                            limit_s=2, poll_s=0.1)
    assert rep["decision"] == "not_evaluated" and rep["level"] is None
    assert rep["isolation"] == "timeout"
    assert "NOT a rejection" in rep["reason"]


def test_the_child_rebuilds_the_same_book():
    """A book rule whose file cannot be named would silently change what the candidate is measured
    against, so `book_paths` raises instead of quietly handing the child a shorter book."""
    bk = B.book()
    paths = book_paths(bk)
    assert len(paths) == len(bk)
    rebuilt = [B.load_rule(p, t) for p, t in paths]
    assert [r.name for r in rebuilt] == [r.name for r in bk]
    assert B.digest(rebuilt) == B.digest(bk)

    class Nameless:
        name, tier = "no_such_rule_on_disk", "accepted"
    with pytest.raises(KeyError):
        book_paths([Nameless()])
