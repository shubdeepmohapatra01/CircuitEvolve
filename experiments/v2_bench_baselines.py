"""Baselines for ONE new benchmark circuit (Nam et al. 2018 arithmetic suite or a generated Cuccaro adder).

    .venv/bin/python experiments/v2_bench_baselines.py <name> <out_dir>

Writes <out_dir>/<name>.json with
  * gate counts of the logical file (ccz/ccx kept) and of the Clifford+T file as given;
  * provenance checks: logical vs Clifford+T-as-given, vs Feynman's independent QASM, vs the authors' Quipper 'before';
  * arms: pyzx (full_reduce graph T-count; extract + basic_optimization circuit), TKET FullPeepholeOptimise on the
    Clifford+T input and on the logical input, and the authors' published optimized circuits (Nam light / heavy),
    each with its T-count and a verification record against the input;
  * a planted-bug control: the Clifford+T input with its first T gate deleted must FAIL the same check;
  * (run2+) every verification also runs MQT QCEC; optimized circuits are saved to <out_dir>/circuits/.
Run one process per circuit (experiments/v2_bench_run_all.py); never fork from a process doing numpy work.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_bench_common import BENCH, check, counts, expand, pyzx_arm, read_qasm, tket_arm, write_qasm  # noqa: E402

OUT_DIR = None


def _arm(rec_ops, ref_ops, n, extra=None, save=None):
    c = counts(rec_ops)
    if save and OUT_DIR:
        d = os.path.join(OUT_DIR, "circuits")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, save + ".qasm"), "w") as f:
            f.write(write_qasm(rec_ops, n))
    r = dict(t_count=c["t"], rz_other=c["rz_other"], cx=c["cx"], h=c["h"], gates=c["gates"])
    r.update(extra or {})
    r["verify"] = check(ref_ops, rec_ops, n)
    return r


def run(name: str) -> dict:
    import pytket
    import pyzx
    rec = dict(circuit=name, python=platform.python_version(), pyzx=pyzx.__version__, pytket=pytket.__version__,
               started=time.strftime("%Y-%m-%dT%H:%M:%S"))
    gen = name.startswith("cuccaro_")
    if gen:
        n, L = read_qasm(f"{BENCH}/generated/{name}.qasm")
        C = expand(L)
        rec["cliffordt_source"] = "expand(logical) with circuitevolve.ir 7-T ccx table"
    else:
        n, L = read_qasm(f"{BENCH}/logical/{name}.qasm")
        n2, C = read_qasm(f"{BENCH}/cliffordt/{name}.qasm")
        assert n2 == n
    rec["qubits"] = n
    rec["logical_counts"] = counts(L)
    rec["cliffordt_counts"] = counts(C)
    prov = {}
    prov["logical_vs_cliffordt"] = check(L, C, n)
    fp = f"{BENCH}/upstream/feynman_qasm/{name}.qasm"
    if os.path.exists(fp):
        prov["logical_vs_feynman"] = check(L, read_qasm(fp)[1], n, zx=False)
    nb = f"{BENCH}/nam/{name}_before.qasm"
    if os.path.exists(nb):
        _, NB = read_qasm(nb)
        prov["logical_vs_nam_before"] = check(L, NB, n, zx=False)
        prov["nam_before_counts"] = counts(NB)
    rec["provenance"] = prov
    # planted bug: delete the first T gate; the check must fail
    i = next(k for k, o in enumerate(C) if o[0] in ("t", "tdg"))
    rec["planted_bug_check"] = check(C, C[:i] + C[i + 1:], n, zx=False)
    assert rec["planted_bug_check"]["verified"] is False, "planted bug not rejected"
    arms = {}
    arms["given_cliffordt"] = dict(t_count=counts(C)["t"], cx=counts(C)["cx"], gates=len(C))
    p = pyzx_arm(C, n)
    arms["pyzx_fr"] = _arm(p["ops"], C, n, dict(t_graph=p["t_graph"], reduce_s=p["reduce_s"],
                                                 pipeline_s=p["pipeline_s"]), save=f"{name}__pyzx_fr")
    k = tket_arm(C, n)
    arms["tket_fpo"] = _arm(k["ops"], C, n, dict(pipeline_s=k["pipeline_s"]), save=f"{name}__tket_fpo")
    k = tket_arm(L, n)
    arms["tket_fpo_logical"] = _arm(k["ops"], L, n, dict(pipeline_s=k["pipeline_s"]),
                                    save=f"{name}__tket_fpo_logical")
    for tag in ("light", "heavy"):
        f = f"{BENCH}/nam/{name}_{tag}.qasm"
        if os.path.exists(f):
            _, NO = read_qasm(f)
            arms[f"nam_{tag}_file"] = _arm(NO, L, n)
    rec["arms"] = arms
    rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return rec


if __name__ == "__main__":
    name, out = sys.argv[1], sys.argv[2]
    OUT_DIR = out
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, name + ".json")
    if os.path.exists(path):
        sys.exit(f"{path} exists (results are append-only; use a new out_dir)")
    r = run(name)
    with open(path + ".tmp", "w") as f:
        json.dump(r, f, indent=1, default=str)
    os.replace(path + ".tmp", path)
