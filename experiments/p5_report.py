"""Collect P5 adder-statistics summaries into a table (no LLM calls, reads results/llm_runs only).

    .venv/bin/python experiments/p5_report.py TAG [TAG ...]   -> prints a JSON list of rows
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "llm_runs"


def _first_reach(traj, final, idx_calls, idx_evals, idx_val):
    for e in traj:
        if e[idx_val] <= final:
            return (e[idx_calls] if idx_calls is not None else None), e[idx_evals]
    return None, None


def row(tag, arm_label):
    s = json.loads((OUT / f"{tag}.summary.json").read_text())
    st, tr = s["stats"], s["trajectory"]
    best = st["best"]
    r = {"arm": arm_label, "seed": s.get("seed"), "tag": tag, "best_T_per_bit": best[0], "best_T_at_n8": best[1],
         "best_qubits_n8": best[2], "evals": st["evals"]}
    fails = sum(v for k, v in st.items() if k.startswith("fail_"))
    if s.get("arm") == "classical":
        _, ev = _first_reach(tr, best[0], None, 0, 1)
        nfail = sum(st["failures"].values())
        r.update(llm_calls=0, calls_to_best=None, evals_to_best=ev,
                 pass_rate=round(1 - nfail / max(1, st["evals"] - 1), 4), repair_success=None)
    elif s.get("arm") == "repair_only":
        c, ev = _first_reach(tr, best[0], 0, 1, 2)
        props = st.get("proposals", 0)
        r.update(llm_calls=0, pseudo_calls=st["pseudo_calls"], calls_to_best=None, pseudo_calls_to_best=c,
                 evals_to_best=ev, proposals=props,
                 pass_rate=round(st.get("raw_pass", 0) / max(1, props), 4),
                 repair_success=round(st.get("repaired", 0) / max(1, fails), 4) if fails else None)
    else:
        c, ev = _first_reach(tr, best[0], 0, 1, 2)
        props = st.get("proposals", 0) - st.get("duplicate", 0)
        raw = st.get("accepted", 0) - st.get("repaired", 0)
        be = st.get("backend", {})
        r.update(llm_calls=st["calls"], llm_errors=st.get("llm_error", 0), backend_retries=be.get("retries", 0),
                 calls_to_best=c, evals_to_best=ev, proposals=props, parse_errors=st.get("parse_error", 0),
                 non_program_blocks=st.get("non_program_block", 0),
                 pass_rate=round(raw / max(1, props), 4),
                 repair_success=round(st.get("repaired", 0) / max(1, fails), 4) if fails else None,
                 tokens_in=be.get("input_tokens"), tokens_out=be.get("output_tokens"),
                 wall_seconds=s.get("wall_seconds"))
    return r


if __name__ == "__main__":
    print(json.dumps([row(t, "?") for t in sys.argv[1:]], indent=1))
