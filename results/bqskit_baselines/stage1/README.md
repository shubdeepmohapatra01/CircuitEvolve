# Stage-1 baselines B0-B3 (no LLM), 2026-10-13

Protocol: skill `bqskit-ft-reference-baseline`. Eight qseed circuits (qft_8, qpe_8, qae_13, heisenberg_6, tfim_6,
hubbard_8, qml_13, hhl_8), total algorithmic error eps in {1e-3, 1e-5}. bqskit-ft branch `algorithmic_error_dpf`
@ 2e99ba614d48970b9afefc0b8c32860c3a3dc9f1; rsgridsynth v1.0.0 built from source (no substitution);
environment in [ENVIRONMENT.md](ENVIRONMENT.md); per-arm error budgets in [ERROR_ACCOUNTING.md](ERROR_ACCOUNTING.md).

## Files

| file | content |
|---|---|
| `inputs/<c>_tket.qasm` | **the shared input** for every arm (and for the Core track): TKET FullPeepholeOptimise -> explicit wire swaps -> {CX, H, Rz} -> RemoveRedundancies. `inputs_manifest.csv`: counts, timing. Distance to the original qseed circuit <= 2.2e-13 (re-checked with the direct-norm metric; the manifest's `state_dist_vs_orig` column used an earlier sqrt(2-2|ov|) formula with a ~1e-7 float floor and should be ignored). |
| **`stage1_baselines_v2.csv`** | **authoritative table** (112 rows = 8 circuits x 2 eps x 7 arms). Primary metric `t_count_canon`. |
| `stage1_baselines.csv` | first pass, as-run rsgridsynth T only (kept, append-only; superseded by v2). |
| `ours_vs_paper_context.csv` | our arm/B2 T ratios next to the paper's Fig. 5 DPF-Synth/Baseline readings (context, not like-for-like). |
| `paper_reported.csv` | arXiv:2606.05397 Table I (verbatim) and Fig. 5 (approximate readings). |
| `runs/`, `runs_v2/`, `runs_v2/canonical/` | one JSON per (circuit, arm, eps): stage counts, logged thresholds, timing, distances. |
| `outputs/`, `outputs_v2/` | gzipped QASM: final Clifford+T circuits (`<tag>.qasm.gz`), pre-gridsynth circuits (`_pregs`, `_cliffrz`), canonical re-lowerings (`_canon`). |

Code: `experiments/bqskit_baselines/stage1/` (`make_inputs.py`, `run_b0_b1.py`, `run_bqskit_arms.py`,
`canonical.py`, `collect.py`, `collect_v2.py`, `u12rz_shim.py`, `vendor/alg_err_workflow.py`), venv `.venv-dpf`.

## Arms
- **B0** TKET input + gridsynth at eps/N_Rz. **B1** pyzx full_reduce of the same input + gridsynth at eps/N_Rz.
- **B2** paper "Baseline": BQSKit-FT CliffordRZ retarget (eps/(P+1) per parameter) + GridSynthPass at eps/N_Rz.
- **B3** published `alg_err_workflow.py` (DPF with k = 3), run as written apart from a crash fix
  (`DPFPass(success_threshold=...)` is not accepted at this commit; same value supplied via PassData).
- Supplementary, clearly not B0-B3: **B2ft** branch-default CliffordTModel compile (itself contains DPF k=3);
  **B3m** script functions with a budget split so the code-accounted total is <= eps; **B3g** script's
  DPF stage at 0.4 eps followed directly by gridsynth at 0.4 eps (drops the script's second CliffordTModel
  compile, which re-derives ZXZXZ angles and adds rotations).
- B4 (full phase kickback, k > 3) is out of scope; the B3 script never uses phase kickback, so no ancillas
  are added by any arm here (0 extra qubits).

## Result (canonical T-count, pygridsynth recount; lower is better)

| circuit | eps | B0 | B1 | B2 | B3 | best B0-B3 | B3g (suppl.) |
|---|---|---|---|---|---|---|---|
| qft_8 | 1e-3 | 2391 | **1577** | 2391 | 2226 | B1 | 2029 |
| qft_8 | 1e-5 | 3299 | **2219** | 3299 | 2297 | B1 | 2866 |
| qpe_8 | 1e-3 | 14761 | **11485** | 14761 | 39565 | B1 | 8020 |
| qpe_8 | 1e-5 | 19853 | **15651** | 19853 | 41604 | B1 | 10391 |
| qae_13 | 1e-3 | 7821 | **4527** | 7821 | 7516 | B1 | 6909 |
| qae_13 | 1e-5 | 11017 | **6361** | 11017 | 7515 | B1 | 9237 |
| heisenberg_6 | 1e-3 | **8200** | **8200** | **8200** | 10128 | B0=B1=B2 | 8600 |
| heisenberg_6 | 1e-5 | 11200 | 11200 | 11200 | **10128**\* | B3\* | 12000 |
| tfim_6 | 1e-3 | **8560** | **8560** | **8560** | 12990 | B0=B1=B2 | 9600 |
| tfim_6 | 1e-5 | **11840** | **11840** | **11840** | 12742 | B0=B1=B2 | 12400 |
| hubbard_8 | 1e-3 | **4312** | **4312** | **4312** | 7588 | B0=B1=B2 | 4712 |
| hubbard_8 | 1e-5 | **6000** | **6000** | **6000** | 6434 | B0=B1=B2 | 6368 |
| qml_13 | 1e-3 | **6326** | **6326** | **6326** | 7668 | B0=B1=B2 | 6790 |
| qml_13 | 1e-5 | 8716 | 8716 | 8716 | **7668**\* | B3\* | 9162 |
| hhl_8 | 1e-3 | 35450 | **29205** | 35450 | 93637 | B1 | 19443 |
| hhl_8 | 1e-5 | 47228 | **38987** | 47228 | 92889 | B1 | 25043 |

\* B3 "wins" at eps = 1e-5 only because its Clifford+T stage synthesizes rotations at a fixed 1e-4 budget
(code-accounted total 2.15e-4 = 21.5 x eps; measured 1.3e-5 > 1e-5 on heisenberg_6). It is not a valid 1e-5
result. All other rows meet their eps in the numerical check.

Key observations
1. B0 = B2 exactly in canonical T: the BQSKit-FT retarget preserves TKET's rotations one-for-one. The paper's
   "Baseline" is therefore equivalent to TKET+gridsynth on these inputs.
2. pyzx (B1) is the best B0-B3 arm on the 4 circuits with dyadic / structured phases (qft, qpe, qae, hhl):
   -18 % to -42 % vs B2. On the Trotter circuits (heisenberg, tfim, hubbard, qml) nothing removes rotations.
3. The published DPF script (B3) is worse than B2 at eps = 1e-3 on 6/8 circuits (up to 2.7x on qpe_8). Cause: its
   second stage (`compile_rz_to_clifft` -> CliffordTModel default workflow) re-runs ZXZXZ on every single-qubit
   run, raising rotations (v2 run: qpe_8 126 -> 560-588, hhl_8 304-317 -> 1252-1266), and it runs at a fixed 1e-4 regardless of eps.
4. The DPF stage itself works: rotations after DPF (both passes) fall qpe_8 257 -> 126-134, hhl_8 583 -> 280-320, qft_8 48 -> 39,
   qae_13 145 -> 119 (no change on the Trotter circuits). B3g, which keeps that stage and gridsynths directly,
   beats every B0-B3 arm on qpe_8 (-30 % / -34 % vs B1 at 1e-3 / 1e-5) and hhl_8 (-33 % / -36 %) at code-accounted total <= eps, but is
   behind pyzx on qft/qae and slightly behind B0/B2 on the Trotter circuits (it pays a 0.4 eps gridsynth budget).
5. The paper's Fig. 5 DPF-Synth/Baseline ratios (QFT 0.42-0.44, QAE 0.28, Ising 0.48, QPE 0.81, ...) are not
   reproduced by the public k = 3 script; they include phase kickback (k > 3) and different circuit sizes (B4,
   out of scope). See `ours_vs_paper_context.csv`.

## Reproducibility caveats
- **rsgridsynth is not a pure function** of (theta, eps): for the same 84 hubbard_8 angles at eps 1e-3 a
  process gives 4312, 4466 or 4472 T depending on its call history; it also panics occasionally ("Invalid
  coefficients for inverse sqrt2 multiplication"), state-dependently (the identical call succeeds in a fresh
  process, which is how the runner resolves it; logged in each JSON). As-run T (`t_count_asrun`) is
  0-3.6 % above canonical. Hence the pygridsynth recount `t_count_canon` (same N_Rz, same per-Rz eps, verified
  circuits in `outputs_v2/*_canon.qasm.gz`) is the comparison metric.
- **BQSKit DPF/instantiation is stochastic** (the script sets no seed): first-pass vs v2 as-run T differ by up to
  +/-14 % for B3 and up to 30 % for B3m/B2ft (column `t_count_asrun_firstpass`). B0, B1, B2 are deterministic.
  Treat single-run B3-type numbers as +/-15 %.
- Missing upstream module `bqskit.passes.rules.u12rz` shimmed (never exercised on these inputs); Compiler replaced
  by an in-process serial compiler (sandbox forbids sockets). See ENVIRONMENT.md.
- Numerical check = 2 Haar-random states per output vs the ORIGINAL qseed circuit (a lower bound on the operator
  distance, not a proof).
- Runtimes (`runtime_s`) are single-process wall times on this machine with up to 8 jobs in parallel; B0/B1
  exclude the shared TKET pre-optimization (0.2-3.6 s, `inputs_manifest.csv`).
