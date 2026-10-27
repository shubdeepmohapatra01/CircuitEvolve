"""Command line.

    python run.py train L0 [--family toffoli|rotation] [--only tof_4,tof_5] [--model sonnet] [--ideas 5] [--attempts 3]
    python run.py test  L0            -> results/test_L0.csv   (no LLM calls)

Training uses the Claude Code CLI (`claude -p`), so run it from a terminal where `claude` is logged in.
Arms: L0 (pure LLM), L1 (pyzx + LLM), L2 (DPF + LLM, rotation family only). Splits: splits.json.
"""
import argparse
import csv
import json
import os

os.environ.setdefault("XDG_CONFIG_HOME", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "xdg"))

from circuitevolve import agents, loop  # noqa: E402


def circuits(split, arm, family=None, only=None):
    out = json.load(open(os.path.join(loop.ROOT, "splits.json")))[split]
    if arm == "L2":
        out = [e for e in out if e["family"] == "rotation"]           # DPF has nothing to do on Toffoli circuits
    if family:
        out = [e for e in out if e["family"] == family]
    if only:
        out = [e for e in out if e["name"] in only.split(",") or e.get("plot_name") in only.split(",")]
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["train", "test"])
    ap.add_argument("arm", choices=["L0", "L1", "L2"])
    ap.add_argument("--family"), ap.add_argument("--only"), ap.add_argument("--model", default="sonnet"), ap.add_argument("--scout-model", default="opus")
    ap.add_argument("--ideas", type=int, default=loop.IDEAS), ap.add_argument("--attempts", type=int, default=loop.ATTEMPTS)
    a = ap.parse_args()
    if a.cmd == "train":
        loop.train(a.arm, circuits("train", a.arm, a.family, a.only), agents.claude_cli(a.model), a.ideas, a.attempts,
                   ask_scout=agents.claude_cli(a.scout_model))
    else:
        rows = loop.test(a.arm, circuits("test", a.arm, a.family, a.only))
        os.makedirs(os.path.join(loop.ROOT, "results"), exist_ok=True)
        path = os.path.join(loop.ROOT, "results", f"test_{a.arm}.csv")
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader(); w.writerows(rows)
        for r in rows:
            print(f"{r['circuit']:12s} T={r['t']:6d} (no playbook {r['t_no_playbook']:6d})  qubits={r['qubits']}  e2e={r['e2e_check']}")
        print("->", path)
