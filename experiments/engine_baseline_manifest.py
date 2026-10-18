"""Write results/engine/BASELINE_MANIFEST.json — the no-recompute contract (PLAN_P1 phase P1.0).

Hashes every baseline-critical file so the permanent test tests/engine/test_manifest.py can
detect any refactor step that touches a number we would otherwise have to recompute.

Covered: BQSKit-track baseline CSVs and the stage-1 TKET input circuits, v2 baseline/eval CSVs
and frozen tier-2 libraries, stage-1 window-run summaries, the ablation report, cvdv results,
all playbooks/rulebooks, and the frozen-verifier digests of both stacks.

Usage:  .venv/bin/python experiments/engine_baseline_manifest.py [--force]
The manifest is written once; rerunning without --force refuses (append-only spirit).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "engine" / "BASELINE_MANIFEST.json"

GLOBS = [
    # BQSKit baselines track (the B0-B3g numbers and their shared TKET inputs)
    "results/bqskit_baselines/**/*.csv",
    "results/bqskit_baselines/stage1/inputs/*.qasm",
    "results/bqskit_baselines/**/*.md",
    # v2 baselines, eval, frozen tier-2 libraries and tier-1 freeze list
    "results/v2/*.csv",
    "results/v2/*.json",
    "results/v2/reused/*.csv",
    "results/v2/tier1/FROZEN.md",
    "results/v2/tier2/*.json",
    "results/v2/tier2/*.sha256",
    "results/v2/eval/eval_results.csv",
    "results/v2/eval/EVAL_REPORT.md",
    # stage-1 window-core runs (summaries + best circuits; jsonl logs are large but included)
    "results/window_runs/stage1/*.md",
    "results/window_runs/stage1/*_summary.json",
    "results/window_runs/stage1/*_best.qasm",
    "results/window_runs/ablation_v1/REPORT.md",
    "results/window_runs/ablation_v1/FROZEN.sha256",
    # legacy milestone reports
    "results/P3_go_no_go.md",
    "results/P4_pilot.md",
    # CV-DV results and rulebook
    "cvdv/results/*.csv",
    "cvdv/results/*.json",
    "cvdv/results/*.md",
    "cvdv/rulebook/rules.py",
    "cvdv/rulebook/ledger.jsonl",
    "cvdv/rulebook/playbook.md",
    "cvdv/FROZEN.sha256",
    # playbooks (stage-1 lineage, ablation artifacts)
    "playbooks/**/*.json",
    "playbooks/**/*.md",
]


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build() -> dict:
    files = {}
    for pattern in GLOBS:
        for p in sorted(REPO.glob(pattern)):
            if not p.is_file():
                continue
            rel = p.relative_to(REPO).as_posix()
            entry = {"sha256": sha256(p), "bytes": p.stat().st_size}
            if p.suffix == ".csv":
                entry["rows"] = sum(1 for _ in p.open("rb"))
            files[rel] = entry

    sys.path.insert(0, str(REPO))
    from circuitevolve import integrity

    return {
        "format": "circuitevolve.engine.baseline_manifest/1",
        "purpose": "no-recompute contract for the unified-engine refactor (PLAN_P1 P1.0)",
        "dv_frozen_digest": integrity.frozen_digest(),
        "cvdv_frozen_sha256_file": sha256(REPO / "cvdv" / "FROZEN.sha256"),
        "n_files": len(files),
        "files": files,
    }


if __name__ == "__main__":
    if OUT.exists() and "--force" not in sys.argv[1:]:
        raise SystemExit(f"{OUT} exists; the manifest is written once (use --force to regenerate)")
    manifest = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT.relative_to(REPO)}: {manifest['n_files']} files, "
          f"dv_frozen_digest {manifest['dv_frozen_digest'][:16]}...")
