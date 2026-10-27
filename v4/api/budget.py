"""A rule's view of the shared error budget (V4_README section 8).

The runner installs the live `Ledger` around every call into rule code, so a rule can ask how much error
it is allowed to spend and draw it:

    budget.remaining()            error still available to rule rewrites, for THIS circuit
    budget.draw(amount) -> bool   reserve it (recorded against this rule in the admission json)
    budget.total() / spent()
    with budget.trial(amount):    draw, and give it back if the block raises

Outside a runner (e.g. while a rule is being written by hand) `remaining()` returns 0.0 and `draw` returns
False, so a rule must treat a refused draw as "do the exact rewrite or nothing" - never as a reason to
snap an angle anyway.

This is the piece that makes budget ALLOCATION part of the search: DPF spends on a fixed greedy schedule,
while a rule here decides how much of the 5e-4 its own rewrite is worth.
"""
from __future__ import annotations

import contextlib
import threading

_LOCAL = threading.local()


def _state():
    s = getattr(_LOCAL, "s", None)
    if s is None:
        s = _LOCAL.s = dict(ledger=None, rule=None)
    return s


@contextlib.contextmanager
def installed(ledger, rule_name: str):
    """Runner-side: make `ledger` the budget that rule code sees while it runs."""
    s = _state()
    prev = dict(s)
    s.update(ledger=ledger, rule=rule_name)
    try:
        yield
    finally:
        s.update(prev)


def total() -> float:
    s = _state()
    return 0.0 if s["ledger"] is None else float(s["ledger"].rule_share)


def spent() -> float:
    s = _state()
    return 0.0 if s["ledger"] is None else float(s["ledger"].spent)


def remaining() -> float:
    s = _state()
    return 0.0 if s["ledger"] is None else float(s["ledger"].remaining)


def draw(amount: float) -> bool:
    s = _state()
    if s["ledger"] is None:
        return False
    return bool(s["ledger"].draw(s["rule"] or "unknown", float(amount)))


def refund(amount: float) -> None:
    s = _state()
    if s["ledger"] is not None:
        s["ledger"].refund(s["rule"] or "unknown", float(amount))


@contextlib.contextmanager
def trial(amount: float):
    """Draw `amount`; give it back if the block raises. Yields True if the draw succeeded."""
    ok = draw(amount)
    try:
        yield ok
    except BaseException:
        if ok:
            refund(amount)
        raise
