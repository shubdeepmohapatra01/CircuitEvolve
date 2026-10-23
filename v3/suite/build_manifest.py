"""Build v3/suite/manifest.json and copy the input files into v3/suite/inputs/ (run once in P0).

    .venv/bin/python -m v3.suite.build_manifest            # refuses to overwrite an existing manifest

Every input is copied byte-for-byte; the manifest records label -> source path, sha256, family, eps list,
and for CV-DV the fixed simulation parameters used identically for Genesis and ours.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys

from ..paths import CVDV, INPUTS, MANIFEST, REPO

STAGE1 = "results/bqskit_baselines/stage1/inputs"
NAM = "benchmarks/nam_arith/logical"
CT = "benchmarks/nam_arith/cliffordt"

DV_ANGLE = [  # label, qubits; inputs = TKET FullPeepholeOptimise outputs shared by all stage-1 baselines
    ("qft_8", 8), ("qpe_8", 8), ("hhl_8", 8), ("qae_13", 13), ("tfim_6", 6)]
DV_RECON = [  # label, source file, qubits; Toffoli-level logical inputs
    ("adder_8", "adder_8.qasm", 24), ("adder_6", "rc_adder_6.qasm", 14), ("mult_4", "gf2^4_mult.qasm", 12),
    ("mcx_10", "barenco_tof_10.qasm", 19), ("modred_21", "mod_red_21.qasm", 11)]
# CV-DV: Genesis *_small instances. The spec is Genesis' intermediate IR (one Trotter step whose term
# coefficients already contain -i*t/r with t = 1, r = 1: e.g. kerr omega = 1.5707963 -> exp(-1.5707963j n)).
# Probe subspace: every system qumode in Fock levels <= n_probe, system qubits arbitrary. n_probe is chosen so
# no term is invisible on the subspace (n^2 - n vanishes on n <= 1 -> n_probe 2 for boseHubbard / z2Higgs;
# a+a+aa vanishes on n <= 1 -> n_probe 3 for kerr). Two cutoffs per circuit (trusted only if they agree);
# [12, 16] for the 4-mode circuits: at N = 8 the ancilla-qumode gadgets truncate (positive control
# heisenberg_small: err 3e-5 at N = 8 vs 9e-10 at N = 12). electronicVibration has 8 system qumodes (+1 Genesis ancilla), so its cutoffs are small.
# exact_cutoff = per-mode cutoff of the space in which exp(-iHt) is applied (then truncated to N).
CVDV_SMALL = {
    "kerr_small":                dict(n_probe=3, cutoffs=[16, 22], exact_pad=12),
    "boseHubbard_small":         dict(n_probe=2, cutoffs=[12, 16], exact_pad=8),
    "z2Higgs_small":             dict(n_probe=2, cutoffs=[12, 16], exact_pad=8),
    "heisenberg_small":          dict(n_probe=1, cutoffs=[12, 16], exact_pad=8),
    "electronicVibration_small": dict(n_probe=1, cutoffs=[3, 4], exact_pad=1),
}
EPS_ANGLE = [1e-3, 1e-5]
EPS_RECON = [1e-3]          # exact Clifford+T inputs; eps only matters if a pass introduces rotations
PROBES = dict(exact_basis_max_dim=64, n_random=8, seed=0,
              note="process fidelity |Tr(V^dag P0 U)/d|^2 on the probe subspace, P0 = ancillas back in |0>/vacuum; "
                   "exact over the basis when d <= exact_basis_max_dim, else estimated as |mean_k <t_k|P0 g_k>|^2 "
                   "over n_random Haar probes (seeded); same probes for every method")
GENESIS_SEEDS = [0, 1, 2, 3, 4]   # run_genesis.py --seed s with PYTHONHASHSEED = s; best by total gates


def sha(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build() -> dict:
    INPUTS.mkdir(parents=True, exist_ok=True)
    circuits = []

    def add(label, family, domain, src, dst_name, **kw):
        src_p = REPO / src
        dst = INPUTS / dst_name
        shutil.copyfile(src_p, dst)
        assert sha(dst) == sha(src_p)
        circuits.append(dict(label=label, family=family, domain=domain, source=str(src),
                             input=f"suite/inputs/{dst_name}", sha256=sha(dst), **kw))

    for label, nq in DV_ANGLE:
        add(label, "dv_angle", "dv", f"{STAGE1}/{label}_tket.qasm", f"{label}.qasm", qubits=nq, eps=EPS_ANGLE,
            control=(label == "tfim_6"), input_kind="clifford_rz (TKET FullPeepholeOptimise output)")
    for label, src, nq in DV_RECON:
        add(label, "dv_recon", "dv", f"{NAM}/{src}", f"{label}.qasm", qubits=nq, eps=EPS_RECON,
            input_kind="toffoli_logical (ccz/ccx + Clifford; every method decomposes it itself)")
        # BQSKit-FT/DPF pass ccx through undecomposed (not in their gate set, left as is), so B2/B3g get the
        # suite's own Clifford+T file (7 T per Toffoli) instead; user decision 2026-10-20.
        c = circuits[-1]
        shutil.copyfile(REPO / CT / src, INPUTS / f"{label}.cliffordt.qasm")
        c.update(bqskit_input=f"suite/inputs/{label}.cliffordt.qasm", bqskit_input_source=f"{CT}/{src}",
                 bqskit_input_sha256=sha(INPUTS / f"{label}.cliffordt.qasm"))
    for label, p in CVDV_SMALL.items():
        ham = f"cvdv/third_party/genesis/benchmark/{label}.ham"
        ir = f"cvdv/results/genesis_baseline/{label}/intermediate_{label}.cvdvqasm"
        add(label, "cvdv", "cvdv", ham, f"{label}.ham")
        c = circuits.pop()
        src_ir = REPO / ir
        shutil.copyfile(src_ir, INPUTS / f"{label}.ir.cvdvqasm")
        c.update(spec_source=ir, spec=f"suite/inputs/{label}.ir.cvdvqasm",
                 spec_sha256=sha(INPUTS / f"{label}.ir.cvdvqasm"),
                 trotter_steps=1, time=1.0, term_order="as listed in the IR file",
                 n_probe=p["n_probe"], cutoffs=p["cutoffs"], exact_pad=p["exact_pad"], probes=PROBES,
                 genesis_seeds=GENESIS_SEEDS)
        circuits.append(c)
    return dict(version=1, created="P0", circuits=circuits,
                excluded=dict(hubbardHolstein_small="IR has non-unitary terms (cvdv/results/P0_genesis_reproduction.md)"))


if __name__ == "__main__":
    if MANIFEST.exists() and "--force" not in sys.argv:
        sys.exit(f"{MANIFEST} exists (frozen); refusing to overwrite")
    m = build()
    MANIFEST.write_text(json.dumps(m, indent=1) + "\n")
    print(f"wrote {MANIFEST} with {len(m['circuits'])} circuits; cvdv root {CVDV}")
