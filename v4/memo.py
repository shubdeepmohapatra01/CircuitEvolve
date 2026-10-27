"""`optimize_memo` - V4_README section 5.1, mechanism 1.

> A given (book-state, circuit) pair is verified ONCE, EVER - not once per `test_rule` call, not once
> per attempt.

That is the single biggest saving in the plan. The measured cost of v3's loop was 139 `test_rule` calls
at 7.7-12.6 min each with a NO-OP rule: ~23 h of the 53.9 h run, spent re-running the same book over the
same five circuits. The key is `(book digest, circuit, eps, order)`; the book digest hashes each rule's
source file and its declared tags, so editing a rule invalidates exactly the entries that used it.

    cur, cost = residual(circuit_label, book, eps)     # the circuit AFTER the book, cached on disk
    optimize_memo(label, book, eps)                    # the whole Result (in-process) + a disk record

The on-disk half (`v4/.cache/residual/`) survives between processes, which is what makes the agent loop's
repeated `test_rule` calls cheap. Entries store the resulting circuit as QASM / IR text plus the cost, and
are keyed by the same digest, so they can never be reused for a different book.
"""
from __future__ import annotations

import hashlib
import json
import time

from . import book as B
from .judge import dv as J
from .paths import CACHE
from .runner import optimize

DISK = CACHE / "residual"
DISK.mkdir(parents=True, exist_ok=True)
_MEM: dict = {}
STATS: dict = dict(mem_hits=0, disk_hits=0, misses=0, seconds_saved=0.0)


def key(label: str, bk, eps: float, order: str = "best") -> str:
    return hashlib.sha256(f"{label}|{B.digest(bk)}|{eps!r}|{order}".encode()).hexdigest()[:24]


def _write_disk(k: str, label: str, bk, eps: float, order: str, res) -> None:
    c = res.circuit
    text = c.to_qasm() if hasattr(c, "to_qasm") else None
    rec = dict(key=k, label=label, eps=eps, order=order, book=[r.name for r in bk],
               book_digest=B.digest(bk), cost=res.cost, err_rules=res.err_rules, err_bound=res.err_bound,
               seconds=round(res.seconds, 2), summary=res.summary(), qasm=text,
               ledger=res.ledger.report() if res.ledger else None, time=time.time())
    (DISK / f"{k}.json").write_text(json.dumps(rec, default=str, indent=1) + "\n")


def optimize_memo(label: str, bk, eps: float, order: str = "best", reference=None, force: bool = False,
                  **kw):
    """The Result of running `bk` on the suite circuit `label` at `eps`. Memoised in-process on
    (book digest, label, eps, order); the cost summary is also written to disk for the next process."""
    k = key(label, bk, eps, order)
    if not force and k in _MEM:
        STATS["mem_hits"] += 1
        STATS["seconds_saved"] += _MEM[k].seconds
        return _MEM[k]
    STATS["misses"] += 1
    start = J.load(label)
    res = optimize(start, bk, eps, reference=reference if reference is not None else start, order=order, **kw)
    _MEM[k] = res
    _write_disk(k, label, bk, eps, order, res)
    return res


def residual(label: str, bk, eps: float, order: str = "best", **kw):
    """(circuit after the book, its cost, the ledger as the book left it). A candidate is then applied to
    THIS residual, so `check_on_target` verifies only the candidate's own applications - v3 re-ran the
    whole book plus the candidate over 5 circuits, 139 times."""
    res = optimize_memo(label, bk, eps, order=order, **kw)
    return res.circuit, res.cost, (res.ledger.copy() if res.ledger else None)


def cached_cost(label: str, bk, eps: float, order: str = "best") -> dict | None:
    """The cost of a (book, circuit, eps) run from an EARLIER PROCESS, or None."""
    p = DISK / f"{key(label, bk, eps, order)}.json"
    if not p.is_file():
        return None
    STATS["disk_hits"] += 1
    return json.loads(p.read_text())["cost"]


def stats() -> dict:
    return dict(STATS, entries=len(_MEM), disk_entries=len(list(DISK.glob("*.json"))))


def clear() -> None:
    _MEM.clear()
    for k in STATS:
        STATS[k] = 0
