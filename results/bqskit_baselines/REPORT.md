# Baselines track: BQSKit by-gate reproduction, TKET / pyzx references, QuickPartitioner profile

Date 2026-10-11. No LLM involved. Code: `experiments/bqskit_baselines/`. Environment: `ENVIRONMENT.md`
(bqskit 1.2.1, bqskit-ft 0.2.0 @ 4a288ae, pygridsynth 2.0.0, pytket 2.18.5, pyzx 0.10.7, qiskit 2.5.2).
Every number below is read from a CSV in this directory; nothing is typed from memory.

## 1. arXiv:2409.00433 Table 3, "By Gate" row

**Verdict: reproduced.** Under the paper's gate-level convention the RZ counts match the published
values exactly for all five circuits. The T-counts are within -0.42 % to +1.56 %. Two inputs needed explanation:

* QFT-32: the qseed `qft_32.qasm` is a *full* QFT. The paper calls its circuit an "approximate QFT".
* Shor-16: the published 816 is a parameter count, not a valid Clifford+T compilation.

Both are detailed below.

### What "By Gate" is (found by matching RZ counts, not by tuning)
For every U3(θ, φ, λ) gate, taken alone (no merging of neighbouring 1q gates, no gate removal), apply the
textbook identity U3 = RZ(φ+π)·SX·RZ(θ+π)·SX·RZ(λ). An angle that is a multiple of π/4 becomes
Clifford/T. Every other RZ becomes one gridsynth call at ε = 1e-9. This reproduces the published RZ counts
for add_17, hhl_6 and mult_16 *exactly* (251 / 243 / 1,079) with no free parameter. It is also consistent
with the paper's own error column: its ε_total equals #RZ × 1e-9 (e.g. Add 2.5e-7 for 251 RZ), so the
By-Gate row has no approximation other than gridsynth. Implementation: `bygate_exact.py::lower_circuit_paramzsx`.
Unitary checks: n ≤ 10 compares the full unitary; n ≤ 17 uses a statevector spot check
(`reference/verify_eval.csv`). Both give 1 − overlap ≤ 1.2e-13 for every pipeline output.

| circuit | input | method_short | rz_count | published_rz | rz_diff_pct | t_count | published_t | t_diff_pct | valid_clifford_t |
|---|---|---|---|---|---|---|---|---|---|
| add_17 | qseed add_17 | paper conv. | 251 | 251 | 0.0 | 23,520 | 23,562 | -0.18 | yes |
| hhl_6 | qseed hhl_6 | paper conv. | 243 | 243 | 0.0 | 22,887 | 22,571 | 1.4 | yes |
| mult_16 | qseed mult_16 | paper conv. | 1,079 | 1,079 | 0.0 | 100,572 | 100,678 | -0.11 | yes |
| qft_32 | qseed qft_32 | paper conv. | 1,395 | 1,080 | 29.17 | 132,345 | 101,480 | 30.41 | yes |
| qft_32 | AQFT-32, d<=17 (reconstructed) | paper conv. | 1,080 | 1,080 | 0.0 | 101,049 | 101,480 | -0.42 | yes |
| shor_16 | qseed shor_16 (qiskit opt0 lowering) | paper conv. | 4,678 | 816 | 473.28 | 437,107 | 74,797 | 484.39 | yes |
| shor_16 | qseed shor_16 (cp/ccp/u1 as given) | param-count conv. | 816 | 816 | 0.0 | 75,965 | 74,797 | 1.56 | no |

`t_count` = T/T† from π/4-multiple angles plus Σ gridsynth T-counts (pygridsynth `gridsynth_gates(θ, 1e-9)`,
the call bqskit-ft's `GridSynthPass` makes; each word re-multiplied and checked against RZ(θ): max phase-aligned operator-norm distance 5.0000e-10). Our gridsynth T per RZ is [93.42, 93.65, 93.0, 94.8, 93.12] (add, hhl, mult, qft, shor rows of the
qseed run). The paper's T/RZ (including fixed T) is {'add_17': 93.87, 'hhl_6': 92.88, 'mult_16': 93.31, 'qft_32': 93.96, 'shor_16': 91.66}. The residual T differences (≤ 1.6 %)
are therefore at the level of the gridsynth implementation and version, not the circuit.

**QFT-32.** qseed `qft_32` has 1,040 CX = 496 controlled-phases × 2 + 16 swaps × 3, which is the full QFT. Under
the same convention it gives 1,395 RZ (= 3 × 465 controlled-phases with distance d ≥ 2). The minimal-RZ variant below gives 1,386, because it writes the 9 RZ with |θ| < 2e-9 as identity.
The paper text calls its QFT-32 an "approximate QFT" (Sec. 5.3). A textbook approximate QFT that keeps
controlled-phases with distance d ≤ 17 has 360 non-Clifford controlled-phases × 3 = **1,080 RZ, exactly the published value**.
Its T-count is 101,049 (-0.42 %). This is a reconstruction: d_max = 17 was *chosen* as the one integer
that gives 1,080 (≡ qiskit `approximation_degree = 14`). It is not stated in the paper. Generator:
`make_aqft.py 32 17`, file `work/aqft32_d17_u3cx.qasm`.

**Shor-16.** 816 equals the number of `cp` / `ccp` / `u1` gates in qseed `shor_16.qasm` whose angle is not a multiple of π/4
(656 + 120 + 40, `table3/shor16_param_convention.json`). Gridsynthing each such angle once gives
75,965 T (+1.56 %; includes 7 T × 7 ccx). The published Shor number therefore counts each controlled-phase as **one**
rotation. Without ancillas, CP(θ) costs 3 RZ(θ/2) and CCP(θ) costs 7 RZ(θ/4). So 816 / 74,797 is a counting
convention, not a valid Clifford+T compilation. A valid gate-level lowering (exact qiskit opt-0 decomposition to
U3+CX, `ccp` via the cp/cx identity) gives 4,678 RZ / 437,107 T. Use those numbers, or the TKET / pyzx rows
below, as the honest Shor baseline. Note: the paper's 2Q/3Q-block rows report the same 816 RZ for Shor.

### Improved exact gate-level (ours, for reference)
Same pipeline, but each *merged* run of 1q gates is written with the provably minimal number of non-Clifford
RZ, k ∈ {0,1,2,3}, decided from the Bloch rotation (`bygate_exact.py::decompose_1q`, tests in
`test_bygate_exact.py`). It matches the paper convention on add/mult and lowers hhl_6 to 215 RZ.

| circuit | input | rz_count | t_count | t_diff_pct |
|---|---|---|---|---|
| add_17 | qseed add_17 | 251 | 23,520 | -0.18 |
| hhl_6 | qseed hhl_6 | 215 | 20,311 | -10.01 |
| mult_16 | qseed mult_16 | 1,079 | 100,572 | -0.11 |
| qft_32 | qseed qft_32 | 1,386 | 131,649 | 29.73 |
| shor_16 | qseed shor_16 | 4,629 | 432,486 | 478.21 |
| qft_32 | reconstructed approximate QFT-32 (d<=17) | 1,080 | 101,049 | -0.42 |

### bqskit-ft `build_circuit_workflow` as shipped does NOT reproduce By Gate
`build_circuit_workflow(optimization_level=1, synthesis_epsilon=1e-8, decompose_rz=False)` with
`CliffordTModel(n)`, then gridsynth at 1e-9. Three seeds (seeded by hand, see issue 1):

| circuit | rz_min | rz_max | t_min | t_max | t_diff_pct_seed0 | bqskit_error_bound_seed0 |
|---|---|---|---|---|---|---|
| add_17 | 484 | 486 | 45,554 | 45,774 | 94.27 | 1.6e-07 |
| hhl_6 | 129 | 134 | 12,128 | 12,650 | -44.73 | 0.0e+00 |
| mult_16 | 2,129 | 2,129 | 199,386 | 199,416 | 98.05 | 1.0e-07 |
| qft_32 | 1,685 | 1,723 | 158,466 | 161,772 | 59.41 | 3.8e-03 |
| shor_16 | 9,294 | 9,327 | 871,590 | 874,349 | 1068.96 | 1.4e-06 |

Causes, from reading `bqskit/ft/cliffordt/defaultworkflow.py` @ 4a288ae:
1. `build_cliffordt_workflow` assigns `passes = build_partitioning_workflow(...)` (line 170) instead of
   `+=`. This silently drops its own `SetRandomSeedPass`, the `UnfoldPass` and the whole multi-qudit
   retarget step. So `seed=` has no effect and non-native gates (Shor's cp/ccp/swap) are never retargeted.
2. `GroupSingleQuditGatePass` + `ZXZXZDecomposition` re-derive Euler angles from the 2×2 unitary. The
   parameter-preserving form is lost, so a U3 with one non-Clifford angle typically becomes 2–3 RZ. This is
   the ~2× inflation on add/mult/qft (e.g. 484–486 vs 251 on add_17).
3. `QuickPartitioner(2)` + `ScanningGateRemovalPass` (instantiation threshold 1e-8 on the
   1 − |Tr|/N cost) removes gates and re-fits angles. It is lossless on hhl_6 (bound 0, 129–134 RZ, below the
   paper's 243). It is lossy on qft_32: it deletes the small-angle rotations and the LogErrorPass bound is 3.8e-3,
   about 3,500× the paper's ε_total for QFT-32 (1.1e-6). It is also seed-dependent (qft_32 RZ varies 1,685–1,723 across seeds).

## 2. Reference pipelines (TKET, pyzx) on the same five circuits, gridsynth at 1e-9
* **tket**: `FullPeepholeOptimise()` (defaults) → `AutoRebase{CX,H,Rz}` → `RemoveRedundancies`.
  **tket+minrz** re-lowers TKET's optimised circuit with the minimal-RZ decomposition. Same CX skeleton; its
  CX count includes the 3-CX expansion of TKET's implicit wire swaps.
* **pyzx**: input = exact Clifford+Rz form (`clifford_rz/<c>_bygate_minrz.qasm`), then `full_reduce` → `extract_circuit`
  → `to_basic_gates` → `basic_optimization`. `float_to_fraction_max_denominator` is raised to 1e15, because the default
  2**20 rounds angles to multiples of π/2**20. Scientific-notation literals are rewritten in fixed point, because
  pyzx parses `9.5e-05` as an expression in a free variable `e`.
* All 10 runs finished well under the 30 min limit. TKET and pyzx ran concurrently on 12 cores, so wall
  times are slightly inflated. `pipeline_s` = optimisation + extraction; `wall_s` adds subprocess start, QASM parse
  and (n ≤ 10) a full unitary check. The last column is the statevector spot check (n ≤ 17; qft_32 not checked).

| circuit | pipeline | cx | rz_count | t_count | t_vs_reproduced_bygate_pct | t_vs_published_bygate_pct | pipeline_s | wall_s | statevector_1_minus_overlap |
|---|---|---|---|---|---|---|---|---|---|
| add_17 | tket | 224 | 189 | 17,721 | -24.66 | -24.79 | 1.2 | 1.7 | 5e-15 |
| add_17 | tket+minrz | 224 | 189 | 17,721 | -24.66 | -24.79 | 0.2 | 2.6 |  |
| hhl_6 | tket | 174 | 89 | 8,352 | -63.51 | -63.0 | 0.7 | 1.1 | 1e-15 |
| hhl_6 | tket+minrz | 174 | 87 | 8,168 | -64.31 | -63.81 | 0.5 | 2.4 |  |
| mult_16 | tket | 1,108 | 1,076 | 100,408 | -0.16 | -0.27 | 3.5 | 4.0 | 1e-14 |
| mult_16 | tket+minrz | 1,108 | 1,044 | 97,306 | -3.25 | -3.35 | 8.0 | 13.2 |  |
| qft_32 | tket | 962 | 935 | 88,445 | -33.17 | -12.84 | 4.6 | 5.0 |  |
| qft_32 | tket+minrz | 1,010 | 933 | 88,329 | -33.26 | -12.96 | 0.5 | 6.4 |  |
| shor_16 | tket | 4,433 | 3,480 | 325,074 | -25.63 | 334.61 | 35.6 | 36.2 | 7e-14 |
| shor_16 | tket+minrz | 4,433 | 3,480 | 325,074 | -25.63 | 334.61 | 40.7 | 78.2 |  |
| add_17 | pyzx | 290 | 112 | 10,508 | -55.32 | -55.4 | 0.3 | 0.6 | 5e-15 |
| hhl_6 | pyzx | 222 | 174 | 16,362 | -28.51 | -27.51 | 0.4 | 8.5 | 7e-15 |
| mult_16 | pyzx | 846 | 351 | 32,738 | -67.45 | -67.48 | 3.4 | 3.7 | 1e-14 |
| qft_32 | pyzx | 1,767 | 470 | 44,167 | -66.63 | -56.48 | 13.3 | 13.7 |  |
| shor_16 | pyzx | 5,334 | 1,525 | 141,327 | -67.67 | 88.95 | 92.6 | 93.3 | 8e-14 |

`t_vs_reproduced_bygate_pct` compares against the paper-convention row of Section 1 on the same qseed input.
Note that pyzx (full_reduce) beats TKET on add/mult/qft/shor by a wide margin, but loses on hhl_6.

## 3. QuickPartitioner block profile (block sizes 2 and 3)
`partition/partition_profile.csv`: 45 circuits (5 eval + 40 dev), two circuit forms:
* `cliffordrz` (minimal-RZ Clifford+RZ; rotation = RZ not a multiple of π/4);
* `u3cx` (benchmark as given; rotations = non-Clifford ZSX angles per U3).

Structures abstract all angles. Distinct unitaries are up to global phase, rounded to 1e-6.
Shor is lowered to U3+CX first; qml barriers are stripped. Clifford+RZ form:

| circuit | n_blocks_2q | rot_per_block_mean_2q | n_struct_2q | n_unitary_2q | n_blocks_3q | rot_per_block_mean_3q | n_struct_3q | n_unitary_3q |
|---|---|---|---|---|---|---|---|---|
| add_17 | 116 | 2.16 | 13 | 35 | 71 | 3.54 | 26 | 42 |
| hhl_6 | 123 | 1.75 | 23 | 42 | 29 | 7.41 | 14 | 26 |
| mult_16 | 700 | 1.54 | 17 | 49 | 148 | 7.29 | 20 | 33 |
| qft_32 | 512 | 2.71 | 7 | 44 | 283 | 4.9 | 14 | 79 |
| shor_16 | 3,078 | 1.5 | 58 | 221 | 1,230 | 3.76 | 76 | 193 |
| qft_3 | 4 | 0.75 | 4 | 4 | 1 | 3.0 | 1 | 1 |
| qft_4 | 8 | 1.12 | 6 | 7 | 4 | 2.25 | 4 | 4 |
| qft_5 | 12 | 1.5 | 6 | 9 | 7 | 2.57 | 6 | 6 |
| qft_6 | 18 | 1.67 | 6 | 11 | 11 | 2.73 | 9 | 9 |
| qft_7 | 24 | 1.88 | 6 | 13 | 15 | 3.0 | 9 | 12 |
| qft_8 | 32 | 1.97 | 6 | 15 | 18 | 3.5 | 10 | 14 |
| qft_16 | 128 | 2.46 | 6 | 31 | 71 | 4.44 | 12 | 37 |
| qpe_6 | 97 | 1.7 | 19 | 22 | 24 | 6.88 | 17 | 18 |
| qpe_8 | 194 | 2.53 | 23 | 26 | 40 | 12.28 | 14 | 14 |
| qpe_10 | 852 | 1.04 | 27 | 31 | 288 | 3.08 | 24 | 26 |
| qpe_12 | 1,476 | 1.98 | 25 | 32 | 396 | 7.4 | 28 | 28 |
| qpe_14 | 3,471 | 1.88 | 32 | 39 | 1,046 | 6.24 | 29 | 30 |
| qae_11 | 55 | 2.35 | 7 | 19 | 28 | 4.61 | 9 | 15 |
| qae_13 | 78 | 2.44 | 7 | 23 | 42 | 4.52 | 12 | 20 |
| qae_15 | 105 | 2.5 | 7 | 27 | 54 | 4.87 | 10 | 22 |
| qae_17 | 136 | 2.56 | 7 | 31 | 71 | 4.9 | 10 | 26 |
| qae_19 | 171 | 2.6 | 7 | 35 | 90 | 4.94 | 12 | 30 |
| qae_21 | 210 | 2.64 | 7 | 39 | 114 | 4.86 | 12 | 33 |
| heisenberg_3 | 60 | 1.0 | 9 | 9 | 1 | 60.0 | 1 | 1 |
| heisenberg_4 | 90 | 1.0 | 10 | 10 | 50 | 1.8 | 12 | 12 |
| heisenberg_5 | 120 | 1.0 | 11 | 11 | 64 | 1.88 | 15 | 15 |
| heisenberg_6 | 150 | 1.0 | 11 | 11 | 92 | 1.63 | 17 | 17 |
| heisenberg_7 | 180 | 1.0 | 11 | 11 | 108 | 1.67 | 18 | 18 |
| heisenberg_8 | 210 | 1.0 | 11 | 11 | 135 | 1.56 | 16 | 16 |
| tfim_3 | 40 | 1.75 | 8 | 8 | 1 | 70.0 | 1 | 1 |
| tfim_4 | 60 | 1.67 | 9 | 9 | 40 | 2.5 | 9 | 9 |
| tfim_5 | 80 | 1.62 | 9 | 9 | 41 | 3.17 | 8 | 8 |
| tfim_6 | 100 | 1.6 | 9 | 9 | 70 | 2.29 | 11 | 11 |
| tfim_7 | 120 | 1.58 | 9 | 9 | 71 | 2.68 | 10 | 10 |
| tfim_8 | 140 | 1.57 | 9 | 9 | 100 | 2.2 | 11 | 11 |
| hubbard_4 | 32 | 0.38 | 11 | 12 | 10 | 1.2 | 7 | 9 |
| hubbard_8 | 459 | 0.18 | 34 | 50 | 205 | 0.41 | 75 | 103 |
| grover_3 | 10 | 0.0 | 7 | 7 | 1 | 0.0 | 1 | 1 |
| grover_5 | 116 | 1.55 | 8 | 11 | 52 | 3.46 | 7 | 8 |
| qml_4 | 12 | 2.5 | 6 | 9 | 8 | 3.75 | 5 | 8 |
| qml_13 | 140 | 0.84 | 15 | 49 | 77 | 1.53 | 21 | 40 |
| shor_12 | 1,378 | 1.06 | 56 | 125 | 512 | 2.85 | 67 | 99 |
| shor_14 | 2,148 | 1.5 | 54 | 205 | 799 | 4.04 | 64 | 175 |
| mult_8 | 116 | 1.39 | 17 | 29 | 28 | 5.75 | 17 | 18 |
| hhl_8 | 1,364 | 1.82 | 28 | 94 | 60 | 41.4 | 27 | 57 |

Totals over all 45 circuits:

| form | block_size | blocks | structs | unitaries | rot | struct_frac | unitary_frac |
|---|---|---|---|---|---|---|---|
| cliffordrz | 2 | 18,725 | 678 | 1,512 | 30,406 | 0.036 | 0.081 |
| cliffordrz | 3 | 6,606 | 798 | 1,365 | 30,406 | 0.121 | 0.207 |
| u3cx | 2 | 18,725 | 353 | 1,512 | 35,504 | 0.019 | 0.081 |
| u3cx | 3 | 5,674 | 588 | 1,418 | 35,504 | 0.104 | 0.25 |

Reading: 18,725 two-qubit blocks collapse to 678 distinct structures (3.6 %) and 1,512 distinct unitaries
(8.1 %). The 6,606 three-qubit blocks (Clifford+RZ form) collapse to 798 structures (12.1 %). So grouping blocks
by structure cuts the number of distinct items an LLM must see by roughly 28× (2q) and 8× (3q). Caveats:
* QuickPartitioner bounds qubits, not gates. Three-qubit circuits become one block, and hhl_8 / qpe_8 3q-blocks
  hold ~41 / ~12 rotations on average.
* Counts are summed per circuit; structures are not de-duplicated across circuits.

## 4. Issues / caveats
1. bqskit-ft at 4a288ae: `passes =` overwrite (seed and retarget dropped). We prepend `SetRandomSeedPass`
   ourselves and lower Shor before the workflow.
2. `bqskit.compiler.Compiler` needs a localhost socket (blocked). The serial in-process runtime
   (`serial_runtime.py`) runs the same passes. Gridsynth uses a multiprocessing pool.
3. `conda create` failed (conda-forge 502), so the environment is a venv registered as `bqskit-ft`.
4. The QFT-32 match relies on a reconstructed input (d_max chosen to fit). The Shor-16 match relies on a counting
   convention that is not a valid compilation. Neither is a property of the qseed files.
5. Statevector checks are floating point and use 2 random states. They are sanity checks, not the repo's exact verifier.
6. Our own first exact lowering used `1 − |Tr|/2 < 1e-9` as the phase-equality test. That silently treated RZ
   angles below ~9e-5 as identity (it gave 936 RZ on qft_32). It was replaced by a phase-aligned Frobenius distance.
   The lossy run is kept as `explore/bygate_exact_v1.csv`. Do not use it.

## 5. Files
* `table3_bygate.csv`: all Table-3 rows (paper convention, Shor parameter convention, minimal-RZ, bqskit-ft
  shipped × 3 seeds), with published values and % differences.
* `reference_pipelines.csv`: TKET / tket+minrz / pyzx rows.
* `partition/partition_profile.csv`: the block profile.
* Raw per-run CSVs: `table3/`, `reference/`, `explore/` (diagnostics). Derived circuits: `clifford_rz/`, `work/`.
* Re-run: `experiments/bqskit_baselines/run_all_table3.sh`; `run_reference.py --pipeline tket|pyzx`;
  `profile_partitions.py`; `verify_equiv.py`.
