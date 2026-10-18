"""Reflector seam (PLAN_P1 P1.4): the interface point 2 redesigns, with today's behavior.

Today the reflector input is the triple (improvements[-4:], failures[-6:], stats) assembled by
the loop and rendered by Playbook.reflect_prompt; credit is already metric-gated
(evidence="improvement"). Point 2 changes WHAT the reflector reads — structured accept anatomy
instead of an outcome-dominated stream — not how credit is assigned. AcceptAnatomy is that
future input record; build_reflector_input() is the seam the loop will call.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AcceptAnatomy:
    """One accepted candidate, described well enough to generalize from (point 2 input)."""
    call: int
    family: str
    action: str                       # window | fix | plan | rule
    rules_shown: list = field(default_factory=list)
    mode: str = ""                    # exact | approx | certified
    distance: float = 0.0
    charge: float = 0.0
    primary_before: int = 0
    primary_after: int = 0
    detail: dict = field(default_factory=dict)   # domain anatomy: Pauli frames, merge path, term kind, ...


def build_reflector_input(improvements: list, failures: list, stats: dict) -> tuple:
    """Today's behavior: pass the loop's triple through unchanged. Point 2 replaces this with
    (anatomy: list[AcceptAnatomy], failures-compressed, stats) behind the same seam."""
    return improvements, failures, stats
