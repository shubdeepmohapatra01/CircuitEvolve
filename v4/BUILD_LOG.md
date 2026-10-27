# v4 build log

Every number here was measured on this machine in this session, with the command shown. Gates are from
`V4_README.md` section 11.

## P0 - scaffold + the caches (6.4) + price-before-verify

**Gate: the suite sweep reproduces v3's T-counts exactly, and is >= 5x faster. No number moves.**

T-counts: **identical on all 10 DV circuits.** Speed: **1.61x on the suite total**, 3.4x on the five
dv_angle circuits. The gate as written is NOT met, and the measurement says why.

```
.venv/bin/python /tmp/.../v3_sweep.py             # v3/runner.py, accepted book, eps 1e-3
.venv/bin/python -m v4.tools.sweep --tag p0       # v4/runner.py, same book, same eps
```

| circuit | v3 T | v4 T | v3 s | v4 s | speedup |
|---|---|---|---|---|---|
| qft_8 | 1583 | 1583 | 7.36 | 1.07 | 6.9x |
| qpe_8 | 11485 | 11485 | 42.01 | 12.73 | 3.3x |
| hhl_8 | 28509 | 28509 | 147.32 | 45.24 | 3.3x |
| qae_13 | 4526 | 4526 | 58.52 | 16.58 | 3.5x |
| tfim_6 | 3354 | 3354 | 0.19 | 0.09 | 2.1x |
| **dv_angle total** | | | **255.40** | **75.71** | **3.4x** |
| adder_8 | 216 | 216 | 91.26 | 91.12 | 1.0x |
| adder_6 | 44 | 44 | 90.57 | 89.02 | 1.0x |
| mult_4 | 36 | 36 | 115.13 | 37.83 | 3.0x |
| mcx_10 | 128 | 128 | 103.40 | 104.29 | 1.0x |
| modred_21 | 68 | 68 | 22.97 | 23.04 | 1.0x |
| **suite total** | | | **678.74** | **421.02** | **1.61x** |

### Why the reconstruction circuits do not speed up (measured)

Profiling adder_6's single run: **147,456 calls to the frozen `circuitevolve/sim.py::run`**, 225 s under
cProfile, 52.6 s of it inside `ring.py::_mul_coeffs`. That is ONE relaxed verification: 16,384 basis
inputs x (1 reference evaluation + 8 sampled measurement branches), all in exact D[omega] ring arithmetic
in the frozen simulator.

v3 paid that check exactly once too, because its `order='best'` already short-circuits when only one rule
fires - which is the case on every reconstruction circuit (only
`and_ancilla_ccz_lowering_with_measured_uncompute` triggers there). So there was no redundancy left for
v4 to remove: **the reconstruction half of the suite is bounded below by one frozen relaxed check per
circuit, and V4_README's 5x estimate was formed on the dv_angle numbers.** The caches, the verdict memo
and price-before-verify do what the plan says they do; they just cannot touch that one check.

What the plan can do about it is a later phase, not a P0 fix: the `branch_kraus` certificate (section 6.2,
built in P5) is branch-wise, so it can in principle be charged per window instead of per whole circuit.
That changes WHAT is verified, so it is not a P0 move and is not claimed here.

### What P0 actually delivered

| change | measured |
|---|---|
| `check_frozen()` once per process | 6.67 ms first call, 0.09 us per call after (v3: 3.3 ms x every verify) |
| reference `ReferenceSpec` + reference unitary / probe images cached | `v4/judge/dv.py`; identical output asserted bit-for-bit against the frozen `core.verifier.check_circuit` in `v4/tests/test_p0.py` |
| verdict memo on (candidate, reference, mode) | qft_8 1.97 s -> 1.14 s on its own; `order='best'` runs the book 2 + len(book) times over one circuit and every repeat is now a cache hit |
| price before verify | qft_8: 40 applications attempted, 19 accepted, **21 dropped on price without any verification** |
| trigger-only pre-pass | a rule that matches nowhere needs no solo run |
| `pauli.conjugate` on flat bit tables | bit-identical to v3 on all 4,096 x 7 gate/input combinations (test) |
| `pauli.frames` via a Clifford tableau | hhl_8: **2.40 ms vs 174.08 ms** for v3's per-rotation backward pass = **72.6x**, same Paulis on all 5 angle circuits |

A note on price-before-verify: it means an application that does NOT improve is never verified. Only kept
applications are verified, and acceptance only ever depended on those. The cost is that v4's sweep no
longer incidentally checks the correctness of rewrites it was going to throw away - which is exactly
V4_README section 0, finding 2: 8 of v3's 9 verification failures were the same verifier limitation, and
the one genuine error was on its own target circuit.

## P1 - optimize_memo + declared preconditions + trigger-only pre-pass

**Gate: the no-op `test_rule` probe drops from 7.7-12.6 min to < 60 s.**

```
.venv/bin/python -m v4.tools.test_rule v4/rules/candidates/_timing_noop.py --target hhl_8
```

**0.31 s** (v3: 7.7-12.6 min). That is a 1,500-2,400x reduction, and the gate is met with three orders of
magnitude to spare. The no-op is `never_fires`, and v4 decides that from 5 trigger calls without running
`optimize` once - where v3 computed `n_match` and then ran both `optimize` calls anyway.

Two more measurements on the same path:

* a candidate that DOES fire: `same_pauli_merge` on top of the six-rule book, target qft_8, **2.6 s**,
  decision `admit`, qft_8 1583 -> **1577**. That is pyzx's exact T-count, and it confirms V4_README's
  "the book is worse than one of its own rules" by 6 T - which `order='min_all'` (section 5.2) removes.
* the two P1 planted-bug rules are still rejected by verification, at the right level
  (`implementation`), in 2.07 s and 1.49 s: distance 7.198e-01 > eps 1e-08 on the qft_8 window.

Preconditions are checked for SOUNDNESS by a test over the whole suite: a precondition may only exclude a
circuit whose trigger matches nowhere (`v4/tests/test_p0.py::test_preconditions_are_sound`). All six
declared preconditions pass.

## P2 - the floor tier, part 1

**Gate: the floor reproduces pyzx on qft_8 / qpe_8 / qae_13 / hhl_8 to the T.**

Met on three of four, and the fourth is a **defect in V4_README 4.1**, measured:

| circuit | floor alone | pyzx | verdict |
|---|---|---|---|
| qpe_8 | 11485 | 11485 | exact ✓ |
| hhl_8 | 29205 | 29205 | exact ✓ |
| qae_13 | 4526 | 4527 | 1 T BELOW pyzx ✓ |
| tfim_6 | 8560 | 8560 | exact ✓ |
| **qft_8** | **1583** | **1577** | **+6 T ✗** |

V4_README 4.1 says `pauli_frame_rotation_merge` **alone** gives qft_8 1577 and that moving two files is
therefore "zero new implementation". That 1577 came from a two-rule book in the P2 attempt log
(`phase_polynomial_rotation_merge` + `pauli_frame_rotation_merge`), not from the rule alone. Measured
here, every subset of the four angle rules gives 1583:

```
1583  pauli_frame_rotation_merge                                    (alone)
1583  pauli_frame_rotation_merge + same_pauli_merge
1583  ... + pauli_exponential_commutation_merge
1583  ... + pauli_subalgebra_dimension_recompression  (all four)
1597  pauli_exponential_commutation_merge                           (alone)
2340  pauli_subalgebra_dimension_recompression                      (alone)
```

The forward-push variant `same_pauli_merge` was tried as a third floor member: its trigger matches twice
on qft_8 and **both applications price out**, so it is in `rules/rejected/` with that reason.
**Conclusion: the 6 T between 1583 and pyzx's 1577 on qft_8 is not in the phase-folding class at all**,
and V4_README 4.1's "local complementation and pivoting mostly move CNOT count, not T" is not true on
qft_8 - they move 6 T there. The floor does not chase it.

### A pricing bug this phase exposed

While testing `same_pauli_merge` as a candidate, `test_rule` reported qft_8 1583 -> 1577 while a run from
scratch gave 1583. Cause: `check_on_target` applies a candidate to the book's cached residual, which has
33 rotations where the original has 48, so `eps_rz = eps_synth / N_Rz` was COARSER there, gridsynth words
were shorter, and two merges looked like a 6 T win. Fixed: `_price_fn` now prices against the **reference**
circuit (the original, which is also what verification compares to), never against whatever intermediate
circuit a call happens to start from. Re-running the full suite after the fix moved no T-count.

`rules/BOOK.md` is regenerated with a "what the floor tier ALONE already reaches" table, and
`agent/scout.md` is rewritten to name the floor's contents and tell the scout not to re-propose them
(V4_README 4.4, "the trap").

## P3 - API primitives, ledger, two-axis tags, DPF k<=3 card

**Gate: the v3 rules re-expressed against the new API verify identically; ledger draws recorded; the
floor matches the best baseline on qpe_8 (7552) and hhl_8 (18701).**

Identical re-expression ✓, ledger ✓, **best-baseline match ✗** - and the measurement says why.

### The re-expressed rules

Both Pauli rules now read their front-frame axes from `v4.api.pauli.frames` (one forward sweep over a
Clifford tableau) instead of transporting each rotation's Z back through the Clifford prefix. Tested
against **v3's own rule files, loaded and run**, not against remembered numbers:

| rule | qft_8 | qpe_8 | hhl_8 | qae_13 | tfim_6 | speedup |
|---|---|---|---|---|---|---|
| `pauli_exponential_commutation_merge` | 9 = 9 | 36 = 36 | 71 = 71 | 31 = 31 | 0 = 0 | 1.7x - 23.1x |
| `pauli_frame_rotation_merge` | 12 = 12 | 51 = 51 | 102 = 102 | 36 = 36 | 0 = 0 | 1.0x - 1.4x |

Same match lists, element for element. The frame rule gains less because its backward walk already
stopped at the first anticommuting rotation; the exponential rule was the quadratic one (14.4 M
`conjugate` calls, 13.5 s of qpe_8's 27 s profiled run).

### What DPF's k <= 3 win actually is (measured, and not what the plan assumed)

V4_README 4.2 describes the card as "greedily fix the Rz nearest a multiple of theta". That cannot be the
mechanism: snapping an angle onto the pi/4 grid costs a phase-aligned distance of up to
`sqrt(2 - 2|cos(pi/8)|)` = 0.39, and the entire rule budget is 5e-4. Two measurements settle it.

**1. Where DPF wins big, the angles are ALREADY dyadic.** Off-grid rotations that sit exactly on the
`k*pi/2^m` grid, on the raw inputs:

| circuit | off-grid rz | distinct | exact at m=3 | m=7 | m=10 | DPF's K* | DPF T |
|---|---|---|---|---|---|---|---|
| qft_8 | 48 | 18 | 13 | **45** | 48 | 7 | 1064 |
| qae_13 | 145 | 44 | 21 | 85 | **112** | 10 | 4264 |
| qpe_8 | 257 | 55 | 4 | 6 | 6 | 3 | 7552 |
| hhl_8 | 583 | 528 | 12 | 24 | 24 | 3 | 18701 |
| tfim_6 | 160 | 5 | 0 | 0 | 0 | 7 | 9600 (LOSES) |

qft_8 and qae_13 are built from controlled-phase ladders, so their angles are exactly dyadic and fixing
them is **free**. DPF's advantage there is not angle fixing at all - it is lowering a *fixed dyadic* Rz
onto a phase-gradient register instead of sending it to gridsynth, which is the PKAC card (4.2b) and
needs `resource_class='measured'`. On qpe_8 and hhl_8 there is no angle lever (6 and 24 of hundreds), and
DPF's win there is rotation-COUNT reduction per block. **One baseline, two different mechanisms, split
exactly along the K* column.** This is the fingerprint of section 7 doing its job, and it is sharper than
the plan's own table.

**2. In-skeleton block refit can remove a rotation inside DPF's own per-block threshold on 10 blocks out
of 225 across the whole suite.** Freeing each width-4 block's angles, pinning each off-grid rotation in
turn to 0 or to its nearest pi/4 point and refitting the rest:

| circuit | blocks with free angles | DPF's threshold `0.4 eps / B` | fit within it | median best distance |
|---|---|---|---|---|
| qft_8 | 26 | 1.54e-05 | 0 | 4.9e-02 |
| qpe_8 | 23 | 1.21e-05 | 1 | 3.5e-02 |
| hhl_8 | 34 | 6.45e-06 | **9** | 3.7e-02 |
| qae_13 | 55 | 7.27e-06 | 0 | 1.2e-02 |
| tfim_6 | 87 | 4.60e-06 | 0 | 7.5e-03 |

The ones that fit are at ~1e-15: genuinely redundant rotations. The median is 3-4 orders of magnitude
above the threshold, so there is no "spend more budget" version of this.

### What the DPF card delivers

`rules/floor/dpf_dyadic_angle_fixing.py` (`approx` + `unitary`), floor gate `results/floor_gate_p3.json`:

| circuit | floor before the card | with the card | best baseline | gap |
|---|---|---|---|---|
| qft_8 | 1583 | 1583 | DPF Synth 1064 | +519 |
| qpe_8 | 11485 | **11364** | DPF Synth 7552 | +3812 |
| hhl_8 | 29205 | **28413** | DPF Synth 18701 | +9712 |
| qae_13 | 4526 | 4526 | DPF Synth 4264 | +262 |
| tfim_6 | 8560 | 8560 | TKET 8560 | 0 ✓ |

-121 T on qpe_8 and -792 T on hhl_8, exactly the 1 and 9 blocks the probe predicted, and nothing on
qft_8 / qae_13, where the probe predicted nothing. The card is correct; the lever is small.

**The gate is not met, and closing it is a larger job than the plan accounts for.** The remaining margin
needs the two things the card deliberately does not do: (a) re-synthesising a block over a FREE CNOT
ansatz rather than keeping its existing skeleton, which is BQSKit's `GreedyNTROPass` and a QSearch /
LEAP-class numerical synthesiser in pure Python; and (b) the PKAC phase-gradient lowering, which
V4_README 4.2b already gates on P5. Scoped in `v4/SCOPE.md`.

### Two bugs the tests caught

* **`angles.rz_distance` was wrong.** It returned `|sin(d/2)|`; the judge's phase-aligned distance for a
  one-rotation window is `sqrt(2 - 2|cos(d/2)|)`. They agree to first order (which is why it passed at
  d = 1e-3) and are 8e-5 apart relatively at d = 0.05; the wrong one also fails to give 0 at d = 2pi,
  where rz differs only by a global phase. Now checked against the judge's own measurement at five
  separations.
* **The ledger was never installed.** `v4.api.budget` was written and tested but the runner never wrapped
  rule calls in it, so `budget.draw` would have returned False for every rule. Now installed around
  every `trigger` / `apply` call, with the runner charging only the difference between the measured
  distance and what the rule already reserved, and refunding a rule's draw when its application is
  priced out or reverted.

## P4 - the certificate layer

**Gate: `tests/` and the acceptance suite pass; phase-folding checks are O(ops) and `certified=True`.**
Met.

`v4/judge/certify.py` dispatches to the cheapest certificate that applies. Two algebraic witnesses, both
O(ops), both proofs, both with no matrices:

* **`pauli.merge_witness`** - the class EVERY admitted angle rule in v3 belongs to. It checks that the
  Clifford skeleton is untouched, that the new op list is the old one with one rotation deleted and one
  earlier rotation's angle changed by the signed deleted angle, and that every rotation strictly between
  them commutes with the moved axis. Because the axes are front-frame Paulis it works straight through
  Hadamards, which is what makes it cover the hot path.
* **`phasepoly.witness`** - any rewrite of a Hadamard-free segment, by comparing the affine part and the
  phase polynomial. More general than a merge, but it stops at the first Hadamard.

Coverage and cost, measured on real runs:

| circuit | algebraic / total checks | algebraic time | other time | per-check |
|---|---|---|---|---|
| qft_8 | **73 / 80** (merge 72, poly 1) | 8.3 ms | 0.21 s | 114 us vs 30 ms = **260x** |
| qpe_8 | **208 / 268** | 145 ms | 1.75 s | |

T-counts unchanged; every accepted application reports `certified=True`. The first draft of the witness
covered only 18 of 80 checks, because the phase-polynomial witness alone declines any window spanning a
Hadamard - the merge witness is what lifted it to 73.

**Its own planted-bug suite** (`v4/tests/test_p4.py`, 21 tests, all pass). V4_README's known risks note
that this checker "becomes the weakest link in the chain it is meant to strengthen" without one. Nine
mutations of a correct merge (wrong sign, wrong angle, off by pi, dropped cx, swapped control and target,
extra x, wrong wire, merged the other pair, nothing deleted) and four of a correct phase-polynomial
rewrite (angle moved to the wrong label, cx dropped, x added, angle scaled), each asserted to be
genuinely wrong numerically AND refused by the certificate. Plus a soundness test on real data: for
every window of every angle circuit that the certificate ACCEPTS, the numeric distance must be below
1e-9.

A design note worth recording: the merge witness's first implementation located the deleted rotation by
scanning forward from the first divergence, which only finds it when the deleted rotation is the first
one to differ. It missed every real case (host first, deletion later). The fix bounds the candidates by
the common prefix and suffix of the two axis streams, which is both correct and O(n).

## P5 - `branch_kraus` with an error allowance: the one unfreeze

**Gate: the P1 planted-bug gate re-run, 4/4 correct. MANDATORY before any v4 result counts.**
**PASS - 4/4** (`v4/results/planted_gate.json`).

### Why it was needed, measured

V4_README section 0 says 8 of 9 P2 verification failures were the same verifier limitation. Reading every
`v3/rules/rejected/*.reason.json` shows it is worse than that, and more specific: **eight rules died on
the single message `candidate not exact: rz(...) is not a multiple of pi/4`**, and they are one family -

```
and_monomial_phase_polynomial_resynthesis
controlled_phase_and_ancilla_single_rotation_lowering
hamming_weight_phasing_on_equal_angle_phase_gadgets
hamming_weight_phasing_same_angle_group
hamming_weight_phasing_shared_angle_layers
multilinear_phase_polynomial_and_ancilla_resynthesis
phase_gradient_addition_for_dyadic_rotation_cascades      <-- the PKAC card of V4_README 4.2b
phase_gradient_catalysis_dyadic_rotations                 <-- the PKAC card of V4_README 4.2b
```

The last two **are** the phase-gradient / PKAC card the plan asks to be written by hand. The LLM had
already found it in v3; the verifier could not check it. That changes P6 from "write a card" to "re-run
what was already found", which is what was done.

### How, without editing a frozen file

`circuitevolve/v2/verify.py` is listed in v3's `FROZEN.sha256` and is covered by CLAUDE.md invariant 4,
so it was NOT edited. `v4/judge/kraus.py` is new v4 code that composes the frozen primitives: the exact
module keeps its behaviour and its hash, and nothing v3 ever decided changes. The check is CLAUDE.md
invariant 2 generalised to continuous angles -

    for every basis input x and every branch m:
        K_m |x, 0_anc> = c_m |U_ref x, 0_anc> + (error <= allowance)
        with the SAME c_m for every x, and sum_m |c_m|^2 = 1

with three separately-reported tolerances: the per-branch state distance, the **ancilla population left
outside |0>**, and the spread of c_m across inputs. Clifford+T candidates still route to the frozen exact
`relaxed` mode, so floating point never accepts a Clifford+T case (invariant 1).

The ancilla-return check is not decoration. Our own measurement of BQSKit's PKAC construction found it
exact at k = 3 (state error 2.6e-16, zero leak) and leaking 1/sqrt(2) at k = 4 and ~1.0 at k = 5, because
the temporary-AND uncompute is measurement-based by construction. A verifier without this check would
accept those.

### The gate

| control | must decide | got |
|---|---|---|
| `same_pauli_merge` (correct merge, empty book) | ADMIT | ADMIT, qft_8 2391 -> 1583 |
| `same_pauli_merge_planted` (1 in 10 merged with the wrong sign) | REJECT | REJECT - and by the ALGEBRAIC certificate, "angles do not add", not by a matrix |
| `ancilla_parity_rotation_lowering` (cx-rz-cx, clean ancilla, continuous angle) | VERIFY | VERIFIED, `branch-kraus-exhaustive` - impossible before P5 |
| `ancilla_parity_rotation_leak` (the same, uncompute removed) | REJECT on ancilla return | REJECT: "ancilla population left outside |0>: 7.071e-01" |

v3's P1 gate was 4 decisions, two of them CV-DV. CV-DV is deferred in v4 as it was in v3, so the two
CV-DV controls are replaced by the two above, which exercise **the path P5 changed**. That is a faithful
re-run: the gate's job is to confirm the verifier still rejects what it should, and this is the only path
that moved.

P5 also added `runner.optimize(price_first=False)`, an audit switch restoring v3's verify-then-price
order. It is needed because price-before-verify means a control that does not improve anything is never
verified - so the gate could not otherwise observe the verifier's verdict on controls 3 and 4.

## P6 - re-running what v3 threw away

All 18 rejected v3 rules are ported to `v4/rules/candidates/` (`PORTED.json`: 8 verifier-blocked,
9 timed out, 1 over error budget) and re-evaluated by `v4/tools/reevaluate.py`, each in its own
subprocess. The subprocess wall clock is infrastructure: a rule that hits it is recorded
`not_evaluated`, never `reject`, so it cannot bias admission - which is exactly what v3's 300 s limit
did.

First results (full table in `results/reevaluate_p6.json`):

| rule | v3 verdict | v4 verdict | measured |
|---|---|---|---|
| `and_monomial_phase_polynomial_resynthesis` | reject: `rz(...) not a multiple of pi/4` | **ADMIT** | qft_8 1583 -> **1390**, qpe_8 11364 -> 11289, qae_13 4526 -> **4414** |

qft_8 at 1390 is **187 T below pyzx's 1577**, and qae_13 at 4414 is 113 below pyzx's 4527. Both numbers
were unreachable in v3 for one reason: the verifier could not check the rule.

## P7 - the loop

**Gate: one full global loop over the suite completes in < 2 h.**

`v4/loop.py` implements section 5 exactly, with the LLM behind two injectable callables so the control
flow is testable without spending anything (`v4/tests/test_p7.py`, stub scout and implementer). The five
outcomes of 5.3 are classified at the right level, and the level decides who is re-run: an idea-level
failure returns to the SCOUT, an implementation-level one re-runs the IMPLEMENTER with the failure report
and the instruction to narrow the guard and keep the idea.

Two corrections the tests forced:

* **classification needs the target.** "The precondition excludes this circuit" and "the trigger matched
  nowhere" are different messages and different advice, and they are only distinguishable with respect to
  the circuit the card was written FOR - `evaluate` runs the whole suite, so a rule excluded on the
  target still has trigger counts from elsewhere.
* **5.2's regression guard is vacuous under `min_all`.** `min(book_order, gain_order, best_single_rule)`
  takes a minimum over a superset when a rule is added, so adding a rule can never raise T, and
  "refuses any admission that raises T" can never fire there. The guard is kept (it fires under
  `order='book'`, and the test checks that it does), and the BINDING guard was added next to it: a rule
  that lowers T on no circuit under the admission ordering is refused. Without it, a rule that improved
  only the cached residual - an ordering the book would not choose - would have entered the book.

## P8 - the report

`v4/report.py` writes `results.json`, `results.csv`, `RESULTS.md` and a figure. Three things it gets
right that v3's report did not: the DPF column is **B4 = DPF Synth** with its seed range, K* and actual
ancilla count, not the retired B3g arm; **hatching is on `resource_class`**, so a DPF result with K* = 3
and zero ancillas is no longer mislabelled relaxed; and the gap to the best baseline is **attributed**
per circuit to a named mechanism with a measured size (`SCOPE.md`).

## Gap A (the PKAC card): the expressiveness barrier is gone and a WIDTH barrier is now the blocker

V4_README 4.2b asks for a hand-written phase-gradient / PKAC floor card, gated on P5. Two things changed
that plan, both measured.

**1. The card already existed.** `phase_gradient_addition_for_dyadic_rotation_cascades` and
`phase_gradient_catalysis_dyadic_rotations` are v3 LLM rules that implement exactly the construction
4.2b describes - CNOT loading of parity bits into a work register, one ripple-carry addition into a
shared phase-gradient catalyst, everything Clifford+T except the gradient preparation. Both were
rejected in v3 on `candidate not exact: rz(...) is not a multiple of pi/4`. So the right move was to
re-run them, not to rewrite them.

**2. Under the new verifier they get past that message and hit a different, named wall.** Measured, on
the floor's residual at eps 1e-3:

| rule | circuit | verdict | why |
|---|---|---|---|
| `phase_gradient_addition_for_dyadic_rotation_cascades` | qft_8 | not verifiable | the candidate has **34 qubits** (8 data + 26 register), the dense branch check caps at **22** |
| | qae_13 | not verifiable | **51 qubits** |
| narrowed to `E_MAX=7` | qft_8 / qae_13 | not verifiable | 28 / 33 qubits |
| narrowed to `E_MAX=6` | qft_8 / qae_13 | not verifiable | **25 / 30** qubits |
| narrowed to `E_MAX=5` | qft_8 / qae_13 | never fires | fewer than 4 distinct exponents remain in range |

The cap is not arbitrary: 2^22 complex128 is 64 MB per state vector, and the check iterates
(basis inputs x branches) of them. 2^25 is 512 MB each, which is not a tuning away - it is a different
algorithm.

**So P5 removed the EXPRESSIVENESS barrier and exposed a SCALABILITY one**, and the two should not be
confused. The expressiveness fix is real and is demonstrated twice over: the planted-bug gate's control 3
(a correct ancilla + continuous-angle identity) now VERIFIES where it could not be expressed before, and
`and_monomial_phase_polynomial_resynthesis` - another of the eight rules blocked by that one message -
now ADMITS and gives qft_8 **1390**, which is 187 T below pyzx.

**What was tried and did not help.** `runner.relaxed_window` was added so that an ancilla / measurement
rewrite is checked on the window it changes rather than on the whole circuit, with the soundness argument
written out in its docstring (a contiguous window whose fresh ancillas are untouched outside it, and
whose every branch acts as `c_m` times the old window on the data wires, splices into any surrounding
circuit with the same coefficients). It is sound, it is kept, and it does not rescue PKAC: this rewrite
replaces a whole rotation cascade at once, so the window IS 34 qubits wide. It will matter for narrower
ancilla rules.

**The route that would work, named rather than attempted.** PKAC's correctness is a composition of three
factors that are each small: (i) CNOT loading of parity bits, affine and exactly checkable by
`phasepoly.witness`; (ii) a Gidney ripple-carry adder, pure Clifford+T and checkable on its own few
qubits by the frozen exact `relaxed` mode; (iii) the phase-gradient kickback identity, which is a
one-register statement independent of the data width. That is the `algebraic` certificate of V4_README
6.2 applied to this family - "the rule supplies a witness; the frozen checker re-derives it" - and it
needs a `witness=` hook on `Rule` so a rule can hand its factorisation to the judge. It is a well-defined
next piece of work, not a parameter sweep, and it is the only thing between v4 and DPF's qft_8 = 1064.

Until then, `SCOPE.md`'s honest statement of the contract stands, with gap A reclassified: it is blocked
on a verification-width problem with a known route, not on the verifier's expressiveness.

## A third verdict: "could not be checked" is not "failed the check"

Found while probing gap A, and it is the same category error that cost v3 eight rules.

`v4/judge/kraus.py` refuses a window wider than 22 qubits, and the frozen numeric path refuses above 20,
both returning `method='skipped'`. The harness recorded that as a **verification failure**: the rule was
rejected, the agent was told its identity was wrong, and the real message - "this is too wide to check" -
was lost. That is exactly how v3 lost the phase-gradient family: eight rules were branded as failing
verification when the verifier had simply declined.

So `Certificate` now has three outcomes, not two:

| verdict | meaning | the application | the rule |
|---|---|---|---|
| `ok=True` | the check passed | kept | may be admitted |
| `ok=False, unverifiable=False` | the check REFUTED it | dropped | rejected, and it is wrong |
| `ok=False, unverifiable=True` | the check could not RUN | dropped | **not rejected, and may be correct** |

Nothing unverified is ever accepted either way - that part does not change. What changes is what is
recorded and what the agent is told. `evaluate` returns `decision='not_verifiable'`, `admit` leaves the
file in `candidates/` rather than moving it to `rejected/`, and the loop classifies it as `too_wide` at
implementation level with feedback that is actually actionable and actually true:

> The construction could NOT BE VERIFIED at this width, so nothing was accepted. This is not a rejection
> of the idea and the identity may well be correct: the judge's branch-wise check needs
> 2^(data + ancilla) amplitudes, and your rewrite asked for more qubits than that allows. Keep the idea
> and make the construction NARROWER - fewer register bits, or rewrite one group at a time instead of a
> whole cascade - so that the changed window plus its own ancillas stays inside the limit.

That is a better route to a verifiable PKAC card than hand-writing one: the agent is told precisely what
to change, and `relaxed_window` means a narrower construction only has to fit in its own window rather
than in the whole circuit.
