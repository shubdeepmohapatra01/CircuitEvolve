# v3 — Agentic rule book for circuit optimization (build spec for Claude Code)

Read this whole file before writing code. Build in phases; each phase ends at a gate you must pass
before starting the next. Phases P0 and P1 use NO LLM. Ask the user before deviating from anything here.

## 0. Goal

An LLM agent looks at a circuit, recognizes an optimization it knows (from training or a paper), and
writes it as a **rule**: a small Python file that code applies automatically. A frozen judge verifies
every application and measures the cost. Rules that pass are kept in a rule book; rules that fail are
recorded and dropped. The LLM never edits circuits by hand and never guesses whether something is
correct: the judge decides.

Success criteria:
- **DV angle circuits (qpe_8, hhl_8, qft_8, qae_13, tfim_6):** at least match the best baseline on each,
  in particular BQSKit-DPF on qpe_8 and hhl_8. tfim_6 is a control: nothing is expected to help.
- **DV reconstruction circuits (adders, multiplier, multi-controlled X):** beat every baseline on T-count.
  Extra ancilla qubits are allowed and must be reported (qubit-count figure).
- **CV-DV circuits:** fewer gates than Genesis at equal or smaller error with respect to the exact
  Hamiltonian evolution, at identical Trotter steps / time / truncation.
- Reconstruction rules may also fire on qpe/hhl. That is allowed and reported as such.

## 1. Ground rules

1. All new code lives in `v3/`. Do NOT edit anything outside `v3/` (import existing modules instead).
   `circuitevolve/v2/` is a different, earlier design; do not modify it.
2. No git operations (no branches, commits, resets). Undo = moving one rule file between status folders.
3. The judge is frozen (section 4). Rules and the agent may never edit judge files, inputs, baselines or
   the suite manifest. `v3/judge/FROZEN.sha256` lists their hashes; every tool checks it at start.
4. No LLM-based baselines. Baselines are TKET, pyzx, BQSKit-FT, BQSKit-DPF (DV) and Genesis (CV-DV).
5. Results are append-only (one JSON line per event); a corrected table is a new file.
6. Never compare numbers at different eps. Never report a relaxed (ancilla / measurement) result as
   unitary-preserving: such bars are hatched and labelled "relaxed".
7. Environments: repo venv / conda env `circuitevolve-dev` (DV); `experiments/bqskit_baselines/.venv-dpf`
   (bqskit-ft runs); conda env `cvdv-opt` (CV-DV sim + Genesis). CV-DV code is called via subprocess.

### Lesson from v2 tier 2 (read `results/v2/tier2/` report): why rules must be programs, not templates
v2 tier 2 let an LLM write pattern -> replacement templates (<= 4 qubits, few gates) applied to
pyzx-optimized circuits. Result: null. 0 of 8833 T-reducing short identities matched anywhere, because
the start circuits were already locally optimal and the remaining gains are non-local. Therefore in v3:
- a rule is an arbitrary deterministic **program** over the whole circuit (global passes, phase-polynomial
  methods, numerical procedures like fix-and-refit, ancilla reconstructions), not only a local template;
- our method starts from the SAME input as the baselines (not from pyzx output);
- relaxed contracts (clean ancillas, measurement + feed-forward) are allowed for reconstruction.

## 2. Folder layout

```
v3/
  SPEC.md                    this file
  suite/manifest.json        circuits, simple labels, source files, family, eps list   (frozen)
  suite/inputs/              copies of the input files (frozen)
  baselines/baselines.csv    one row per circuit x method x eps (frozen after P0)
  judge/                     verify + measure wrappers (frozen), FROZEN.sha256
  api/                       what rules may import: IR, Pauli frames, commutation, unitary sim,
                             refit (numerical re-instantiation), phase-polynomial helpers, cost
  runner.py                  applies a rule book to a circuit
  tools/test_rule.py         the ONLY command the implementer agent may run
  tools/admit.py             harness-side admission test; moves the file
  rules/candidates/          files being written by the agent
  rules/accepted/            admitted rules (one file each)
  rules/rejected/            rejected rules + reason JSON
  rules/retired/             rules later superseded
  rules/BOOK.md              generated index: name, status, kind, contract, where it helped
  agent/run.py               orchestrates scout -> implementer -> admit (subprocess `claude -p`)
  agent/prompts/scout.md, implementer.md
  results/                   append-only logs (events.jsonl, tokens.jsonl, runs/)
  report/                    figure scripts + figures
  tests/                     unit tests for judge, runner, admission, planted bugs
```

## 3. Benchmark suite (simple labels; manifest maps label -> source)

### 3a. DV angle (inputs = TKET FullPeepholeOptimise outputs already used by all baselines)
| label | source input | qubits |
|---|---|---|
| qft_8 | results/bqskit_baselines/stage1/inputs/qft_8_tket.qasm | 8 |
| qpe_8 | .../qpe_8_tket.qasm | 8 |
| hhl_8 | .../hhl_8_tket.qasm | 8 |
| qae_13 | .../qae_13_tket.qasm | 13 |
| tfim_6 | .../tfim_6_tket.qasm (control) | 6 |

Baselines: read from `results/bqskit_baselines/stage1/stage1_baselines_v2.csv`, column `t_count_canon`
(no reruns). Method -> arm: **TKET = B0** (naive reference), **pyzx = B1**, **BQSKit-FT = B2**,
**BQSKit-DPF = B3g** (the published-script arm B3 exceeds its eps by code accounting; B3g is the valid
DPF arm, total <= eps). Expected values (gate for P0 = reproduce exactly):

| label | eps | TKET | pyzx | BQSKit-FT | BQSKit-DPF |
|---|---|---|---|---|---|
| qft_8 | 1e-3 | 2391 | 1577 | 2391 | 2029 |
| qft_8 | 1e-5 | 3299 | 2219 | 3299 | 2866 |
| qpe_8 | 1e-3 | 14761 | 11485 | 14761 | 8020 |
| qpe_8 | 1e-5 | 19853 | 15651 | 19853 | 10391 |
| hhl_8 | 1e-3 | 35450 | 29205 | 35450 | 19443 |
| hhl_8 | 1e-5 | 47228 | 38987 | 47228 | 25043 |
| qae_13 | 1e-3 | 7821 | 4527 | 7821 | 6909 |
| qae_13 | 1e-5 | 11017 | 6361 | 11017 | 9237 |
| tfim_6 | 1e-3 | 8560 | 8560 | 8560 | 9600 |
| tfim_6 | 1e-5 | 11840 | 11840 | 11840 | 12400 |

### 3b. DV reconstruction (input = Toffoli-level logical circuit; every method decomposes it itself)
| label | source (benchmarks/nam_arith/logical/) | qubits | TKET (tket_fpo_logical) | pyzx (pyzx_fr) |
|---|---|---|---|---|
| adder_8 | adder_8.qasm | 24 | 361 | 173 |
| adder_6 | rc_adder_6.qasm | 14 | 59 | 47 |
| mult_4 | gf2^4_mult.qasm | 12 | 96 | 68 |
| mcx_10 | barenco_tof_10.qasm | 19 | 192 | 100 |
| modred_21 | mod_red_21.qasm | 11 | 107 | 73 |

TKET/pyzx values come from `results/v2/baselines_new.csv` (exact, eps 0). **The only new baseline runs in
this project:** BQSKit-FT (B2) and BQSKit-DPF (B3g) on these five, via
`experiments/bqskit_baselines/stage1/run_bqskit_arms.py` (env `.venv-dpf`), at eps 1e-3 (they are exact
Clifford+T inputs, so eps only matters if a pass introduces rotations). Record T-count and qubits.

### 3c. CV-DV (Genesis `*_small` instances; spec = Genesis' intermediate Trotter-step IR)
Labels: kerr_small, boseHubbard_small, z2Higgs_small, heisenberg_small, electronicVibration_small.
(hubbardHolstein_small excluded: its IR has non-unitary terms, see cvdv/results/P0_genesis_reproduction.md.)
Genesis is a BASELINE ONLY, never a pre-optimization step. Run `cvdv/scripts/run_genesis.py`
(env `cvdv-opt`) with 5 seeds and keep the best by total gates. Genesis seed-0 reference (cvdv/results/
compare_isas_small_nmax3.csv): kerr 453/142/595/3032, boseHubbard 76/42/118/461, z2Higgs 78/41/119/301,
heisenberg 184/136/320/1810, electronicVibration 566/305/871/5358 (1-op/2-op/total/duration).
Ours compiles from the same IR terms (the spec), never from Genesis' output.

Fixed for both Genesis and ours (store in manifest): Trotter step count r, total time t, term order,
Fock cutoff N (two cutoffs, results trusted only if they agree), probe states and seeds.

## 4. The judge (frozen; thin wrappers over existing, already-tested code)

| domain | verify | measure |
|---|---|---|
| DV exact / approx / relaxed | `circuitevolve/v2/verify.py::verify(candidate, reference, mode, eps)` (modes exact, approx, relaxed); local window checks via `circuitevolve/core/verifier.py` | T-count with BQSKit convention (`circuitevolve/core/metric.py`: gridsynth at eps_synth / N_Rz, pi/4 multiples exact), plus #rotations, #CNOT, #qubits |
| CV-DV | `cvdv/src/cvdv/verify.py::verify` (vs ordered Trotter product; ancilla wires must return to |0>/vacuum) | `cvdv/src/cvdv/metrics.py` (1-op, 2-op, total, duration — equals Genesis --stats) |

CV-DV error, two numbers per circuit and method:
- `err_trotter` = distance of the compiled circuit to the ordered product of the Trotter terms (synthesis error);
- `err_exact` = distance to exp(-i H t) of the full Hamiltonian at the same t and the same r (total error,
  includes Trotter error). Use process infidelity on the system subspace with ancillas required to return
  clean; same probes for every method.

DV error accounting (total eps per circuit): approximate rule applications are charged their measured
phase-aligned operator distance, capped at eps/2 in total; synthesis gets eps - spent, split over N_Rz.
Report the bound. (BQSKit-DPF uses a Hilbert-Schmidt threshold, which is up to sqrt(2^w) looser than our
operator norm on w-qubit blocks; keep ours, note it in the report.)

## 5. What a rule is

One file `v3/rules/<status>/<name>.py` exporting `RULE`:

```python
RULE = Rule(
    name="same_pauli_merge",
    domain="dv",                       # "dv" | "cvdv"
    kind="rewrite",                    # rewrite | procedure | reconstruction | resource
    contract="exact",                  # exact | approx | relaxed (clean ancillas / measurement allowed)
    source="textbook / paper ref",
    idea="one-paragraph statement of the identity and why it holds",
    trigger=find_matches,              # (circuit) -> list[Match]   pure, deterministic
    apply=apply_match,                 # (circuit, match) -> circuit  pure, deterministic
)
```
Rules may import only: python stdlib, numpy, scipy, sympy, and `v3.api`. They may NOT import pyzx,
pytket, bqskit or Genesis (otherwise "ours" would just be a baseline). `v3.api` exposes generic tools:
IR read/write, Pauli frames of rotations, commutation tests, small-unitary simulation, numerical
re-instantiation (`refit`, wrapping `circuitevolve/core/refit.py`), phase-polynomial extraction, cost.

## 6. Runner

`runner.optimize(circuit, book, eps)`: for each accepted rule in book order (structural/reconstruction
first, angle rules last), find matches, apply one at a time, verify each application with the judge,
keep it only if the cost drops (lexicographic: primary metric, then secondary), charge approx errors to
the ledger; repeat until no rule fires or a pass limit is hit. Primary metric: T-count (DV), total
gates then 2-op count (CV-DV). Output: circuit, cost, qubits, error bound, per-rule application log.

## 7. Admission test (`tools/admit.py`, run by the harness, never by the agent)

A candidate is admitted iff all hold:
1. the file imports only allowed modules and defines a valid `RULE`;
2. on EVERY suite circuit of its domain, every application verifies (zero failures; one failure anywhere
   = reject, with the failing circuit and location in the reason);
3. adding it to the book lowers the primary metric on at least one circuit beyond the current book
   (specialist rules are welcome: helping one circuit is enough);
4. runtime per circuit below a limit (default 120 s).
On admit: move to `rules/accepted/`, append to `rules/BOOK.md` (name, kind, contract, idea, circuits it
helped and by how much). On reject: move to `rules/rejected/` with `<name>.reason.json`.

`tools/test_rule.py <candidate.py>`: same checks as admission but read-only, returns JSON per circuit:
fired?, #applications, #verified, first failure (circuit, gate indices, qubits, distance or infidelity),
cost before/after, qubits before/after, error bound. Counts its own calls per attempt and refuses after 5.

## 8. The agent loop (the only place an LLM is called)

One attempt = scout -> implementer -> admit.

**Scout** (`claude -p --model claude-opus-5`, tools: Read, WebSearch, WebFetch; read access only to a
context folder). Input: a short circuit summary (gate histogram, #Toffoli / CCZ, #non-Clifford rotations
and angle histogram, repeated motifs, qubit count; for CV-DV the term list), the current BOOK.md, the
baselines for that circuit, and the log of earlier attempts on it. Output: ONE rule card as JSON: name,
domain, kind, contract, the exact identity or procedure, why it is correct (math), trigger in precise
terms, expected effect, source. No code.

**Implementer** (`claude -p --model claude-sonnet-5-5`, tools limited to Read, Write and Edit inside
`v3/rules/candidates/`, and Bash restricted to `python -m v3.tools.test_rule`). Input: the rule card,
`v3/api` docs, two accepted rule files as examples. Writes `v3/rules/candidates/<name>.py`, runs
test_rule (max 5), fixes implementation errors, stops. It must not change the idea; if the idea itself
fails it reports that and stops.

**Harness** runs admit. On reject: if the failure is implementation-level, one more implementer try; if
idea-level, the failure JSON goes back to the scout once. Then move on.
Budget: 10 attempts per circuit (configurable). Log tokens and cost per call (`--output-format json`).
Check every flag against the installed CLI (`claude --help`, version 2.1.274 here): `--model`, `--tools`,
`--allowedTools` / `--disallowedTools` (path-scoped Write/Edit, prefix-scoped Bash), `--permission-mode`,
`--add-dir`, `--append-system-prompt`, `--output-format`, `--max-budget-usd`.

The rule book starts EMPTY of LLM-found rules. Allowed seeds (hand-written, no LLM): for CV-DV only the
direct native-gate mappings needed to compile at all (a term that IS a native gate). Classify the rules in
`cvdv/rulebook/rules.py` and list which ones are direct mappings; LLM-harvested ones (e.g. R7, R8) are NOT
seeds.

## 9. Figures (`v3/report/`)

1. **DV angle T-count:** one panel per eps; per circuit 5 bars: TKET, pyzx, BQSKit-FT, BQSKit-DPF, ours.
2. **DV reconstruction T-count:** same 5 bars per circuit.
3. **Qubit count:** same layout for both DV families (shows ancillas added by reconstruction rules).
4. **CV-DV gate count:** per circuit, Genesis vs ours (total gates; 2-op as a second panel).
5. **CV-DV error:** per circuit, Genesis vs ours, `err_exact` (and `err_trotter` as a second panel), log scale.
Ours bars are hatched when the result uses a relaxed contract. Every figure has its numbers in a CSV.
Plus `rules/BOOK.md` and a token table (tokens and cost per admitted rule).

## 10. Phases and gates

**P0 — scaffold, judge, suite, baselines (no LLM).**
Build `v3/` layout, manifest, input copies, judge wrappers, FROZEN.sha256, runner (with an empty book it
must return the input unchanged), baselines.csv (DV angle from CSV; reconstruction TKET/pyzx from CSV +
the new BQSKit-FT/DPF runs; Genesis best-of-5 + its two errors). Baseline-only figures.
Gate: baselines.csv reproduces every number in section 3 exactly; empty-book run returns inputs unchanged
with error 0; judge hash check works.

**P1 — harness self-test (no LLM).** Hand-write four rules into `rules/candidates/` and run admit:
1. DV same-Pauli rotation merge (exact) -> must be ADMITTED (it helps at least qft_8/qpe_8/hhl_8);
2. CV-DV displacement merge D(a)D(b) = exp((a b* - a* b)/2) D(a+b) (exact up to global phase) -> ADMITTED
   if any suite circuit contains adjacent displacements, else reported as "never fires";
3. WRONG rule: merge a conditional and an unconditional displacement dropping the phase -> REJECTED
   (the phase is a relative qubit phase, not global);
4. planted bug: a correct merge that corrupts 1 match in 10 -> REJECTED.
Gate: 4/4 decisions correct. Then move these four to their final folders and record them as hand-written.

**P2 — LLM pilot.** Run `agent/run.py` over all 15 circuits, 10 attempts each. Log everything.
Report: rules admitted (by kind), per-circuit result vs the 4 baselines / Genesis, tokens per admitted rule,
and whether known ideas were found (dyadic phase fixing on qpe/hhl, Toffoli pairing / temporary AND on
adders, displacement merging on CV-DV).

**P3 — report.** Figures of section 9, BOOK.md, a one-page summary with honest caveats.

## 11. Do not
- edit frozen files or anything outside v3/; run git commands;
- let the agent run anything except test_rule; give it network access in the implementer role;
- start our method from pyzx/TKET-optimized output on reconstruction circuits or from Genesis output on CV-DV;
- average over the suite to judge a rule (one circuit is enough to admit);
- quote a number that is not in a results file.
