# Error accounting for the stage-1 baseline arms

Total algorithmic error eps in {1e-3, 1e-5}. "Code-accounted bound" = the sum of the per-stage bounds the
code itself enforces (the BQSKit convention: sequential composition, distances add). Each stage uses its own
metric, so the sum mixes metrics; this is stated per term. Every output is additionally checked numerically
against the ORIGINAL qseed circuit (`state_dist_vs_orig`, see bottom).

Metrics that appear:
- **op**: phase-aligned operator norm, min_phi ||U - e^{i phi} V||_2 (gridsynth's guarantee per Rz).
- **round**: `RoundToDiscreteZPass` replaces Rz(theta) by the nearest k*pi/4 gate if the raw angle residual
  r <= threshold; the op-norm error of one such event is 2 sin(r/4) <= r/2.
- **HS**: `DPFPass` accepts a fixed-angle block iff `MatrixDistanceCost` = sqrt(1 - (|Tr(U^dag V)|/d)^2) <
  threshold (d = 2^block_width). This is ~ the phase-aligned normalized Frobenius distance; the op norm can be
  up to sqrt(d) times larger (x4 for 4-qubit blocks, x2.8 for 3-qubit blocks). Sums of HS over blocks bound
  the whole-circuit HS distance; they do not bound the op norm without that factor.

Notation: P = number of parameters (Rz gates) of the TKET input; B = number of 4-qubit blocks from
`ScanPartitioner(4)` (`QuickPartitioner(4)` when > 30 qubits or > 600 ops); B_C = number of 3-qubit blocks of
the CliffordTModel workflow; N_Rz = number of Rz handed to gridsynth.

## B0 TKET + gridsynth, B1 pyzx + gridsynth
Input -> (B1 only: pyzx full_reduce, exact) -> each non-pi/4 Rz gridsynth'd at eps/N_Rz (op).
Bound = N_Rz * eps/N_Rz = **eps** (op), plus the TKET input's exact-arithmetic drift (measured <= 2.2e-13).

## B2 paper "Baseline" (BQSKit-FT retarget + gridsynth, no DPF)
1. `compile(circ, CliffordRZModel(n, epsilon_per_gate = eps/(P+1)))` - same first stage as
   `alg_err_workflow.full_rz_compile`. Rounding threshold eps/(P+1) per event (round). Nominal <= eps/2 if at
   most P+1 rounding events (the ZXZXZ step can create new Rz, so the event count is not strictly bounded by
   the code). Realized: input-vs-Clifford+Rz distance <= 3.4e-14 on all 8 circuits (only exactly-Clifford angles
   were rounded).
2. `GridSynthPass` with `algorithmic_error = eps` -> eps/N_Rz per Rz (op).
Code-accounted bound: **1.5 eps** nominal (realized ~ eps).

## B3 published DPF script `alg_err_workflow.py` (as written, one crash fix)
`__main__`: `rz = full_rz_compile(circ, error=eps)`; `out = compile_rz_to_clifft(rz, success_threshold=eps)`.
The script passes `error` to THREE places and a fourth stage ignores it:
1. CliffordRZModel retarget, epsilon_per_gate = eps/(P+1) (round): nominal <= eps/2.
2. Partition (Scan/Quick, width 4) into B blocks; per block `DPFPass` threshold eps/B (HS) -> **eps** total.
   (The script's `DPFPass(success_threshold=...)` raises TypeError at this commit; we supply the same value
   through PassData, which is what `DPFPass.run` reads. `ConvertFractionalRZPass(max_k=3)` is exact.)
3. `compile_rz_to_clifft`: computes err_per_gate = eps/N_Rz and passes it as `CliffordTModel(err_per_gate=...)`,
   but `CliffordTModel.__init__` never uses `err_per_gate`; its `algorithmic_error` keeps the default **1e-4**
   independent of eps. That workflow (bqskit/ft/cliffordt/defaultworkflow.py at 2e99ba6) then runs:
   multi-qudit retarget (CX already native, so bqskit's `build_multi_qudit_retarget_workflow` runs
   `ScanningGateRemovalPass` over 3-qubit blocks: it deletes CNOTs whenever re-instantiation stays within
   synthesis_epsilon = 1e-8 (HS) per block; this is why B3/B3m/B2ft have fewer CNOTs than the input; adds
   <= #blocks x 1e-8), `QuickPartitioner(3)`, AssignErrors
   1e-4/B_C per block, per block: RoundToDiscreteZ (threshold 1e-4/B_C per event, count not bounded),
   **ZXZXZ re-derivation of every single-qubit run**, RoundToDiscreteZ, **another DPFPass (k=3)** at 1e-4/B_C
   (HS) -> 1e-4 total, ConvertFractionalRZ; finally `GridSynthPass` at 1e-4/N_Rz per Rz (op) -> 1e-4.
Code-accounted bound: eps/2 (round) + eps (HS) + 1e-4 (HS) + 1e-4 (op) + stage-3 rounding
= **1.5 eps + 2e-4** (+ unbounded-count rounding): 1.7e-3 at eps = 1e-3 (1.7x), **2.15e-4 at eps = 1e-5 (21.5x)**.
Consequences: at eps = 1e-3 gridsynth runs 10x tighter than needed (costs ~ +10 T per rotation); at eps = 1e-5 it
runs 10x looser than B0-B2 (saves ~ 10 T per rotation) and the measured error can exceed 1e-5
(heisenberg_6: 1.3e-5). B3's T-counts at the two eps are therefore nearly identical. The ZXZXZ step raises the
rotation count (over both passes: qpe_8 126-134 -> 538-588 Rz, hhl_8 280-320 -> 1107-1266), which dominates B3's T-count.

## Supplementary arms (not part of B0-B3)
- **B2ft** branch default `compile(circ, CliffordTModel(n, algorithmic_error=eps))`: AssignErrors eps/B_C, per
  block rounding + ZXZXZ + DPF(k=3) at eps/B_C (HS) -> eps, GridSynthPass eps/N_Rz (op) -> eps.
  Bound **2 eps** + rounding.
- **B3m** budget-matched script: `full_rz_compile(error=0.4 eps)` and `CliffordTModel(algorithmic_error=0.2 eps)`:
  0.2 eps (round) + 0.4 eps (HS) + 0.2 eps (HS) + 0.2 eps (op) = **1.0 eps** + stage-3 rounding.
- **B3g** DPF then direct gridsynth: `full_rz_compile(error=0.4 eps)` then `GridSynthPass(algorithmic_error=0.4 eps)`,
  skipping the second CliffordTModel compile: 0.2 eps (round) + 0.4 eps (HS) + 0.4 eps (op) = **1.0 eps**.

## Numerical check (all arms, all circuits <= 13 qubits)
`state_dist_vs_orig` = max over 2 Haar-random input states of min_phi ||U_orig psi - e^{i phi} U_out psi||
(qiskit Statevector, direct norm, floor ~1e-14). It estimates the normalized-Frobenius distance and is a LOWER
bound on the op-norm distance; it is not a proof of the bound. Observed: every B0/B1/B2/B3g/B2ft/B3m output is
below its eps; B3 at eps = 1e-5 is not always (see stage1 tables).

## Gridsynth tool
All arms use rsgridsynth v1.0.0 as-run (what bqskit-ft GridSynthPass calls). rsgridsynth is not a pure
function of (theta, eps) (call-history dependent; occasional panics, resolved by re-running the identical call
in a fresh process). The `t_count_canon` columns re-lower every arm's exact pre-gridsynth circuit with
pygridsynth 2.0.0 (deterministic) at the same per-Rz precision; bounds are unchanged by the recount.
