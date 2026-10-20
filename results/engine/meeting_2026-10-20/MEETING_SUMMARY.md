# CircuitEvolve: group-meeting summary (2026-10-20)

All numbers come from committed result files; no new computation was run for this summary.
Tables: table_reconstruction.csv, table_angle.csv. Sample LLM calls: SAMPLE_PROMPTS.md.

## Headline

| | Reconstruction method (recon_campaign1) | Angle method (angle_campaign1, paused) |
|---|---|---|
| What the LLM proposes | a whole-circuit compilation PLAN (pairings, temporary-AND, MCX ladders) for Toffoli-level circuits | replacement gates for ONE window (<= 4 qubits, <= 40 gates) of a TKET-optimized Clifford+Rz circuit |
| Circuits evaluated | 14 (5 trained on, 9 never trained on) | 5 DEV x 3 arms; held-out not reached |
| vs the deterministic, no-LLM comparator | beats the deterministic planner on 8/14, matches 6/14; 6 of the 8 wins on never-trained circuits (to -56%) | +0 T on 3/5 circuits, -2 T on qft_8 (-0.1%), -147 T on hhl_8 (-0.46%) on top of the G1 pass |
| vs best external baseline (pyzx / BQSKit-FT) | lower T than pyzx (exact) on all 10 circuits where pyzx was computed; NOTE relaxed contract (ancillas + measurement) vs exact | never better than the best of pyzx / BQSKit-FT DPF; pyzx (qft_8) and BQSKit DPF+gridsynth variant (hhl_8) stay ahead |
| Learned rules (fig2) | 10 seeds + 87 reflector-written; **15 promoted** by A/B test (13 reflector, 2 seeds) | 10 seeds + 12 inherited + 27 reflector-written; **0 promoted** (single active rule R3 predates the campaign) |
| Playbook effect | frozen playbook transferred (6/9 never-trained circuits beat the planner) | arms A (playbook) = B (placebo) = C (none) on all 4 circuits run in all arms |
| Graduated into deterministic code | G2 AND-preserving pairing: reproduces the LLM's rc_adder_6 (24 T) and mod_red_21 (44 T) with zero LLM calls | (G1 same-Pauli merge, from an earlier seed rule: -10..-15% vs B0 on merge-rich circuits; deterministic) |

## Reconstruction: per-circuit T (relaxed contract unless noted)

| circuit | split | naive_T | B0_tket | B1_pyzx | control_exact | control_relaxed | llm_relaxed |
|---|---|---|---|---|---|---|---|
| cuccaro_4 | dev | 56 | 48 | 32 | 32 | 16 | 16 |
| cuccaro_8 | dev | 112 | 96 | 64 | 64 | 32 | 32 |
| barenco_tof_5 | dev | 84 | 72 | 40 | 40 | 36 | 16 |
| tof_5 | dev | 49 | 43 | 31 | 31 | 16 | 16 |
| rc_adder_6 | dev | 77 | 59 | 47 | 47 | 40 | 24 |
| cuccaro_16 | held-out | 224 | 192 | 128 | 128 | 64 | 64 |
| adder_8 | held-out | 399 | 361 | 173 | 173 | 180 | 160 |
| barenco_tof_10 | held-out | 224 | 192 | 100 | 100 | 96 | 96 |
| mod_adder_1024 | held-out | 1995 | 1711 | 1011 | 1011 | 660 | 628 |
| gf2^4_mult | held-out | 112 | 96 | 68 | 68 | 64 | 36 |
| ham15-med | reserved | 574 |  |  | 212 | 220 | 208 |
| gf2^6_mult | reserved | 252 |  |  | 150 | 144 | 144 |
| hwb6 | reserved | 105 |  |  | 75 | 56 | 52 |
| mod_red_21 | reserved | 119 |  |  | 73 | 56 | 44 |

## Angle: per-circuit T at eps = 1e-3 (unitary-preserving, approximate)

| circuit | split | B0_tket | B1_pyzx | B2_bqskit_ft | B3_bqskit_dpf_published | B3g_bqskit_dpf_gridsynth | G1_pass | llm_arm_A | llm_arm_B | llm_arm_C |
|---|---|---|---|---|---|---|---|---|---|---|
| qft_8 | dev | 2391 | 1577 | 2391 | 2226 | 2029 | 2115 | 2113 | 2113 | 2113 |
| heisenberg_6 | dev | 8200 | 8200 | 8200 | 10128 | 8600 | 8200 | 8200 | 8200 | 8200 |
| hubbard_8 | dev | 4312 | 4312 | 4312 | 7588 | 4712 | 4312 | 4312 | 4312 | 4312 |
| qml_13 | dev | 6326 | 6326 | 6326 | 7668 | 6790 | 6326 | 6326 | 6326 | 6326 |
| hhl_8 | dev | 35450 | 29205 | 35450 | 93637 | 19443 | 31762 | 31615 |  |  |
| qpe_8 | held-out | 14761 | 11485 | 14761 | 39565 | 8020 | 12597 |  |  |  |
| qae_13 | held-out | 7821 | 4527 | 7821 | 7516 | 6909 | 6683 |  |  |  |
| tfim_6 | held-out | 8560 | 8560 | 8560 | 12990 | 9600 | 8560 |  |  |  |

Columns: B0 = TKET FullPeephole + gridsynth; B1 = pyzx full_reduce; B2 = BQSKit-FT CliffordRZ baseline (paper's "Baseline", no DPF);
B3 = published BQSKit-FT DPF workflow as written; B3g = supplementary DPF + gridsynth variant (budget-valid). Blank LLM cells:
not run (campaign paused on 2026-10-20; held-out cells were cut short by a plan usage limit and are recorded invalid).

## Honest assessment

1. **Reconstruction showed real promise; angle did not.** Reconstruction works in a discrete, structural space (which
   Toffolis pair up, which become temporary-ANDs, whether 12 Toffolis are really one C5X). The deterministic planner
   leaves real headroom there, the exact verifier can certify an idea in one shot, and good ideas generalize. The
   playbook learned 15 rules that survived A/B testing, transferred frozen, and one discovery became exact code (G2).
2. **Why the angle tricks did not work:**
   - *No local headroom.* Inputs are already TKET FullPeephole-optimized; a <= 4-qubit, <= 40-gate window rarely holds a
     local improvement TKET missed. The gains that exist on these circuits (pyzx on qft_8, BQSKit's DPF variant on
     hhl_8 / qpe_8) are **global** phase-polynomial / rotation-merging effects that span many windows.
   - *The cost is mostly rotation synthesis.* Each non-Clifford Rz costs about 3 log2(1/eps_rz) T after gridsynth, so the only
     levers are deleting, merging or snapping rotations. An arbitrary angle cannot be removed exactly, and approximate
     snaps cost far more than the per-window error allowance (smoke test: snaps 80x over allowance).
   - *The model knew it.* Most calls on TKET-saturated circuits answered NONE (declined), which the verifier
     data says was correct: nothing local was available.
   - *The learning signal was nearly empty.* With almost no accepted improvements, the A/B gate had nothing to
     promote; all 10 seed rules and the reflector's additions retired.
3. **"The LLM knows BQSKit's algorithms, so it should at least land on them."** Knowing an algorithm is not executing
   it. BQSKit's partition-and-resynthesize is numerical: it instantiates parametrized circuits by gradient optimization
   over thousands of unitary evaluations per block, and DPF fixes phases with error-budgeted arithmetic. Our harness asks
   the LLM to emit the replacement gates directly, by reasoning in text, for one window; it cannot run that optimizer in
   its head. The LLM-as-proposer design never gave it the program. Two calibrating facts: (a) on these circuits BQSKit's
   own primary baseline (B2) equals TKET (B0) exactly, and the published DPF workflow (B3) is WORSE than B0 on 6/8; G1 + LLM is
   at or below B2 on every circuit run, so we did "land on" BQSKit's primary baseline (but that is the G1 pass, not the
   LLM). (b) The strong numbers (pyzx, B3g) come from global, programmatic methods.
4. **What to conclude.** The LLM adds value where the search space is structural and the deterministic tool is
   incomplete (reconstruction); it adds little where a mature local optimizer has already saturated the space and the
   remaining gains are global and numerical (angle windows). The productive path for the angle side is to have the LLM
   propose *passes / programs* (the G1 story: an idea, graduated into code, gives -10..-15%) or work on a global
   representation (phase polynomial / Pauli-rotation list), not window rewrites.

## Caveats to state on the slide

- Reconstruction numbers are RELAXED-contract (clean ancillas + mid-circuit measurement allowed, every branch verified
  exactly); pyzx/TKET are exact. Do not present relaxed-vs-exact as like-for-like.
- Single seed per circuit; no variance estimates. Angle campaign incomplete: held-out not evaluated, so its transfer
  question is open (null on DEV).
- Mixed-circuit cascade numbers (fig5) are from the ZERO-LLM demo; no LLM cascade run exists.
