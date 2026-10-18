# Ripple-carry adder with one ancilla (Cuccaro et al. 2004)

**What it does.** In-place n-bit addition |a>|b> -> |a>|a+b> by a ladder of MAJ (majority) blocks that write
each carry into the a-register in place, a CNOT of the top carry to the carry-out qubit, then UMA
(unmajority-and-add) blocks that restore a and write the sum into b. Linear depth, a single ancillary qubit
(prior ripple-carry adders needed linearly many), fewer gates than earlier ripple-carry adders.

**When it applies (pattern).** Integer addition in a logical circuit (`add`, `+=`, modular arithmetic
cores, multipliers built from adders). It is the project's naive adder seed; it is the right choice when
qubits are scarce. When clean ancillas are available, card 01 (Gidney) is cheaper in T.

**Cost.** 2n Toffolis in our generator (`circuitevolve/baselines/cuccaro.py`), 2n + 2 qubits (one ancilla +
carry-out), no measurement: 14n T with 7-T Toffolis; 8n T after pyzx full_reduce (measured n = 1..8 in the
legacy track); Gidney's measurement-based adder reaches 4n + O(1) T.

**Verification mode: exact** (unitary, no ancilla assumptions needed for the generator's own circuit).

**Worked example (computed: MANIFEST.csv and `results/v2/bench_runs/run2/cuccaro_4.json`).** cuccaro_4:
10 qubits, 8 ccx, 56 T as 7-T Toffolis; pyzx full_reduce 32 T (= 8n), TKET FullPeepholeOptimise 48 T;
both verified by dense unitary.

**Citation.** S. A. Cuccaro, T. G. Draper, S. A. Kutin, D. P. Moulton, "A new quantum ripple-carry addition
circuit", arXiv:quant-ph/0410184 (2004).
