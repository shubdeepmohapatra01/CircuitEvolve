# Development / evaluation split for optimizer-program evolution (`split.json`, v1, 2026-10-11)

Machine-readable copy: `benchmarks/split.json` (loaded by `circuitevolve/evolve_opt/split.py`). The evolution
code refuses every circuit that is not in `dev` (`split.check_dev`), and `blocks/circuit_io.bench_path`
independently refuses the evaluation circuits.

## Evaluation (never loaded in the development phase)

| set | circuits |
|---|---|
| Table-3 circuits | add_17, hhl_6, mult_16, qft_32, shor_16 |
| held-out transfer family | the whole adder family: add_17, add_41, add_65 (no adder in dev) |

## Development (17 circuits, every non-adder Table-3 family plus the other qseed families)

| family | dev circuits | why this size |
|---|---|---|
| qft | qft_8, qft_16 | qft_32 is eval; qft_16 exercises the statevector check (n = 16) |
| qpe | qpe_6, qpe_8 | qpe_10+ have > 2,000 rotations; qpe_8 is where TKET + folding beats pyzx |
| qae | qae_11, qae_13 | smallest qae instances |
| heisenberg | heisenberg_6, heisenberg_8 | |
| tfim | tfim_6, tfim_8 | |
| hubbard | hubbard_8 | hubbard_18 has 3,344 rotations |
| grover | grover_5 | grover_3 has no non-Clifford rotation; grover_10 has 12,258 |
| qml | qml_4, qml_13 | |
| shor | shor_12 | **shor_14 excluded**: its best classical result (pyzx, 1,072 rz) already exceeds the 1e-6 budget at eps_rz = 1e-9 (1,072 x 1e-9 = 1.07e-6), so no valid output exists unless the program first removes at least 82 rotations (budget 1e-6 minus the 1e-8 numeric slack leaves room for at most 990 rz at 1e-9; 1,072 - 990 = 82) |
| mult | mult_8 | mult_16 is eval |
| hhl | hhl_8 | hhl_6 is eval; best-classical compile ~ 106 s (the most expensive dev circuit) |

The brief listed shor_12/14; shor_14 was dropped for the error-budget reason above (measured, see
`.cache` timing run: pyzx 99,804 T / 1,072 rz; TKET 240,370 T / 2,582 rz).

## FAST subset (cascade stage 1, 6 circuits)

`qft_8, qpe_8, grover_5, mult_8, tfim_6, qae_11` - one circuit from six families, every best-classical
compile < 25 s, both winners (pyzx: qft/grover/mult/qae; TKET: qpe_8, tfim_6), one statevector-checked circuit
(qae_11), and qpe_8, where whole-circuit phase folding is known to help (24,003 -> 20,357 T).
Candidates whose FAST score is within 2 % of the best FAST score are evaluated on the full dev set.

## Best-classical compile times (one process per circuit, 8 in parallel, 2026-10-11)

pyzx + TKET + gridsynth + whole-circuit checks (`blocks.classical.best_classical`): qft_8 4 s, qft_16 17 s,
qpe_6 3 s, qpe_8 21 s, qae_11 7 s, qae_13 8 s, heisenberg_6 4 s, heisenberg_8 14 s, tfim_6 3 s, tfim_8 12 s,
hubbard_8 15 s, grover_5 4 s, qml_4 2 s, qml_13 10 s, shor_12 47 s, mult_8 6 s, hhl_8 106 s
(shor_14 152 s, excluded). One full dev compile of the seed program therefore takes a few minutes serially.
Reference T-counts used for fitness: `results/evolve_opt/baseline_dev.json`.
