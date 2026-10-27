"""Write v3/judge/FROZEN.sha256 (harness only, once at the end of P0; never run by the agent).

    .venv/bin/python -m v3.tools.freeze          # refuses to overwrite an existing FROZEN.sha256

Frozen: the v3 judge files, the suite manifest + every input, baselines.csv, and the upstream modules the judge
wraps (circuitevolve v2 verify / metric, core verifier / metric / circuit, blocks cost_model, the frozen exact
stack listed by circuitevolve/integrity.py, and the cvdv modules the CV-DV worker imports).
"""
from __future__ import annotations

import sys

from ..judge.frozen import sha256
from ..paths import BASELINES_CSV, FROZEN_FILE, INPUTS, JUDGE, MANIFEST, REPO

UPSTREAM = [
    "circuitevolve/v2/verify.py", "circuitevolve/v2/metric.py",
    "circuitevolve/core/verifier.py", "circuitevolve/core/metric.py", "circuitevolve/core/circuit.py",
    "circuitevolve/blocks/cost_model.py", "circuitevolve/blocks/circuit_io.py", "circuitevolve/integrity.py",
    "circuitevolve/ir.py", "circuitevolve/ring.py", "circuitevolve/sim.py", "circuitevolve/spec.py",
    "circuitevolve/verify.py", "circuitevolve/cost.py", "circuitevolve/blocks/verify_block.py",
    "cvdv/src/cvdv/metrics.py", "cvdv/src/cvdv/qasm.py", "cvdv/src/cvdv/sim.py", "cvdv/src/cvdv/target.py",
]


def files() -> list:
    out = [p.relative_to(REPO).as_posix() for p in sorted(JUDGE.glob("*.py"))]
    out += [MANIFEST.relative_to(REPO).as_posix()]
    out += [p.relative_to(REPO).as_posix() for p in sorted(INPUTS.iterdir()) if p.is_file()]
    out += [BASELINES_CSV.relative_to(REPO).as_posix()]
    return out + UPSTREAM


def main():
    if FROZEN_FILE.exists() and "--force" not in sys.argv:
        sys.exit(f"{FROZEN_FILE} exists; refusing to overwrite")
    lines = ["# v3 frozen files: <sha256>  <repo-relative path>; checked by v3/judge/frozen.py at every tool start"]
    lines += [f"{sha256(f)}  {f}" for f in files()]
    FROZEN_FILE.write_text("\n".join(lines) + "\n")
    print(f"wrote {FROZEN_FILE}: {len(lines) - 1} files")


if __name__ == "__main__":
    main()
