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
