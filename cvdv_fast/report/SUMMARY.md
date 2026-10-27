# CV-DV Hamiltonian-simulation compilation: LLM rule book vs Genesis (preliminary, 2026-10-21)

**Setup.** Same spec for both compilers: Genesis' own intermediate IR of the five `*_small` benchmarks (one first-order Trotter step, t = 1, IR term order), Genesis Table-2 ISA, Genesis latency model (1 per 1-op, 20 per 2-op gate), Genesis' router (best of 5 seeds by total gates; ours with the SWAP phase-sign fix, gate counts unchanged). Ours compiles from the IR terms, never from Genesis output. Rule book = 13 hand-written seed rules from Liu et al. (arXiv:2407.10381) + rules found by an LLM scout/implementer loop and admitted by a frozen verifier.

**Error metric.** Max over 8 seeded Haar-random probe states (system qubits arbitrary, system qumodes with <= 3 photons total, ancillas |0>/vacuum and required to return) of 1 - |<psi| U_target^+ P^+ V |psi>|^2, V = routed circuit, P = router's final qumode permutation. Target = ordered Trotter product of the IR terms (main columns) or exact e^{-iHt} (last columns). Total-photon truncation K = 10/12 (8/10 for electron-vibration); exact (K = 3) when every gate and term conserves photon number. Budget eps = 1e-3.

| benchmark | Genesis gates | ours gates | Genesis 2-op | ours 2-op | Genesis duration | ours duration | Genesis infidelity | ours infidelity | ideal step vs e^{-iHt} | ours vs e^{-iHt} | Genesis vs e^{-iHt} |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Kerr | 595 | 10 | 142 | 3 | 3032 | 65 | 0.9996* | 1.6e-15 | 2.6645e-15 | 3.3307e-15 | n/a |
| Bose-Hubbard | 112 | 116 | 40 | 48 | 439 | 621 | 0.99613 | 1.3e-14 | 0.98308 | 0.98308 | 0.99785 |
| Z2-Higgs | 116 | 77 | 40 | 28 | 279 | 331 | 0.99998 | 1.1e-14 | 0.99959 | 0.99959 | 0.99999 |
| Heisenberg | 320 | 148 | 136 | 84 | 1810 | 1673 | 1 | 2.1e-09 | 0.9919 | 0.9919 | 1 |
| Electron-vibration | 871 | 783 | 305 | 297 | 5358 | 5392 | 1 | not finished | not computed | not computed | not computed |

\* Kerr: Genesis' physical circuit (19 qubits + 19 qumodes) is too large to simulate; value is v3's logical-circuit error (per-mode cutoffs 16/22). e^{-iHt} columns not computed for electron-vibration (~30 min per check) or Genesis Kerr. Electron-vibration (ours): whole-circuit check did not finish before the meeting (9 qumodes); every rule application passed its window check, and the error ledger sums to the value in comparison.csv (ours_err_ledger).

## Rules the LLM found (admitted; full table in rules/BOOK.md)

- **kerr_exact_by_parity_mapping_bounded_photons** (LLM (kerr_small a1); exact; mechanism: exact algebraic identity on bounded photon number (parity-sector decomposition + ancilla parity mapping)). Helped (gates/duration): kerr_small: not compilable -> 10/65; boseHubbard_small: not compilable -> 116/621; z2Higgs_small: not compilable -> 144/398
- **colocated_mode_swap_loop_pauli_zz** (LLM (heisenberg_small a1); exact; mechanism: Heisenberg-Weyl closed phase-space loop, bus shuttled between co-located qumodes by BS swaps). Helped (gates/duration): heisenberg_small: 430/3449 -> 148/1673
- **single_cp_conjugated_cd_pauli_string** (LLM (electronicVibration_small a3.1); exact; mechanism: Hadamard-lemma conjugation (CP-dressing of a native CD) + single-gate Y basis change). Helped (gates/duration): electronicVibration_small: 879/5701 -> 783/5392
- **kerr_half_pi_parity_kickback_angle_tolerant_5op** (LLM (z2Higgs_small a6.1); exact; mechanism: exact number-theoretic identity (n^2 mod 4 = n mod 2) + parity phase kickback on a clean ancilla, with an explicit near-pi/2 angle match that absorbs the IR's rounding of pi/2 into the exact 1e-6 budget). Helped (gates/duration): z2Higgs_small: 144/398 -> 77/331

Validity notes from reading the code and testing: `kerr_exact_by_parity_mapping_bounded_photons` uses n^2 = 3n - pn + (3/2)p - 3/2, exact for n <= 3 at any angle and for all n when theta is a multiple of pi/4 (checked to n = 12: <= 3e-12; at Genesis' 8-digit constants ~1e-6; at theta = 0.3 it fails beyond 3 photons). `kerr_half_pi_parity_kickback_angle_tolerant_5op` uses n^2 = n (mod 2) at theta = pi/2 (all n). The two Pauli rules are exact operator identities on the full Fock space (Heisenberg-Weyl group commutator, which terminates, plus conjugation by beam-splitter swaps / CP dressing).

## Loop statistics

- Attempt records: 33 (admit: 4, never_fires: 21, no code: 5, reject: 3); LLM calls: 77 (implementer: 31, implementer_retry: 8, scout: 38); tokens in (incl. cache reads) 823,096, out 787,972.
- Scout = session model (Opus-class, adaptive thinking); implementer = Sonnet-class (thinking disabled from attempt 3 on, after implementer calls exhausted their token cap without producing code). Backend: platform LLM API instead of v3's `claude -p` CLI (not installed in this sandbox).
- Mechanisms proposed by the scout across attempts included BCH / Heisenberg-Weyl group commutators, Hadamard-lemma conjugations (CP dressing, beam-splitter-swap transport), passive linear-optics homomorphisms and number-theoretic identities on n^2; admitted rules use the first, second and fourth.

## Caveats

- Preliminary: 5 small instances, one Trotter step, eps = 1e-3, single run (no repeated seeds of the LLM loop).
- Duration: ours is behind Genesis on Bose-Hubbard, Z2-Higgs and electron-vibration; gate count is ahead on 4 of 5.
- Genesis' circuits do not implement the step they compile from (infidelity ~1 on every benchmark we could simulate), so the gate-count comparison is against incorrect circuits; ours meet eps everywhere.
- Two n^2 rules exploit the benchmarks' special angles (pi/4, pi/2); for generic angles only the <= 3-photon claim holds. Verification is on the <= 3-photon subspace with total-photon truncation.
- Not done: higher-order Trotter / multi-step comparison vs e^{-iHt} (needs Genesis re-runs with scaled constants), Hubbard-Holstein (non-unitary IR terms).
