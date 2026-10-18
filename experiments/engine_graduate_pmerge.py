"""First graduation: dev replay + freeze of the same-Pauli merge pass (PLAN_P2 phase P2.3).

Replays playbooks/graduated/same_pauli_merge.py over the 8 stage-1 dev circuits at eps=1e-3,
reporting T under the candidate's own ledger exactly like the loop would see it (d_input
measured against the ORIGINAL qseed circuit AFTER the pass, eps_rz = eps_synth / N_rz).

KEEP RULE (plan gate): every application verified (the pass enforces allowance 1e-12 per
merge); total T must drop; NO circuit may rise. Only then is the file frozen into
playbooks/graduated/index.json via engine.graduate.promote() with the evidence-override
provenance (seed rule R29 + the ablation control measurement).

Output: results/engine/graduation_pmerge.json (refused if it exists).
Usage:  .venv/bin/python experiments/engine_graduate_pmerge.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from circuitevolve.blocks.circuit_io import classify_angle  # noqa: E402
from circuitevolve.blocks.cost_model import CACHE_DIR  # noqa: E402
from circuitevolve.core.circuit import STAGE1, load_input, original_ops  # noqa: E402
from circuitevolve.core.ledger import Ledger  # noqa: E402
from circuitevolve.core.metric import BqskitTMetric  # noqa: E402
from circuitevolve.core.verifier import check_circuit  # noqa: E402
from circuitevolve.engine.graduate import promote  # noqa: E402
from circuitevolve.integrity import frozen_digest  # noqa: E402
from circuitevolve.search.playbook import Playbook  # noqa: E402

OUT = REPO / "results" / "engine" / "graduation_pmerge.json"
PASS_PATH = "playbooks/graduated/same_pauli_merge.py"
EPS = 1e-3

EVIDENCE = ("evidence-override graduation: provenance rule is dv.windows R29 (seed, candidate); "
            "measured support is the INDEPENDENT no-LLM ablation control arm "
            "(experiments/window_pmerge_control.py -> results/window_runs/stage1/control_pmerge.json; "
            "ablation_v1 REPORT: 10.4-14.7% T vs B0 at 1e-3 on merge-rich stage-1 circuits), "
            "plus the dev replay recorded in results/engine/graduation_pmerge.json at freeze time.")


def _t(ops, led, metric):
    n_rz = sum(1 for g, _, a in ops if g == "rz" and classify_angle(a) is None)
    return metric.cost(ops, eps_rz=led.eps_synth / n_rz)["t"] if n_rz else metric.cost(ops, eps_rz=1.0)["t"]


def replay() -> dict:
    sys.path.insert(0, str(REPO / "playbooks" / "graduated"))
    import same_pauli_merge as pm

    metric = BqskitTMetric(1.0, cache_dir=CACHE_DIR / "bqskit_conv")
    rows = []
    for name in STAGE1:
        t0 = time.time()
        circ = load_input(name)
        orig, n = original_ops(name)
        led_b = Ledger(EPS).with_input(check_circuit(orig, circ.ops, n, bound=EPS)["dist"])
        t_before = _t(circ.ops, led_b, metric)
        ops, rep = pm.apply_pass(circ.ops, n)
        chk = check_circuit(orig, ops, n, bound=EPS / 4, seed=12345)
        led_a = Ledger(EPS).with_input(chk["dist"])
        t_after = _t(ops, led_a, metric)
        rows.append(dict(name=name, eps=EPS, t_before=t_before, t_after=t_after,
                         merges=rep["merges"], passes=rep["passes"],
                         max_merge_dist=rep["max_merge_dist"],
                         final_check=dict(ok=chk["ok"], method=chk["method"], dist=chk.get("dist")),
                         seconds=round(time.time() - t0, 1)))
        print(json.dumps(rows[-1]), flush=True)
    return dict(description=__doc__.split("\n\n")[1], eps=EPS, pass_path=PASS_PATH,
                verifier_digest=frozen_digest()[:16], rows=rows)


def main():
    if OUT.exists():
        raise SystemExit(f"{OUT} exists; the replay is recorded once (append-only)")
    rec = replay()
    rows = rec["rows"]
    total_b, total_a = sum(r["t_before"] for r in rows), sum(r["t_after"] for r in rows)
    risers = [r["name"] for r in rows if r["t_after"] > r["t_before"]]
    bad_checks = [r["name"] for r in rows if not r["final_check"]["ok"]]
    rec["keep"] = dict(total_t_before=total_b, total_t_after=total_a,
                       improved_pct=round(100 * (total_b - total_a) / total_b, 2),
                       risers=risers, bad_checks=bad_checks,
                       kept=(total_a < total_b and not risers and not bad_checks))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1) + "\n")
    print(f"replay: total T {total_b} -> {total_a} ({rec['keep']['improved_pct']}%), "
          f"risers={risers}, bad_checks={bad_checks}")
    if not rec["keep"]["kept"]:
        raise SystemExit("KEEP RULE FAILED - not promoting; see the replay record")
    pb = Playbook.load(REPO / "playbooks" / "families" / "dv.windows.json")
    r29 = pb.get("R29")
    assert r29 is not None and r29.origin == "seed"
    entry = promote("dv.windows", "R29", "pass", PASS_PATH, frozen_digest()[:16],
                    EVIDENCE, rule_status=r29.status)
    print(f"promoted: {entry.id} sha {entry.sha256[:16]}...")


if __name__ == "__main__":
    main()
