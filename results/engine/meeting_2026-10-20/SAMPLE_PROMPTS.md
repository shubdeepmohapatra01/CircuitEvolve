# Sample LLM calls at each stage (verbatim excerpts from committed run logs)

Every excerpt below is copied from an append-only run log; long prompts are clipped (marked `[… N lines omitted …]`, long lines end in `…`). Nothing was re-run to produce this file.

## 1. Reconstruction method: PROPOSER call (claude-opus-5-5)

Source: `results/engine/recon_campaign1/runs/recon_c1_dev_barenco_tof_5.jsonl`, call 1. The LLM sees the recognizer's structural summary (Toffolis, pairs, multi-controlled cascades), the toolbox, verifier feedback and the playbook rules, and returns a compilation PLAN that a deterministic compiler executes.

**Prompt (clipped):**
```
You choose a fault-tolerant COMPILATION STRATEGY for one logical reversible circuit (Toffoli level). A deterministic compiler executes your plan and an exact ve …

OBJECTIVE: minimise T-count (then qubits, then T-depth). Two separate leaderboards:
- EXACT: unitary-preserving on the same qubits (no measurement, no extra qubit, no zero-init promise).
- RELAXED: may use fresh clean ancillas, mid-circuit measurement + classically controlled fix-ups, and the declared zero-init promise; every ancilla must return …
THIS CALL TARGETS: RELAXED.

CIRCUIT barenco_tof_5: 9 qubits, 12 gates (ccx:12); classical reversible (x/cx/ccx + diagonal).
Naive cost: 84 T (7 per Toffoli, 12 Toffolis).
Declared zero-init qubits (benchmark contract, start in |0>): none.
QUBITS (q: Z=declared zero-init / first touch / R=restored to |0> at end / guessed role):
  q0:-/ccx-control/-/data; q1:-/ccx-control/-/data; q2:-/ccx-control/-/data; q3:-/ccx-control/-/data; q4:-/ccx-control/-/data; q5:-/ccx-control/-/data; q6:-/ccx …
TOFFOLIS (id: gate index, kind, controls -> target):
  T0:g0 ccx q4 q7->q8; T1:g1 ccx q3 q6->q7; T2:g2 ccx q2 q5->q6; T3:g3 ccx q0 q1->q5; T4:g4 ccx q2 q5->q6; T5:g5 ccx q3 q6->q7; T6:g6 ccx q4 q7->q8; T7:g7 ccx q …
PAIRS (same Toffoli repeated, controls unchanged in between; class: clean = declared-zero target, |0> before, not written between; mirror = target only read bet …
  P0 = T3+T9 (g3..g9) target q5 controls q0 q1: mirror
  P1 = T4+T8 (g4..g8) target q6 controls q2 q5: mirror
  P2 = T5+T7 (g5..g7) target q7 controls q3 q6: mirror
UNPAIRED TOFFOLIS: T0, T1, T2, T6, T10, T11
MULTI-CONTROLLED-X CASCADES (middle Toffoli + enclosing pairs):
  M0: C5X controls ['q0', 'q1', 'q2', 'q3', 'q4'] -> q8, middle T6, pairs ['P2', 'P1', 'P0'], work qubits ['q7', 'q6', 'q5'] (dirty/borrowed)
REPEATED BLOCKS (gate pattern with relabelled qubits, count):
  [ccx(0,1,2) ccx(3,4,1) ccx(5,6,4) ccx(7,8,6) ccx(5,6,4) ccx(3,4,1)] x2 at gates [0, 6]
  [ccx(0,1,2) ccx(3,4,1) ccx(5,6,4) ccx(3,4,1) ccx(0,1,2)] x2 at gates [1, 7]
  [ccx(0,1,2) ccx(3,4,1) ccx(0,1,2) ccx(5,2,6)] x2 at gates [2, 8]
  [ccx(0,1,2) ccx(3,2,4) ccx(5,4,6)] x2 at gates [3, 9]
ROTATIONS (non-Toffoli phase gates): {'t_like': 0, 's_like': 0, 'z': 0}
SUBROUTINE GUESSES: M0 is a C5X built from an AND ladder on borrowed (dirty) work qubits
NORMALIZED LOGICAL GATES (g<index>):
  g0 ccx q4 q7 -> q8; g1 ccx q3 q6 -> q7; g2 ccx q2 q5 -> q6; g3 ccx q0 q1 -> q5; g4 ccx q2 q5 -> q6; g5 ccx q3 q6 -> q7; g6 ccx q4 q7 -> q8; g7 ccx q3 q6 -> q7 …

TOOLBOX (tier1-toolbox-v1). Routes: name [applies to] (verification mode; T cost): description
- toffoli_7T [T] (exact; 7 T): standard exact Toffoli/CCZ decomposition (default for unnamed Toffolis)
- relative_phase_toffoli [P/Ti+Tj] (exact; 4 T each, 8 T per pair): Maslov RCCX (Toffoli up to a diagonal phase). ONLY valid on a PAIR whose second member cance …
- temporary_and [P/Ti+Tj] (relaxed; 4 T per pair (compute 4 T, uncompute 0 T by X-measurement + CZ fix-up)): Gidney temporary AND. Default: computed directly in …
- clean_and [T] (relaxed; 4 T, no measurement): compute-only Gidney AND (no uncompute) into a target that is a declared zero-init qubit and |0> just before this …
- jones_toffoli [T] (relaxed; 4 T + 1 fresh ancilla + 1 measurement): Jones 2013: AND into a fresh clean ancilla (4 T), cx/cz(ancilla, target), measurement-base …
- ancilla_mcx [M] (relaxed; 4 T per work AND, middle 4 T (jones) or 7 T): multi-controlled X cascade: every enclosing pair -> temporary_and (direct if clean, el …
- barenco_mcx [M] (exact; 8 T per enclosing pair, middle 7 T): multi-controlled X cascade kept unitary: enclosing pairs -> relative_phase_toffoli, middle -> tof …
- custom [T/P/Ti+Tj] (auto; count of t/tdg in the gate list): your own construction for ONE element in the gate DSL (Clifford+T + measurement + feed-forward).
Global pass after routing (applied to every measurement-free segment, kept only where it lowers T): pyzx, tket, none, pyzx_then_tket.
Custom gate DSL, one gate per string: 'h|s|sdg|t|tdg|x|z q<i>', 'cx|cz q<i>, q<j>', 'measure q<i> -> c<k>', 'if(c<k>) <gate>'; a<k> = fresh clean ancilla local  …

TECHNIQUE CARDS (index; ask for any by name with "request_cards"):
| # | card | pattern | T cost (vs 7 T Toffoli) | ancilla / meas. | verification |
   [… 94 lines omitted …]
**Citation.** A. Barenco, C. H. Bennett, R. Cleve, D. P. DiVincenzo, N. Margolus, P. Shor, T. Sleator,
J. Smolin, H. Weinfurter, "Elementary gates for quantum computation", *Phys. Rev. A* 52, 3457 (1995),
doi:10.1103/PhysRevA.52.3457, arXiv:quant-ph/9503016.

REFERENCE POINTS: naive 84 T. Best classical EXACT T-count on record for this circuit (pyzx / TKET / Nam et al. / published optimizers, unitary-preserving): .

BEST VERIFIED SO FAR (this circuit):
- exact: none yet
- relaxed: none yet

RECENT RESULTS (newest last):
- none yet

Reply with ONE JSON object and nothing else:
{"target": "relaxed", "decisions": [{"element": "...", "route": "...", ...}], "global_pass": "...", "request_cards": [], "rationale": "<= 3 sentences"}
Unnamed Toffolis use toffoli_7T. Prefer changing something that has not been tried; do not resubmit a plan already listed above.

PLAYBOOK RULES (apply where relevant):
- [seed 2026-10-18 tier-1 toolbox] Relative-phase Toffoli pairing (Maslov RCCX): a mirror pair (same Toffoli repeated, target only READ in between) can use the  …
- [seed 2026-10-18 literature harvest] Ancilla-vs-T tradeoff for multi-controlled gates: best known k-control X is 4k-4 T using k-1 CLEAN ancillas (temporary-AN …
- [seed 2026-10-18 tier-1 toolbox] Clean-AND compute-only: a Toffoli whose target is a declared zero-init qubit still |0> at that point is a pure AND - 4 T, no  …
- [seed 2026-10-18 tier-1 routing lesson] Mirror pair writing into a declared-zero target => temporary-AND: when the recognizer shows a pair whose target is a d …
- [seed 2026-10-18 literature harvest] Compute/uncompute asymmetry: computing a temporary AND costs 4 T but UNcomputing it costs 0 T (X-basis measurement + clas …
- When the parent is already a relaxed plan at the floor, do not switch relaxed routes to exact ones (temporary_and/jones -> RCCX/Barenco). That raises T (4 ->  …
- Floor check BEFORE proposing, measured against the CURRENT parent, not the original baseline. Relaxed bound = 4 T per compute/uncompute pair + 4 per unpaired  …
```

**LLM response (verbatim):**
```
{"target": "relaxed", "decisions": [{"element": "M0", "route": "ancilla_mcx", "middle": "jones"}, {"element": "T0", "route": "jones_toffoli"}, {"element": "T1", "route": "jones_toffoli"}, {"element": "T2", "route": "jones_toffoli"}, {"element": "T10", "route": "jones_toffoli"}, {"element": "T11", "route": "jones_toffoli"}], "global_pass": "pyzx_then_tket", "request_cards": [], "rationale": "The C5X cascade M0 sends its three mirror pairs (P0, P1, P2) to temporary ANDs via fresh ancillas, since there are no declared-zero targets, at 4 T each, and its middle Toffoli T6 to Jones at 4 T. The five remaining unpaired Toffolis each take a 4-T Jones gadget, giving 36 T total, which meets the relaxed per-element bound of 4 T per pair plus 4 T per unpaired Toffoli. A global pyzx_then_tket pass runs on the measurement-free segments in case it trims further."}
```

**Verifier / loop decision:** best so far -> ACCEPTED, T 84 -> 36 (exact relaxed verifier).

## 2. Reconstruction method: REFLECTOR call (claude-sonnet-5-5)

Source: same log, call 9. The reflector sees accepted improvements (with anatomy), recent rejections with the verifier's reason, and the current rules with their A/B statistics; it may add / edit / retire at most 3 rules.

**Prompt (clipped):**
```
You maintain a playbook of short lessons that is shown to a program-proposing model.



Current playbook:
  R1 [candidate; shown 25; pass with 20/20, without 27/27; improving prompts with 5/25, without 8/31] [seed 2026-10-18 tier-1 toolbox] Gidney 2018 temporary AND …
  R2 [candidate; shown 25; pass with 22/22, without 25/25; improving prompts with 5/25, without 8/31] [seed 2026-10-18 tier-1 toolbox] Jones Toffoli / measureme …
  R3 [candidate; shown 31; pass with 26/26, without 21/21; improving prompts with 8/31, without 5/25] [seed 2026-10-18 tier-1 toolbox] Clean-AND compute-only: a …
  R4 [active; shown 50; pass with 6/6, without 2/2; improving prompts with 6/8, without 0/6] [seed 2026-10-18 tier-1 toolbox] Relative-phase Toffoli pairing (Ma …
  R5 [candidate; shown 23; pass with 20/20, without 27/27; improving prompts with 5/23, without 8/33] [seed 2026-10-18 tier-1 routing lesson] Mirror pair writin …
  R6 [candidate; shown 24; pass with 20/20, without 27/27; improving prompts with 6/24, without 7/32] [seed 2026-10-18 tier-1 toolbox] MCX cascades: an unpaired …
  R8 [candidate; shown 24; pass with 22/22, without 19/19; improving prompts with 6/24, without 3/20] [seed 2026-10-18 literature harvest] Compute/uncompute asy …
  R9 [active; shown 27; pass with 8/8, without 15/15; improving prompts with 4/8, without 3/17] [seed 2026-10-18 literature harvest] Ancilla-vs-T tradeoff for m …
  R10 [candidate; shown 15; pass with 14/14, without 27/27; improving prompts with 3/15, without 6/29] [seed 2026-10-18 literature harvest] Floor awareness: a m …
  R13 [candidate; shown 16; pass with 16/16, without 17/17; improving prompts with 2/16, without 1/20] When the parent is already a relaxed plan at the floor, d …
  R15 [candidate; shown 11; pass with 10/10, without 7/7; improving prompts with 2/11, without 0/7] Floor check BEFORE proposing, measured against the CURRENT p …
  R16 [candidate; shown 2; pass with 2/2, without 7/7; improving prompts with 0/2, without 2/8] Plans must cover every occurrence: the accepted plan used x26 fo …
  R17 [candidate; shown 4; pass with 4/4, without 5/5; improving prompts with 1/4, without 1/6] Floor check BEFORE proposing, against the CURRENT parent (after  …

Search statistics since the last update: {"proposal_calls": 8, "reflect_calls": 0, "llm_errors": 0, "declined": 0, "candidates": 7, "parse_errors": 1, "verified …

Accepted improvements (parent -> child):
# fitness 84 -> 36
## parent

## child
plan[T0x13, T1x13, T10x13, T11x13, T2x13, T3x26, T4x26, T5x26, T6x13, T7x26, T8x26, T9x26]
# ANATOMY: action= mode=relaxed distance=0.00e+00 charge=0.00e+00 primary 84 -> 36
rules shown in this prompt: R3, R5, R8, R13, R15

# fitness 36 -> 16
## parent

## child
plan[T0x6, T1x6, T10x6, T11x6, T2x6, T3x6, T4x6, T5x6, T6x6, T7x6, T8x6, T9x6]
# ANATOMY: action= mode=relaxed distance=0.00e+00 charge=0.00e+00 primary 36 -> 16
rules shown in this prompt: R2, R6, R8, R13, R15, R17

Recent rejections with the exact verifier's reason:
# rejected: plan[T0x10, T1x10, T10x10, T11x10, T2x10, T3x10, T4x10, T5x10, T6x10, T7x10, T8x10, T9x10]: rejected: no improvement (t_count 36 -> 84) (x5 since la …
plan[T0x10, T1x10, T10x10, T11x10, T2x10, T3x10, T4x10, T5x10, T6x10, T7x10, T8x10, T9x10]

Propose at most 3 changes that would help the proposer write programs that pass the
verifier and score better. Prefer specific, checkable lessons (a wiring pattern, a precondition that is often
violated, a phase fix-up that is needed) over generic advice. Do not restate an existing rule. Each rule at most
400 characters, in the same role and gate names as the programs above.
Answer with one ```json block containing a list of objects, each one of:
  {"op": "add", "text": "..."}
  {"op": "edit", "id": "R3", "text": "..."}   (creates a candidate that replaces R3 if it proves better)
  {"op": "retire", "id": "R3", "why": "..."}
An empty list is a valid answer.
```

**Reflector response (clipped):**
```
```json
[
  {
    "op": "edit",
    "id": "R16",
    "text": "Plan multiplicities must match the CURRENT parent's per-type occurrence counts (accepted: x13/x26 mix at 84->36, then x6 for all 12 types at 36->16 …
  },
  {
    "op": "retire",
    "id": "R17",
    "why": "Near-verbatim duplicate of R15 (same floor check against the current parent, same bounds, same NONE answer). Keeping both wastes prompt space."
  },
  {
    "op": "add",
    "text": "Re-read the parent's t_count before every proposal. Accepted children cut it 84 -> 36 -> 16, so the baseline in the task text is stale. A plan that …
  }
]
```
```

**Applied deltas:** [['edit', 'R18'], ['retire', 'R17'], ['add', 'R19']] (new rules enter as CANDIDATES; promotion only via A/B evidence).

## 3. Angle method: PROPOSER call (claude-opus-5)

Source: `results/engine/angle_campaign1/runs/ac1_dev_qft_8_A_e3.jsonl`, call 2. The LLM sees ONE window (<= 4 qubits, <= 40 gates) of the TKET-optimized circuit, its T-cost, its error allowance, playbook rules and recent feedback, and returns up to 3 replacement windows in a literal text format.

**Prompt (clipped):**
```
You are optimizing a fault-tolerant quantum circuit compiled to Clifford+T. You get one WINDOW of the
circuit (a sub-circuit on 4 local qubits q0..q3) and propose a cheaper replacement that implements the same
4-qubit unitary up to global phase, within an error allowance.

Cost model (lower is better, compared lexicographically): total T-count of the whole circuit, where
  * t / tdg cost 1 T; h, s, sdg, x, z, cx, cz are free; rz at a multiple of pi/4 is exact (odd multiples = 1 T);
  * every other rz is synthesized by gridsynth at eps_rz = 2.326e-05, costing about 3*log2(1/eps_rz) T
    (~46 T each here); removing a rotation also loosens eps_rz for all others; error budget you spend is
    taken from synthesis, so a rewrite must save more T than it costs the other rotations.
So the main gains are FEWER rotations that need synthesis, then fewer t/tdg. Merely changing an angle
to a different non-pi/4 value is not counted as an improvement.

Acceptance (decided by an exact/numerical verifier, not by you): phase-aligned operator-norm distance
between the original and the replacement window <= allowance = 6.250e-05. Clifford+T windows are checked exactly.

Two actions (you may mix them; at most 3 blocks in total, best first):
 A. EXACT REWRITE - a full replacement window in a ```window block (gates h s sdg x z t tdg cx cz rz(angle) on
    q0..q3; `cx a b` = control a, target b; angles as decimals or k*pi/m). Useful facts: rz on the CONTROL of
    cx commutes with it; x on the TARGET commutes with it; rz(a) rz(b) = rz(a+b) on one wire; a cx pair
    conjugating an rz moves the rotation to a wire parity; h rz(a) h = rx(a).
 B. FIX-AND-REFIT - a ```fix block naming rotations of this window by op index and a target value each:
        ```fix
        op 7 -> pi/4
        op 12 -> 0
        ```
    Targets: 0 (delete), a multiple of pi/4 (exact, free or 1 T), or 2*pi*m/2^k with k <= 4 (pi/8 multiples are
    still synthesized here, so they save nothing by themselves). A numerical optimizer then re-fits ALL OTHER
    non-pi/4 rotations of the window to stay as close as possible to the original unitary; the verifier
    checks the refitted window against the allowance. A fix only survives if the remaining rotations can
    absorb the change - e.g. another rotation acting on the same wire or the same cx-parity, or a set of
    rotations whose combined effect is redundant. A rotation with nothing to absorb it fails unless its
    plain snap distance (table) is itself within the allowance. Fixing several rotations at once is allowed.

Window (time order, top to bottom; angles reduced to [-pi, pi]; `# op i` = index for fix blocks):
```window
cx q3 q2
tdg q2
cx q3 q2
t q2
cx q3 q1
rz(-0.3926990816987246) q1  # op 5
h q2
rz(1.3744467859455345) q2  # op 7
cx q3 q1
rz(0.39269908169872414) q1  # op 9
cx q3 q0
rz(-0.1963495408493614) q0  # op 11
cx q2 q1
tdg q1
cx q3 q0
   [… 18 lines omitted …]
Two rotations with the same P letters merge (same sign: angles add; opposite sign: subtract) when every
rotation between them has a P that COMMUTES with theirs (two Paulis commute iff they differ, both non-I, on an
even number of qubits); a fix of one of them to 0 is then refitted exactly. Different P letters do not merge.
  op 5 on q1: rz(-0.3926990817) | -1*pi/4 | 3.927e-01 | 1.960e-01 | 50 | P=+IZIZ
  op 7 on q2: rz(1.374446786) | 2*pi/4 | 1.963e-01 | 9.814e-02 | 50 | P=+IIXI
  op 9 on q1: rz(0.3926990817) | 0*pi/4 | 3.927e-01 | 1.960e-01 | 50 | P=+IZII
  op 11 on q0: rz(-0.1963495408) | 0*pi/4 | 1.963e-01 | 9.814e-02 | 50 | P=+ZIIZ
  op 15 on q0: rz(0.5890486225) | 1*pi/4 | 1.963e-01 | 9.814e-02 | 48 | P=+ZIII
  op 19 on q0: rz(-0.3926990817) | -1*pi/4 | 3.927e-01 | 1.960e-01 | 50 | P=+ZIXI
  op 21 on q1: rz(1.178097245) | 2*pi/4 | 3.927e-01 | 1.960e-01 | 50 | P=+IXII
  t/tdg gates (rotations by +-pi/4, cost 1 T each): op 1: +IIZZ, op 3: +IIZI, op 13: +IZXI, op 17: +IZII, op 24: +ZXII, op 26: +ZIII, op 28: +XIII
Window T-cost now: 355 T (7 rotation(s) to synthesize, 7 explicit T).
Lessons from earlier verifier feedback on this task (hints for proposing; scoring and verification are unchanged):
  - A 'fix' proposal that removes a single rz without compensating for the Clifford gates around it on the same qubit will fail the operator-norm verifier; trac …
  - When zeroing an rz inside an sdg/h/.../h/s wrapper, also check the immediately preceding rz on the same qubit: a valid fix may require renegating it (theta  …
  - Do not pattern-match 'zero the leading rz(q2)/rz(q1)/rz(q0) gates before the cx-chain' from past accepted fixes: those angles must individually be near 0 mo …
  - A 't q_b' ... 'tdg q_b' pair that sandwiches a 'cx q_a q_b' in between is NOT a cancelling pair even though t/tdg are inverses: cx changes the effective ope …
  - Before proposing op->0 on any rz (leading or not), numerically compute angle mod 2*pi yourself -- never infer zero-ability from a nearby accepted fix on a d …
  - [seed 2026-10-18 FTQC primer] Two rz with the SAME Pauli frame P (shown per rotation in the prompt) merge into one rz with the summed angle when every gate  …
  - [seed 2026-10-18 FTQC primer] Snap rz(theta) to the nearest pi/4 multiple ONLY if 2|sin(delta/4)| <= allowance AND the saved gridsynth word (roughly 10-60 T …
  - [seed 2026-10-18 FTQC primer] Never propose rz -> 0 unless 2|sin(theta/4)| <= allowance for THAT rotation, or the rest of the window is refit to compensate; …
  - [seed 2026-10-18 literature harvest] Rotations are pi/4-parity-phase gadgets: two rz merge whenever their PARITIES agree, not only when they sit on the same …
  - [seed 2026-10-18 literature harvest] In a Hadamard-free stretch the T-count is the number of DISTINCT odd parities in the phase polynomial. A candidate that …

Keep the reasoning short. If you see no valid improvement, reply NONE.
```

**LLM response (clipped):**
```
**Analysis (short).** No two *synthesized* rotations share a Pauli frame, and every snap distance (≥9.8e-2) is far above the allowance, so the 7 gridsynth rotat …

- op 9 `rz(+π/8)` and op 17 `t q1` are both **P=+IZII**; intermediates op 11 (ZIIZ), op 13 (IZXI) commute with IZII → exact merge, angle 0.3927+π/4 = 3π/8.
- op 15 `rz(+3π/16)` and op 26 `t q0` are both **P=+ZIII**; intermediates op 17 (IZII), 19 (ZIXI), 21 (IXII), 24 (ZXII) all commute with ZIII → exact merge, ang …

Both merges are charge-0 (exact Clifford+T identity), so 355 T → 353 T, still 7 synthesized rotations.

```window
cx q3 q2
tdg q2
cx q3 q2
t q2
cx q3 q1
rz(-0.3926990816987246) q1
h q2
rz(1.3744467859455345) q2
cx q3 q1
rz(1.1780972450961724) q1
cx q3 q0
rz(-0.1963495408493614) q0
cx q2 q1
tdg q1
cx q3 q0
rz(1.3744467859455345) q0
cx q2 q1
cx q2 q0
rz(-0.3926990816987246) q0
h q1
rz(1.1780972450961724) q1
cx q2 q0
cx q1 q0
tdg q0
cx q1 q0
h q0
t q0
```

Fallbacks (each a single merge only, in case one of the two frame-pushes is rejected):

```window
   [… 50 lines omitted …]
rz(-0.3926990816987246) q0
h q1
rz(1.1780972450961724) q1
cx q2 q0
cx q1 q0
tdg q0
cx q1 q0
h q0
t q0
```
```

**Verifier / loop decisions per candidate:**
```
candidate 1: rejected: no improvement (T 2115 -> 2115, rz 43 -> 43)
candidate 2: best so far
candidate 3: rejected: no improvement (T 2115 -> 2116, rz 43 -> 43)
```

Accepted: T 2115 -> 2114, charged distance 1.20e-15 (approximate mode, within the window allowance).

## 4. Angle method: REFLECTOR call (claude-sonnet-5-5)

Source: same log, call 9.

**Prompt (clipped):**
```
You maintain a playbook of short lessons that is shown to a program-proposing model.

The proposer rewrites windows (<= 4 qubits, <= 40 gates) of a Clifford+Rz circuit to lower its T-count under gridsynth synthesis at eps_rz = eps_synth / N_Rz; a …

Current playbook:
  R3 [active; shown 164; pass with 3/3, without 0/4; improving prompts with 3/37, without 0/53] A 'fix' proposal that removes a single rz without compensating f …
  R15 [candidate; shown 28; pass with 3/9, without 10/11; improving prompts with 0/28, without 3/50] When simplifying rz(theta), first reduce theta into (-pi,pi …
  R16 [candidate; shown 39; pass with 7/9, without 6/11; improving prompts with 1/39, without 2/39] A near-miss rejection like 'op 24->0: distance 2.330e-04' (j …
  R18 [candidate; shown 26; pass with 6/7, without 6/10; improving prompts with 1/26, without 1/33] Repeated 'cx qA q3 / sdg q3 / h q3 / rz(theta) q3 / h q3 / s …
  R19 [candidate; shown 27; pass with 9/12, without 3/5; improving prompts with 2/27, without 0/32] When zeroing an rz inside an sdg/h/.../h/s wrapper, also che …
  R21 [candidate; shown 30; pass with 3/4, without 9/12; improving prompts with 1/30, without 1/19] Do not pattern-match 'zero the leading rz(q2)/rz(q1)/rz(q0)  …
  R22 [candidate; shown 21; pass with 9/11, without 3/4; improving prompts with 2/21, without 0/18] A 't q_b' ... 'tdg q_b' pair that sandwiches a 'cx q_a q_b'  …
  R23 [candidate; shown 13; pass with 0/1, without 12/14; improving prompts with 0/13, without 2/26] Before proposing op->0 on a leading rz(q_k) preceding a cx- …
  R24 [candidate; shown 18; pass with 3/3, without 9/12; improving prompts with 1/18, without 1/21] When reducing a chain of rz(theta) on the same qubit separat …
  R25 [candidate; shown 19; pass with 6/7, without 6/6; improving prompts with 1/19, without 1/10] Rejected twice verbatim: 'fix op 3->0, op 7->0, op 11->0' (di …
  R27 [candidate; shown 16; pass with 6/7, without 6/6; improving prompts with 1/16, without 1/13] Before proposing op->0 on any rz (leading or not), numericall …
  R28 [candidate; shown 3; pass with 6/6, without 6/6; improving prompts with 0/3, without 2/6] A 'cx qA qB / rz(theta) qB / cx qA qB' block is only a no-op/sim …
  R29 [candidate; shown 7; pass with 9/9, without 3/3; improving prompts with 1/7, without 1/1] [seed 2026-10-18 FTQC primer] Two rz with the SAME Pauli frame P …
  R30 [candidate; shown 5; pass with 9/9, without 3/3; improving prompts with 1/5, without 1/3] [seed 2026-10-18 FTQC primer] A gate between two rz preserves th …
  R31 [candidate; shown 2; pass with 3/3, without 9/9; improving prompts with 0/2, without 2/6] [seed 2026-10-18 FTQC primer] If two equal-P rotations straddle  …
  R32 [candidate; shown 3; pass with 6/6, without 6/6; improving prompts with 1/3, without 1/5] [seed 2026-10-18 FTQC primer] Snap rz(theta) to the nearest pi/4 …
  R33 [candidate; shown 3; pass with 6/6, without 6/6; improving prompts with 1/3, without 1/5] [seed 2026-10-18 FTQC primer] Adjacent same-qubit pi/4 diagonals …
  R34 [candidate; shown 3; pass with 6/6, without 6/6; improving prompts with 1/3, without 1/5] [seed 2026-10-18 FTQC primer] Never propose rz -> 0 unless 2|sin …
  R35 [candidate; shown 4; pass with 6/6, without 6/6; improving prompts with 0/4, without 2/4] [seed 2026-10-18 FTQC primer] Candidates may differ from the ori …
  R36 [candidate; shown 1; pass with 0/0, without 12/12; improving prompts with 0/1, without 2/7] [seed 2026-10-18 FTQC primer] Change ONE thing per candidate ( …
  R37 [candidate; shown 4; pass with 9/9, without 3/3; improving prompts with 1/4, without 1/4] [seed 2026-10-18 literature harvest] Rotations are pi/4-parity-p …
  R38 [candidate; shown 4; pass with 6/6, without 6/6; improving prompts with 2/4, without 0/4] [seed 2026-10-18 literature harvest] In a Hadamard-free stretch  …

Search statistics since the last update: {"proposal_calls": 8, "reflect_calls": 0, "llm_errors": 0, "declined": 0, "candidates": 12, "parse_errors": 4, "verifie …

   [… 156 lines omitted …]
rz(1.3744467859455345) q0
cx q2 q1
cx q2 q0
rz(-0.3926990816987246) q0
h q1
rz(1.1780972450961724) q1
cx q2 q0
cx q1 q0
tdg q0
cx q1 q0
h q0
t q0

Propose at most 3 changes that would help the proposer write programs that pass the
verifier and score better. Prefer specific, checkable lessons (a wiring pattern, a precondition that is often
violated, a phase fix-up that is needed) over generic advice. Do not restate an existing rule. Each rule at most
400 characters, in the same role and gate names as the programs above.
Answer with one ```json block containing a list of objects, each one of:
  {"op": "add", "text": "..."}
  {"op": "edit", "id": "R3", "text": "..."}   (creates a candidate that replaces R3 if it proves better)
  {"op": "retire", "id": "R3", "why": "..."}
An empty list is a valid answer.
```

**Reflector response (clipped):**
```
```json
[
  {
    "op": "add",
    "text": "Both accepted fixes (T-1, distance ~1e-15) absorbed an explicit t/tdg into a non-pi/4 rz of the SAME Pauli frame: delete the partner rz, replace th …
  },
  {
    "op": "add",
    "text": "Do not move +/-pi/4 into an rz whose frame differs from the t/tdg being deleted. Rejected 10x as 'no improvement (T 2115->2115)': rz(0.5890)->rz(1. …
  },
  {
    "op": "retire",
    "id": "R23",
    "why": "Duplicates R21/R27/R34 (compute angle mod 2*pi before op->0). Only 1 pass with it, 0/13 improving prompts, no new content."
  }
]
```
```

**Applied deltas:** [['add', 'R39'], ['add', 'R40'], ['retire', 'R23']]
