"""Genesis baseline on the CV-DV suite (SPEC 3c): 5 seeds per circuit, best kept by total gates.

    python v3/baselines/run_genesis.py [label ...]          # any python; Genesis itself runs in env cvdv-opt

Each job runs Genesis' `src.main` unchanged through cvdv/scripts/run_genesis.py (seeds `random` / numpy and
records the final qumode mapping) in a fresh copy of Genesis' src/ + generated/, with PYTHONHASHSEED = seed
(Genesis' router iterates over Python sets, so its output depends on the hash seed as well; see
cvdv/experiments/compare_isas.py). Input = v3/suite/inputs/<label>.ham. Output per job:
v3/baselines/genesis/<label>/seed<s>/{*.cvdvqasm, *.mapping.json, stats.json, log.txt}; an existing job with
stats.json is skipped (append-only).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

V3 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V3.parent))
from v3.paths import CACHE, CVDV, CVDV_PY, GENESIS, INPUTS, MANIFEST  # noqa: E402

OUT = V3 / "baselines" / "genesis"


def run_one(label: str, seed: int) -> dict:
    out = OUT / label / f"seed{seed}"
    if (out / "stats.json").exists():
        return dict(label=label, seed=seed, status="exists")
    out.mkdir(parents=True, exist_ok=True)
    wd = CACHE / "genesis_work" / f"{label}_s{seed}"
    shutil.rmtree(wd, ignore_errors=True)
    wd.mkdir(parents=True)
    for d in ("src", "generated"):
        shutil.copytree(GENESIS / d, wd / d)
    shutil.copy(CVDV / "scripts" / "run_genesis.py", wd / "run_genesis.py")
    (wd / "benchmark").mkdir()
    (wd / "output").mkdir()
    shutil.copy(INPUTS / f"{label}.ham", wd / "benchmark" / f"{label}.ham")
    (wd / "job.json").write_text(json.dumps([{"input_file": f"benchmark/{label}.ham",
                                              "output_file": f"output/{label}.cvdvqasm"}]))
    env = dict(os.environ, PYTHONHASHSEED=str(seed))
    env["PATH"] = f"{CVDV_PY.parent}:{env['PATH']}"          # java / antlr of env cvdv-opt
    t0 = time.time()
    with open(out / "log.txt", "w") as log:
        p = subprocess.run([str(CVDV_PY), "run_genesis.py", "--batch-json", "job.json", "--stats",
                            "--seed", str(seed)], cwd=wd, env=env, stdout=log, stderr=subprocess.STDOUT)
        log.write(f"\nexit={p.returncode} wall_s={time.time() - t0:.1f} PYTHONHASHSEED={seed}\n")
    for f in (wd / "output").iterdir():
        shutil.copy(f, out / f.name)
    stats = sorted(wd.glob("compilation_stats_*.json"))
    if p.returncode == 0 and stats:
        shutil.copy(stats[0], out / "stats.json")
    shutil.rmtree(wd, ignore_errors=True)
    return dict(label=label, seed=seed, status="ok" if p.returncode == 0 and stats else f"exit {p.returncode}",
                wall_s=round(time.time() - t0, 1))


def main():
    m = json.loads(MANIFEST.read_text())
    cv = [c for c in m["circuits"] if c["domain"] == "cvdv"]
    labels = sys.argv[1:] or [c["label"] for c in cv]
    jobs = [(c["label"], s) for c in cv if c["label"] in labels for s in c["genesis_seeds"]]
    with ThreadPoolExecutor(max_workers=int(os.environ.get("JOBS", "6"))) as ex:
        for r in ex.map(lambda j: run_one(*j), jobs):
            print(json.dumps(r), flush=True)


if __name__ == "__main__":
    main()
