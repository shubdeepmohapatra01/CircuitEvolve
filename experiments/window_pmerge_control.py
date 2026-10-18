"""No-LLM control for the stage-1 window runs: deterministic same-Pauli merges inside windows.

The stage-1 prompt shows each rotation's Pauli frame P (core/mutator.rotation_paulis) and the merge rule. This
control applies that rule exhaustively and greedily, with no LLM: repeat { partition into windows (same
windows() as the loop); in every window merge the first pair of synthesized rz with equal P and a commuting path
(angle a_i +- a_j at the earlier op, the later op deleted) } until no window changes. Every merge goes through the
frozen verifier (core/verifier.verify_window at allowance 1e-12) and is charged its measured distance under ledger
v1; the final circuit is checked against the ORIGINAL qseed circuit. T is reported under the same metric as the
loop (eps_rz = eps_synth / N_Rz). A separate gridsynth cache directory is used so this can run next to the loop.

Output: results/window_runs/stage1/control_pmerge.json (refused if it exists).
    .venv/bin/python experiments/window_pmerge_control.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from circuitevolve.blocks.cost_model import CACHE_DIR  # noqa: E402
from circuitevolve.core.circuit import STAGE1, Circuit, load_input, original_ops, splice, windows  # noqa: E402
from circuitevolve.core.ledger import Ledger  # noqa: E402
from circuitevolve.core.metric import BqskitTMetric  # noqa: E402
from circuitevolve.core.mutator import rotation_paulis  # noqa: E402
from circuitevolve.core.refit import free_rotations  # noqa: E402
from circuitevolve.core.verifier import check_circuit, verify_window  # noqa: E402

OUT = REPO / "results" / "window_runs" / "stage1" / "control_pmerge.json"


def _commute(p, q) -> bool:
    return sum(1 for a, b in zip(p[1:], q[1:]) if a != "I" and b != "I" and a != b) % 2 == 0


def merge_once(ops, k):
    """First mergeable (i, j) in a window -> new local ops, or None."""
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


def run_one(name: str, eps: float, metric: BqskitTMetric) -> dict:
    t0 = time.time()
    circ = load_input(name)
    orig, n = original_ops(name)
    d_in = check_circuit(orig, circ.ops, n, bound=eps)["dist"]
    led = Ledger(eps).with_input(d_in)
    ops = list(circ.ops)
    merges, passes = 0, 0
    while True:
        passes += 1
        ws, flat = windows(Circuit(n, ops))
        changed = False
        cur = list(flat)
        for w in sorted(ws, key=lambda w: -w.start):
            new = merge_once(w.ops, w.k)
            if new is None:
                continue
            v = verify_window(w.ops, new, w.k, 1e-12)
            if not v["ok"] or not led.can_charge(v["charge"]):
                continue
            led = led.charge(v["charge"], mode="pmerge")
            cur = splice(cur, w, new)
            merges += 1
            changed = True
        ops = cur
        if not changed or passes > 50:
            break
    n_rz = sum(1 for g, _, a in ops if g == "rz" and __import__("circuitevolve.blocks.circuit_io", fromlist=["x"]).classify_angle(a) is None)
    cost = metric.cost(ops, eps_rz=led.eps_synth / n_rz)
    chk = check_circuit(orig, ops, n, bound=led.d_input + led.spent, seed=12345)
    return dict(name=name, eps=eps, t=cost["t"], rz=cost["rz"], cx=cost["cx"], merges=merges, passes=passes,
                window_spent=led.spent, bound=led.bound(n_rz), final_check=dict(ok=chk["ok"], method=chk["method"],
                dist=chk.get("dist")), seconds=round(time.time() - t0, 1))


def main():
    metric = BqskitTMetric(1.0, cache_dir=CACHE_DIR / "bqskit_conv_control")
    rows = []
    for eps in (1e-3, 1e-5):
        for name in STAGE1:
            r = run_one(name, eps, metric)
            rows.append(r)
            print(json.dumps(r), flush=True)
    with OUT.open("x") as f:
        json.dump(dict(description=__doc__.split("\n\n")[1], rows=rows), f, indent=1)


if __name__ == "__main__":
    main()
