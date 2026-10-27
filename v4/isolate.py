"""Run one candidate evaluation in a child process that cannot take the harness down with it.

WHY THIS FILE EXISTS. `v4.tools.evaluate.evaluate` runs arbitrary LLM-written rule code and then a
verification whose cost is set by the candidate's own output width. Both the training loop and
`v4.tools.admit` called it IN-PROCESS, with no wall clock and no memory cap, and both died silently
because of it on the night of 2026-10-27:

* the batch admission of what P6 found processed 3 of its 4 rules and then vanished (no traceback, no
  event row) while evaluating `multilinear_phase_polynomial_and_ancilla_resynthesis`;
* the training loop spent 2 of 60 attempts, then vanished the same way on a
  `hamming_weight_phasing_equal_angle_groups` candidate for qpe_8 - an `ancilla`-class rewrite whose
  output is wide enough for the whole-circuit check to allocate past RAM.

`LoopConfig.subprocess_limit_s` had existed since the loop was written and was never read, which is why
nothing caught either one. A candidate that is too expensive or too wide to check is INFRASTRUCTURE
hitting its limit, never evidence against the rule, so every failure here returns `not_evaluated` -
the one decision that neither admits nor rejects (V4_README 5.3).
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time

from pathlib import Path

import psutil

from . import book as B
from .paths import DV_PY, REPO

DEFAULT_LIMIT_S = 1800.0
DEFAULT_RSS_GB = 12.0          # of 24 GB: a child may use half the machine, never swap it to death

_CHILD = """\
import json, sys
from v4 import book as B
from v4.tools.evaluate import evaluate
bk = [B.load_rule(p, t) for p, t in {book!r}]
rep = evaluate({path!r}, bk=bk, eps={eps!r}, target={target!r}, opcode_budget={budget!r})
rep.pop('t0', None)
print('@@@' + json.dumps(rep, default=str))
"""


def book_paths(bk) -> list[tuple[str, str]]:
    """(path, tier) for each rule in `bk`, so a child can rebuild the SAME book.

    `Rule` is frozen and carries no path, so `book.load_rule` records one in `book.SRC` as it loads.
    A rule whose file we cannot name would silently change the book the candidate is measured against,
    so that is an error here rather than a quietly shorter book."""
    out = []
    for r in bk:
        p = B.SRC.get(r.name)
        if p is None:
            raise KeyError(f"no source file recorded for book rule {r.name!r}; cannot isolate")
        out.append((str(p), r.tier))
    return out


def _tree_rss(proc) -> int:
    """Resident bytes of the child and anything it spawned. 0 once it is gone."""
    try:
        total = proc.memory_info().rss
        for c in proc.children(recursive=True):
            try:
                total += c.memory_info().rss
            except psutil.Error:
                pass
        return total
    except psutil.Error:
        return 0


def supervise(code: str, limit_s: float, rss_gb: float, poll_s: float = 2.0) -> dict:
    """Run `code` in a child under a wall clock AND a resident-memory cap.

    -> dict(status='ok'|'timeout'|'memory'|'crash', stdout, stderr, returncode, peak_rss_gb, seconds).

    The cap is enforced by POLLING, not by `setrlimit`: macOS reports RLIMIT_AS and RLIMIT_DATA as
    unlimited and then refuses to set any finite value ("current limit exceeds maximum limit"), so the
    only portable cap is the parent watching the child's tree and killing it. Polling also catches memory
    a grandchild allocates, which a cap on the child alone would miss."""
    cap = int(rss_gb * 1024 ** 3)
    t0 = time.time()
    out_f, err_f = tempfile.TemporaryFile("w+"), tempfile.TemporaryFile("w+")
    p = subprocess.Popen([str(DV_PY), "-c", code], cwd=REPO, stdout=out_f, stderr=err_f, text=True,
                         env=dict(os.environ, V4_ISOLATED="1"))
    try:
        proc = psutil.Process(p.pid)
    except psutil.Error:
        proc = None
    peak, status = 0, "ok"
    while p.poll() is None:
        if time.time() - t0 > limit_s:
            status = "timeout"
            break
        if proc is not None:
            peak = max(peak, _tree_rss(proc))
            if peak > cap:
                status = "memory"
                break
        time.sleep(poll_s)
    if status != "ok":
        _kill(p)
    p.wait()
    out_f.seek(0), err_f.seek(0)
    stdout, stderr = out_f.read(), err_f.read()
    out_f.close(), err_f.close()
    return dict(status=status, stdout=stdout, stderr=stderr, returncode=p.returncode,
                peak_rss_gb=round(peak / 1024 ** 3, 2), seconds=round(time.time() - t0, 1))


def evaluate_isolated(path, bk=None, eps: float = 1e-3, target=None, opcode_budget=None,
                      limit_s: float = DEFAULT_LIMIT_S, rss_gb: float = DEFAULT_RSS_GB,
                      poll_s: float = 2.0) -> dict:
    """`evaluate` in a supervised child. Never raises; every failure is `not_evaluated`."""
    path = Path(path)
    bk = B.book() if bk is None else bk
    code = _CHILD.format(book=book_paths(bk), path=str(path), eps=eps, target=target,
                         budget=opcode_budget)
    r = supervise(code, limit_s, rss_gb, poll_s)
    common = dict(seconds=r["seconds"], isolation=r["status"], peak_rss_gb=r["peak_rss_gb"])
    tail = [l for l in r["stdout"].splitlines() if l.startswith("@@@")]
    if r["status"] == "ok" and tail:
        return json.loads(tail[-1][3:]) | common
    why = {"timeout": f"harness wall clock {limit_s:g}s exceeded in a subprocess",
           "memory": f"the candidate's check reached {r['peak_rss_gb']:.1f} GB resident, over the "
                     f"{rss_gb:g} GB cap",
           }.get(r["status"], f"the child exited {r['returncode']} without a report")
    return dict(candidate=str(path), decision="not_evaluated", level=None, circuits=[], excluded={},
                static="", returncode=r["returncode"],
                reason=f"{why}. This is infrastructure, NOT a rejection: the rule is neither admitted "
                       f"nor rejected.\n{(r['stderr'] or r['stdout'])[-1200:]}") | common


def _kill(p) -> None:
    """SIGTERM the whole tree, then SIGKILL what is left - a verification child of its own must go too."""
    try:
        procs = [psutil.Process(p.pid)]
        procs += procs[0].children(recursive=True)
    except psutil.Error:
        return
    for q in procs:
        try:
            q.terminate()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(procs, timeout=5)
    for q in alive:
        try:
            q.kill()
        except psutil.Error:
            pass
