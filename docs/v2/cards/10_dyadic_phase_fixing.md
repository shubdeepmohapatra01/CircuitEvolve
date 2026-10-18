# Dyadic phase fixing + phase kickback (Kalloor et al. 2026)

**What it does.** For circuits with continuous rotations: partition into width-4 blocks; in each block
greedily *fix* an Rz angle to the nearest multiple of pi/2^k (k = 1, 2, ...), re-instantiate the block's other
angles numerically to stay within the block budget eps/B (Hilbert-Schmidt distance), and keep the
lowest-T accepted circuit. Fixed angles with k <= 3 become Clifford/T gates; larger-k dyadic angles can be
applied by phase kickback (an adder into one shared phase-gradient register), sized by a decision matrix
that falls back to gridsynth when that is cheaper. Reported: up to 70 % T-count reduction vs gridsynth and
up to 60 % vs Repeat-Until-Success; T-count and space-time volume can diverge.

**When it applies (pattern).** Clifford+Rz circuits after pre-optimization: QFT / QPE / QAE, Trotter steps,
Shor circuits with cp/ccp (qseed shor_12/14/16). Not needed for the exact Clifford+T arithmetic suite.

**Cost.** Phase kickback: an adder per dyadic rotation (Gidney adder ~4k T) plus one-time gradient-register
preparation; register uses 2k_reg - 2 ancillas (k_reg gradient + k_reg - 2 scratch). Public script
(`alg_err_workflow.py`, k = 3) needs no ancillas.

**Verification mode: approximate** (unitary within the eps budget, `blocks/verify_block.py` + error ledger);
phase-kickback lowering adds an ancilla-register precondition (relaxed).

**Worked example (run: `results/v2/cards_worked_examples.json`, project gridsynth wrapper, eps 2.5e-4).**
Rz(pi/8) 38 T, Rz(pi/16) 36 T, Rz(0.39) 38 T by gridsynth; fixing 0.39 -> pi/8 (if the block re-fits within
budget) turns it into a dyadic k = 4 rotation eligible for phase kickback. Project convention: skill
`bqskit-ft-reference-baseline`, arms B2/B3 in `results/bqskit_baselines/stage1/`.

**Citation.** J. Kalloor, M. Weiden, E. Younis, J. Kubiatowicz, C. Iancu, "Multi-Qubit Dyadic Phase Fixing
for Fault-Tolerant Quantum Compilation", arXiv:2606.05397 (2026); QCE 2026 per the project skill
(venue not checked against metadata).
