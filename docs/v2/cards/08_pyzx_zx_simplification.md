# ZX-calculus T-count reduction / phase teleportation (Kissinger & van de Wetering 2020)

**What it does.** Converts the circuit to a ZX-diagram, simplifies it to a graph-like normal form
(local complementation and pivoting remove interior Clifford spiders), gadgetizes phases so non-Clifford
phases on the same parity meet and fuse across Hadamards ("phase teleportation"), then extracts a circuit.
Phase teleportation does not change the number or location of non-phase gates; it also works with arbitrary
and symbolic phases. The same simplifier often proves the optimized circuit equal to the original.

**When it applies (pattern).** Any Clifford+T or Clifford+Rz circuit; strongest where Hadamards split phase
polynomials into regions that phase folding alone cannot merge (Toffoli-heavy arithmetic). It cannot
introduce ancillas or measurements, so it stays at the unitary T-count (e.g. 8n for ripple-carry adders).

**Cost.** Never increases T-count in our runs; no ancillas, no measurements. Extraction can increase CNOT
count (TKET / basic_optimization help).

**Verification mode: exact** (unitary-preserving). Self-check: `zx.Circuit.verify_equality`; the project
re-checks every output independently (dense unitary / statevector / sparse basis pairs).

**Worked example (run: `results/v2/bench_runs/run2/`, pyzx 0.10.7, full_reduce -> extract_circuit ->
to_basic_gates -> basic_optimization).** tof_3: 21 -> 15 T; adder_8: 399 -> 173 T; cuccaro_4: 56 -> 32 T;
all verified against the input. The paper's Table 1 (arXiv:1903.10477v2 p.4) lists 15 for tof3 and 173 for
adder8 (PyZX column).

**Citation.** A. Kissinger, J. van de Wetering, "Reducing the number of non-Clifford gates in quantum
circuits", *Phys. Rev. A* 102, 022406 (2020), doi:10.1103/PhysRevA.102.022406, arXiv:1903.10477 (arXiv title:
"Reducing T-count with the ZX-calculus").
