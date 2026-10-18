"""Seed the dv.windows family playbook with known-construction rules (PLAN_P2 phase P2.2a).

Seeds are DECLARED PRIOR KNOWLEDGE (FTQC primer facts + this repo's own measured evidence),
entered as status=candidate, origin="seed": they are shown/hidden by the same A/B machinery and
must EARN active status through measured improvements like any learned rule (CLAUDE.md
invariant 7; PLAN_P2 section 2). The stage-1 originals (playbooks/dev_v1.json etc.) are not
touched; only the tier file playbooks/families/dv.windows.json gains rules.

Idempotent: refuses to run twice (looks for the seed marker) without --force-reseed, which
removes previous seed-origin rules first (candidates only - it will refuse if any seed has
been promoted, because promoted rules are campaign results).

Usage: .venv/bin/python experiments/engine_seed_playbooks.py [--force-reseed]
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
TARGET = REPO / "playbooks" / "families" / "dv.windows.json"
MARK = "[seed 2026-10-18 FTQC primer]"

SEEDS = [
    # -- merging (the single biggest measured effect in the repo: ablation no-LLM arm 10.4-14.7% vs B0)
    "Two rz with the SAME Pauli frame P (shown per rotation in the prompt) merge into one rz with the "
    "summed angle when every gate between them preserves P; the merge is exact (charge 0). Scan the "
    "window for equal-P pairs FIRST - this is the highest-value rewrite known.",
    "A gate between two rz preserves the rotation's frame iff it commutes with that Pauli: cx commutes "
    "with Z on its CONTROL (not its target), cz and rz commute with any Z-frame, h maps Z<->X. Check "
    "the path gate-by-gate before claiming a merge.",
    "If two equal-P rotations straddle sub-regions, prefer a fix block that sets ONE of them to 0 and "
    "lets the refit re-absorb the angle into the partner, instead of rewriting both regions by hand.",
    # -- snapping / dyadic structure
    "Snap rz(theta) to the nearest pi/4 multiple ONLY if 2|sin(delta/4)| <= allowance AND the saved "
    "gridsynth word (roughly 10-60 T at current eps_rz, shown in the prompt) exceeds any T added by "
    "the refit. A snap that fails either test will be rejected by the metric or the verifier.",
    "Adjacent same-qubit pi/4 diagonals fold exactly: t;t = s, tdg;tdg = sdg, t;tdg = identity, "
    "s;s = z. Fold them whenever they appear - exact, free, and reduces explicit T count.",
    # -- verifier preconditions (failure classes the stage-1 runs paid for repeatedly)
    "Never propose rz -> 0 unless 2|sin(theta/4)| <= allowance for THAT rotation, or the rest of the "
    "window is refit to compensate; zeroing a non-tiny rotation without compensation always fails the "
    "whole-window check.",
    "Candidates may differ from the original by a GLOBAL phase only; a relative phase between basis "
    "branches is a real error the verifier measures. If a rewrite introduces s/z/t fix-ups, place "
    "them so branch phases match, not just the first column.",
    # -- batching discipline (measured: large multi-edit windows fail disproportionately)
    "Change ONE thing per candidate (one merge, one snap, or one fold) and keep the rest of the window "
    "byte-identical; multi-edit candidates are rejected far more often and teach nothing when they fail.",
]


def main(force: bool = False):
    sys.path.insert(0, str(REPO))
    from circuitevolve.search.playbook import MAX_RULE_CHARS, Playbook

    pb = Playbook.load(TARGET)
    existing = [r for r in pb.rules if r.origin == "seed" and MARK in r.text]
    if existing and not force:
        raise SystemExit(f"{TARGET.name} already has {len(existing)} '{MARK}' seeds; use --force-reseed")
    if force:
        promoted = [r.id for r in existing if r.status == "active"]
        if promoted:
            raise SystemExit(f"refusing to reseed: {promoted} earned ACTIVE (campaign result, append-only)")
        pb.rules = [r for r in pb.rules if not (r.origin == "seed" and MARK in r.text)]
    added = []
    for text in SEEDS:
        full = f"{MARK} {text}"
        assert len(full) <= MAX_RULE_CHARS, f"seed too long ({len(full)}): {text[:60]}"
        added.append(pb.add(full, 0, origin="seed").id)
    pb.save(TARGET)
    print(f"seeded {len(added)} rules into {TARGET.relative_to(REPO)}: {', '.join(added)}")


if __name__ == "__main__":
    main(force="--force-reseed" in sys.argv[1:])
