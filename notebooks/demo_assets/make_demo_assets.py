"""Copy the few cached records the group-meeting demo needs out of the (large) stage-1 logs.

Run once from the repo root:  .venv/bin/python notebooks/demo_assets/make_demo_assets.py
Writes (small, JSON):
  qpe_8_e3_records.json   the run's `start` record + two `propose` records, verbatim
                          (call 4 = ACCEPTED fix-and-refit on the TKET input; call 18 = verifier-REJECTED fix)
  playbook_stage1.json    the final stage-1 playbook rules (all fields except history) + status counts after
                          every run snapshot, in run order
Every record carries its source file and a sha1 of that file, so the demo can show where it came from.
Nothing here calls an LLM or the network.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "results" / "window_runs" / "stage1"
OUT = Path(__file__).resolve().parent

ACCEPTED_CALL, REJECTED_CALL = 4, 18
RUN_ORDER = ["qft_8_e3", "qpe_8_e3", "qae_13_e3", "heisenberg_6_e3", "tfim_6_e3", "hubbard_8_e3", "qml_13_e3",
             "hhl_8_e3", "qpe_8_e5", "qae_13_e5", "hhl_8_e5"]          # SUMMARY.md: fixed run order


def sha1(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()


def main():
    src = RUNS / "stage1_qpe_8_e3.jsonl"
    recs = [json.loads(line) for line in src.open()]
    start = next(r for r in recs if r["kind"] == "start")
    props = {r["call"]: r for r in recs if r["kind"] == "propose"}
    acc, rej = props[ACCEPTED_CALL], props[REJECTED_CALL]
    assert acc.get("accepted") and acc["parent"] == props[min(props)]["parent"], "call 4 must be accepted on the input"
    assert not rej.get("accepted") and rej["candidates"][0]["decision"] == "rejected: verifier"
    out = dict(source=str(src.relative_to(ROOT)), source_sha1=sha1(src),
               note="verbatim records; call 4 parent = the TKET input (first parent of the run)",
               start=start, accepted=acc, rejected=rej)
    (OUT / "qpe_8_e3_records.json").write_text(json.dumps(out, indent=1))

    final = RUNS / "stage1_hhl_8_e5_playbook.json"            # last run's snapshot (== playbooks/stage1.json)
    pb = json.loads(final.read_text())
    timeline = []
    for tag in RUN_ORDER:
        p = RUNS / f"stage1_{tag}_playbook.json"
        rules = json.loads(p.read_text())["rules"]
        cnt = {s: sum(r["status"] == s for r in rules) for s in ("active", "candidate", "retired")}
        timeline.append(dict(run=tag, n_rules=len(rules), **cnt))
    (OUT / "playbook_stage1.json").write_text(json.dumps(dict(
        source=str(final.relative_to(ROOT)), source_sha1=sha1(final), settings=pb.get("settings"),
        rules=pb["rules"], timeline=timeline,
        note="timeline = rule status counts in each run's playbook snapshot (playbook started empty before qft_8_e3)"),
        indent=1))
    print("wrote", [p.name for p in OUT.glob("*.json")])


if __name__ == "__main__":
    main()
