#!/usr/bin/env python3
"""Regenerate benchmarks/train_v2 (2nd CircuitEvolve training set), deterministically.
Run in conda env `benchgen` (qiskit/cirq/supermarq; NOT the project .venv): python benchmarks/fetch_training.py
Sources (no hand-picking, every circuit, mechanical filters only):
  1. The whole QASMBench suite (github.com/pnnl/QASMBench, small+medium+large), every benchmark.
  2. Supermarq's VQEProxy/HamiltonianSimulation/QAOAVanillaProxy/QAOAFermionicSwapProxy at
     4/6/8/10/12 qubits, fixed seeds, exported to QASM via cirq.
Mechanical filters (run as a subprocess in the project .venv, which has circuitevolve+pytket):
must load via circuitevolve.library.load; size <=16q toffoli / <=12q & <=400 rz rotation;
T-cost = t + 7*toffoli + rz (after tket) > 0; drop exact dups and same family+qubit-count as a
test circuit; equivalence sanity <=10q via circuitevolve.verifier.check(load, tket(load)).
KNOWN LIMITATION (see MANIFEST/DROPPED notes): circuitevolve.verifier.check() is built for local
rewrite-rule checks and, on these whole, heavily-restructured circuits, fails via two DIFFERENT
mechanisms that both look like "large distance" but are not a demonstrated tket bug in the spot
checks we ran: (a) on the whole-circuit fallback, the "branch residual" term is ~1-2 even when old
and new are the same unitary -- confirmed for qaoavanilla_6 by decomposing the distance: residual
~0.99 on BOTH sides, phase/unitary-match term alone ~1e-15; (b) on the SequenceMatcher-based
blockwise path, heavy gate reordering by tket can make the diff align an unrelated small block
(e.g. a single S gate) against a large one touching other qubits -- confirmed for vqeproxy_10_z by
inspecting the failing block: residual ~1e-15 (not the cause here) but the aligned old/new gate
spans are simply unrelated, a diff-alignment artifact, not a rewrite window. Both were spot-checked
on 1-2 circuits each, not on every drop; circuits are still dropped on any check() failure per spec.
"""
from __future__ import annotations
import csv
import json
import os
import random
import subprocess
import tempfile
import time
import zipfile
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "benchmarks", "train_v2")
VENV_PY = os.path.join(REPO, ".venv", "bin", "python")
XDG = os.path.join(REPO, ".cache", "xdg")
SPLITS_PATH = os.path.join(REPO, "splits.json")
QASMBENCH_SHA = "357b942396d5c2b7cbc1c229c585a6ef5ccaebac"
QASMBENCH_URL = f"https://github.com/pnnl/QASMBench/archive/{QASMBENCH_SHA}.zip"
QASMBENCH_LICENSE = "BSD-style (Battelle Memorial Institute / PNNL QASMBench, see upstream LICENSE)"
SUPERMARQ_LICENSE = "Apache-2.0 (Infleqtion Supermarq)"
CACHE = os.path.join(tempfile.gettempdir(), "circuitevolve_train_v2_qasmbench")
# test-set (name -> crude name token) used for the "same family+size as a test circuit" check
TOKEN_MAP = {"rc_adder_6": "adder", "gf2^4_mult": "mult", "adder_8": "adder", "barenco_tof_10": "tof",
             "mod_red_21": "mod_red", "qft_8": "qft", "qpe_8": "qpe", "hhl_8": "hhl", "qae_13": "qae",
             "tfim_6": "tfim", "heisenberg_6": "heisenberg", "hubbard_8": "hubbard", "qml_13": "qml"}
SIZES = [4, 6, 8, 10, 12]

def download_qasmbench():
    """Download+extract the pinned QASMBench commit (cached under /tmp); returns its root dir."""
    root = os.path.join(CACHE, f"QASMBench-{QASMBENCH_SHA}")
    if os.path.isdir(root):
        return root
    import requests
    os.makedirs(CACHE, exist_ok=True)
    r = requests.get(QASMBENCH_URL, timeout=180)
    r.raise_for_status()
    zpath = os.path.join(CACHE, "qasmbench.zip")
    open(zpath, "wb").write(r.content)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(CACHE)
    os.remove(zpath)
    return root

def list_qasmbench_candidates(root):
    """Every benchmark folder's main (non hardware-transpiled) .qasm file, in small/medium/large."""
    cands, dropped = [], []
    for suite in ("small", "medium", "large"):
        d = os.path.join(root, suite)
        for name in sorted(os.listdir(d)):
            sub = os.path.join(d, name)
            if not os.path.isdir(sub):
                continue
            qasms = [f for f in sorted(os.listdir(sub)) if f.endswith(".qasm") and "_transpiled" not in f]
            cand_name = f"qasmbench_{suite}_{name}"
            if not qasms:
                dropped.append(dict(name=cand_name, path=sub, reason="no non-transpiled .qasm source file in folder"))
                continue
            fn = f"{name}.qasm" if f"{name}.qasm" in qasms else qasms[0]
            cands.append(dict(name=cand_name, path=os.path.join(sub, fn), suite=suite, bench=name,
                               license=QASMBENCH_LICENSE,
                               source=f"QASMBench@{QASMBENCH_SHA[:12]} {suite}/{name}/{fn}"))
    return cands, dropped

def gen_supermarq(stage_dir):
    """Deterministic (fixed-seed) SupermarQ circuits, exported to QASM via cirq."""
    import cirq
    from supermarq.benchmarks import (HamiltonianSimulation, QAOAFermionicSwapProxy, QAOAVanillaProxy,
                                       VQEProxy)
    os.makedirs(stage_dir, exist_ok=True)
    cands = []
    def emit(name, bench_desc, circuit):
        path = os.path.join(stage_dir, f"{name}.qasm")
        open(path, "w").write(cirq.qasm(circuit))
        cands.append(dict(name=name, path=path, suite="supermarq", bench=bench_desc,
                           license=SUPERMARQ_LICENSE, source=f"Supermarq 0.5.70 {bench_desc}"))
    # dt=1,T=1 (the class default) gives EXACTLY pi/4-multiple angles for every qubit count (a cancellation
    # in the TFIM constants at t=0.5), i.e. almost no T-cost; these dt/T pairs give 2-4 generic-angle steps.
    HAMSIM_STEPS = {4: (0.1, 0.2), 6: (0.1, 0.3), 8: (0.25, 0.75), 10: (0.25, 1.0), 12: (0.4, 1.6)}
    for n in SIZES:
        random.seed(31000 + n)
        dt, tt = HAMSIM_STEPS[n]
        emit(f"supermarq_hamsim_{n}", f"HamiltonianSimulation(n={n},dt={dt},T={tt})",
             HamiltonianSimulation(n, time_step=dt, total_time=tt).circuit())
    for n in SIZES:
        random.seed(32000 + n)
        cz, cx = VQEProxy(n, num_layers=1).circuit()
        emit(f"supermarq_vqeproxy_{n}_z", f"VQEProxy(n={n},layers=1,basis=z)", cz)
        emit(f"supermarq_vqeproxy_{n}_x", f"VQEProxy(n={n},layers=1,basis=x)", cx)
    for n in SIZES:
        random.seed(33000 + n)
        emit(f"supermarq_qaoavanilla_{n}", f"QAOAVanillaProxy(n={n})", QAOAVanillaProxy(n).circuit())
    for n in SIZES:
        random.seed(34000 + n)
        emit(f"supermarq_qaoafsp_{n}", f"QAOAFermionicSwapProxy(n={n})", QAOAFermionicSwapProxy(n).circuit())
    return cands
# Runs inside CircuitEvolve/.venv (has circuitevolve+pytket); written to a temp file at run time,
# never persisted in the repo. Applies the mechanical filters that need the project's own code.

CHECKER_SRC = '''
import os, sys, json, hashlib
IN_PATH, OUT_PATH = sys.argv[1], sys.argv[2]
cfg = json.load(open(IN_PATH))
os.environ.setdefault("XDG_CONFIG_HOME", cfg["xdg"])
sys.path.insert(0, cfg["repo"])
from circuitevolve import circuit as C
from circuitevolve import library
from circuitevolve.verifier import check as veq, Req
TOFFOLI_MAX_Q, ROTATION_MAX_Q, ROTATION_MAX_RZ, EQUIV_MAX_Q = 16, 12, 400, 10

def canon_hash(c):
    rep = [(g.name, g.qubits, None if g.theta is None else round(g.theta, 9), g.cbit, g.cond) for g in c.gates]
    return hashlib.sha256(repr((c.n, c.nc, rep)).encode()).hexdigest()
test_hashes, test_sig = set(), []
for t in cfg["test_entries"]:
    try:
        tc = library.load(os.path.join(cfg["repo"], t["path"]))
        test_hashes.add(canon_hash(tc))
        test_sig.append((t["token"], t["family"], tc.n))
    except Exception:
        pass
import signal
class _TO(Exception): pass
def _alarm(signum, frame): raise _TO()
signal.signal(signal.SIGALRM, _alarm)
PER_CANDIDATE_BUDGET_S = 120  # cost guard: some QASMBench files are >1M lines (unrolled); never hang on one

accepted, dropped, seen_hashes = [], [], set()
for cand in cfg["candidates"]:
    name, path = cand["name"], cand["path"]
    row = dict(name=name, suite=cand["suite"], bench=cand["bench"], license=cand.get("license", ""),
               source=cand.get("source", cand["bench"]))
    signal.alarm(PER_CANDIDATE_BUDGET_S)
    try:
        c = library.load(path)
    except _TO:
        dropped.append(dict(name=name, path=path, reason="timed out (> %ds) in library.load (file too large to process)" % PER_CANDIDATE_BUDGET_S))
        signal.alarm(0)
        continue
    except Exception as e:
        signal.alarm(0)
        dropped.append(dict(name=name, path=path, reason=("library.load failed: %r" % e)[:300]))
        continue
    try:
        tk = library.piecewise(library.tket, c)
    except _TO:
        dropped.append(dict(name=name, path=path, reason="timed out (> %ds) in library.tket (file too large to optimize)" % PER_CANDIDATE_BUDGET_S))
        signal.alarm(0)
        continue
    except Exception as e:
        signal.alarm(0)
        dropped.append(dict(name=name, path=path, reason=("library.tket failed: %r" % e)[:300]))
        continue
    signal.alarm(0)
    cnt = C.counts(tk)
    logical_toffoli = C.counts(c)["toffoli"]  # ccx/ccz count on the LOGICAL file; tket always rebases them away
    qubits = max(c.n, tk.n)
    family = "rotation" if cnt["rz"] >= 1 else "toffoli"
    cap = ROTATION_MAX_Q if family == "rotation" else TOFFOLI_MAX_Q
    if qubits > cap:
        dropped.append(dict(name=name, path=path, reason="%s: qubits %d > cap %d" % (family, qubits, cap)))
        continue
    if family == "rotation" and cnt["rz"] > ROTATION_MAX_RZ:
        dropped.append(dict(name=name, path=path, reason="rotation: rz_after_tket %d > cap %d" % (cnt["rz"], ROTATION_MAX_RZ)))
        continue
    tcost = cnt["t"] + 7 * cnt["toffoli"] + cnt["rz"]
    if tcost <= 0:
        dropped.append(dict(name=name, path=path, reason="T-cost == 0 (pure Clifford after tket)"))
        continue
    h = canon_hash(c)
    if h in seen_hashes:
        dropped.append(dict(name=name, path=path, reason="exact duplicate of another accepted candidate"))
        continue
    if h in test_hashes:
        dropped.append(dict(name=name, path=path, reason="exact duplicate of a test-set circuit"))
        continue
    collide = [tok for tok, fam, q in test_sig if fam == family and q == qubits and tok in name.lower()]
    if collide:
        dropped.append(dict(name=name, path=path, reason="same family+size as test circuit token(s) %r" % collide))
        continue
    eq_note = "not checked (>10 qubits)"
    if qubits <= EQUIV_MAX_Q:
        signal.alarm(PER_CANDIDATE_BUDGET_S)
        try:
            v = veq(c, tk, Req(eps=0.0), zero_init=())
        except _TO:
            v = None
        signal.alarm(0)
        if v is None:
            dropped.append(dict(name=name, path=path, reason="timed out (> %ds) in verifier.check" % PER_CANDIDATE_BUDGET_S))
            continue
        eq_note = "ok (%s, dist=%.2e)" % (v.mode, v.dist) if v.ok else ("FAILED: %s" % v.reason)
        if not v.ok:
            dropped.append(dict(name=name, path=path,
                                 reason=("equivalence check failed (dist=%.3f, mode=%s): NOT individually root-"
                                         "caused for this circuit; fetch_training.py docstring spot-checked 2 "
                                         "similar failures and found both were verifier artifacts (large intrinsic "
                                         "branch-residual, or a spurious blockwise diff-alignment), not a "
                                         "demonstrated tket error -- dropped per the mechanical rule regardless" % (v.dist, v.mode))))
            continue
    seen_hashes.add(h)
    row.update(family=family, qubits=qubits, gates=len(c.gates), toffoli_count=logical_toffoli,
               rz_after_tket=cnt["rz"], t_cost_cheap=tcost, equivalence=eq_note, src_path=path)
    accepted.append(row)
json.dump(dict(accepted=accepted, dropped=dropped), open(OUT_PATH, "w"), indent=1)
print("accepted=%d dropped=%d" % (len(accepted), len(dropped)))
'''

def run_checker(candidates, test_entries):
    """Mechanical filters that need circuitevolve: run as a subprocess in the project .venv."""
    with tempfile.TemporaryDirectory() as td:
        checker_path = os.path.join(td, "checker.py")
        open(checker_path, "w").write(CHECKER_SRC)
        in_path, out_path = os.path.join(td, "in.json"), os.path.join(td, "out.json")
        json.dump(dict(repo=REPO, xdg=XDG, test_entries=test_entries, candidates=candidates), open(in_path, "w"))
        subprocess.run([VENV_PY, checker_path, in_path, out_path], check=True)
        return json.load(open(out_path))

def write_outputs(accepted, dropped, pre_dropped):
    import glob
    for fam in ("toffoli", "rotation"):
        os.makedirs(os.path.join(OUT, fam), exist_ok=True)
        for stale in glob.glob(os.path.join(OUT, fam, "*.qasm")):  # a circuit can change family between runs
            os.remove(stale)
    manifest_fields = ["name", "family", "source", "license", "qubits", "gates", "toffoli_count",
                        "rz_after_tket", "t_cost_cheap", "zero_init", "zero_init_source", "equivalence_check"]
    with open(os.path.join(OUT, "MANIFEST.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=manifest_fields)
        w.writeheader()
        for row in accepted:
            dst = os.path.join(OUT, row["family"], row["name"] + ".qasm")
            with open(row["src_path"]) as sf, open(dst, "w") as df:
                df.write(sf.read())
            w.writerow(dict(name=row["name"], family=row["family"], source=row.get("source", row["bench"]),
                             license=row.get("license", ""), qubits=row["qubits"], gates=row["gates"],
                             toffoli_count=row["toffoli_count"], rz_after_tket=row["rz_after_tket"],
                             t_cost_cheap=row["t_cost_cheap"], zero_init="",
                             zero_init_source="none (QASMBench/Supermarq declare no ancillas; not inferred)",
                             equivalence_check=row["equivalence"]))
    with open(os.path.join(OUT, "DROPPED.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "path", "reason"])
        w.writeheader()
        for d in pre_dropped + dropped:
            w.writerow(d)

def update_splits(accepted):
    splits = json.load(open(SPLITS_PATH))
    tof = sorted([a for a in accepted if a["family"] == "toffoli"], key=lambda a: a["qubits"])
    rot = sorted([a for a in accepted if a["family"] == "rotation"], key=lambda a: a["qubits"])
    splits["train_v2"] = [dict(name=a["name"], family=a["family"],
                                path=f"benchmarks/train_v2/{a['family']}/{a['name']}.qasm", zero_init=[])
                           for a in tof + rot]
    with open(SPLITS_PATH, "w") as f:
        json.dump(splits, f, indent=1)

def main():
    t0 = time.time()
    qb_root = download_qasmbench()
    qb_cands, qb_predropped = list_qasmbench_candidates(qb_root)
    # cheap pre-filters, before any load/tket is attempted:
    # (1) both family caps are <= 16 qubits, so anything bigger is unconditionally dropped;
    # (2) a few QASMBench "benchmarks" are >1MB of literally-unrolled text (hhl_n14 is 85MB for 14 qubits)
    #     that pytket/our parser cannot process in finite time -- a hard byte-size cost guard, not a
    #     qubit-count judgement call.
    import re
    MAX_BYTES = 1_000_000
    def cheap_qubits(path):
        return sum(int(m.group(2)) for m in re.finditer(r"qreg\s+(\w+)\s*\[\s*(\d+)\s*\]", open(path).read()))
    kept, oversize = [], []
    for c in qb_cands:
        sz = os.path.getsize(c["path"])
        if sz > MAX_BYTES:
            qb_predropped.append(dict(name=c["name"], path=c["path"],
                                       reason=f"file is {sz / 1e6:.1f} MB > {MAX_BYTES / 1e6:.0f} MB cost guard (unrolled text, not practical to parse/optimize)"))
            continue
        (kept if cheap_qubits(c["path"]) <= 16 else oversize).append(c)
    for c in oversize:
        qb_predropped.append(dict(name=c["name"], path=c["path"], reason=f"qubits {cheap_qubits(c['path'])} > 16 (cheap qreg count)"))
    sm_cands = gen_supermarq(os.path.join(tempfile.gettempdir(), "circuitevolve_train_v2_supermarq"))
    splits = json.load(open(SPLITS_PATH))
    test_entries = [dict(path=t["path"], family=t["family"], token=TOKEN_MAP[t["name"]]) for t in splits["test"]]
    result = run_checker(kept + sm_cands, test_entries)
    accepted, dropped = result["accepted"], result["dropped"]
    write_outputs(accepted, dropped, qb_predropped)
    update_splits(accepted)
    tof, rot = [a for a in accepted if a["family"] == "toffoli"], [a for a in accepted if a["family"] == "rotation"]
    print(f"QASMBench: {len(qb_cands)} with source, {len(kept)} pass the cheap pre-filters -> checker; "
          f"{len(qb_predropped)} pre-dropped (missing source / oversized / >1MB) | Supermarq: {len(sm_cands)}")
    print(f"Accepted: {len(accepted)} (toffoli={len(tof)}, rotation={len(rot)}); dropped (checker): {len(dropped)}")
    print(f"Done in {time.time() - t0:.0f}s")

if __name__ == "__main__":
    main()
