# recon_campaign1 — DEV report (learning phase)

Proposer claude-opus-5-5 (adaptive thinking), reflector claude-sonnet-5-5; 20 calls/circuit
(18 proposer + 2 reflect), batch 1, seed 0, playbook mutable. Contract: RELAXED column
(frozen v2 relaxed verifier; measurement-based uncompute allowed). Comparators: committed
baselines (results/engine/recon_bench/baselines.csv) and the v2 deterministic control route.

| circuit | naive | B0 tket | B1 pyzx | control exact | control relaxed | LLM (relaxed) | qubits | accepts | vs control |
|---|---|---|---|---|---|---|---|---|---|
| cuccaro_4 | 56 | 48 | 32 | 32 | 16 | **16** | 14 | 6 | MATCH |
| cuccaro_8 | 112 | 96 | 64 | 64 | 32 | **32** | 26 | 1 | MATCH |
| barenco_tof_5 | 84 | 72 | 40 | 40 | 36 | **16** | 13 | 3 | **-20 (-56%)** |
| tof_5 | 49 | 43 | 31 | 31 | 16 | **16** | 10 | 3 | MATCH |
| rc_adder_6 | 77 | 59 | 47 | 47 | 40 | **24** | 20 | 3 | **-16 (-40%)** |

Every accepted plan passed the FROZEN v2 relaxed verifier in-loop; final_check_vs_original
ok on all 5 circuits; ledger charge 0 (exact branch-wise); verifier digest bc3eac23 checked
at loop start/end of every run.

## Winning plans (verbatim from run logs)

- **cuccaro_4**: `{"target": "relaxed", "decisions": [{"element": "P0", "route": "temporary_and", "via_ancilla": true}, {"element": "P1", "route": "temporary_and", "via_ancilla": true}, {"element": "P2", "route": "temporary_and", "via_ancilla": true}, {"element": "P3", "route": "temporary_and", "via_ancilla": true}], "global_pass": "pyzx", "request_cards": [], "rationale": "All four Toffoli pairs 
- **cuccaro_8**: `{"target": "relaxed", "decisions": [{"element": "P0", "route": "temporary_and", "via_ancilla": true}, {"element": "P1", "route": "temporary_and", "via_ancilla": true}, {"element": "P2", "route": "temporary_and", "via_ancilla": true}, {"element": "P3", "route": "temporary_and", "via_ancilla": true}, {"element": "P4", "route": "temporary_and", "via_ancilla": true}, {"element": "P5"
- **barenco_tof_5**: `{"target": "relaxed", "decisions": [{"element": "T6", "route": "custom", "gates": ["h a0", "cx q0, a0", "tdg a0", "cx q1, a0", "t a0", "cx q0, a0", "tdg a0", "cx q1, a0", "t a0", "h a0", "s a0", "h a1", "cx q2, a1", "tdg a1", "cx a0, a1", "t a1", "cx q2, a1", "tdg a1", "cx a0, a1", "t a1", "h a1", "s a1", "h a2", "cx q3, a2", "tdg a2", "cx a1, a2", "t a2", "cx q3, a2", "tdg a
- **tof_5**: `{"target": "relaxed", "decisions": [{"element": "M0", "route": "ancilla_mcx", "middle": "jones"}], "global_pass": "none", "request_cards": [], "rationale": "All three enclosing pairs (P0, P1, P2) are clean pairs on declared-zero targets, so each becomes a direct temporary AND at 4 T. The middle Toffoli T3 writes into data qubit q8, so it uses the Jones construction (4 T, one fresh an
- **rc_adder_6**: `{"target": "relaxed", "decisions": [{"element": "P0", "route": "temporary_and", "via_ancilla": true}, {"element": "T1+T9", "route": "temporary_and", "via_ancilla": true}, {"element": "T2+T8", "route": "temporary_and", "via_ancilla": true}, {"element": "T3+T7", "route": "temporary_and", "via_ancilla": true}, {"element": "T4+T6", "route": "temporary_and", "via_ancilla": true}, {"e

## Playbook outcome (A/B machinery, unchanged settings)

Rules now: 28 (10 seeds + 18 reflector-born R11-R28).

- R1 [retired] origin=seed exposures=40 with 32/34 without 45/45 improvements=7
- R2 [retired] origin=seed exposures=40 with 35/36 without 44/45 improvements=7
- R3 [retired] origin=seed exposures=40 with 34/35 without 28/28 improvements=10
- R4 [active] origin=seed exposures=96 with 6/6 without 2/2 improvements=19
- R5 [retired] origin=seed exposures=40 with 36/36 without 41/43 improvements=10
- R6 [retired] origin=seed exposures=40 with 33/34 without 36/36 improvements=6
- R7 [retired] origin=seed exposures=8 with 8/8 without 6/6 improvements=2
- R8 [retired] origin=seed exposures=40 with 38/38 without 26/27 improvements=9
- R9 [active] origin=seed exposures=73 with 8/8 without 15/15 improvements=12
- R10 [candidate] origin=seed exposures=37 with 34/35 without 49/50 improvements=5
- R11 [retired] origin=reflector exposures=12 with 11/11 without 13/13 improvements=1
- R12 [retired] origin=reflector exposures=2 with 2/2 without 6/6 improvements=0
- R13 [candidate] origin=reflector exposures=36 with 35/36 without 40/41 improvements=3
- R14 [retired] origin=reflector exposures=3 with 1/1 without 7/7 improvements=0
- R15 [candidate] origin=reflector exposures=35 with 33/34 without 26/27 improvements=5
- R16 [retired] origin=reflector exposures=6 with 5/5 without 11/11 improvements=1
- R17 [retired] origin=reflector exposures=4 with 4/4 without 5/5 improvements=1
- R18 [retired] origin=reflector exposures=6 with 4/4 without 11/12 improvements=0
- R19 [retired] origin=reflector exposures=14 with 12/13 without 12/12 improvements=1
- R20 [candidate] origin=reflector exposures=17 with 16/17 without 19/20 improvements=3
- R21 [candidate] origin=reflector exposures=19 with 18/19 without 17/18 improvements=3
- R22 [retired] origin=reflector exposures=5 with 5/5 without 3/3 improvements=0
- R23 [candidate] origin=reflector exposures=15 with 14/15 without 13/13 improvements=3
- R24 [candidate] origin=reflector exposures=7 with 7/7 without 12/13 improvements=0
- R25 [retired] origin=reflector exposures=4 with 4/4 without 4/4 improvements=0
- R26 [candidate] origin=reflector exposures=5 with 5/5 without 5/5 improvements=0
- R27 [retired] origin=reflector exposures=4 with 4/4 without 4/4 improvements=0
- R28 [candidate] origin=reflector exposures=1 with 1/1 without 1/1 improvements=0

Notable: seeds R4 (Maslov RCCX pairing) and R9 (ancilla-vs-T tradeoff) PROMOTED to active;
7 seeds retired on small negative deltas (z_retire -1.0, as configured). The reflector
independently re-derived the floor-check lesson (R11/R14/R15/R17 variants of seed R10's
bound) from metric-rejection evidence, plus genuinely procedural rules: copy multiplicities
from the CURRENT parent (R16/R18/R20/R22/R25), one decision per element type (R23),
verbatim-resubmit check (R24), heavy-type support invariants from verifier counterexamples
(R26/R28), output format discipline (R21).

## Honest caveats

- 2/5 circuits beat the deterministic control (barenco_tof_5 36->16, rc_adder_6 40->24);
  3/5 matched it exactly (the control was already at the 4T/pair relaxed floor there).
- Qubit counts rose where T fell (lexicographic fitness, T first): e.g. barenco_tof_5
  9->13 qubits, rc_adder_6 ->20. The exact-contract column is untouched by this campaign.
- Single seed (0), single run per circuit: no variance estimate; transfer is measured in
  the FROZEN held-out phase, not here.
