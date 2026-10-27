# CircuitEvolve v4 — build plan

Written 2026-10-26. v4 is a new subfolder `v4/`. It **imports** from `v3/` and `circuitevolve/`;
it does not copy them. Everything measured below was measured in this session on this machine.

v3's pipeline idea is kept wholesale. What changes is: the loop shape, where knowledge lives,
what gets verified and how often, and what is allowed to reject a rule.

---

## 0. Why v4 exists — the four measured facts

| finding | measurement |
|---|---|
| The harness, not the LLM, was the cost | 139 `test_rule` calls x 7.7-12.6 min each (measured with a **no-op** rule) = ~23 h of the 53.9 h. LLM is ~7-10 h of it. |
| The suite-wide correctness sweep caught nothing | 8 of 9 verification failures were the SAME verifier limitation (`relaxed` + continuous angle -> `method=literal`, never simulated). The 1 genuine error was on its own target circuit. |
| `never_fires` cost 20.86 h to discover nothing | A trigger-only pass over the whole suite x 6 rules costs **0.48 s**. `evaluate()` computes `n_match` and then runs both `optimize` calls anyway. |
| The timeout discarded the two best rules | `staircase_knapsack_exact_angle_assignment` (qft_8 1583->1417, qpe_8 11485->10249, qae_13 4526->4370) and `joint_budget_direct_rotation_synthesis` (hhl_8 29029->24967) — every application verified, both rejected on `runtime limit 300.0s`. |

Plus two structural defects:
- **Rule interaction regresses the book.** `pauli_frame_rotation_merge` alone gives qft_8 = 1577
  (pyzx exactly). The 6-rule book gives **1583**. The book is worse than one of its own rules.
- **Knowledge lives in prose, not in code.** `v3.api` exposes 5 Pauli helpers
  (`z_on, conjugate, commutes_with_z, is_z`) and circuit accessors. Every expensive part of every
  good rule — Jordan-Wigner/Majorana maps, Givens cascades, Lie-algebra closure, least-squares refit,
  width-4 partitioning, phase-polynomial labels — was re-derived by the implementer from raw numpy,
  under a time limit, once per rule.

---

## 1. What v4 reuses from v3 unchanged

Import, do not fork:

| from | what | why |
|---|---|---|
| `circuitevolve/{ir,ring,sim,spec,verify,cost}.py` | the exact D[omega] stack | frozen, correct, fast (sparse) |
| `circuitevolve/blocks/verify_block.py` | approximate block verifier | frozen |
| `circuitevolve/v2/verify.py` | the 3-mode verifier | frozen **except** the one change in section 6 |
| `circuitevolve/blocks/cost_model.py` | cached pygridsynth oracle | pure function, persistent memo |
| `circuitevolve/core/metric.py` | T-count under the BQSKit convention | reproduces the frozen 2391 exactly |
| `v3/suite/` | manifest + input QASM | frozen, hash-checked |
| `v3/baselines/baselines.csv` | TKET, pyzx, BQSKit-FT numbers | frozen; **the DPF column is replaced, see section 3** |
| `experiments/bqskit_baselines/pk/` | the DPF Synth arm built this session | `.venv-pk`, `dpf_pk.py`, shims, 530-cell sweep |
| `v3/rules/accepted/*.py` | 6 admitted rules | 2 become the floor tier, section 4 |

New in `v4/`: the loop, the API primitives, the ledger, the certificate layer, the fingerprint,
the floor tier, the caps.

---

## 2. Layout

```
v4/
  README.md                 this file
  loop.py                   the training loop (section 5)
  book.py                   playbook: tiers, credit, retirement
  fingerprint.py            lever headroom + baseline attribution (section 7)
  ledger.py                 shared error budget, per (circuit, eps) (section 8)
  caps.py                   opcode budget for rule code; wall clock for LLM only
  judge/
     certify.py             certificate dispatch (section 6)
     frozen.py              hash check — ONCE PER PROCESS, not per verify
  api/                      what a rule may import (section 9) — THE main investment
     dv.py  pauli.py  phasepoly.py  blocks.py  sim.py  refit.py  angles.py  budget.py
  rules/
     floor/                 pretrained, never retired (section 4)
     accepted/  rejected/  never_fires/  retired/  candidates/
  agent/
     scout.md  implementer.md  run.py
     references/            translation-layer notes (section 4.3)
  results/                  append-only
```

---

## 3. Baselines: the DPF column is replaced

The old B3/B3g (k=3) arm is retired. The new arm is **B4 = DPF Synth**, built this session from
`bqskit-ft` branch `greedy_ntro` @ `c04a32245d88a0877277dccbcb8001cd85a7eef0`, best over K in 3..10
(extended to 14 for qae_13) and best of 5 seeds:

| circuit | eps | TKET | pyzx | BQSKit-FT | **DPF Synth** | K* | ancillas |
|---|---|---|---|---|---|---|---|
| qft_8 | 1e-3 | 2391 | 1577 | 2391 | **1064** | 7 | 13 |
| qpe_8 | 1e-3 | 14761 | 11485 | 14761 | **7552** | 3 | 0 |
| hhl_8 | 1e-3 | 35450 | 29205 | 35450 | **18701** | 3 | 0 |
| qae_13 | 1e-3 | 7821 | 4527 | 7821 | **4264** | 10 | 19 |
| tfim_6 | 1e-3 | 8560 | 8560 | 8560 | 9600 | 7 | 0 |

It is the lowest T on 4 of 5 circuits. Caveats that travel with it: it is **stochastic** (seed spread
2 T at K=3, 104 T at K=8 on qft_8), K* is chosen by our sweep not the paper's decision matrix, and
at K>=4 it is a **measurement-based** result (ancilla leak 1/sqrt(2) at k=4, ~1.0 at k=5 — measured),
so only the qft_8 and qae_13 rows are relaxed; the rest use 0 ancillas and are unitary.

**Primary error budget: eps = 1e-3 for every circuit.** 1e-5 stays as a secondary sweep. Never
compare across eps.

---

## 4. Pretraining the playbook — the floor tier

`rules/floor/` holds rules that are admitted before the loop sees a circuit and **never retire**.

### THE FLOOR GUARANTEE (the design contract of v4)

> On every circuit, the floor tier alone must reach **the best of every baseline** — pyzx, or DPF at
> any k, whichever is lower on that circuit — using only Python over `v4.api`. No rule may import
> bqskit, pyzx, pytket or qiskit. Therefore the LLM's worst case is "ties the best baseline", and
> every attempt it makes is scored against that, not against zero.

Consequence, measured (best-of-5 seeds, eps 1e-3): the best baseline is pyzx on qft_8/qae_13/tfim_6
and DPF on qpe_8/hhl_8, and on qft_8 and qae_13 the best DPF number is only reachable **with phase
kickback** (K* = 7 and 10). So the floor needs THREE reimplemented rules, not one, and the guarantee
is reached in stages:

| phase | floor contents | qft_8 | qpe_8 | hhl_8 | qae_13 | tfim_6 |
|---|---|---|---|---|---|---|
| target = best baseline | — | **1577** | **7552** | **18701** | **4527** | **8560** |
| after P2 | pyzx-class fusion (2 existing files) | 1577 | 11485 | 29205 | 4527 | 8560 |
| after P3 | + DPF k<=3 card | 1577 | **7552** | **18701** | 4527 | 8560 |
| after P5+P6 | + PKAC card (k >= 4) | **1577** | **7552** | **18701** | **4527** | **8560** |

(The floor takes the per-circuit minimum over its rules, so adding DPF-k3 cannot hurt qft_8 even
though DPF-k3 alone scores 2029 there against pyzx's 1577.)

**P5 is therefore a hard prerequisite for the floor guarantee, not an optional enhancement.** Without
the `relaxed -> branch_kraus` verifier change, the PKAC card cannot be verified at all, and the floor
cannot reach DPF's qft_8 = 1064 or qae_13 = 4264 — the two circuits where phase kickback supplies the
entire advantage.

### Which v3 rules go where

| rule | destination | why |
|---|---|---|
| `pauli_frame_rotation_merge` | `floor/` | reproduces pyzx on qft_8/qpe_8/qae_13 exactly |
| `pauli_exponential_commutation_merge` | `floor/` | reproduces pyzx on hhl_8 exactly |
| `free_fermion_gaussian_resynthesis` | `accepted/` | original discovery (tfim_6 -60.8%), not a baseline |
| `and_ancilla_ccz_lowering_with_measured_uncompute` | `accepted/` | original |
| `bilinear_rank_resynthesis_karatsuba` | `accepted/` | original |
| `pauli_subalgebra_dimension_recompression` | `accepted/` | original |

Only baseline reimplementations are permanent. Original discoveries stay retireable under the
two-global-loop rule, so the floor never silently accumulates.

### 4.1 The pyzx floor already exists — move two files

From the P2 attempt log, `pauli_frame_rotation_merge` **alone** gives qft_8 2125->1577,
qpe_8 14569->11485, qae_13 6725->4527 — pyzx's numbers on three circuits, bit-identical. And
`pauli_exponential_commutation_merge` takes hhl_8 to 29205 = pyzx exactly. Those two files **are**
the pyzx floor; move them to `rules/floor/` with their measured evidence. Zero new implementation.

This also bounds how much of pyzx is worth reimplementing: pyzx's T win here is phase-gadget fusion,
which these rules do on an op list. Local complementation and pivoting mostly move CNOT count, not T
(measured: pyzx inflates cx qft_8 68->90, qpe_8 268->323, hhl_8 497->663, tfim_6 180->490). Do not
chase them.

### 4.2 The DPF floor — one pre-written card, no scouting

Do not make the scout rediscover Dyadic Phase Fixing. Write the card by hand in the exact scout
schema and hand it straight to the implementer. Contents: partition to width 4; for
theta in {pi, pi/2, ..., 2pi/2^kmax} greedily fix the Rz nearest a multiple of theta; re-instantiate
the remaining angles by least squares to minimise phase-aligned HS distance; accept if
<= budget/B; keep the lowest T. Source arXiv:2606.05397. With section 9's primitives this file is short.

### 4.2b The PKAC floor card — REQUIRED, gated on P5

A second pre-written card for **phase-gradient / PKAC lowering** is a required floor member, not an
optional extra: it is the sole source of DPF's advantage on qft_8 (1064 vs 2029 at k=3) and qae_13
(4264 vs 6915). Contents, reimplemented in Python over `v4.api` (never calling bqskit): prepare a
shared phase-gradient register of k_reg qubits; lower each fixed dyadic Rz with k <= k_reg onto it via
a Gidney adder (temporary-AND compute at 4 T per AND, measurement-based uncompute at 0 T); sweep
k_reg and keep the per-circuit minimum; send every remaining Rz to gridsynth at eps_rz.
`error_class='approx'`, `resource_class='measured'`. Source arXiv:2606.05397 and branch `greedy_ntro`
@ c04a3224.

It is **blocked until section 6.3's verifier change lands** — it needs ancillas together with
continuous angles, which `relaxed` cannot currently express. Our own measurement of the BQSKit
construction confirms why the contract must be `measured` and not `unitary`: at k = 3 the output is
exact (state error 2.6e-16, zero ancilla leak), but every k >= 4 path leaks ancilla population
(1/sqrt(2) on the 2-qubit k=4 cases, ~1.0 on the 3-qubit k=5 cases), because the temporary-AND
uncompute is measurement-based by construction.

Expected qubit cost, from the `ConvertToPKAC` code path: `n + 2*k_reg - 1` (+2 with catalysed
sqrt-T at k=4). Measured on qft_8 at K=7: 13 ancillas; qae_13 at K=10: 19 ancillas.

### 4.3 References as a translation layer, not paper summaries

`agent/references/` holds distilled notes in the scout's working directory. Each baseline move is
written as an operation on a `(name, qubits, angle)` op list, and moves with **no op-list analogue**
(local complementation, pivoting) are flagged as such so the scout does not burn attempts on them.
This buys variance reduction, not capability — the scout already has WebSearch and already proposed
Lie-subalgebra recompression unprompted. Lowest priority.

### 4.4 The trap

A floor tier silently changes what the scout sees. It reads current-T-with-book alongside the
baselines; if the floor contains pyzx-class fusion and DPF-class fixing but `scout.md` and `BOOK.md`
do not say so, it will keep proposing both and they will come back as "no improvement beyond the
book". **Update the prompt and regenerate BOOK.md in the same change as the floor tier.**

---

## 5. The loop

```python
book = floor_tier()                      # pyzx-class + DPF-class, never retired
while global_budget_remains():           # ONE global budget, not per-circuit quotas
  for A in CIRCUIT_ORDER:                # fixed, recorded as configuration
    cur_A, cost_A = optimize_memo(A, book, eps)        # keyed on (hash(book), A, eps)

    card = scout(residual=summary(cur_A),              # the circuit AFTER the book
                 fingerprint[A], book_digest, baselines[A], log[A])
    if prefilter(card): continue                       # deterministic, zero compute

    for attempt in (1, 2, 3):
        rule = implementer(card, feedback)
        if precondition_excludes(rule, A): feedback = IDEA;  continue   # free
        if not rule.trigger(cur_A):        feedback = IDEA;  continue   # ~ms
        res = check_on_target(rule, A, cur_A, cost_A, ledger, OpcodeBudget)
        if res.verified and res.improves:
            book = admit(rule, book, res); break
        feedback = classify(res)        # fire-and-fail => NARROW THE GUARD, keep the idea
  retire(book)                          # no accepted application in 2 global loops
```

One global loop = one pass over `CIRCUIT_ORDER`. The playbook is a single mutable object handed
along the chain: A either updates it or leaves it, B receives whatever it now is. A circuit's second
turn is where transfer happens — in loop 1 the first circuit only ever sees the floor.

### 5.1 Three mechanisms that remove the redundant computation

1. `optimize_memo` keyed on `(hash(book), circuit, eps)`: a given (book-state, circuit) pair is
   verified **once, ever** — not once per `test_rule` call, not once per attempt.
2. A candidate is applied to the **cached residual** `cur_A`, so `check_on_target` verifies only the
   candidate's own applications. v3 re-ran the whole book plus candidate over 5 circuits, 139 times.
3. The **full order-optimised re-run happens only on admission** (8 times in P2, not 139). During
   search the semantics are "new rule runs last"; admission restores the true order.

### 5.2 Admission must never regress the book

Because order matters (mult_4: 36 T gain-order vs 64 book-order) and because the P2 book is 6 T
worse on qft_8 than `pauli_frame_rotation_merge` alone, the admission re-run keeps
`min(book_order, gain_order, best_single_rule)` per circuit and **refuses any admission that raises
T on any circuit**. The solo results are cached and shared between the two orderings (v3 computed
them twice — 6 of 12 solo runs were literal duplicates).

### 5.3 Failure classification

| outcome | means | level | response |
|---|---|---|---|
| precondition excludes A | not applicable | — | free, not a rejection |
| trigger matches nowhere | precondition does not describe A | idea | scout retry |
| **trigger matches, rewrite fails** | **guard too broad** | **implementation** | **narrow it, keep the idea** |
| matched + verified, no T drop | idea does not pay here | idea | scout retry |
| exception / opcode budget hit | bug or runaway | implementation | fix; judge on the partial result |

---

## 6. Verification

### 6.1 Two orthogonal contract tags, replacing v3's single field

v3 has one `contract` in {exact, approx, relaxed}, which conflates error with resources. That caused
a real reporting error this session: DPF Synth bars were hatched as relaxed on circuits where K* = 3
and **0 ancillas** were used — i.e. unitary results mislabelled. Two independent tags fix it:

```python
error_class    in {'exact', 'approx'}                 # exact = 0 error; approx = charged to the ledger
resource_class in {'unitary', 'ancilla', 'measured'}  # no extra qubits | clean ancillas |0>->|0> |
                                                      # ancillas + mid-circuit measurement + feedforward
```

This covers your (a)/(b)/(c) and is strictly more informative: Gidney's temporary AND is
`exact` + `measured`; DPF angle-snapping is `approx` + `unitary`; PKAC is `approx` + `measured`.
The verifier dispatches on the pair, the scout reasons with it, the figures hatch on
`resource_class != 'unitary'`, and the qubit-count figure reads off the same field.

### 6.2 Certificates — the check a rule can prove

| certificate | check | cost | proof? |
|---|---|---|---|
| `algebraic` | rule supplies a witness; frozen checker re-derives it | **O(ops), no matrices** | **yes** |
| `exact_ring` | D[omega] equality over Z[omega,1/sqrt2] | sparse | yes (sampled above 2^14) |
| `numeric_block` | phase-aligned operator norm, width-bounded | `ops * 4**n` | bound; certified n <= 10 |
| `branch_kraus` | `K_m|x,0> = c_m|f(x),0>`, same `c_m` for all x, `sum|c_m|^2 = 1` | branch-wise exact | yes within branch budget |

The phase-folding class — which produced **every** admitted angle rule — is an exact identity on the
phase polynomial. Its witness is the affine parity label; the checker re-derives
`cx a,b: p[b] ^= p[a]`, `x a: c[a] ^= 1` over the Hadamard-free segment. O(ops). Today that same
rewrite costs a **48 ms full-width 256x256 matrix build** (120 of qft_8's 190 checks), and at 11-20
qubits the matrix check is a Haar-statevector *lower bound*, not certified. So this is ~100x cheaper
**and** upgrades the hot path from uncertified to proof.

### 6.3 The one frozen-file change

`circuitevolve/v2/verify.py::_norm_angle_gates` raises `NotExact` for any angle off the pi/4 grid, and
`relaxed` routes through it. So **ancillas + continuous rotations cannot be verified at all** — which
structurally forbids the phase-gradient / PKAC family, the one lever that closes the gap to DPF Synth.
8 of 9 P2 verification failures were exactly this. `branch_kraus` must accept a per-branch
operator-norm allowance.

**This invalidates the P1 planted-bug gate until it is re-run (4/4 decisions). That re-run is
mandatory before any v4 result counts.**

### 6.4 Cheap fixes on the same path

- `check_frozen()` **once per process**, not per `verify`: it re-reads and SHA-256s **52 files,
  299 KB** per call = **3.303 ms**, against 0.421 ms for the comparison it guards (87% of a window check).
- **Cache the reference unitary** in `circuit_check`: it rebuilds both sides every call; the reference
  is the same original circuit every time (110 ms of qpe_8's 283 ms = 39%).
- **Price before verify**: v3 verifies, then checks cost. qft_8 does 40 attempted applications for 19
  accepted; price is 1.4 ms, a whole-circuit check is 48 ms.
- **Memoise window checks** on `(normalise(old), normalise(new), k)`.
- NOT doing (measured, not a bottleneck): an incremental cost model. `J.measure` on hhl_8's 1101
  rotations is **1.4 ms** with a warm gridsynth cache.

---

## 7. The lever fingerprint

Deterministic, no LLM, computed once per (circuit, eps). This is what stops the scout rediscovering
pyzx — in P2 it saw only a gate histogram, proposed phase folding, and landed on pyzx's exact
T-count.

```python
LeverReport(
  # (a) fewer rotations — pyzx owns this
  parity_classes, foldable, foldable_remaining,
  # (b) cheaper angles — DPF Synth owns this
  dyadic_fraction: dict[int, float], fixable_at_k: dict[int, int],
  # (c) algebraic structure — nobody owns this
  generator_algebra_rank, free_fermion: bool,
  # (d) ancilla reconstruction — relaxed rules only
  ccz_count, shared_control_pairs,
  # attribution
  best_baseline, lever_consumed_by, residual)
```

Measured, and it discriminates:

| circuit | (a) foldable | (b) fixable at K* | (c) | winner |
|---|---|---|---|---|
| qft_8 | 19 (pyzx takes all) | **28 of 39 (71.8%)** | - | DPF Synth 1064 |
| qae_13 | 67 (pyzx takes all) | **82 of 119 (68.9%)** | - | DPF Synth 4264 |
| qpe_8 | 67 (pyzx takes all) | 0 | - | DPF Synth 7552 |
| hhl_8 | 131 (pyzx takes all) | 0 (N_Rz ~298 at every K) | - | DPF Synth 18701 |
| tfim_6 | **0** | **0** | **free fermion** | **ours 3354 (-60.8%)** |

tfim_6 is the thesis in one row: zero headroom in both baseline levers, and the only project win came
from lever (c). The fingerprint points there on attempt 1.

**Pre-filter** (free, before any code): reject a card whose lever has zero remaining headroom; whose
predicted gain exceeds the lever's computed upper bound; that duplicates an existing
`(lever, precondition)` signature; or that proposes to improve rotation synthesis (gridsynth is
within a small additive constant of optimal — zero headroom).

---

## 8. The error ledger — make the budget spendable

`scout.md` already defines approx as "charged to a budget, total <= eps/2 = 5e-4". Both accepted
approx rules hard-code `TOL = 1e-10` and never spend it — one five-millionth of the allowance.
DPF's whole advantage is that it *does* spend: snapping a far-off angle onto the dyadic grid is legal
only because error was paid for it, eps/B per block.

```python
ledger = Ledger(total=eps, rule_share=eps/2, synth_share=eps/2)   # per (circuit, eps)
ledger.draw(rule_name, amount) -> bool     # recorded in the admission json
```
Rules draw from a shared pool; the draw is recorded per rule per circuit; the reported bound is
`sum(draws) + N_Rz * eps_rz`. This gives v4 something no baseline has: **budget allocation across
rules becomes part of the search space.** DPF spends on a fixed greedy schedule; an LLM deciding
which rule gets which share of 5e-4 is new territory.

---

## 9. `v4/api/` — the main investment

Knowledge in the API is knowledge the implementer cannot get wrong. Knowledge in prose is knowledge
it must re-derive, under a budget, once per rule. Every expensive part of every good v3 rule was
machinery, not insight. Precedent: `and_compute` / `and_uncompute` are already API gadgets, and the
two rules built on them (`and_ancilla_ccz_lowering`, `bilinear_rank_resynthesis_karatsuba`) are among
the cleanest wins.

New primitives, in priority order:

| module | primitives | replaces hand-rolled code in |
|---|---|---|
| `phasepoly` | `labels(ops)` — affine parity label per wire over H-free segments | retired `phase_polynomial_rotation_merge` |
| `pauli` | general multi-qubit signed X/Y/Z exponentials + frame predicates (v3 has only Z-flavoured `is_z`/`commutes_with_z`) | `pauli_exponential_commutation_merge` |
| `blocks` | `partition(c, width=4)` dependency-contiguous | `rotation_count_minimal_block_refit` |
| `sim` | `unitary(ops, n)`, `hs_distance(U, V)` phase-aligned | several |
| `refit` | `least_squares(template, target, pinned)` | `pauli_subalgebra_dimension_recompression`, `free_fermion_gaussian_resynthesis` |
| `angles` | `dyadic(theta, kmax)` -> nearest k*pi/2^m + its distance | the DPF card (4.2) |
| `budget` | `draw(amount)` against the ledger | section 8 |
| `fermion` | Jordan-Wigner / Majorana map, Givens cascade | `free_fermion_gaussian_resynthesis` |

Rules may import only: stdlib, numpy, scipy, sympy, `v4.api`. Never pyzx, pytket, bqskit, qiskit,
or `circuitevolve` directly.

---

## 10. Caps — and which kind where

Four loops are provably bounded: the global budget; `attempt in 1..3`; `passes < pass_limit`; and the
inner re-trigger loop (an application is kept only on a **strict** lexicographic decrease in
(T, qubits, CX) — non-negative integers, well-ordered, so it terminates).

Two places are genuinely unbounded:

| what | cap | why this kind |
|---|---|---|
| a rule's `trigger` / `apply` | **opcode budget** via `sys.settrace` | deterministic, machine-independent, reproducible. A call-counter does not help if one call hangs inside itself. |
| an LLM subprocess | **wall clock + `--max-budget-usd`** | infrastructure, not science |

The governing principle:

> **Cap the LLM on wall clock and tokens. Never cap verification on wall clock.**

A timeout on an agent subprocess does not bias which rules are admitted — it retries or moves on.
A timeout on verification discards correct, verified, improving rules, which is exactly what the
300 s limit did.

---

## 11. Build order, each phase ending at a gate

| # | phase | gate |
|---|---|---|
| P0 | Scaffold `v4/`, import frozen v3 modules, `check_frozen` once per process, reference-unitary cache, price-before-verify, window memo, shared solo runs | the suite sweep reproduces v3's T-counts exactly, and is >= 5x faster. No number moves. |
| P1 | `optimize_memo` + declared preconditions + trigger-only pre-pass | the no-op `test_rule` probe drops from 7.7-12.6 min to < 60 s. Re-run the same probe for before/after. |
| P2 | Floor tier part 1: move the two pyzx-class rules to `floor/`, the other four to `accepted/`, regenerate `BOOK.md`, update `scout.md` | floor reproduces pyzx on qft_8/qpe_8/qae_13/hhl_8 to the T. |
| P3 | `v4/api/` primitives (section 9) + ledger (section 8) + two-axis contract tags + **DPF k<=3 floor card (4.2)** | the 6 v3 rules re-expressed against the new API verify identically; ledger draws recorded; **floor matches the best baseline on qpe_8 (7552) and hhl_8 (18701)**. |
| P4 | Certificate layer + algebraic witness for phase folding | `tests/` + acceptance suite pass; phase-folding checks are O(ops) and `certified=True`. |
| P5 | **Unfreeze `relaxed` -> `branch_kraus` with an error allowance** | **P1 planted-bug gate re-run, 4/4 correct.** Mandatory before any v4 result counts, and a hard prerequisite for the floor guarantee. |
| P6 | **PKAC floor card (4.2b)** + re-admit the two rules P2 timed out on | **FLOOR GUARANTEE MET: floor alone >= best baseline on all 5 circuits** (1577/7552/18701/4527/8560 or better); the two rules re-admit (qft_8 1417, hhl_8 24967). |
| P7 | Fingerprint + pre-filter + the loop (section 5) + opcode/LLM caps | one full global loop over the suite completes in < 2 h. |
| P8 | Run and report | per-circuit vs 4 baselines at eps 1e-3, hatched on `resource_class`, honest caveats. |

P0-P1 are mechanical and make the loop fast. P2-P3 are where the leverage is. P5 is the only
unfreeze. P7 is what makes it find something new.

### Known open risks
- DPF Synth is stochastic (9.8% seed spread at K=8); any "we beat DPF" claim needs its seed range.
- The algebraic-certificate checker is new frozen code — it must be covered by planted-bug tests of
  its own, or it becomes the weakest link in the chain it is meant to strengthen.
- Round-robin results depend on `CIRCUIT_ORDER`; fix it, record it, treat it as configuration.
