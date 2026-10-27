# What each baseline actually does, as an operation on a `(name, qubits, angle)` op list

V4_README 4.3. Every move below is written in terms of the op list a rule sees, and every number is
measured on this suite at eps 1e-3 (`v4/BUILD_LOG.md`). Moves with **no op-list analogue** are flagged,
so you do not spend an attempt on them.

---

## pyzx (`full_reduce`) — lever (a), fewer rotations. OWNED: the floor reproduces it.

**The move that pays: phase-gadget fusion.** Transport a Z-rotation through the Clifford skeleton as a
signed multi-qubit Pauli exponential, and merge two whose axes are equal when everything between them
commutes with that axis. On an op list: `pauli.frames(ops)` gives every rotation's front-frame axis in one
sweep; `pauli.axis_eq` tests the merge; `pauli.commutes` tests the path. This is the whole of pyzx's T win
on these inputs, and `rules/floor/` already does it, reaching pyzx exactly on qpe_8 (11485) and hhl_8
(29205) and one T below it on qae_13 (4526 vs 4527).

**Moves with NO op-list analogue — do not propose these.** Local complementation and pivoting are
rewrites of a ZX *graph*, not of an op list: they change which vertex is a spider and re-route edges, and
there is no sequence of op-list edits that corresponds to one of them. Measured, they are also not where
the T is: pyzx inflates CNOT count on every circuit here (qft_8 68 -> 90, qpe_8 268 -> 323,
hhl_8 497 -> 663, tfim_6 180 -> 490) while moving T only through fusion.

**Measured residual.** 6 T on qft_8: the floor gets 1583, pyzx gets 1577, and no subset of the four angle
rules closes it. So that 6 T is NOT in the phase-folding class. It is the one place pyzx does something
this project has not identified.

---

## DPF Synth (`bqskit-ft` branch `greedy_ntro`) — lever (b), cheaper angles. OWNED, by TWO mechanisms.

DPF is not one move. Which one it uses is decided by the circuit's angles, and the split is exact:

**Mechanism 1 — the angles are ALREADY dyadic (qft_8, qae_13).** Both are built from controlled-phase
ladders, so their rotation angles are exact multiples of pi/2^m. Measured off-grid rotations landing
exactly on the grid:

| circuit | off-grid rz | exact at m=3 | m=7 | m=10 | DPF's K* | DPF T |
|---|---|---|---|---|---|---|
| qft_8 | 48 | 13 | **45** | 48 | 7 | 1064 |
| qae_13 | 145 | 21 | 85 | **112** | 10 | 4264 |

Fixing costs **zero error**. The T saving comes from lowering a *fixed dyadic* Rz onto a shared
**phase-gradient register** instead of sending it to gridsynth: load parity bits into a work register with
CNOTs, add that register into the gradient register with a Gidney ripple-carry adder (4 T per AND compute,
0 T measurement-based uncompute), and the gradient imparts the phase. Only the gradient preparation
rotations survive to gridsynth — DPF's qft_8 row has `n_rz = 11` where the input had 48.
`resource_class='measured'`. **This is the open lever**: it is implemented in
`rules/candidates/phase_gradient_*`, and it currently fails on verification WIDTH (34 qubits on qft_8
against a 22-qubit branch-check cap), not on correctness. A narrower version — fewer register bits, or one
group at a time — is the single highest-value thing to propose.

**Mechanism 2 — the angles are NOT dyadic (qpe_8 6 of 257, hhl_8 24 of 583).** No angle lever exists, and
DPF's win is **rotation-COUNT reduction per width-4 block**: re-synthesise the block so fewer of its
rotations need gridsynth at all, accepting it when the block's phase-aligned distance stays under
`0.4 eps / num_blocks`. On an op list: `blocks.partition(c, 4)`, then `refit.least_squares` /
`refit.pin_to_grid` against the block's own unitary, then `budget.draw` for the distance used.
`rules/floor/dpf_dyadic_angle_fixing.py` does this **keeping the block's existing CNOT skeleton** and gets
qpe_8 -121 T and hhl_8 -792 T. Measured limit: in-skeleton refit reaches the threshold on **10 blocks of
225** across the suite; the median achievable distance is 3-4 orders of magnitude above it. The rest needs
a **free CNOT ansatz** (BQSKit's `GreedyNTROPass`, a QSearch/LEAP-class search), which is a compiler pass,
not a rewrite rule.

**Do not propose "snap angles to the pi/4 grid".** A pi/4 snap costs a phase-aligned distance of up to
`sqrt(2 - 2|cos(pi/8)|)` = 0.39 and the entire rule budget is 5e-4. The distance of moving one rotation by
`d` is `sqrt(2 - 2|cos(d/2)|)` — `angles.rz_distance(d)` — so work out the cost before proposing.

**DPF loses on tfim_6**: 9600 against TKET's 8560. Zero dyadic angles, only 5 distinct angles.

---

## TKET (`FullPeepholeOptimise`) — already applied.

Every dv_angle input IS the TKET output. Local peephole templates are therefore exhausted on these
circuits by construction: do not propose short local templates.

---

## Gidney 2018 temporary AND — lever (d), ancilla reconstruction. Ours on the Toffoli circuits.

`ccz/ccx(x, y, z)` = AND-compute(x, y -> a) at 4 T; `cz/cx(a, z)`; measurement-based uncompute at 0 T. On
an IR op list these are the `and_compute` / `and_uncompute` gadgets. `exact` + `measured`: the identity is
exact, the uncompute is measurement-based. Already in `rules/accepted/`; a run of ccz with the same
control pair shares one AND. Measured limit on adder_8: the carry controls change from gate to gate, so
only 54 of 57 CCZs collapse into runs and the result is close to the no-sharing floor.

---

## gridsynth (Ross-Selinger) — ZERO headroom.

Within a small additive constant of optimal. The prefilter rejects any card that proposes to improve it,
before any code is written.

---

## Lever (c), algebraic structure — OWNED BY NOBODY.

No baseline looks for it, and it is where this project's one large win came from: tfim_6 is a free-fermion
(Gaussian) circuit, its rotations are all Majorana bilinears, and resynthesising it through one orthogonal
matrix and a Givens cascade gave 8560 -> 3354, **-60.8%**. tfim_6 is also the one circuit where levers (a)
and (b) have **exactly zero** headroom: 0 foldable rotations and 0 dyadic angles at any level. The
fingerprint reports `free_fermion`, `majorana_planes` and `generator_algebra_rank` so you can look for the
same thing elsewhere; `api/fermion.py` and `refit.closure` are the machinery.
