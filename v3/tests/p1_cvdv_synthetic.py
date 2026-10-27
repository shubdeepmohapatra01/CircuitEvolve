"""P1 supplementary check (NOT admission): does the CV-DV judge catch the wrong rule and pass the right one?

    .venv/bin/python -m v3.tests.p1_cvdv_synthetic      -> one JSON line per check, appended to v3/results/events.jsonl

Admission only sees suite circuits; if no suite circuit contains displacements, rules 2 and 3 never fire there.
This applies each rule's own apply() to a synthetic circuit on (q0, qm0) and asks the judge (reference mode,
probe parameters of heisenberg_small: n_probe 1, cutoffs 12 / 16) whether the result equals the original:
  rule 2: D(0.3) D(0.2j)                 -> D(0.3 + 0.2j)            expected: err ~ 0 (global phase only)
  rule 3: CD(0.3) D(0.2j) CD(0.1)        -> D(0.2j) CD(0.4)          expected: err >> 1e-9 (relative phase
          exp(2 i z Im(b a*)) = exp(+-0.12 i))
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from ..api import cvdv
from ..judge.cvdv_judge import judge
from ..paths import CACHE, RESULTS, RULES
from ..tools.evaluate import load_rule

Q, M = ("q", 0), ("qm", 0)


def _rule(name):
    for folder in ("candidates", "accepted", "rejected", "never_fires"):
        p = RULES / folder / f"{name}.py"
        if p.exists():
            return load_rule(p)
    raise FileNotFoundError(name)


def check(rule_name, ops, expect_ok):
    r = _rule(rule_name)
    circ = {"label": "synthetic", "ops": ops}
    (m,) = r.trigger(circ)
    cand = r.apply(circ, m)
    d = CACHE / "p1_synthetic"
    d.mkdir(parents=True, exist_ok=True)
    ref_p, cand_p = d / f"{rule_name}_ref.json", d / f"{rule_name}_cand.json"
    ref_p.write_text(json.dumps(circ))
    cand_p.write_text(json.dumps(cand))
    res = judge("heisenberg_small", cand_p, what=("metrics", "errors"), reference=ref_p)
    ok = res["err_ref"] <= 1e-9 and res["cutoffs_agree"]
    return dict(event="p1_cvdv_synthetic", rule=rule_name, original=[o["name"] for o in ops],
                result=[o["name"] for o in cand["ops"]], err_ref=res["err_ref"], cutoffs_agree=res["cutoffs_agree"],
                per_cutoff=[(e["N"], e["err_ref"]) for e in res["errors"]], verifies=ok, expected_verifies=expect_ok,
                as_expected=ok == expect_ok, time=time.time())


def main():
    rows = [check("displacement_merge", [cvdv.gate("D", [0.3], [M]), cvdv.gate("D", [0.2j], [M])], True),
            check("cond_displacement_merge_wrong", [cvdv.gate("CD", [0.3], [Q, M]), cvdv.gate("D", [0.2j], [M]),
                                                    cvdv.gate("CD", [0.1], [Q, M])], False)]
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "events.jsonl", "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
            print(json.dumps(r))


if __name__ == "__main__":
    main()
