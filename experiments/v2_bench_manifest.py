"""Write benchmarks/nam_arith/MANIFEST.csv and split_v2.json from the normalized files (counts are computed here,
nothing is typed in). qseed shor_12/14/16 are added BY REFERENCE (row values read from
benchmarks/bqskit_qseed/MANIFEST.csv; files stay in benchmarks/bqskit_qseed/qasm/shor/).

    .venv/bin/python experiments/v2_bench_manifest.py
"""
from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v2_bench_common import BENCH, ROOT, counts, read_qasm, sparse_run  # noqa: E402

import numpy as np  # noqa: E402


def clean_qubits(name):
    """Indices (QASM order = Feynman .v order) of qubits not listed in the .qc `.i` line (start in |0>)."""
    p = os.path.join(BENCH, "upstream", "feynman_qc", name + ".qc")
    v = i = None
    for line in open(p):
        if line.startswith(".v"):
            v = line.split()[1:]
        elif line.startswith(".i"):
            i = set(line.split()[1:])
    return [k for k, q in enumerate(v) if q not in i], len(v)


def ancillas_restored(ops, n, anc, trials=64, seed=0):
    """Fraction of random primary inputs (ancillas 0) after which every ancilla is back in |0>."""
    rng = np.random.default_rng(seed)
    inputs = [k for k in range(n) if k not in anc]
    good = 0
    for _ in range(trials):
        x = sum(1 << k for k in inputs if rng.integers(2))
        st = sparse_run(ops, {x: 1.0})
        good += all(all(not (key >> a) & 1 for a in anc) for key, v in st.items() if abs(v) > 1e-12)
    return good / trials

sys.path.insert(0, BENCH)
from fetch_suite import FEYNMAN_SHA, NAM_SHA, NAMES, QUARTZ_SHA  # noqa: E402
from normalize import CUCCARO_N  # noqa: E402

FAMILY = {
    **{f"tof_{k}": "mcx_toffoli" for k in (3, 4, 5, 10)},
    **{f"barenco_tof_{k}": "mcx_toffoli" for k in (3, 4, 5, 10)},
    "adder_8": "adder", "rc_adder_6": "adder", "vbe_adder_3": "adder", "qcla_adder_10": "adder",
    "csla_mux_3": "adder", "csum_mux_9": "adder",
    **{f"cuccaro_{k}": "adder" for k in CUCCARO_N},
    **{f"gf2^{k}_mult": "gf2_mult" for k in (4, 5, 6, 7, 8, 9, 10, 16, 32)},
    "mod5_4": "modular", "mod_mult_55": "modular", "mod_red_21": "modular", "mod_adder_1024": "modular",
    "qcla_mod_7": "modular", "qcla_com_7": "comparator",
    "hwb6": "hidden_weighted_bit", "ham15-low": "hamming", "ham15-med": "hamming", "ham15-high": "hamming",
    "grover_5": "grover_oracle",
    "shor_12": "shor", "shor_14": "shor", "shor_16": "shor",
}
DEV = {"tof_3", "tof_4", "tof_5", "barenco_tof_3", "barenco_tof_4", "barenco_tof_5",
       "cuccaro_4", "cuccaro_8", "vbe_adder_3", "rc_adder_6", "csla_mux_3",
       "gf2^4_mult", "gf2^5_mult", "gf2^6_mult", "mod5_4", "mod_mult_55", "shor_12"}
LARGE_OPTIONAL = {"gf2^32_mult": "baseline not computed (run stopped after ~110 min, no output); published Nam 2018 Table 4 numbers only"}
NOT_IN_NAM = {"grover_5", "ham15-low", "ham15-med", "ham15-high", "hwb6"}  # not in Nam et al. 2018 Table 4


def main():
    rows = []
    for name in list(NAMES) + [f"cuccaro_{k}" for k in CUCCARO_N]:
        gen = name.startswith("cuccaro_")
        lp = f"generated/{name}.qasm" if gen else f"logical/{name}.qasm"
        n, L = read_qasm(os.path.join(BENCH, lp))
        cl = counts(L)
        if gen:
            ct = dict(t=cl["t_if_expanded"], gates=None)
            src = "generated: circuitevolve.baselines.cuccaro.construct (Cuccaro et al. 2004)"
            cp, lic = "", "project code"
            anc = [0]  # carry-in ancilla c0 (circuitevolve/baselines/cuccaro.py)
        else:
            _, C = read_qasm(os.path.join(BENCH, f"cliffordt/{name}.qasm"))
            ct = counts(C)
            src = (f"quantum-compiler/quartz@{QUARTZ_SHA[:12]} circuit/nam-benchmarks + nam_circs; "
                   f"cross-checked vs meamy/feynman@{FEYNMAN_SHA[:12]}"
                   + ("" if name in NOT_IN_NAM else f" and njross/optimizer@{NAM_SHA[:12]} (authors)"))
            cp, lic = f"cliffordt/{name}.qasm", "Apache-2.0 (Quartz copy); upstream T-par/Feynman suite BSD-3-Clause"
            anc, nv = clean_qubits(name)
            assert nv == n, (name, nv, n)
        split = "large_optional" if name in LARGE_OPTIONAL else ("dev" if name in DEV else "heldout")
        rows.append(dict(name=name, family=FAMILY[name], split=split, qubits=n,
                         gates_logical=cl["gates"], gates_cliffordt=ct["gates"], t_count_given=ct["t"],
                         ccx_count=cl["ccx"] + cl["ccz"], cx_logical=cl["cx"],
                         logical_path=lp, cliffordt_path=cp, source=src, license=lic,
                         in_nam2018_table4=not gen and name not in NOT_IN_NAM,
                         zero_init_qubits=" ".join(map(str, anc)),
                         zero_init_restored_frac=(ancillas_restored(L, n, anc) if len(anc) < n else None),
                         notes="; ".join(x for x in ("ccz form (h-conjugated ccz = ccx)" if not gen else "ccx form",
                                                      LARGE_OPTIONAL.get(name, "")) if x)))
    with open(os.path.join(ROOT, "benchmarks", "bqskit_qseed", "MANIFEST.csv")) as f:
        q = {r["circuit"]: r for r in csv.DictReader(f)}
    for name in ("shor_12", "shor_14", "shor_16"):
        r = q[name]
        rows.append(dict(name=name, family="shor", split="dev" if name in DEV else "heldout", qubits=int(r["qubits"]),
                         gates_logical=int(r["gates"]), gates_cliffordt=None, t_count_given=None,
                         ccx_count=int(r["ccx"]), cx_logical=None,
                         logical_path=f"../bqskit_qseed/{r['source_path']}", cliffordt_path="",
                         source="by reference: benchmarks/bqskit_qseed (mtweiden/qseed@eb9ccab7a073)",
                         license="no license declared (research-use copy)", in_nam2018_table4=False,
                         zero_init_qubits="", zero_init_restored_frac=None,
                         notes=f"gateset {r['gateset']}; has continuous cp/ccp rotations, no Clifford+T 'as given' "
                               "T-count; baselines reused from results/bqskit_baselines (not recomputed)"))
    rows.sort(key=lambda r: (r["split"], r["family"], r["qubits"], r["name"]))
    out = os.path.join(BENCH, "MANIFEST.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    split = dict(version="v2-nam-arith-1", created="2026-10-14",
                 dev=sorted(r["name"] for r in rows if r["split"] == "dev"),
                 heldout=sorted(r["name"] for r in rows if r["split"] == "heldout"),
                 large_optional=sorted(r["name"] for r in rows if r["split"] == "large_optional"))
    json.dump(split, open(os.path.join(BENCH, "split_v2.json"), "w"), indent=1)
    print(len(rows), len(split["dev"]), len(split["heldout"]), len(split["large_optional"]))


if __name__ == "__main__":
    main()
