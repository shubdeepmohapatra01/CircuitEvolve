# P2 summary (DV only, eps = 0.001) - generated 2026-10-23 18:29

Attempts recorded: 36; LLM calls: 119; total LLM cost: $59.14. Run state: finished.

## Rules admitted (LLM-found; hand-written P1 rules excluded)

| rule | kind | contract | helped (circuit: before -> after T) | attempt | target: est. vs measured T saved | limitation | LLM calls | tokens in / out (cache read) | cost |
|---|---|---|---|---|---|---|---|---|---|
| and_ancilla_ccz_lowering_with_measured_uncompute | reconstruction | relaxed | adder_8: 399 -> 216; adder_6: 77 -> 44; mult_4: 112 -> 64; mcx_10: 224 -> 128; modred_21: 119 -> 68 | adder_8 a1 | 240 vs 183 | 216 T is 54 AND computes at 4 T each, so 57 ccz gates collapsed into only 54 runs. The card expected about 39. The ccz gates on adder_8 almost never share a control pair, because the carry controls change from gate to gate. Only a few adjacent gates merge, so the saving is close to the no-sharing floor of 171 T. | 5 | 42 / 19448 (433735) | $1.09 |
| bilinear_rank_resynthesis_karatsuba | reconstruction | relaxed | mult_4: 64 -> 36 | mult_4 a1 | 28 vs 28 | - | 2 | 22 / 30629 (260562) | $0.91 |
| free_fermion_gaussian_resynthesis | procedure | approx | tfim_6: 8560 -> 3354 | tfim_6 a1 | 4500 vs 5206 | - | 4 | 50 / 45959 (761278) | $1.52 |
| pauli_exponential_commutation_merge | procedure | exact | hhl_8: 29331 -> 29205 | qpe_8 a2 | 2200 vs ? | - | 4 | 36 / 32196 (422989) | $1.66 |
| pauli_frame_rotation_merge | procedure | exact | qft_8: 2125 -> 1577; qpe_8: 14569 -> 11485; hhl_8: 34266 -> 29331; qae_13: 6725 -> 4527 | hhl_8 a1 | 4200 vs 4935 | - | 2 | 12 / 9715 (87340) | $0.45 |
| pauli_subalgebra_dimension_recompression | procedure | approx | hhl_8: 29029 -> 28509 | hhl_8 a3 | 6500 vs 520 | - | 3 | 6 / 16786 (55620) | $0.97 |

## Per circuit: ours vs best baseline

| circuit | P2 status | attempts used / budget | admitted here | best baseline | ours T | vs best | ours qubits | relaxed | certified |
|---|---|---|---|---|---|---|---|---|---|
| qft_8 | done | 3 / 3 | - | pyzx 1577 | 1583 | +0.4% | 8 | no | yes |
| qpe_8 | done | 5 / 5 | phase_polynomial_rotation_merge (retired), pauli_exponential_commutation_merge | BQSKit-DPF 8020 | 11485 | +43.2% | 8 | no | yes |
| hhl_8 | done | 5 / 5 | pauli_frame_rotation_merge, rotation_count_minimal_block_refit (retired), pauli_subalgebra_dimension_recompression | BQSKit-DPF 19443 | 28509 | +46.6% | 8 | no | yes |
| qae_13 | done | 3 / 3 | - | pyzx 4527 | 4526 | -0.0% | 13 | no | no: sampled check, not a proof |
| tfim_6 | done | 2 / 2 | free_fermion_gaussian_resynthesis | TKET 8560 | 3354 | -60.8% | 6 | no | yes |
| adder_8 | done | 4 / 4 | and_ancilla_ccz_lowering_with_measured_uncompute | pyzx 173 | 216 | +24.9% | 25 | yes | no: sampled check, not a proof |
| adder_6 | done | 3 / 3 | - | pyzx 47 | 44 | -6.4% | 15 | yes | no: sampled check, not a proof |
| mult_4 | done | 4 / 4 | bilinear_rank_resynthesis_karatsuba | pyzx 68 | 36 | -47.1% | 13 | yes | no: sampled check, not a proof |
| mcx_10 | done | 4 / 4 | - | pyzx 100 | 128 | +28.0% | 20 | yes | no: sampled check, not a proof |
| modred_21 | done | 3 / 3 | - | pyzx 73 | 68 | -6.8% | 12 | yes | no: sampled check, not a proof |

**Not run** (zero P2 attempts): none.

## Reference row (NOT ours): hand-written P1 same-Pauli merge, eps 1e-3

| circuit | before -> after T | applications |
|---|---|---|
| qft_8 | 2391 -> 1583 | 19 |
| qpe_8 | 14761 -> 11485 | 67 |
| hhl_8 | 35450 -> 29331 | 131 |
| qae_13 | 7821 -> 4527 | 67 |

## Retired (superseded)

- phase_polynomial_rotation_merge replaced by pauli_frame_rotation_merge
- rotation_count_minimal_block_refit replaced by pauli_subalgebra_dimension_recompression

## Attempt outcomes

admit: 8, never_fires: 13, reject: 13, scout_failed: 2

## Caveats

- eps 1e-3 only; DV only (CV-DV deferred). Baselines from v3/baselines/baselines.csv (frozen).
- Verification: every rule application checked exactly on its changed window (Clifford+T: D[omega]; continuous angles: dense operator norm), plus one whole-circuit check per rule pass against the original. Checks are sampled, not proofs (column 'certified') when: the circuit has more than 2^14 basis inputs (mcx_10, adder_8); a numerical check is on 11-20 qubits (qae_13); or a relaxed (measurement) result has more measurement branches than are enumerated (method 'branchwise-exhaustive+sampled-branches': every basis input, sampled branches; adder_6, mult_4, modred_21).
- Admission: full DV suite at eps 1e-3, 300 s per circuit (SPEC default 120 s; raised by user decision).
- BQSKit-FT / BQSKit-DPF on reconstruction start from the Nam Clifford+T files (they leave ccx undecomposed) and return the input T-count unchanged.
- Relaxed results (clean ancillas / measurement) are hatched in the figures and never counted as unitary-preserving.

Figures: report/figures/p2_dv_angle_tcount.png, p2_dv_recon_tcount.png, p2_dv_qubits.png (+ CSVs).
