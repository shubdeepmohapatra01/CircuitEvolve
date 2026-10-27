"""BQSKit-FT (B2) and BQSKit-DPF (B3g) on the DV reconstruction circuits (SPEC 3b: the only new DV baseline runs).

    experiments/bqskit_baselines/.venv-dpf/bin/python v3/baselines/run_bqskit_recon.py <label> <arm> <eps>

Runs `run_job` of experiments/bqskit_baselines/stage1/run_bqskit_arms.py UNCHANGED (same arms, same bqskit-ft
commit, same serial compiler and patches). Only its module-level paths are redirected so that nothing is written
outside v3/: input = v3/suite/inputs/<label>.cliffordt.qasm (the Nam suite's Clifford+T file, 7 T per Toffoli:
BQSKit-FT passes ccx through undecomposed, user decision 2026-10-20), reference for the state-distance check =
the logical input v3/suite/inputs/<label>.qasm, outputs -> v3/baselines/bqskit_recon/{outputs,runs}/.
One JSON per job; an existing ok job is kept, a failed one is moved aside (append-only).
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

V3 = Path(__file__).resolve().parents[1]
REPO = V3.parent
STAGE1 = REPO / "experiments" / "bqskit_baselines" / "stage1"
sys.path[:0] = [str(STAGE1), str(STAGE1.parent), str(STAGE1 / "vendor")]

import run_bqskit_arms as R  # noqa: E402  (installs the u12rz shim at import, as in its own main)

OUT = V3 / "baselines" / "bqskit_recon"
INPUTS = V3 / "suite" / "inputs"


def main():
    label, arm, eps = sys.argv[1], sys.argv[2], float(sys.argv[3])
    R.OUTPUTS = OUT / "outputs"
    R.input_path = lambda name: INPUTS / f"{R.short(name)}.cliffordt.qasm"
    R.orig_path = lambda name: INPUTS / f"{R.short(name)}.qasm"
    # The stage-1 dense state-vector check takes > 30 min at 24 qubits (adder_8); above 20 qubits it is skipped
    # (state_dist = None, user decision 2026-10-20). T-counts are unaffected; outputs are exact Clifford+T and
    # can be checked with the exact judge instead.
    from bqskit.ir.circuit import Circuit as _C
    if _C.from_file(str(INPUTS / f"{label}.cliffordt.qasm")).num_qudits > 20:
        R.state_distance = lambda *a, **k: None
    runs = OUT / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    f = runs / f"{label}_{arm}_{R.eps_tag(eps)}.json"
    if f.exists():
        if json.loads(f.read_text()).get("status") == "ok":
            print("exists", f.name)
            return
        f.rename(f.with_name(f.stem + f".failed_{int(f.stat().st_mtime)}.json"))
    t0 = time.time()
    try:
        r = R.run_job(label, arm, eps)
        from bqskit.ir.circuit import Circuit
        r["qubits"] = Circuit.from_file(str(INPUTS / f"{label}.qasm")).num_qudits
    except BaseException as e:  # incl. pyo3 PanicException
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        r = dict(circuit=label, arm=arm, eps=eps, status="error", error=f"{type(e).__name__}: {e}",
                 traceback=traceback.format_exc()[-3000:], wall_s=round(time.time() - t0, 1))
    r["wall_s"] = round(time.time() - t0, 1)
    r["driver"] = "v3/baselines/run_bqskit_recon.py -> stage1/run_bqskit_arms.run_job (unchanged)"
    R.dump_json(r, f)
    print(json.dumps({k: r.get(k) for k in ("circuit", "arm", "eps", "status", "t_count", "n_rz", "cx", "qubits",
                                             "runtime_s", "state_dist_vs_orig", "error")}), flush=True)


if __name__ == "__main__":
    main()
