# P0 gate (2026-10-20): PASS

Gate (SPEC section 10): baselines.csv reproduces every number in section 3 exactly; an empty-book run returns the
inputs unchanged with error 0; the judge hash check works.

`.venv/bin/python -m pytest -q v3/tests/test_p0.py`: **20/20 passed**. `python -m v3.tools.empty_book`: PASS
(20 rows in `results/events.jsonl`, event `p0_empty_book`). `judge/FROZEN.sha256`: 51 files (judge, manifest,
all inputs, baselines.csv, wrapped upstream modules).

## 1. Section-3 numbers, reproduced exactly (`baselines/baselines.csv`, 70 rows)

| check | result |
|---|---|
| DV angle, 5 circuits x 2 eps x 4 methods (TKET=B0, pyzx=B1, BQSKit-FT=B2, BQSKit-DPF=B3g) | 40/40 exact |
| Judge T-count of the unchanged TKET input == TKET column | 10/10 (independent check of the judge metric) |
| DV reconstruction TKET (tket_fpo_logical) / pyzx (pyzx_fr), qubits | 10/10 exact, qubits 24/14/12/19/11 |
| Genesis seed 0 (1-op/2-op/total/duration) == SPEC reference | 5/5 exact |

## 2. New baseline runs

**BQSKit-FT (B2) / BQSKit-DPF (B3g) on reconstruction**, eps 1e-3, bqskit-ft @ 2e99ba6 via the unchanged
`stage1/run_bqskit_arms.run_job` (`baselines/run_bqskit_recon.py` redirects paths into v3/):

| circuit | B2 T | B3g T | input T (7/Toffoli) |
|---|---|---|---|
| adder_8 | 399 | 399 | 399 |
| adder_6 | 77 | 77 | 77 |
| mult_4 | 112 | 112 | 112 |
| mcx_10 | 224 | 224 | 224 |
| modred_21 | 119 | 119 | 119 |

Both arms are no-ops on exact Clifford+T input (they optimize rotations only). Deviations (user decisions):
BQSKit leaves `ccx` undecomposed (not in its gate set, passed through), so it gets the Nam suite's Clifford+T file
(`benchmarks/nam_arith/cliffordt/`, Quartz nam_circs, 7 T per CCZ) instead of the logical file. The stage-1 dense
state-vector check is skipped above 20 qubits (adder_8: > 30 min), recorded as `state_dist = None`.

**Genesis** (5 seeds, `--seed s`, PYTHONHASHSEED = s), best by routed total gates:

| circuit | best seed | routed 1-op/2-op/total/dur | logical total | err_trotter | err_exact |
|---|---|---|---|---|---|
| kerr_small | 0 | 453/142/595/3032 | 409 | 0.9996 (logical) | 0.9996 (logical) |
| boseHubbard_small | 1 | 72/40/112/439 | 100 | 0.987 | 0.997 |
| z2Higgs_small | 3 | 76/40/116/279 | 83 + 3 unsynth. pauli | skipped | skipped |
| heisenberg_small | 0 | 184/136/320/1810 | 0 + 13 unsynth. pauli | skipped | skipped |
| electronicVibration_small | 0 | 566/305/871/5358 | 224 + 16 unsynth. pauli | skipped | skipped |

Genesis errors for z2Higgs / heisenberg / electronicVibration were **skipped (user decision 2026-10-20)**: the
exact-evolution step (single-threaded sparse expm on 2.6M / 6M dimensions) ran > 20 min.

## 3. Notes the user asked for

**(a) DV verification above 20 qubits.** The judge (not the baselines) verifies Toffoli-level / Clifford+T
circuits with the v2 exact / relaxed basis-state method (frozen D[omega] simulator `circuitevolve/sim.py`) at
every size. Up to 2^14 basis inputs the check is exhaustive and **certified**; above it is **sampled** (256
random inputs + edge cases, `certified = False`). For references that are not permutation-like as written (Nam
files spell Toffolis h-ccz-h; Barenco circuits interleave them) the judge builds `ReferenceSpec.from_function`
with f(x) = the exact simulator's output of the reference on |x>, so v2 can sample instead of refusing.

| circuit | qubits | method | certified | planted bug (one gate dropped) |
|---|---|---|---|---|
| adder_6 | 14 | basis-exhaustive (16384 inputs) | yes | caught |
| mult_4 | 12 | basis-exhaustive | yes | caught |
| modred_21 | 11 | basis-exhaustive | yes | caught |
| mcx_10 | 19 | basis-sampled (256) | **no** | caught |
| adder_8 | 24 | basis-sampled (256) | **no** | caught |
| angle circuits n <= 10 | 6-8 | dense operator norm | yes | |
| qae_13 | 13 | Haar statevectors (lower bound) | **no** | |

Every runner log entry and every admission report carries `method` and `certified` per application.

**(b) Two levels for CV-DV.** `baselines.csv` has two Genesis rows per circuit: `level = routed` (physical
output, equals Genesis --stats) and `level = logical` (before routing). The logical count is INCOMPLETE for
z2Higgs / heisenberg / electronicVibration (Genesis synthesizes multi-Pauli gadgets only while routing), so it
is flagged `complete = False` with the number of placeholders. Ours is compared at the same level: ours-logical
vs Genesis-logical only where Genesis' logical count is complete, ours routed through Genesis' own router
(`cvdv/src/cvdv/route.py`: same router and options; only Genesis' SWAP phase is fixed, gate counts unchanged)
vs Genesis-routed.

**(c) CV-DV error target.** Genesis kerr_small has process infidelity **0.9996** (err_trotter and err_exact,
measured on its logical circuit because the routed one, 19 qubits + 20 qumodes, exceeds the dense simulator);
boseHubbard_small 0.987 / 0.997. Genesis does not implement the Trotter step it compiles (consistent with
`cvdv/results/P0_genesis_reproduction.md`), so "equal or smaller error than Genesis" is vacuous. **CV-DV
comparisons will be made at a fixed error target** (value to be set before P2), with Genesis' gate count and its
measured error reported side by side.

## 4. CV-DV judge parameters (manifest) and controls

Probe subspace: system qumodes Fock <= n_probe (kerr 3, boseHubbard / z2Higgs 2, others 1), basis-exact when
dim <= 64 else 8 seeded Haar probes; cutoffs kerr 16/22, 4-mode circuits 12/16 (8 was too low: positive
control heisenberg err 3e-5 at N = 8 vs 9e-10 at N = 12), electronicVibration 3/4. Positive control (cvdv
certified compiler, kerr_small): err_trotter 7e-16, err_exact 1e-13, cutoffs agree (test).

## 5. Figures (baseline only) `report/figures/p0_*.png` + one CSV each

dv_angle_tcount, dv_recon_tcount, dv_qubits, cvdv_gates (routed total, routed 2-op, logical total), cvdv_error.
