"""GRADUATED PASS: exhaustive same-Pauli-frame rotation merging (PLAN_P2 phase P2.3).

Provenance (append-only chain):
    prose rule   playbooks/families/dv.windows.json R29 ("[seed 2026-10-18 FTQC primer] Two rz
                 with the SAME Pauli frame P ... merge ... exact (charge 0) ...")
    evidence     the no-LLM ablation control arm (experiments/window_pmerge_control.py,
                 results/window_runs/stage1/control_pmerge.json; REPORT: 10.4-14.7% T vs B0 at
                 1e-3 on merge-rich stage-1 circuits) - an INDEPENDENT measurement, stronger
                 than any single-campaign z-score; recorded as an evidence-override graduation.
    replay       results/engine/graduation_pmerge.json (dev replay at freeze time, P2.3 gate)
    this file    frozen by sha256 in playbooks/graduated/index.json; the loader refuses to
                 import it if the hash drifts.

Algorithm (byte-level port of the control arm): repeat { partition into the loop's own windows;
in every window merge the first pair of synthesized rz with equal Pauli frame and a commuting
path (angle a_i +- a_j onto the earlier op, later op deleted) } until a fixed point. EVERY merge
is verified by the FROZEN window verifier at allowance 1e-12 before it is kept - this pass
re-proves each application rather than trusting the pattern (stricter than verify-once).
Termination: every kept merge strictly removes one rz; passes are capped like the control.

apply_pass(ops, n) -> (new_ops, report). No LLM, no eval, no ledger mutation - the caller
charges the aggregate measured distance through the loop's standard input check.
"""
from __future__ import annotations

from circuitevolve.core.circuit import Circuit, splice, windows
from circuitevolve.core.mutator import rotation_paulis
from circuitevolve.core.refit import free_rotations
from circuitevolve.core.verifier import verify_window

ALLOWANCE = 1e-12
MAX_PASSES = 50


def _commute(p, q) -> bool:
    return sum(1 for a, b in zip(p[1:], q[1:]) if a != "I" and b != "I" and a != b) % 2 == 0


def _merge_once(ops, k):
    """First mergeable (i, j) in a window -> new local ops, or None (control-arm logic)."""
    P = rotation_paulis(ops, k)
    rot = sorted(P)
    free = set(free_rotations(ops))
    for x, i in enumerate(rot):
        if i not in free:
            continue
        for j in rot[x + 1:]:
            if P[j][1:] == P[i][1:]:
                if j in free and all(_commute(P[m], P[i]) for m in rot if i < m < j):
                    s = 1 if P[i][0] == P[j][0] else -1
                    new = list(ops)
                    new[i] = ("rz", ops[i][1], float(ops[i][2]) + s * float(ops[j][2]))
                    del new[j]
                    return new
                break
    return None


def apply_pass(ops, n: int):
    ops = list(ops)
    merges, passes, max_dist = 0, 0, 0.0
    while True:
        passes += 1
        ws, flat = windows(Circuit(n, ops))
        changed = False
        cur = list(flat)
        for w in sorted(ws, key=lambda w: -w.start):
            new = _merge_once(w.ops, w.k)
            if new is None:
                continue
            v = verify_window(w.ops, new, w.k, ALLOWANCE)
            if not v["ok"]:
                continue
            max_dist = max(max_dist, float(v["dist"]))
            cur = splice(cur, w, new)
            merges += 1
            changed = True
        ops = cur
        if not changed or passes >= MAX_PASSES:
            break
    rz = sum(1 for g, _, _ in ops if g == "rz")
    return ops, dict(rule="same_pauli_merge", merges=merges, passes=passes,
                     max_merge_dist=max_dist, rz_after=rz)
