# Approximate QFT (Coppersmith 1994/2002; Barenco, Ekert, Suominen, Torma 1996)

**What it does.** The n-qubit QFT applies controlled phases R_k = diag(1, e^{2 pi i / 2^k}) for k = 2..n.
The approximate QFT (AQFT) of degree m keeps only R_k with k <= m and drops the rest (the smallest angles).
This removes O(n (n - m)) controlled rotations, each of which would otherwise need gridsynth synthesis.
Barenco et al. analyse AQFT under decoherence and argue that extensive approximation is possible before
accuracy is compromised, and that the approximation can even improve performance in some settings.

**When it applies (pattern).** QFT / inverse-QFT blocks: QPE, QAE, Shor (qseed shor_n contain cp ladders),
QFT-based (Draper) adders, i.e. the QFTAdd circuits of Nam et al. Table 1 and TRbO Table II. Choose m from
the error budget: the dropped rotations' total error must fit the eps allocated to approximation.

**Cost.** Removes rotations (fewer T after synthesis); no ancillas, no measurements.

**Verification mode: approximate** (operator distance to the exact QFT must be within the allocated eps;
`blocks/verify_block.py`, error ledger).

**Worked example (run: `results/v2/cards_worked_examples.json`, key `aqft_n8`, n = 8, no final swaps).**
Kept / 28 controlled phases and worst-case operator distance to the exact QFT: m = 5: 22, 0.31; m = 6: 25,
0.092; m = 7: 27, 0.018. Operator norm is the worst case over inputs; average-case fidelities are higher, but
the project's ledger uses operator norm.

**Citations.** D. Coppersmith, "An approximate Fourier transform useful in quantum factoring",
arXiv:quant-ph/0201067 (1994 IBM internal report, posted 2002). A. Barenco, A. Ekert, K.-A. Suominen,
P. Torma, "Approximate quantum Fourier transform and decoherence", *Phys. Rev. A* 54, 139 (1996),
doi:10.1103/PhysRevA.54.139, arXiv:quant-ph/9601018.
