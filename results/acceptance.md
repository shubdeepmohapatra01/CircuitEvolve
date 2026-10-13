# Verifier acceptance report

Generated 2026-10-06 13:43. Correct: **21/21** (gate: all).

| case | planted behaviour | expected | verifier | correct | s |
|---|---|---|---|---|---|
| cuccaro | naive ripple-carry adder | accept | accept | yes | 0.0 |
| gidney_tierA | temporary-AND adder, gadget form | accept | accept | yes | 0.1 |
| gidney_tierB | temporary-AND adder, primitives | accept | accept | yes | 0.1 |
| gidney_global_phase | global phase -1 inserted (unobservable; must be accepted) | accept | accept | yes | 0.1 |
| pyzx_cuccaro | pyzx full_reduce output (dense; small n only) | accept | accept | yes | 2.6 |
| wrong_carry_wiring | first MAJ targets the wrong qubit | reject @ L1 | reject @ L1 (n=1) | yes | 0.0 |
| ancilla_left_dirty | one carry ancilla never uncomputed | reject @ L1 | reject @ L1 (n=2) | yes | 0.0 |
| missing_cz_correction | measurement-based uncompute without the CZ fix-up | reject @ L2 | reject @ L2 (n=2) | yes | 0.0 |
| unconditional_cz | CZ fix-up applied on both branches | reject @ L2 | reject @ L2 (n=2) | yes | 0.0 |
| cz_wrong_qubits | CZ fix-up on the wrong pair of qubits | reject @ L2 | reject @ L2 (n=2) | yes | 0.0 |
| z_instead_of_cz | single-qubit Z instead of CZ in the fix-up | reject @ L2 | reject @ L2 (n=2) | yes | 0.0 |
| missing_ancilla_reset | measured ancilla not reset to |0> on outcome 1 | reject @ L1 | reject @ L1 (n=2) | yes | 0.0 |
| relative_phase_bug | correct on basis states, wrong relative phase (T on a_0) | reject @ L2 | reject @ L2 (n=1) | yes | 0.0 |
| measures_data_qubit | measures a data qubit (collapses superpositions) | reject @ L2 | reject @ L2 (n=1) | yes | 0.0 |
| dirty_target_assumed_clean | and_compute into a data qubit (n >= 2) | reject @ L1 | reject @ L1 (n=2) | yes | 0.0 |
| uncompute_precondition | and_uncompute while t != a·b | reject @ L1 | reject @ L1 (n=3) | yes | 0.0 |
| sum_into_wrong_register | sum written into a instead of b | reject @ L1 | reject @ L1 (n=1) | yes | 0.0 |
| missing_carry_out | carry-out never written | reject @ L1 | reject @ L1 (n=1) | yes | 0.0 |
| correct_only_even_n | top sum bit dropped for odd n | reject @ L1 | reject @ L1 (n=1) | yes | 0.0 |
| bug_only_n_ge_6 | carry propagation broken at bit 5 (caught only by sampled n = 6) | reject @ L1 | reject @ L1 (n=6) | yes | 0.0 |
| gadget_outside_vocab | tier-B candidate uses a tier-A gadget | reject @ L0 | reject @ L0 (n=1) | yes | 0.0 |
