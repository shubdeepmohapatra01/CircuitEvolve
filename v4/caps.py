"""Caps - V4_README section 10.

    > Cap the LLM on wall clock and tokens. Never cap verification on wall clock.

v3's 300 s per-circuit limit discarded two correct, verified, IMPROVING rules
(`staircase_knapsack_exact_angle_assignment`: qft_8 1583->1417, qpe_8 11485->10249, qae_13 4526->4370;
`joint_budget_direct_rotation_synthesis`: hhl_8 29029->24967). A wall-clock cap on verification biases
which rules get admitted by how fast the machine was that day; an opcode budget does not.

Two caps, for the two kinds of unboundedness:

    OpcodeBudget(n)     a rule's own trigger / apply. Deterministic, machine-independent, reproducible:
                        `sys.settrace` counts Python lines executed inside the rule and raises
                        `OpcodeExceeded` past the budget. A call counter does not help if one call hangs
                        inside itself, so this counts lines, not calls.
    LLM subprocesses    wall clock + --max-budget-usd (v4/agent/run.py). Infrastructure, not science: a
                        timeout there retries or moves on, it does not discard a verified result.

Numpy / scipy spend their time in C, where no Python line executes, so a rule that calls one enormous
`scipy.linalg` routine is not caught by this. That is deliberate: the frozen libraries terminate, and the
budget exists to stop RULE code looping, not to police library calls. The per-attempt wall clock of the
whole LLM step remains the outer backstop.
"""
from __future__ import annotations

import sys
import threading
import time

DEFAULT_BUDGET = 200_000_000          # Python lines; ~minutes of pure-Python work, hours of a hot loop


class OpcodeExceeded(RuntimeError):
    def __init__(self, used: int, budget: int):
        super().__init__(f"opcode budget exceeded: {used} >= {budget} Python lines executed in rule code")
        self.used, self.budget = used, budget


class OpcodeBudget:
    """Context manager counting Python lines executed inside the block.

        with OpcodeBudget(10_000_000) as b:
            matches = rule.trigger(circuit)
        b.used          # lines actually executed

    Re-entrant use is refused (one budget per thread at a time). Nested budgets would each install a
    trace function and the inner one would silently uninstall the outer.
    """

    _active = threading.local()

    def __init__(self, budget: int = DEFAULT_BUDGET, check_every: int = 4096):
        self.budget = int(budget)
        self.check_every = int(check_every)
        self.used = 0
        self.seconds = 0.0
        self._t0 = 0.0
        self._prev = None

    def _trace(self, frame, event, arg):
        self.used += 1
        if self.used >= self.budget:
            raise OpcodeExceeded(self.used, self.budget)
        return self._trace

    def __enter__(self):
        if getattr(OpcodeBudget._active, "on", False):
            raise RuntimeError("OpcodeBudget is already active in this thread")
        OpcodeBudget._active.on = True
        self._t0 = time.perf_counter()
        self._prev = sys.gettrace()
        sys.settrace(self._trace)
        return self

    def __exit__(self, et, ev, tb):
        sys.settrace(self._prev)
        OpcodeBudget._active.on = False
        self.seconds = time.perf_counter() - self._t0
        return False

    def report(self) -> dict:
        return dict(opcodes=self.used, budget=self.budget, seconds=round(self.seconds, 3))


def run_capped(fn, *args, budget: int = DEFAULT_BUDGET, **kw) -> tuple:
    """(result, report) - or (None, report with 'exceeded': True) if the budget ran out."""
    b = OpcodeBudget(budget)
    try:
        with b:
            out = fn(*args, **kw)
    except OpcodeExceeded as e:
        return None, dict(b.report(), exceeded=True, reason=str(e))
    return out, dict(b.report(), exceeded=False)
