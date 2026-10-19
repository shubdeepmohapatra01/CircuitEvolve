"""P2.4 end-to-end dry run (fake LLM): one optimize() run exercising the WHOLE P2 stack —
graduated pre-opt pass, seeded playbook in proposer prompts, an exact in-loop accept, and the
anatomy-fed reflector — with the family playbook file left untouched (tmp copy)."""
from __future__ import annotations

import hashlib
import shutil

from circuitevolve.blocks import REPO
from circuitevolve.core.circuit import window_text
from circuitevolve.engine.graduate import load_callable, load_graduated
from circuitevolve.engine.run import optimize

FAMILY = REPO / "playbooks" / "families" / "dv.windows.json"
# P2.2 seeded state = the committed pre-campaign file; the live family file is MUTATED by
# angle_campaign1 arm-A learning (by protocol), so seed/inheritance invariants are checked on the
# sha-recorded snapshot (6876d37c..., identical to playbooks/families/dv.windows.json at d054cea).
SEEDED = REPO / "results" / "engine" / "angle_campaign1" / "A_playbook_at_start.json"
EPS = 1e-3

QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
h q[0];
cx q[0],q[1];
rz(0.30) q[1];
cx q[1],q[2];
h q[2];
rz(0.25) q[1];
rz(0.90) q[2];
t q[0];
t q[0];
"""


def test_p2_stack_end_to_end(tmp_path):
    # the pass will merge the equal-frame 0.30/0.25 pair; predict its output to script the LLM
    apply_pass = load_callable(load_graduated("dv.windows")[0])
    ops0 = [("h", (0,), None), ("cx", (0, 1), None), ("rz", (1,), 0.30), ("cx", (1, 2), None),
            ("h", (2,), None), ("rz", (1,), 0.25), ("rz", (2,), 0.90), ("t", (0,), None), ("t", (0,), None)]
    passed, rep0 = apply_pass(ops0, 3)
    assert rep0["merges"] == 1
    folded, seen_t = [], 0
    for g, q, a in passed:                       # t;t on q0 -> one s (first kept as s, second dropped)
        if g == "t" and q == (0,):
            seen_t += 1
            if seen_t == 1:
                folded.append(("s", (0,), None))
        else:
            folded.append((g, q, a))
    assert seen_t == 2
    reply = "```window\n" + window_text(folded) + "\n```\n"

    pb_copy = tmp_path / "dv.windows.json"
    shutil.copyfile(SEEDED, pb_copy)
    family_sha = hashlib.sha256(FAMILY.read_bytes()).hexdigest()

    prompts_seen, reflects_seen = [], []

    def complete(prompts):
        prompts_seen.extend(prompts)
        return [reply] + ["NONE"] * (len(prompts) - 1) if prompts_seen == prompts else ["NONE"] * len(prompts)

    def reflect(prompts):
        reflects_seen.extend(prompts)
        return ["no changes"] * len(prompts)

    s = optimize(QASM, 1e-3, complete, runs_dir=tmp_path, playbook_path=pb_copy,
                 reflect_complete=reflect, n_calls=3, batch=1, reflect_every=1, seed=0)

    # 1. routing + graduated pre-opt
    assert s["routing"]["family"] == "dv.windows"
    assert s["pre_opt"]["reports"][0]["merges"] == 1 and s["pre_opt"]["rules"] == ["G1"]
    assert s["pre_opt"]["rz_before"] == 3 and s["pre_opt"]["rz_after"] == 2
    # 2. the in-loop accept (t;t -> s fold): the window still holds free rotations, so the
    # verifier takes the numeric path — an approx accept charged only q-grid dust
    assert s["stats"]["accepted"] == 1 and s["stats"]["approx_accepts"] == 1
    assert 0 < s["ledger"]["window_spent"] <= 2 * EPS * 2**-12
    # 3. seeded rules reached the proposer prompts (A/B-sampled across calls)
    assert any("[seed 2026-10-18 FTQC primer]" in p for p in prompts_seen)
    # 4. the reflector ran on anatomy input
    assert reflects_seen and "# ANATOMY" in reflects_seen[0]
    # 5. ledger discipline end to end
    assert s["ledger"]["bound"] <= 1e-3 and s["final_check_vs_original"]["ok"]
    # 6. the real family playbook file was never touched
    assert hashlib.sha256(FAMILY.read_bytes()).hexdigest() == family_sha