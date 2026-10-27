"""The planted-bug gate - V4_README P5: "MANDATORY before any v4 result counts".

    .venv/bin/python -m v4.tools.planted_gate

v3's P1 gate was four hand-written rules with four known-correct decisions (SPEC section P1: admit a
correct merge, admit-or-never-fire a CV-DV displacement merge, reject a wrong one, reject a planted bug;
gate 4/4). CV-DV is deferred in v4 as it was in v3, so the two CV-DV controls are replaced by two that
exercise **the path P5 actually changed** - ancillas together with continuous rotations, which the frozen
`relaxed` mode cannot express at all. That is a faithful re-run, not a weaker one: the gate's job is to
confirm the verifier still rejects what it should, and the only thing that moved is this path.

| # | control | must decide |
|---|---|---|
| 1 | `same_pauli_merge` (correct merge, empty book) | ADMIT, qft_8 2391 -> 1583 |
| 2 | `same_pauli_merge_planted` (1 match in 10 merged with the wrong sign) | REJECT by verification |
| 3 | `ancilla_parity_rotation_lowering` (cx-rz-cx, clean ancilla, continuous angle) | VERIFY |
| 4 | `ancilla_parity_rotation_leak` (the same with the uncompute cx removed) | REJECT by verification |

Controls 3 and 4 are run with `price_first=False`, because neither lowers the T-count and the whole point
is to observe the VERIFIER's verdict rather than the optimiser's. Control 4 must be rejected for the
right reason: the ancilla-return check, not just a distance.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .. import book as B
from ..judge import dv as J
from ..judge.frozen import check_frozen
from ..paths import RESULTS, RULES
from ..runner import optimize
from .evaluate import evaluate

HAND = RULES / "handwritten"
EPS = 1e-3


def _verify_only(name: str, label: str = "qft_8") -> dict:
    """Run one control for its VERIFICATION verdict, with price-before-verify switched off."""
    r = B.load_rule(HAND / f"{name}.py")
    c = J.load(label)
    res = optimize(c, [r], EPS, reference=c, order="book", price_first=False)
    mine = [e for e in res.log if e["rule"] == r.name]
    first = mine[0] if mine else {}
    return dict(control=name, label=label, applications=len(mine),
                verified=first.get("verified"), certificate=first.get("certificate"),
                method=first.get("method"), certified=first.get("certified"),
                distance=first.get("distance"), reason=(first.get("reason") or "")[:400],
                witness=first.get("witness") if isinstance(first.get("witness"), dict) else None)


def run() -> dict:
    check_frozen()
    t0 = time.time()
    rows, verdicts = [], {}

    # 1 + 2: the admit / reject pair, through the FULL admission path against an EMPTY book, which is how
    # v3's P1 ran them (the floor tier already contains this class, so against the live book the correct
    # merge rightly adds nothing).
    for name, want in (("same_pauli_merge", "admit"), ("same_pauli_merge_planted", "reject")):
        rep = evaluate(HAND / f"{name}.py", bk=[], target="qft_8", small_only=True,
                       stop_at_first_failure=True)
        got = rep["decision"]
        rows.append(dict(control=name, kind="full admission (empty book)", want=want, got=got,
                         ok=got == want, level=rep.get("level"), reason=rep["reason"][:300],
                         circuits=[dict(label=r["label"], before=r["cost_before"], after=r["cost_after"])
                                   for r in rep["circuits"]],
                         seconds=rep["seconds"]))
        verdicts[name] = got == want

    # 3: the correct ancilla + continuous-angle rewrite must VERIFY (it was unverifiable before P5)
    v = _verify_only("ancilla_parity_rotation_lowering")
    ok3 = v["verified"] is True and v["certificate"] == "branch_kraus"
    rows.append(dict(v, kind="verification only", want="verified",
                     got=("verified" if v["verified"] else "rejected"), ok=ok3))
    verdicts["ancilla_parity_rotation_lowering"] = ok3

    # 4: the leak must be REJECTED, and specifically by the ancilla-return check
    v = _verify_only("ancilla_parity_rotation_leak")
    ok4 = v["verified"] is False and "ancilla population left outside" in (v["reason"] or "")
    rows.append(dict(v, kind="verification only", want="rejected (ancilla return)",
                     got=("verified" if v["verified"] else "rejected"), ok=ok4))
    verdicts["ancilla_parity_rotation_leak"] = ok4

    n_ok = sum(1 for r in rows if r["ok"])
    out = dict(gate="planted-bug (P5 re-run)", decisions=len(rows), correct=n_ok,
               passed=n_ok == len(rows), verdicts=verdicts, rows=rows,
               seconds=round(time.time() - t0, 1),
               note="CV-DV controls 2 and 3 of v3's P1 are replaced by the two ancilla + "
                    "continuous-angle controls, which exercise the path P5 changed; CV-DV stays deferred")
    return out


def main():
    out = run()
    p = RESULTS / "planted_gate.json"
    p.write_text(json.dumps(out, default=str, indent=1) + "\n")
    for r in out["rows"]:
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['control']:<36} want {r['want']:<26} got {r['got']}")
        if r.get("reason"):
            print(f"        {r['reason'][:150]}")
    print(f"\nPLANTED-BUG GATE: {out['correct']}/{out['decisions']} correct -> "
          f"{'PASS' if out['passed'] else 'FAIL'}   ({p})")


if __name__ == "__main__":
    main()
