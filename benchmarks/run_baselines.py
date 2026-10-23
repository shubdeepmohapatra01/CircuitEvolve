"""TKET and pyzx baselines on the benchmark circuits, T-count measured by the v3 judge.

    .venv/bin/python benchmarks/run_baselines.py                 # all DV circuits, eps 1e-3
    .venv/bin/python benchmarks/run_baselines.py qft_8 mult_4 --eps 1e-5

Angle circuits (benchmarks/dv_angle/): the files are already the TKET FullPeepholeOptimise output, so TKET is the
file as given; pyzx = full_reduce -> extract_circuit -> to_basic_gates -> basic_optimization on it. Remaining Rz
are priced by gridsynth at eps / N_Rz (BQSKit convention).
Reconstruction circuits: TKET = FullPeepholeOptimise + AutoRebase{CX,H,Rz} + RemoveRedundancies on the Toffoli-level
file (dv_reconstruction/logical/); pyzx = the same pyzx pipeline on the Clifford+T file (dv_reconstruction/cliffordt/).
The frozen numbers are in v3/baselines/baselines.csv (BQSKit-FT / BQSKit-DPF need the bqskit-ft branch, see README).
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from circuitevolve.core.circuit import Circuit  # noqa: E402
from v3.judge import dv as J  # noqa: E402

B = ROOT / "benchmarks"
ANGLE = ["qft_8", "qpe_8", "hhl_8", "qae_13", "tfim_6"]
RECON = ["adder_8", "adder_6", "mult_4", "mcx_10", "modred_21"]


def pyzx_reduce(text: str) -> str:
    import pyzx as zx
    zx.settings.float_to_fraction_max_denominator = 10 ** 15
    text = re.sub(r'(?<![\w.])-?\d+\.?\d*[eE][-+]?\d+', lambda m: format(float(m.group(0)), '.25f'), text)
    text = re.sub(r'^creg .*;\n', '', text, flags=re.M)      # pyzx turns creg bits into extra wires
    g = zx.Circuit.from_qasm(text).to_graph()
    zx.full_reduce(g)
    c = zx.extract_circuit(g.copy())
    return zx.basic_optimization(c.to_basic_gates()).to_qasm()


def tket_fpo(text: str) -> str:
    from pytket.circuit import OpType
    from pytket.passes import AutoRebase, FullPeepholeOptimise, RemoveRedundancies
    from pytket.qasm import circuit_from_qasm_str, circuit_to_qasm_str
    text = text.replace(J.CCZ_DEF + "\n", "")                 # ccz as h-ccx-h (TKET has no ccz in qelib1)
    text = re.sub(r'^ccz (\S+),(\S+),(\S+);', r'h \3;\nccx \1,\2,\3;\nh \3;', text, flags=re.M)
    c = circuit_from_qasm_str(text)
    FullPeepholeOptimise().apply(c)
    AutoRebase({OpType.CX, OpType.H, OpType.Rz}).apply(c)
    RemoveRedundancies().apply(c)
    return circuit_to_qasm_str(c)


def t_count(qasm: str, eps: float) -> int:
    return J.measure(Circuit.from_qasm(qasm, name="b"), eps)["t_count"]


def frozen(label, eps):
    rows = list(csv.DictReader(open(ROOT / "v3" / "baselines" / "baselines.csv")))
    return {r["method"]: r["t_count"] for r in rows if r["label"] == label and
            (float(r["eps"] or 0) == eps or label in RECON)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="*", default=ANGLE + RECON)
    ap.add_argument("--eps", type=float, default=1e-3)
    a = ap.parse_args()
    print(f"{'circuit':<10} {'TKET':>7} {'pyzx':>7}   frozen TKET / pyzx")
    for lab in a.labels:
        if lab in ANGLE:
            text = (B / "dv_angle" / f"{lab}.qasm").read_text()
            tk, zx = t_count(text, a.eps), t_count(pyzx_reduce(text), a.eps)
        else:
            tk = t_count(tket_fpo((B / "dv_reconstruction" / "logical" / f"{lab}.qasm").read_text()), a.eps)
            zx = t_count(pyzx_reduce((B / "dv_reconstruction" / "cliffordt" / f"{lab}.qasm").read_text()), a.eps)
        f = frozen(lab, a.eps)
        print(f"{lab:<10} {tk:>7} {zx:>7}   {f.get('TKET', '-')} / {f.get('pyzx', '-')}", flush=True)


if __name__ == "__main__":
    main()
