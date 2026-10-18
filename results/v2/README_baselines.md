# v2 baselines for the NEW benchmark circuits (Benchmarks track, 2026-10-14)

Scope: the 37 new circuits of `benchmarks/nam_arith/` (34 Nam et al. 2018 / T-par circuits + cuccaro_4/8/16).
The qseed circuits (incl. shor_12/14/16, listed in the manifest by reference) are NOT recomputed; their baselines
stay in `results/bqskit_baselines/` (see "Reused baselines" below).

## Files

| file | content |
|---|---|
| `baselines_new.csv` | schema `circuit, source, arm, eps, t_count, qubits, notes`; one row per circuit x arm (our runs, the authors' files, published tables, TRbO QFTAdd rows) |
| `baselines_new_detail.csv` | our runs only: CNOT / gate counts, pi/4-only T, verification method / distance / QCEC verdict, runtime |
| `baselines_new_summary.md` | pivot table of T-counts per circuit |
| `baselines_consistency.json` | provenance checks, planted-bug controls, published-vs-ours comparisons, open problems |
| `published_arith.csv` | transcription of Nam et al. 2018 Table 4 and Kissinger & van de Wetering Table 1 (page/table cited per row) |
| `rotations_gridsynth_run2_eps0.001.json` | BQSKit-convention costing of TKET outputs that kept non-pi/4 rotations |
| `cards_worked_examples.json` | numbers quoted in `docs/v2/cards/` |
| `bench_runs/run2/` | per-circuit JSON + optimized circuits (`circuits/<name>__<arm>.qasm`) - the run used in the CSVs |
| `bench_runs/run3_large/` | gf2^16_mult (6 sparse trials for n > 40); gf2^32_mult stopped (see below) |
| `bench_runs/run1/`, `bench_runs/smoke/` | first pass without QCEC and without saved circuits (superseded by run2; kept, append-only). run1 left 9 TKET-row checks undecided (sparse support cap) - run2 decides them with QCEC |

Code: `experiments/v2_bench_{common,baselines,run_all,manifest,published,gridsynth,report,cards_check,qcec_worker}.py`.
Reproduce: `v2_bench_run_all.py results/v2/bench_runs/<tag>` -> `v2_bench_gridsynth.py <run>` ->
`v2_bench_report.py results/v2 results/v2/bench_runs/run2 results/v2/bench_runs/run3_large`.

## Arms (all on the same input; T-counts exact, eps = 0, unless a row says otherwise)

* `given_cliffordt` - the Clifford+T circuit as given (Quartz `nam_circs`, 7 T per CCZ). Equals Nam et al.'s
  "pre-optimization" T for every Table 4 circuit.
* `pyzx_fr` - pyzx 0.10.7 full_reduce -> extract_circuit -> to_basic_gates -> basic_optimization (the project's
  `blocks/classical.pyzx_optimise`), Clifford+T input. Notes also give the reduced-graph T-count (identical in all rows).
* `tket_fpo` / `tket_fpo_logical` - pytket 2.18.5 FullPeepholeOptimise -> replace_implicit_wire_swaps ->
  AutoRebase{CX,H,Rz} -> RemoveRedundancies, on the Clifford+T input / on the logical (ccx) input.
  On 7 circuits TKET with Clifford+T input leaves rotations that are not multiples of pi/4 (12-36 per circuit;
  they cancel to a Clifford+T unitary but are not dyadic individually). Those rows report the BQSKit-convention
  T-count at total eps = 1e-3 (`core/metric.BqskitTMetric`: gridsynth at eps/N_Rz), e.g. vbe_adder_3 62 T + 16
  rotations -> 782 T. With the logical input TKET leaves no such rotations.
* `nam_light_file` / `nam_heavy_file` - the authors' optimized circuits (njross/optimizer), converted from Quipper,
  T counted by us and verified against the logical input.
* `published:*` - table values as printed (eps 0).

## Verification (every optimized circuit vs its input; labels in the CSV notes)

`unitary_dense` (n <= 12, phase-aligned operator distance of full unitaries), `statevector_haar` (13 <= n <= 22),
`sparse_pair_states` (n > 22: 24 random (|x>+|y>)/sqrt2 basis-pair inputs, 6 if n > 40), plus pyzx `zx_identity`
(12 < n <= 40) and MQT QCEC 3.8 (all n; hard-killed subprocess). verified = primary passes, or primary undecided and
QCEC proves equivalence. Planted-bug control per circuit (first T deleted) was rejected for all 36 circuits.

Result: every pyzx / TKET / Nam-Light output is verified. **Exception: Nam et al.'s Heavy output for qcla_mod_7
(235 T) is NOT equivalent to the input** (sparse distance 0.77, QCEC `not_equivalent`; also wrong on clean-ancilla
inputs in 35 of 40 trials). This agrees with Kissinger & van de Wetering Table 1, which marks the previously reported
235 for qcla-mod7 as an error (footnote a). Use 237 (Light, verified) as the Nam reference for qcla_mod_7.

## Cross-checks against the literature

* Our pyzx T-counts equal the "PyZX" column of Kissinger & van de Wetering (arXiv:1903.10477v2 Table 1, p.4) for
  all 28 overlapping circuits (adder_8 173, mod5_4 8, csum_mux_9 84, ham15-high 1019, ...).
* Our counts of the authors' Light/Heavy files equal Nam et al. Table 4 (p.5) for every listed circuit.
* Kissinger & van de Wetering print original T = 589 for qcla-adder10, while the authors' / Quartz file has 238 (=
  Nam Table 4); Feynman's qcla_adder_10.qasm also has 238 T but a different function. Our circuit = the authors'.
* Best published T per circuit is mostly PyZX+TODD (e.g. gf2^n multipliers, mod_mult_55 20, csla_mux_3 45);
  among our arms pyzx is lowest on every circuit; it ties Nam Light everywhere except adder_8 (173 vs 215),
  csla_mux_3 (62 vs 64) and mod5_4 (8 vs 16), where it is lower.

## gf2^32_mult

Baseline not computed: run1 and run2 timed out (5400 s, 7200 s); run3_large (started 00:07:21) had written no arm
output by 01:56 and its driver was stopped at ~01:57 (~110 min) on instruction. Its worker (pid 174) had exited by 01:57:07
(checked: no such process); no gf2^32 output file was written. It is `large_optional` in `MANIFEST.csv` / `split_v2.json`; only Nam Table 4 numbers (7168 -> 4128)
are given. 
## TRbO QFTAdd rows

The TRbO table (arXiv:2603.25101 Table II, via `published_baselines.csv`) reports RZ counts (not T) for QFT-based
adders QFTAdd8..1024 starting from Nam et al.'s optimized circuits. Those circuits are not in this suite (they are in
`njross/optimizer/QFT_and_Adders`, not fetched); the rows are carried with `t_count` empty and the RZ counts in notes.

## Reused baselines (not recomputed)

shor_12/14/16 (qseed): `results/bqskit_baselines/reference_pipelines.csv` has shor_16 rows (tket, tket+minrz, pyzx;
older eps_rz = 1e-9 convention); no shor_12 / shor_14 rows exist in `stage1_baselines_v2.csv`,
`reference_pipelines.csv` or `published_baselines.csv` (only `explore/tket_shor12.csv`, an exploratory file).
