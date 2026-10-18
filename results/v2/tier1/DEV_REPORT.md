# Tier 1 (compilation strategy) - development report, run `dev_v1`

**Verdict (null result for the LLM arm).** On the 16 DEV arithmetic circuits the LLM never produced a verified
plan with lower T-count than the no-LLM control at the same budget (8 compile+verify evaluations each): exact
mode 16/16 equal; relaxed mode 13 equal, 2 worse (mod_mult_55 28 vs 24, rc_adder_6 44 vs 40), and on gf2^6_mult
no valid relaxed plan (the control found 144). The gains that do exist come from the toolbox itself (Gidney temporary
AND, Jones Toffoli, clean compute-only AND), and the deterministic cheapest-route heuristic applies them just as
well: relaxed T-counts are below the best unitary-preserving classical number on 10/16 circuits (cuccaro_4 16 vs 32,
cuccaro_8 32 vs 64, tof_5 16 vs 31, barenco_tof_5 36 vs 40, csla_mux_3 40 vs 45), at the cost of extra qubits and
mid-circuit measurements (cuccaro_8: 26 qubits, 8 measurements). In exact mode neither arm beats pyzx; the published
TODD numbers (Kissinger & van de Wetering 2020) stay 1-29 T lower on 6 circuits.

## Key observations

1. **Exact mode adds nothing over pyzx here.** Relative-phase Toffoli pairs (Maslov) are verified exactly, but after
   the pyzx pass they reach the same T-count as pyzx on the plain logical circuit (e.g. barenco_tof_5: 40 either
   way); pyzx's phase-polynomial merging already captures that saving on these circuits.
2. **Relaxed routes are not uniformly better.** The best relaxed plan is worse than exact pyzx on mod5_4 (16 vs 8)
   and vbe_adder_3 (32 vs 24): measurement-based gadgets split the circuit into segments that the global pass cannot
   merge across. On gf2^n_mult, Jones' 4-T Toffoli everywhere beats pyzx (64 vs 68, 100 vs 115, control 144 vs 150)
   but not the published TODD numbers (52, 86, 122). The best overall number per
   circuit is therefore min(exact, relaxed), and that is not always the relaxed one.
3. **LLM behaviour.** 0/128 replies used the `custom` gate DSL (the model only recombined toolbox routes); 31/128
   resubmitted a plan it had already tried, despite the "do not resubmit" instruction and the visible history; 8 were
   rejected by the plan parser (e.g. element names `all`, `all_unassigned`); 28 were rejected by the verifier, mostly
   `temporary_and` / `clean_and` on a target that is not |0> at that point (e.g. gf2^6_mult T15 on q17, first written
   by a CNOT; the same rejected plan came back 4 times). No LLM call failed at the API level.
4. **Certification.** Results marked `samp` are verified on sampled inputs and/or sampled measurement branches
   (n > 14, or 2^M x inputs > 2^17): strong evidence, not a proof. All n <= 14 exact results and most small relaxed
   results are exhaustive (`cert`).
5. **Qubit overhead is not optimized.** The ancilla pool reuses freed ancillas but nested via-ancilla pairs keep one
   ancilla each (cuccaro_8: +8). Gidney's adder needs about n ancillas; a construction that computes carries directly
   into fresh ancillas (without the Cuccaro data-register writes) would use fewer qubits. That is a toolbox item,
   not something either arm found.

## What this means for the evaluation phase

The held-out run should still include the LLM arm (frozen prompt, `FROZEN.md`) and must report it next to the
control, but on this evidence the expected outcome is LLM = control. Tier-1 improvements more likely come from
new verified routes (ancilla-reusing Gidney adder; Karatsuba-style gf2 multiplication; segment-aware pass that
chooses exact vs relaxed per pair) than from LLM route selection over the current toolbox. Not run: `shor_12`
(rotation-dominated; toolbox v1 has no rotation route; no comparable reused baseline row).

## Files

- `dev_results.csv` (= `dev_v1_dev_results.csv` + tag column): one row per circuit x arm (llm, control,
  control_V1_spec, best_classical) x mode.
- `logs/dev_v1_<circuit>_{llm,control}.jsonl`: every evaluation (LLM: full prompt, reply, token usage, verdict).
- `plans/dev_v1_<circuit>.json`: best plan per arm x mode with metrics; `circuits/dev_v1_<circuit>_<arm>_<mode>.qasm`:
  the verified circuit (OpenQASM 3, gadgets expanded); `summaries/<circuit>.{json,txt}`: recognizer output.
- `dev_v1_run.json`: tokens, timings, per-circuit call outcomes, frozen digest. `FROZEN.md`: prompt/toolbox hashes.
- Code: `circuitevolve/v2/tier1/`, `experiments/v2_tier1_dev.py`, `experiments/v2_tier1_report.py`; tests
  `tests/v2/test_tier1.py`. Design: `docs/v2/TIER1.md`.

The "V1 (spec)" column is empty where the circuit has no clean compute/uncompute pair: V1 then contains no
relaxed route and its result is an exact one (counted under the control's exact column).


Model `claude-sonnet-5` (in-platform host.llm via `make_api_backend`, thinking disabled); 8 LLM calls per circuit; the no-LLM control gets the SAME number of compile+verify evaluations. Split `v2-nam-arith-1`, DEV circuits only (16 run; skipped: shor_12 - rotation-dominated (cp:490, ccp:150, 5 ccx); toolbox v1 has no rotation route and best_classical() has no comparable row; not run).
Tokens: 905,089 input + 58,206 output in 128 calls; wall time 860 s. Frozen verifier digest unchanged (`bc3eac23a403dbc5...`, checked before and after).

Every number below comes from `dev_v1_dev_results.csv` (written by `experiments/v2_tier1_dev.py`) or from the reused baseline files through `circuitevolve.v2.baselines.best_classical(c, eps=0)`. Each candidate was verified against the LOGICAL circuit (ccx-normalized Nam QASM; normalization itself checked against the original QASM, exhaustive for n <= 14, sampled above). `cert` = the check is a proof (exhaustive inputs and branches); `samp` = sampled inputs and/or branches (n > 14 or too many measurement branches), NOT a proof.

Arms: **LLM** = best verified plan from the model; **control** = deterministic route sets V1-V4 x global passes (`circuitevolve/v2/tier1/control.py`) at the same evaluation budget; **V1** = the control restricted to the named heuristic (clean compute/uncompute pairs -> temporary_and, rest 7 T); **best classical** = lowest reused unitary-preserving T-count on record (pyzx / TKET / Nam et al. files / published TODD etc.).

## A. Unitary-preserving (mode `exact`: same qubits, no measurement, no zero-init promise)

| circuit | n | best classical (arm) | pyzx_fr | tket_fpo | control | LLM | LLM - control | LLM - classical | LLM check | LLM routes |
|---|---|---|---|---|---|---|---|---|---|---|
| barenco_tof_3 | 5 | 16 (best_prev_as_reported_by_kvdw2020) | 16 | 24 | 16 | 16 | +0 | +0 | cert | relative_phase_toffoli: 1; toffoli_7T: 2 |
| barenco_tof_4 | 7 | 28 (best_prev_as_reported_by_kvdw2020) | 28 | 44 | 28 | 28 | +0 | +0 | cert | relative_phase_toffoli: 2; toffoli_7T: 4 |
| barenco_tof_5 | 9 | 40 (best_prev_as_reported_by_kvdw2020) | 40 | 64 | 40 | 40 | +0 | +0 | cert | relative_phase_toffoli: 3; toffoli_7T: 6 |
| csla_mux_3 | 15 | 45 (kvdw2020_pyzx_todd) | 62 | - | 62 | 62 | +0 | +17 | samp | toffoli_7T: 10 |
| cuccaro_4 | 10 | 32 (pyzx_fr) | 32 | 48 | 32 | 32 | +0 | +0 | cert | relative_phase_toffoli: 4 |
| cuccaro_8 | 18 | 64 (pyzx_fr) | 64 | 96 | 64 | 64 | +0 | +0 | samp | relative_phase_toffoli: 8 |
| gf2^4_mult | 12 | 52 (kvdw2020_pyzx_todd) | 68 | 96 | 68 | 68 | +0 | +16 | cert | toffoli_7T: 16 |
| gf2^5_mult | 15 | 86 (kvdw2020_pyzx_todd) | 115 | 155 | 115 | 115 | +0 | +29 | samp | toffoli_7T: 25 |
| gf2^6_mult | 18 | 122 (kvdw2020_pyzx_todd) | 150 | 216 | 150 | 150 | +0 | +28 | samp | toffoli_7T: 36 |
| mod5_4 | 5 | 7 (kvdw2020_pyzx_todd) | 8 | 26 | 8 | 8 | +0 | +1 | cert | toffoli_7T: 4 |
| mod_mult_55 | 9 | 20 (kvdw2020_pyzx_todd) | 35 | 45 | 35 | 35 | +0 | +15 | cert | toffoli_7T: 7 |
| rc_adder_6 | 14 | 47 (best_prev_as_reported_by_kvdw2020) | 47 | - | 47 | 47 | +0 | +0 | cert | relative_phase_toffoli: 1; toffoli_7T: 9 |
| tof_3 | 5 | 15 (best_prev_as_reported_by_kvdw2020) | 15 | 19 | 15 | 15 | +0 | +0 | cert | relative_phase_toffoli: 1; toffoli_7T: 1 |
| tof_4 | 7 | 23 (best_prev_as_reported_by_kvdw2020) | 23 | 31 | 23 | 23 | +0 | +0 | cert | barenco_mcx: 1 |
| tof_5 | 9 | 31 (best_prev_as_reported_by_kvdw2020) | 31 | 43 | 31 | 31 | +0 | +0 | cert | barenco_mcx: 1 |
| vbe_adder_3 | 10 | 24 (best_prev_as_reported_by_kvdw2020) | 24 | - | 24 | 24 | +0 | +0 | cert | relative_phase_toffoli: 2; toffoli_7T: 6 |

LLM vs control (exact): better 0, equal 16, worse 0. LLM vs best classical: better 0, equal 10, worse 6.

## B. Relaxed (mode `relaxed`: clean ancillas, measurement + feed-forward, declared zero-init promise)

Not the same contract as table A: the classical column is the best UNITARY-PRESERVING number and is shown only as a reference point; no classical relaxed baseline exists in the reused files, so the control is the relevant comparison.

| circuit | best classical exact | V1 (spec) | control | LLM | LLM - control | LLM qubits / anc / meas | zero-init promise | LLM check | LLM routes |
|---|---|---|---|---|---|---|---|---|---|
| barenco_tof_3 | 16 | - | 12 | 12 | +0 | 7 / 2 / 3 | none | cert | temporary_and(via_ancilla): 1; jones_toffoli: 2 |
| barenco_tof_4 | 28 | - | 24 | 24 | +0 | 10 / 3 / 6 | none | cert | temporary_and(via_ancilla): 2; jones_toffoli: 4 |
| barenco_tof_5 | 40 | - | 36 | 36 | +0 | 13 / 4 / 9 | none | samp | temporary_and(via_ancilla): 3; jones_toffoli: 6 |
| csla_mux_3 | 45 | - | 40 | 40 | +0 | 16 / 1 / 7 | q3 q7 q12 | samp | clean_and: 3; jones_toffoli: 7 |
| cuccaro_4 | 32 | - | 16 | 16 | +0 | 14 / 4 / 4 | none | cert | temporary_and(via_ancilla): 4 |
| cuccaro_8 | 64 | - | 32 | 32 | +0 | 26 / 8 / 8 | none | samp | temporary_and(via_ancilla): 8 |
| gf2^4_mult | 52 | - | 64 | 64 | +0 | 13 / 1 / 16 | none | samp | jones_toffoli: 16 |
| gf2^5_mult | 86 | - | 100 | 100 | +0 | 16 / 1 / 25 | none | samp | jones_toffoli: 25 |
| gf2^6_mult | 122 | - | 144 | - | - | - | none | - |  |
| mod5_4 | 7 | - | 16 | 16 | +0 | 6 / 1 / 4 | none | cert | jones_toffoli: 4 |
| mod_mult_55 | 20 | - | 24 | 28 | +4 | 10 / 1 / 2 | q3 q5 q6 q7 q8 | cert | clean_and: 5; jones_toffoli: 2 |
| rc_adder_6 | 47 | - | 40 | 44 | +4 | 15 / 1 / 9 | none | samp | relative_phase_toffoli: 1; jones_toffoli: 9 |
| tof_3 | 15 | 11 | 8 | 8 | +0 | 6 / 1 / 2 | q4 | cert | temporary_and: 1; jones_toffoli: 1 |
| tof_4 | 23 | 15 | 12 | 12 | +0 | 8 / 1 / 3 | q4 q5 | cert | ancilla_mcx(middle=jones): 1 |
| tof_5 | 31 | 19 | 16 | 16 | +0 | 10 / 1 / 4 | q5 q6 q7 | cert | ancilla_mcx(middle=jones): 1 |
| vbe_adder_3 | 24 | - | 32 | 32 | +0 | 13 / 3 / 8 | none | samp | temporary_and(via_ancilla): 2; jones_toffoli: 6 |

LLM vs control (relaxed): better 0, equal 13, worse 2. Relaxed LLM T vs best classical exact T: lower 10, equal 0, higher 5 (different contracts).

## C. Control: which variant won

| circuit | exact: variant + pass, T | relaxed: variant + pass, T, qubits / meas |
|---|---|---|
| barenco_tof_3 | V1 + pyzx, 16 | V2 + pyzx, 12, 7 / 3 |
| barenco_tof_4 | V1 + pyzx, 28 | V2 + pyzx, 24, 10 / 6 |
| barenco_tof_5 | V1 + pyzx, 40 | V2 + pyzx, 36, 13 / 9 |
| csla_mux_3 | V1 + pyzx, 62 | V2 + pyzx, 40, 16 / 7 |
| cuccaro_4 | V3 + pyzx, 32 | V2 + pyzx, 16, 14 / 4 |
| cuccaro_8 | V1 + pyzx, 64 | V2 + pyzx, 32, 26 / 8 |
| gf2^4_mult | V1 + pyzx, 68 | V2 + pyzx, 64, 13 / 13 |
| gf2^5_mult | V1 + pyzx, 115 | V2 + pyzx, 100, 16 / 21 |
| gf2^6_mult | V1 + pyzx, 150 | V2 + pyzx, 144, 19 / 31 |
| mod5_4 | V1 + pyzx, 8 | V2 + pyzx, 16, 6 / 4 |
| mod_mult_55 | V1 + pyzx, 35 | V2 + pyzx, 24, 11 / 4 |
| rc_adder_6 | V1 + pyzx, 47 | V2 + pyzx, 40, 16 / 10 |
| tof_3 | V4 + pyzx, 15 | V2 + pyzx, 8, 6 / 2 |
| tof_4 | V4 + pyzx, 23 | V2 + pyzx, 12, 8 / 3 |
| tof_5 | V4 + pyzx, 31 | V2 + pyzx, 16, 10 / 4 |
| vbe_adder_3 | V1 + pyzx, 24 | V2 + pyzx, 32, 13 / 8 |

## D. LLM call outcomes

| circuit | calls | verified | plan rejected | verifier rejected | LLM errors | input tok | output tok | LLM-arm wall s |
|---|---|---|---|---|---|---|---|---|
| barenco_tof_3 | 8 | 5 | 0 | 3 | 0 | 51,386 | 2,382 | 141.8 |
| barenco_tof_4 | 8 | 5 | 1 | 2 | 0 | 54,500 | 2,554 | 145.5 |
| barenco_tof_5 | 8 | 6 | 0 | 2 | 0 | 57,860 | 3,363 | 150.0 |
| csla_mux_3 | 8 | 8 | 0 | 0 | 0 | 56,664 | 4,850 | 164.7 |
| cuccaro_4 | 8 | 7 | 0 | 1 | 0 | 56,163 | 2,375 | 155.5 |
| cuccaro_8 | 8 | 7 | 1 | 0 | 0 | 64,801 | 3,204 | 168.6 |
| gf2^4_mult | 8 | 6 | 0 | 2 | 0 | 56,807 | 5,905 | 201.9 |
| gf2^5_mult | 8 | 5 | 1 | 2 | 0 | 61,057 | 6,596 | 198.9 |
| gf2^6_mult | 8 | 2 | 2 | 4 | 0 | 66,115 | 7,624 | 245.5 |
| mod5_4 | 8 | 5 | 0 | 3 | 0 | 49,905 | 2,859 | 178.4 |
| mod_mult_55 | 8 | 3 | 0 | 5 | 0 | 54,894 | 5,027 | 180.1 |
| rc_adder_6 | 8 | 6 | 0 | 2 | 0 | 61,380 | 3,470 | 303.0 |
| tof_3 | 8 | 7 | 1 | 0 | 0 | 50,889 | 1,737 | 91.5 |
| tof_4 | 8 | 8 | 0 | 0 | 0 | 51,962 | 1,653 | 57.5 |
| tof_5 | 8 | 7 | 1 | 0 | 0 | 53,135 | 1,621 | 56.2 |
| vbe_adder_3 | 8 | 5 | 1 | 2 | 0 | 57,571 | 2,986 | 60.9 |
| total | 128 | 92 | 8 | 28 | 0 | | | |
