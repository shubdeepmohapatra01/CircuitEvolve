# Nam-Ross-Su-Childs-Maslov 2018 arithmetic / reversible suite (v2 benchmarks)

All upstream files are pinned (`COMMIT`) and re-fetchable with `python fetch_suite.py`; `python normalize.py`
rebuilds the CircuitEvolve copies; `../../experiments/v2_bench_manifest.py` rebuilds `MANIFEST.csv` / `split_v2.json`.

| role | repo @ commit | path | license |
|---|---|---|---|
| logical circuits (ccz kept) | quantum-compiler/quartz @ ce31db1c91f502f6ef2b9af655855f17f78caf17 | circuit/nam-benchmarks/*.qasm | Apache-2.0 |
| Clifford+T as given (7 T per CCZ) | quantum-compiler/quartz @ ce31db1c91f5... | circuit/nam_circs/*.qasm | Apache-2.0 |
| authors' circuits (before / after Light / after Heavy, Quipper ASCII) | njross/optimizer @ 8cd55d504c8a268048d559e80cdc506831959d12 | Arithmetic_and_Toffoli/* | no license file (README: research benchmark release; cite Nam et al. 2018) |
| independent cross-check + ancilla declarations | meamy/feynman @ d2c382a2ab43a40a87f12f4255645bbb55f704f8 | benchmarks/qasm/*.qasm, benchmarks/qc/*.qc | BSD-3-Clause |

The authors' README states that the Arithmetic_and_Toffoli inputs were taken from the T-par repository
(github.com/meamy/t-par; Amy, Maslov, Mosca 2014). grover_5, ham15-*, hwb6 are not in the authors' repo (they are
T-par / Feynman benchmarks, optimized in Kissinger & van de Wetering 2020 Table 1).

Layout: `upstream/` (unchanged downloads), `logical/` (OpenQASM 2 + a `gate ccz` definition), `cliffordt/`
(`rz(+-pi/4)` renamed t / tdg), `nam/<name>_{before,light,heavy}.qasm` (Quipper converted gate by gate;
negative controls conjugated by X), `generated/cuccaro_{4,8,16}.qasm` (`circuitevolve.baselines.cuccaro`).

## Provenance checks (results/v2/bench_runs/run2/<name>.json, `provenance`)

* logical vs Clifford+T-as-given: equal for every circuit.
* logical vs authors' `before`: equal for every circuit in the authors' repo (gate-for-gate the same CCZ counts).
* logical vs Feynman QASM: equal except **qcla_adder_10** (same T-count 238, but a different function: operator
  distance ~1.41 on random basis pairs). We use the authors' version (= Quartz). Kissinger & van de Wetering list
  original T = 589 for qcla-adder10, i.e. a third variant.
* Clean-ancilla info: `MANIFEST.csv` `zero_init_qubits` = qubits not in the Feynman `.qc` `.i` line (start in |0>);
  `zero_init_restored_frac` = fraction of 64 random inputs after which all of them are back in |0> (1.0 = true
  ancillas; < 1 = they also hold outputs, e.g. the product register of gf2 multipliers).
