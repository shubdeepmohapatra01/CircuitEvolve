"""Re-evaluate v3's rejected rules under v4's verifier and without the wall-clock cap (V4_README P6).

    .venv/bin/python -m v4.tools.reevaluate [--only name,name] [--subprocess-limit 1800] [--tag p6]

V4_README section 0 names two reasons v3 threw away work, and both are now gone:

* **the timeout discarded the two best rules.** `staircase_knapsack_exact_angle_assignment`
  (qft_8 1583->1417, qpe_8 11485->10249, qae_13 4526->4370) and
  `joint_budget_direct_rotation_synthesis` (hhl_8 29029->24967) were rejected on `runtime limit 300.0s`
  with every application verified. v4 caps rule CODE on opcodes and never caps verification on a clock.
* **the verifier could not express ancillas with continuous angles.** Reading every rejection reason in
  `v3/rules/rejected/*.reason.json` shows this is worse than the plan says: **8** rules died on the one
  message `candidate not exact: rz(...) is not a multiple of pi/4`, and two of them -
  `phase_gradient_addition_for_dyadic_rotation_cascades` and `phase_gradient_catalysis_dyadic_rotations` -
  ARE the phase-gradient / PKAC card that V4_README 4.2b asks to be written by hand. The LLM already
  found it; the verifier could not check it. P5 removes that.

So the honest first move for P6 is not to write a new card, it is to re-run what was already found.
18 rules are ported (`rules/candidates/PORTED.json`): 8 verifier-blocked, 9 timed out, 1 over budget.

Each is evaluated in its own SUBPROCESS with a generous wall clock. That clock is infrastructure, not
science: a rule that hits it is recorded as `not_evaluated`, never as `reject`, so it cannot bias which
rules are admitted - which is exactly what v3's 300 s limit did.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from ..paths import CANDIDATES, DV_PY, REPO, RESULTS

PORTED = CANDIDATES / "PORTED.json"
DEFAULT_LIMIT = 1800.0


def one(name: str, limit: float, eps: float = 1e-3) -> dict:
    """Evaluate one candidate in a subprocess. -> the report, or a `not_evaluated` row."""
    code = (
        "import json, sys\n"
        "from v4.tools.evaluate import evaluate\n"
        f"rep = evaluate({str(CANDIDATES / (name + '.py'))!r}, eps={eps!r})\n"
        "rep.pop('t0', None)\n"
        "print('@@@' + json.dumps(rep, default=str))\n"
    )
    t0 = time.time()
    try:
        p = subprocess.run([str(DV_PY), "-c", code], cwd=REPO, capture_output=True, text=True,
                           timeout=limit)
    except subprocess.TimeoutExpired:
        return dict(candidate=name, decision="not_evaluated", level=None,
                    reason=f"harness wall clock {limit:g}s exceeded in a subprocess. This is "
                           f"infrastructure, NOT a rejection: the rule is neither admitted nor rejected.",
                    seconds=round(time.time() - t0, 1))
    tail = [l for l in p.stdout.splitlines() if l.startswith("@@@")]
    if p.returncode != 0 or not tail:
        return dict(candidate=name, decision="harness_error",
                    reason=f"exit {p.returncode}: {(p.stderr or p.stdout)[-900:]}",
                    seconds=round(time.time() - t0, 1))
    rep = json.loads(tail[-1][3:])
    rep["seconds"] = round(time.time() - t0, 1)
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--subprocess-limit", type=float, default=DEFAULT_LIMIT)
    ap.add_argument("--eps", type=float, default=1e-3)
    ap.add_argument("--tag", default="p6")
    a = ap.parse_args()
    ported = json.loads(PORTED.read_text())
    names = a.only.split(",") if a.only else sorted(ported)
    out, path = [], RESULTS / f"reevaluate_{a.tag}.jsonl"
    for i, name in enumerate(names, 1):
        rep = one(name, a.subprocess_limit, a.eps)
        rep["v3_group"] = ported.get(name, {}).get("group")
        rep["v3_reason"] = ported.get(name, {}).get("v3_reason")
        out.append(rep)
        with open(path, "a") as f:
            f.write(json.dumps(rep, default=str) + "\n")
        helped = ", ".join(f"{h['label']} {h['before']}->{h['after']}" for h in rep.get("helped", []))
        print(f"[{i}/{len(names)}] {name:<56} {rep['v3_group']:<17} -> {rep['decision']:<14} "
              f"{rep['seconds']:>7.1f}s  {helped or rep.get('reason','')[:110]}", flush=True)
    summary = {}
    for r in out:
        summary[r["decision"]] = summary.get(r["decision"], 0) + 1
    changed = [dict(name=r["candidate"].split("/")[-1].replace(".py", "") if "/" in str(r["candidate"])
                    else r["candidate"], v3=r["v3_group"], v4=r["decision"],
                    helped=r.get("helped"))
               for r in out if r["decision"] == "admit"]
    (RESULTS / f"reevaluate_{a.tag}.json").write_text(json.dumps(
        dict(summary=summary, admitted=changed, rows=out), default=str, indent=1) + "\n")
    print("\n" + json.dumps(dict(summary=summary, now_admitted=[c["name"] for c in changed])))


if __name__ == "__main__":
    main()
