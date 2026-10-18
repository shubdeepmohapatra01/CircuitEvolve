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


def render_anatomy(a: AcceptAnatomy) -> str:
    """Factual, compact anatomy block appended to the accepted-improvement text the reflector
    reads (P2.1). No interpretation — frames, angles, deltas, charges only."""
    L = [f"# ANATOMY: action={a.action} mode={a.mode} distance={a.distance:.2e} charge={a.charge:.2e} "
         f"{'T' if a.action in ('window', 'fix') else 'primary'} {a.primary_before} -> {a.primary_after}"]
    if a.rules_shown:
        L.append(f"rules shown in this prompt: {', '.join(map(str, a.rules_shown))}")
    d = a.detail or {}
    if "rz_before" in d:
        L.append(f"rotations {d['rz_before']} -> {d['rz_after']}")
    if d.get("removed"):
        L.append("removed rotations: " + "; ".join(f"P={r['P']} angle={r['angle']:+.6f}" for r in d["removed"]))
    if d.get("added"):
        L.append("added/retuned rotations: " + "; ".join(f"P={r['P']} angle={r['angle']:+.6f}" for r in d["added"]))
    if d.get("merged_frames"):
        L.append("equal-frame merge: removed angle absorbed by a partner with the SAME Pauli frame "
                 f"({', '.join(d['merged_frames'])})")
    if d.get("note"):
        L.append(str(d["note"]))
    return "\n".join(L)


def compress_failures(failures: list, max_groups: int = 4) -> list:
    """Group raw (what, why) rejections by reason class -> <= max_groups entries shaped like the
    originals: (example_what, 'why_class (xN)'). The reflector should see the PATTERN of
    rejections, not a stream that drowns the accepts (P2.1)."""
    import re
    groups: dict = {}
    for what, why in failures:
        cls = re.sub(r"[-+]?\d+\.?\d*(e[-+]?\d+)?", "<n>", str(why)).strip()[:90]
        if cls not in groups:
            groups[cls] = [0, what, why]
        groups[cls][0] += 1
    ranked = sorted(groups.values(), key=lambda g: -g[0])[:max_groups]
    return [(what, f"{why} (x{n} since last reflection)" if n > 1 else why) for n, what, why in ranked]


def build_reflector_input(improvements: list, failures: list, stats: dict) -> tuple:
    """P2.1 behavior: improvements already carry rendered anatomy (engine appends
    render_anatomy to each accepted entry); failures are compressed into reason-class groups."""
    return improvements, compress_failures(failures), stats
