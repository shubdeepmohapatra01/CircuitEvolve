# CircuitEvolve core: window mutator, verifier, metric, loop

Status 2026-10-13 (stage-1 runs: results/window_runs/stage1/SUMMARY.md). One pipeline with three parts and a simple selection loop, in `circuitevolve/core/`.
Everything older (adder search, block rule library, optimizer-program evolution) is in
`circuitevolve/legacy/` and still reproducible (see the end of this file).

```
TKET-pre-optimized input ─► windows (≤4 qubits, ≤40 ops)
         │                        │ highest T-cost first, round-robin
         │                 ┌──────▼──────┐   playbook rules, recent verifier feedback, allowance eps_w
         │                 │   MUTATOR   │◄─ (LLM, literal window text, never exec/eval)
         │                 └──────┬──────┘
         │                 ┌──────▼──────┐   frozen blocks/verify_block.py: exact D[ω] for Clifford+T
         │                 │  VERIFIER   │   windows, else operator distance ≤ eps_w; whole circuit vs
         │                 └──────┬──────┘   the ORIGINAL (n ≤ 20) on every accept
         │                 ┌──────▼──────┐
         └────────────────►│   METRIC    │   T-count, BQSKit convention (gridsynth at eps_synth / N_Rz)
                           └──────┬──────┘
                       accept iff improves and the ledger can pay; archive best + 3 others
```

## Modules

| File | Role |
|---|---|
| `core/circuit.py` | `Circuit` (n, ops over h s sdg x z t tdg cx cz rz), QASM in/out (multi-qreg, pytket `k*pi` angles, literal parser), `load_input(name)` (Baselines-track file `results/bqskit_baselines/stage1/inputs/<name>_tket.qasm` if present, else the same TKET pass here), `original_ops(name)`, `windows()` (BQSKit QuickPartitioner(4) + ≤40-op cuts via `blocks/partition.py`), `splice()` |
| `core/metric.py` | `BqskitTMetric(eps_synth).cost(ops)` → t, t_fixed, t_gs, rz, cx, gates, eps_rz; `improves()` |
| `core/ledger.py` | `Ledger` — error rule v1 (default since stage 1) and v0 (below) |
| `core/refit.py` | fix-and-refit action: `parse_fix`, `validate_target`, `refit(window, k, fixes)` (BQSKit instantiation of the remaining angles) |
| `core/verifier.py` | `verify_window(orig, new, k, allowance)`, `check_circuit(original, cand, n, bound)` |
| `core/mutator.py` | `build_prompt(WindowTask)`, `extract_candidates(text)`, `parse_window`, `parse_angle` |
| `core/loop.py` | `WindowLoop(...).run()`, `run(name, eps, complete, tag=..., playbook_path=...)` |
| `llm_backends.py` | `make_api_backend` (host.llm, thinking disabled), `make_cli_backend`, `make_batch_merger` |
| `search/playbook.py` | self-evolving playbook (unchanged; evidence = measured improvement) |
| `locks.py` | `NUMERIC_LOCK`, one process-wide lock (never fork while numpy verification runs) |

Run: `experiments/window_run.py` (`run_api(host, name, eps, tag=...)` in a platform kernel, or the CLI).

## Metric: T-count under BQSKit's convention

Read from bqskit-ft `algorithmic_error_dpf` @ `2e99ba614d48970b9afefc0b8c32860c3a3dc9f1`,
`alg_err_workflow.py`, `compile_rz_to_clifft`: `err_per_gate = success_threshold / num_rz_gates`, then
`CliffordTModel(err_per_gate)`, i.e. every remaining Rz is synthesized by gridsynth at eps / N_Rz.

* eps_rz = eps_synth / N_Rz, N_Rz = rotations that are not multiples of π/4 (angles reduced to [−π, π]).
* T = explicit T/T† + 1 per odd-π/4 Rz + Σ gridsynth T(angle, eps_rz). gridsynth = pygridsynth 2.0.0 at
  mpmath dps 128, every word re-multiplied and checked (`blocks/cost_model.Gridsynth`); bqskit-ft calls
  rsgridsynth (same algorithm; word T-counts can differ slightly). Cache: one file per `repr(eps)` under
  `.cache/blocks/bqskit_conv/`.
* Also reported: rotation count (`rz`), CNOT count (`cx`, includes CZ), gate count.

**Acceptance (`metric.improves`)**, lexicographic, same rule as `blocks/cost_model.improves`: T must not
increase; if the rotation count changed it must drop; with equal rotations, explicit T must drop; with equal
rotations and explicit T, total T must be equal and CNOT/gate count drop. A change of angles alone
(same number of rotations) is never an improvement — gridsynth word lengths vary by ±4 T between angles, and
such "wins" would spend error budget on luck.

## Error ledger

### v1 rule (default since 2026-10-13, stage-1 runs): unspent window budget returns to synthesis

| Pool | Size | Spent by |
|---|---|---|
| window pool W | cap eps / 4 | measured operator distance d_w of every ACCEPTED approximate window rewrite (exact D[ω] rewrites cost 0) |
| synthesis S | eps − d_input − ceil_q(Σ d_w) | final gridsynth of every remaining rotation at eps_rz = S / N_Rz |

* q = eps · 2^-12; the window spend is rounded UP to a multiple of q (conservative; lets nearby spends share one
  gridsynth cache file). d_input (TKET input vs original, ~1e-13) is taken from S.
* Allowance offered to the next rewrite: min(W − ceil_q(Σ d_w), W/4) = eps/16 at the start.
* **Acceptance and reported T both use eps_rz = S / N_Rz of the candidate's own ledger**, so a rewrite that spends
  budget must out-save the tighter synthesis it imposes on every other rotation (measured, not estimated).
* With no accepted rewrite T = B0's t_count_canon exactly (S = eps − 1e-13; `tests/test_core_stage1.py`).
* Bound: d_input + Σ d_w + N_Rz · eps_rz ≤ eps.

### v0 rule (`Ledger(eps, rule="v0")`; smoke run only)

W = eps/2 (d_input + Σ d_w), S = eps/2 fixed (eps_rz = (eps/2)/N_Rz), allowance min(W left, W/4);
`t_after_reclaimed` reported T with the unspent part of W returned, never used for acceptance. It cost about +3 T
per rotation versus B0 (3·log2 2), which v1 removes.

**How this compares with B0–B3.** B0/B1 spend all of eps on gridsynth (eps / N_Rz each), bound ≤ eps.
The published B3 script gives the same eps to each of its three stages — Clifford+RZ angle collapse
(eps/(num_params+1) per parameter), DPF per block (eps / #blocks, checked with BQSKit's instantiation
cost), and gridsynth (eps / N_Rz) — so its additive bound is up to 3·eps, while the run is labelled eps.
B3g (DPF stage at 0.4 eps HS + gridsynth at 0.4 eps) is bounded by eps in its own (mixed HS/op) accounting.
Our bound is ≤ eps in operator norm for the whole circuit.

## Verifier

`verify_window` (wraps the FROZEN `blocks/verify_block.py`, which already takes `eps` — no edit was needed):

1. literal checks: core gate set, local qubits in range, ≤ 120 ops, finite angles;
2. both windows Clifford+T after snapping exact π/4 multiples → `verify_exact` ONLY (Z[ω]/√2^k, equality
   up to ω^j), charge 0; an unequal pair is rejected, never re-checked numerically (CLAUDE.md invariant 1);
3. otherwise `verify_instance(orig, new, k, eps=allowance)`: phase-aligned operator norm ≤ allowance; charge
   = measured d. The record also carries BQSKit's HS quantities `hs_cost = 1 − |Tr U†V|/N` and
   `hs_dist = sqrt(1 − (|Tr|/N)²)`, both ≤ d.

`check_circuit` runs on every accept against the ORIGINAL qseed circuit: dense unitary for n ≤ 10,
4 Haar-random statevectors for 11 ≤ n ≤ 20 (a lower bound on the operator distance — catches errors, does
not certify), skipped above 20. Pass iff dist ≤ d_input + Σ d_w + 1e-10. It is a second line of defence: the
test suite plants a lying window verifier and checks that the whole-circuit check rejects the result.

## Mutator

Prompt (one window per call): the window in the literal format (angles reduced to [−π, π], `# op i` comment on
every rz line); per synthesized rotation: angle, nearest π/4 multiple, |angle − multiple|, the plain snap distance
2|sin(Δ/4)| ("an upper bound; usable directly only if ≤ allowance"), its gridsynth T at the current eps_rz, and its
**Pauli frame P** — with all Clifford gates of the window moved to its end, op i = exp(−i·angle/2·P)
(`mutator.rotation_paulis`, numerically with the frozen `verify_block.unitary`), plus the rule that equal-P
rotations with a commuting path merge; t/tdg gates are listed with their P too. Also: the window's T-cost; the
allowance; active + A/B-shown playbook rules; the last six verifier outcomes. Reply: up to three blocks in total:

* ` ```window ` — **exact rewrite** (full replacement window). Syntax: `h q0`, `cx q0 q1` (control, target),
  `rz(-3*pi/8) q2`, `rz(0.0123) q1`, `q[0]` and trailing `;` tolerated, `tdag`/`sdag`/`cnot` aliases.
* ` ```fix ` — **fix-and-refit** (`core/refit.py`): lines `op i -> target`, target 0 (delete), a multiple of π/4,
  or 2πm/2^k with k ≤ 4 (validated literally; anything else is a parse error). The toolbox re-instantiates every
  other non-π/4 rotation of the window to minimise the distance to the window's unitary — BQSKit `Minimization`
  (Ceres Levenberg–Marquardt on Hilbert–Schmidt residuals, as instantiation inside bqskit-ft's DPFPass), starts:
  current angles, a Pauli-informed merge start (the fixed rotation's angle moved onto an equal-P partner with a
  commuting path), 8 seeded random starts, then ≤ 3 polish restarts from the best. The refitted window goes to the
  frozen verifier at the allowance like any window. The LLM chooses which rotations to fix; the toolbox never
  fixes rotations on its own.

Parsing is regex-only; `rz(eval(1))`, `__import__`, unknown gates, wrong arity are parse errors (tested with
`eval`/`exec` monkeypatched to raise).

## Loop

* Parent: the best circuit with probability 0.7, else another archive member (archive = best + up to 3
  other distinct circuits by (T, rz, cx, gates), ties by ledger spend). Each member has its own ledger.
* Windows of the parent (deterministic: QuickPartitioner's global `Bin.id` counter is reset before each
  partition — without that the same circuit was partitioned differently depending on process history),
  ranked by window T-cost; the batch takes the top untried ones (round-robin restart when all were tried).
* All candidates of a window are verified; the best improving one is accepted if the ledger can pay; windows
  of a batch are evaluated in descending position so splices never shift each other.
* Playbook (`search/playbook.py`, `evidence="improvement"`): a prompt counts as an improvement only if one of
  its candidates was ACCEPTED and reduced T. Raw verifier passes (e.g. a copy of the window) are logged but
  are not evidence. A reflector call every `reflect_every` proposal calls, skipped when there was no new
  verifier outcome; reflector calls count against the call budget.
* Logs (append-only, refused if the tag exists): `results/window_runs/<tag>.jsonl` — `start`, one `propose`
  line per call (prompt, full response, parse errors, every candidate with verifier record, cost, decision,
  whole-circuit check), `reflect` lines, `playbook_gate` changes, `end`; plus `<tag>_summary.json`,
  `<tag>_best.qasm`, `<tag>_playbook.{json,md}`.
* `integrity.frozen_digest()` is checked at start and end.
* Concurrency: LLM calls are one batched host call; gridsynth runs serially in-process; nothing is forked,
  and verification holds `locks.NUMERIC_LOCK`.

## Tests

`tests/test_core_window.py` (fake LLM only): literal parsing and refusals; windows reassemble on a TKET
input; planted bad rewrites rejected (wrong angle, dropped CNOT, dropping a rotation whose distance exceeds
the allowance, out-of-range qubit) and good exact/approximate ones accepted with the right charge; exact
D[ω] mode; metric convention vs direct gridsynth; ledger arithmetic and bound ≤ eps; the loop end-to-end
(rejections, LLM error, non-improving pass, two accepts, log contents, append-only tag); the whole-circuit
check catching a bypassed window verifier; playbook credit only for measured improvement.

`tests/test_core_stage1.py` (fake LLM only): ledger v1 arithmetic, rounding, pool cap and bound; zero accepted
rewrites reproduce B0's t_count_canon exactly on qft_8 and tfim_6 (eps 1e-3); fix-block parsing and refusals
(non-dyadic targets, eval/exec monkeypatched); refit absorbs a redundant rotation exactly and the frozen verifier
agrees, cannot absorb a lone rotation (verifier rejects), maps BQSKit's cycle-ordered parameters back to the right
ops; Pauli frames and the merge claim (exact merge with a commuting path, no merge across an anticommuting
rotation); the loop with the fix action end-to-end (one accepted, one verifier-rejected, one parse error).

## Legacy (archived 2026-10-13, reproducible)

| Stack | New home | Old import path (alias, same module object) | Tests |
|---|---|---|---|
| adder slice search (P3/P4) | `circuitevolve/legacy/adder/{slice,evolve,llm}.py` | `circuitevolve.search.{slice,evolve,llm}` | `tests/legacy/test_legacy_{search,llm,controls,playbook_loop}.py` |
| block optimizer v1 rule library | `circuitevolve/legacy/blocks_v1/{program,rules,proposer,pipeline}.py` | `circuitevolve.blocks.{program,rules,proposer,pipeline}` | `tests/legacy/test_legacy_blocks_v1.py` |
| optimizer-program evolution | `circuitevolve/legacy/evolve_opt/` | `circuitevolve.evolve_opt.*` (child: `python -m circuitevolve.legacy.evolve_opt.child`) | `tests/legacy/test_legacy_evolve_opt.py` |

The exact adder verifier (`ir, ring, sim, spec, verify, cost, acceptance`) and `blocks/verify_block.py`
did not move. Shared block infrastructure (`circuit_io, partition, cost_model, passes, classical, runtime`)
stays in `circuitevolve/blocks/`. `tests/legacy/test_legacy_aliases.py` checks that every old path is the
same module object as its new home, so `experiments/*.py`, notebooks and `results/discovered/*.py` run
unchanged.

## Playbook ablation v1 (2026-10-14, `results/window_runs/ablation_v1/REPORT.md`)

Question: does a learned shared playbook improve the loop on HELD-OUT circuits? Script `experiments/window_ablation.py`
(`learn_dev`, `run_ablation`, `run_control`), report code `experiments/window_ablation_report.py`.

* Learning: fresh `playbooks/dev_v1.json` on development circuits only (qft_4..7, qpe_6, qae_11, qae_15; 33 calls each,
  reflector every 10 proposer calls) -> 28 rules proposed, 1 ACTIVE; frozen, SHA-256 in `ablation_v1/FROZEN.sha256`.
  Placebo `playbooks/placebo_v1.json`: one generic active rule of similar length, same rendering path.
* Held-out: qft_8, qpe_8, qae_13, hhl_8 x {none, learned, placebo} x seeds {0, 1} (seed 2 dropped for the token
  budget), 20 proposer calls, no reflector; frozen playbooks show ACTIVE rules only and consume no loop RNG.
  `WindowLoop(seeded_ties=True)` (new, default False = stage-1 behaviour) orders equal-T-cost windows by a seed-dependent
  hash of their content; tests in `tests/test_core_ablation.py`.
* Result: null. Learned - none +0.38 pp (bootstrap 95 % CI -1.21 to +1.93, sign test 4/2/1, p = 0.69); learned -
  placebo +0.66 pp (CI -0.60 to +1.99, 4/3/0, p = 1.0) over 7 complete blocks (hhl_8 seed 1 lost to the platform's
  per-frame host.llm token ceiling). The no-LLM same-Pauli merge rule (10.4-14.7 % vs B0) beats every LLM run (<= 5.2 %).
