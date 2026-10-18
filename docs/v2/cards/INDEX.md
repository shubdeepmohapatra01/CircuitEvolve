# Technique cards (v2) - index

Short, cited summaries the tier-1 / tier-2 LLM prompts can include. Each card: what it does, the circuit pattern
it applies to, T / ancilla / measurement cost, the verification mode it needs, a worked example whose numbers come
from a run (`results/v2/cards_worked_examples.json`, `results/v2/bench_runs/`) or from `benchmarks/nam_arith/MANIFEST.csv`,
and a citation checked against arXiv / Crossref metadata (`CITATIONS.md`).

Verification modes: **exact** = unitary-preserving (D[omega] / dense unitary / QCEC); **relaxed** = specification
contract with ancilla preconditions and/or measurements (`circuitevolve/verify.py`, invariant 2); **approximate** =
within an eps budget (`blocks/verify_block.py`, error ledger).

| # | card | pattern | T cost (vs 7 T Toffoli) | ancilla / meas. | verification |
|---|---|---|---|---|---|
| 01 | [Gidney temporary AND adder](01_gidney_temporary_and.md) | Toffoli compute/uncompute pair onto a fresh ancilla; adders | 4 T per AND, 0 T uncompute; adder 4n+O(1) | clean ancilla per AND; 1 X-meas. + CZ fix-up | relaxed |
| 02 | [Jones 4-T Toffoli](02_jones_toffoli_measurement.md) | in-place Toffoli, one clean ancilla available | 4 T | 1 ancilla, 1 meas. | relaxed |
| 03 | [Relative-phase Toffoli (Maslov)](03_relative_phase_toffoli.md) | Toffoli later undone, middle commutes with the diagonal | RCCX 4 T, RC3X 8 T | none | exact (as a pair) |
| 04 | [Selinger T-depth one](04_selinger_tdepth_one.md) | ccz/ccx when T-depth matters | 7 T, T-depth 1 | 4 clean ancillas | relaxed (no meas.) |
| 05 | [Barenco multi-control decompositions](05_barenco_multicontrolled.md) | mcx with dirty or clean work qubits | 4(m-2) or 2m-3 Toffolis | borrowed / clean | exact / relaxed |
| 06 | [Cuccaro ripple-carry adder](06_cuccaro_ripple_carry.md) | integer addition, few qubits | 2n Toffolis (14n T; pyzx 8n) | 1 ancilla | exact |
| 07 | [Phase folding / T-par (AMM)](07_phase_folding_tpar.md) | repeated parities in CNOT+phase regions | never increases | none | exact |
| 08 | [pyzx ZX simplification](08_pyzx_zx_simplification.md) | any Clifford+T / Clifford+Rz | never increases | none | exact |
| 09 | [Nam rotation merging + H reduction](09_nam_rotation_merging.md) | Toffoli-expanded arithmetic, QFT adders | never increases | none | exact |
| 10 | [Dyadic phase fixing (BQSKit-FT)](10_dyadic_phase_fixing.md) | continuous Rz near dyadic angles | gridsynth vs phase kickback | phase-gradient register (2k-2) | approximate (+ relaxed) |
| 11 | [Approximate QFT](11_qft_approximation.md) | QFT / QPE / Draper adders / Shor | drops small rotations | none | approximate |

Card files are <= 300 words each (`wc -w`). Not covered by a card yet: Hadamard gadgetization (pyzx internals),
TODD / Reed-Muller decoders (cited only as "best previous" in Kissinger & van de Wetering 2020 Table 1).
