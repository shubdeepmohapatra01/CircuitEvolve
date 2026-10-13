# Test scope and build plan: a harness for LLM-discovered relaxed-spec circuit constructions

*Written 2026-10-06. To be executed in the user's experiment repository (path to be granted).
Builds on `pipeline_overview.md` and `ftqc_optimization_primer.md`.*

## 1. The question the first experiment answers

> Starting from a naive ripple-carry adder, can an LLM-in-the-loop search, filtered by an exact verifier
> of a **relaxed specification** (clean ancillas, measurement + feed-forward allowed), find a
> construction with **fewer than 8n T gates** - the floor that exact-unitary optimization (pyzx) reaches -
> and ideally rediscover the ~4n Gidney adder? And does the LLM loop do better than (a) a classical
> mutation search and (b) simply asking the LLM once?

Why this test:
- **Known answer.** The target (~4n) is published, so success is checkable.
- **Measured gap.** 14n (naive) -> 8n (pyzx, measured) -> ~4n (relaxed spec). The 8n -> 4n gap is
  unreachable by any exact-unitary method, so finding it requires exactly the capability we claim.
- **Cheap, exact verification** at small n, with a generalization check across n.
- **Contamination is testable.** Gidney's adder is in the LLM's training data, so the test design must
  separate "retrieved" from "found by search" (section 4).

## 2. The key design decision: what language the candidates are written in

What the search can discover depends on the intermediate representation (IR) it writes in.

| IR tier | Primitives available to candidates | What can be discovered | Verifier |
|---|---|---|---|
| **A (easy)** | X, CNOT, Toffoli, plus `and_compute` (4 T) and `and_uncompute_mbu` (0 T) as given gadgets | Where and how to use temporary ANDs - an arrangement problem | Classical: all gates act as permutations; check the function on all basis inputs, plus gadget preconditions (t == a AND b before `and_uncompute_mbu`) |
| **B (hard)** | H, S, T, CNOT, measurement, classically controlled Pauli/Clifford | The gadget itself (measurement-based uncomputation, 4-T AND) | Quantum, branch-exact: for every measurement outcome, the corrected Kraus operator restricted to clean-ancilla inputs must equal the target isometry up to a phase |

Tier A tests the search loop; tier B tests discovery. Run A first; B is the result that would matter.

## 3. Verifier specification (the scientific core)

A candidate is a program `construct(n) -> Circuit`. It is accepted only if **all** levels pass:

- **L0 - well-formed.** Parses, uses only IR primitives, has the declared register layout, finishes
  within time and memory limits.
- **L1 - classical function (tiers A and B).** For every basis input (exhaustive for 2n <= 16, then 10^5
  random inputs): output registers hold (a, a+b), ancillas are returned to |0>, and gadget preconditions
  hold.
- **L2 - phase-exact (tier B; also gadget certification for tier A).** Branch-wise statevector simulation
  on clean-ancilla inputs for n <= 4 (<= ~16 qubits). Every outcome branch m must satisfy
  K_m = c_m * V_target with sum |c_m|^2 = 1. Use floating point with a 1e-9 tolerance first, then
  re-check winners in exact Z[1/sqrt2, i] arithmetic.
- **L3 - generalization.** L1 at n = 1..16 and L2 at n = 1..4, run on the same `construct` program. A
  candidate that is correct only for the n values it was tuned on is rejected.

Fitness is lexicographic: `0 if any level fails, else (-T_count(n_eval), -qubits, -T_depth)`, evaluated
at a held-out n (for example n = 12) as well as the training n.

**Verifier acceptance test (must pass before any search runs).** The verifier must
1. accept: Cuccaro, the pyzx-optimized Cuccaro, and a hand-written Gidney adder;
2. reject at least 12 planted-bug mutants, for example: wrong carry wiring; ancilla left dirty; missing CZ
   correction after measurement; correction on the wrong branch; correct only for even n; correct on
   basis states but wrong relative phase (caught only by L2); dirty ancilla assumed clean; output
   overwritten into the input register.
Target: 100% correct classification.

## 4. Experimental arms (all with the same evaluation budget)

| Arm | What it is | Why it is there |
|---|---|---|
| Baselines | naive (14n), pyzx (8n, measured), hand-written Gidney (~4n reference) | Fixed reference points |
| **Zero-shot LLM** | k independent samples of "write a minimal-T adder in this IR", no loop | If this already reaches 4n, the loop adds nothing on this task: it is retrieval |
| **Classical search** | Random / GA mutation over the same `construct(n)` representation | The ablation IBM's results showed is essential |
| **LLM evolution** | LLM as mutation operator, verifier-filtered, MAP-Elites archive | The method under test |
| LLM evolution, blinded | Same, with prompts that never mention adders, Gidney, or "AND" (task given only as a spec) | Reduces retrieval cues |

**Metrics.** Best verified T-count vs n; number of evaluations and LLM calls to first reach < 8n and
<= 4n + O(1); fraction of proposals that pass each verifier level; wall-clock time; >= 3 seeds per arm.

**Success tiers.**
1. Verifier acceptance test passes (gate for everything else).
2. Tier A: LLM evolution reaches <= 4n + O(1) and generalizes across n.
3. Tier B: any arm finds a verified construction with < 8n T. This is the meaningful result.
4. Tier B, LLM evolution beats both zero-shot and classical search at equal budget.

**Transfer probe (after success).** Targets where hand-optimization is less complete: controlled adders,
comparators, constant and modular adders, multi-controlled X under a limited clean-ancilla budget. A
literature check of the best known T-counts is needed first.

## 5. Repository layout

```
<repo>/
  ir/            circuit IR incl. measurement + classical control; QASM 3 import/export
  sim/           classical permutation simulator; branch-wise statevector simulator (small n)
  spec/          Spec objects: target function, register layout, ancilla contracts (clean in / clean out)
  verify/        L0-L3 levels; exact-ring re-check; planted-bug suite lives in tests/
  cost/          T-count, T-depth, qubits; later: fault-tolerant resource-estimator adapter
  baselines/     naive Cuccaro, pyzx pass, hand-written Gidney reference
  candidates/    seed construct(n) programs
  search/        mutation operators (classical), LLM proposer, evolutionary loop + archive
  experiments/   configs per arm, run scripts, results tables and figures
  tests/         unit tests + verifier acceptance suite
```

Two fixed interfaces keep every phase comparable: `optimize(spec, budget) -> construct` and
`score(construct, n_values) -> table`.

## 6. Build phases

| Phase | Deliverable | Acceptance criterion | LLM needed? |
|---|---|---|---|
| P0 Skeleton | IR, both simulators, QASM I/O | Simulators agree with pyzx tensors on Cuccaro n <= 4 | no |
| P1 Verifier | spec/ + verify/ L0-L3 + planted-bug suite | 100% classification on section 3 acceptance test | no |
| P2 Baselines | Baseline table | Reproduces 14n / 8n (measured) and ~4n reference across n = 1..16 | no |
| P3 Classical search | GA over construct(n) | Runs end to end; report whether it gets below 8n (tier A and B). **Go/no-go**: if the harness cannot run classical search reliably, stop and fix | no |
| P4 LLM proposer | Proposer via Claude Code CLI; minimal custom loop first, OpenEvolve optional | Zero-shot arm runs; loop runs 100 iterations without silent failures (count non-zero exits, unmatched diffs, edits outside the allowed region) | yes |
| P5 Experiment | All arms, >= 3 seeds, tiers A and B | Results table + figure: best T-count vs evaluations per arm | yes |
| P6 Extension | Transfer target; fault-tolerant cost as slow-loop evaluator | Defined after P5 | yes |

**Known pitfalls to design around** (from the earlier OpenEvolve audit): EVOLVE-BLOCK markers are not
enforced (confine edits ourselves); the `claude_code` provider treats a non-zero exit with stdout as
success; unmatched SEARCH blocks are skipped silently; unknown config keys are ignored. With a
millisecond verifier, LLM calls are ~100% of the cost, so cache and deduplicate proposals.

## 7. Risks

- **Retrieval, not discovery.** Mitigated by the zero-shot and blinded arms and by tier B.
- **Verifier bugs** that accept wrong circuits. Mitigated by the planted-bug suite and the exact-ring
  re-check of every winner.
- **Tier B too hard** for any arm within budget. This is still a publishable negative result if the
  arms are fair; fall back to intermediate IRs (give measurement, withhold the AND gadget).
- **Generalization.** Candidates that hard-code small n; L3 checks this.

## 8. What I need to start

1. Repository path (rw grant) and whether it is empty or already contains code (`tforge`?).
2. Python version and whether to reuse an existing environment.
3. LLM access route confirmed: Claude Code CLI on this machine.
