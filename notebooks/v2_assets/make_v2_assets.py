"""Copy the few small cached records the v2 group-meeting notebook replays (no LLM calls, no network).

    .venv/bin/python notebooks/v2_assets/make_v2_assets.py

Reads results/v2/tier1/logs/dev_v1_*.jsonl (append-only run logs, never modified) and writes
notebooks/v2_assets/tier1_cached_records.json with:
  * cuccaro_8, LLM call 2  : the best verified relaxed plan (prompt, reply, logged verdict + metrics)
  * cuccaro_4, LLM call 4  : a plan the verifier rejected (reply + logged reason; prompt hash only)
Every field is copied verbatim from the log line; the source path and line number are recorded.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "results" / "v2" / "tier1" / "logs"
OUT = Path(__file__).resolve().parent / "tier1_cached_records.json"

PICK = [("cuccaro_8", 2, "accepted_best_relaxed", True), ("cuccaro_4", 4, "verifier_rejected", False)]
KEEP = ["circuit", "arm", "call", "target", "cards", "prompt_sha256", "prompt_chars", "usage", "llm_seconds",
        "ok", "stage", "reason", "mode", "certified", "method", "verdict_mode", "unitary_preserving", "digest",
        "global_pass", "zero_qubits", "t_count", "t_depth", "qubits", "ancillas", "measurements", "cx", "gates"]


def main():
    out = {"source": "results/v2/tier1/logs (run dev_v1)", "records": {}}
    for circ, call, role, with_prompt in PICK:
        path = LOGS / f"dev_v1_{circ}_llm.jsonl"
        lines = path.read_text().splitlines()
        hits = [(i, json.loads(l)) for i, l in enumerate(lines) if json.loads(l).get("call") == call]
        assert len(hits) == 1, (circ, call, len(hits))
        i, r = hits[0]
        rec = {k: r.get(k) for k in KEEP}
        rec["reply"] = r["reply"]
        if with_prompt:
            rec["prompt"] = r["prompt"]
            assert hashlib.sha256(r["prompt"].encode()).hexdigest() == r["prompt_sha256"]
        rec["_source"] = f"{path.relative_to(ROOT)}:{i + 1}"
        out["records"][f"{circ}_call{call}"] = dict(role=role, **rec)
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
