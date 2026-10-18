# Verifier / harness changelog (append-only)

- 2026-10-06 — verify.py: added opt-in `Limits.trust_gadget_lemma` (default False). Used only by the
  search evaluator for tier-A-only circuits; final verification of winners keeps it off. Acceptance
  suite re-run with the flag on and off: 21/21 both ways.
- 2026-10-06 — search/evolve.py (not verifier): fitness ranks T per bit first; search-side cap of
  2 measurement events per bit; search-time branch budget 4096. First P3 launch (8/15 runs finished,
  7 stalled on L2 branch enumeration) superseded; its run files were overwritten by the rerun.
- 2026-10-06 — search/evolve.py: crossover operator, hash-keyed compact cache, progress snapshots.
  10⁶-evaluation classical runs stopped early at 1.2–4×10⁵ evaluations (all still 14n); last snapshots
  appended to results/classical_search_strong.csv as `stopped_early_last_snapshot`.
- 2026-10-06 — search/llm.py: LLM proposer (literal ast parsing, blinded naming, CLI backend with
  is_error checks, empty-dir sandbox), hybrid local repair (`repair_budget`). Pilot: results/P4_pilot.md.
- 2026-10-11 — search/playbook.py (new, not verifier): self-evolving rule file for the LLM proposer
  (generator / reflector / curator; JSON deltas only; candidates A/B-tested on raw verifier pass rate and
  promoted/retired by a z-score gate; frozen mode for evaluation). search/llm.py: optional `playbook`,
  `reflect_every`, `reflect_complete`; with playbook=None the loop and RNG stream are unchanged.
  circuitevolve/integrity.py (new): SHA-256 digest of the frozen verifier files, checked at the start and
  end of every llm_search run and recorded in its stats. Verifier untouched; 77/77 tests pass.
- 2026-10-11 — harness fixes (not verifier; verifier files and digest untouched).
  search/llm.py: `make_api_backend` (batch LLM callable with the host.llm signature, injected — the module
  never imports `host`; thinking disabled by default; error dicts / exceptions / empty text are errors;
  bounded retries with exponential backoff for transient errors; `stats` Counter incl. tokens),
  `make_batch_merger` (thread-safe merging of concurrent runs' requests into one batch call),
  `make_cli_backend` hardened (stdout/JSON-envelope diagnostics on exit != 0, configurable timeout,
  retries for transient failures, extra args such as --max-turns, injectable runner for tests).
  Parser: line-based fence pairing (the old regex could open a bogus block at a closing fence after a
  ```text block); blocks that assign none of FWD/TOP/BWD (hand traces, diagrams) or are non-python are
  skipped and counted as `non_program_block`, not parse errors; a response with no program block is one
  error; unambiguous gate aliases normalised ('T†'/'Tdg'/'tdag' -> 'tdg', 'S†' -> 'sdg', 'CNOT' -> 'cx',
  case) only when the result is a known gate; `FWD = (G(...))` accepted as a 1-tuple. Literal-AST parsing
  only, as before. P4 parser kept as `parse_programs_p4` for before/after measurement.
  Prompt: new output-format paragraph (only final programs in ```python blocks; traces in plain text;
  ASCII gate names); `format_rules=False` reproduces the P4 prompt exactly. llm_search: `format_rules`
  argument, per-response `parse_counts`, `stats["backend"]` (backend counter delta). RNG stream unchanged.
  experiments/search_llm.py refactored into `run(...)` usable from a platform kernel; CLI flags for the
  new CLI options; tags never overwrite existing results files. experiments/p5_controls.py (new):
  matched-evaluation classical MAP-Elites and repair-only control. docs/LLM_BACKENDS.md (new).
  New tests in tests/test_llm.py and tests/test_controls.py; 88/88 pass.
- 2026-10-11 — VERIFIER ADDITION: circuitevolve/blocks/verify_block.py (new, FROZEN; added to
  integrity.FROZEN, so frozen_digest() values change from this entry on: new digest bc3eac23a403dbc594265a91ebb9f0ff12672dc913c56c5cf5d9d950c2a242c6).
  Approximate verification mode for continuous-angle blocks of the block optimizer. ACCEPT iff the
  phase-aligned operator-norm distance ||U - e^{i phi*} V||_2 (phi* = trace phase; an upper bound on the
  phase-invariant operator distance, so block errors add) is <= eps_block = 1e-8 on the instance angles;
  rules stated over the instance angles must also pass on >= 32 uniform random angle vectors. Exact
  D[omega] equality-up-to-omega^j mode (via the frozen sim.py) for all-Clifford+T blocks. Whole-circuit
  check: dense unitary n <= 10, Haar-random statevectors n <= 20. The existing exact verifier files are
  unchanged. CLAUDE.md invariants 1 and 4 updated (exact mode decides Clifford+T acceptance; this module
  decides continuous-angle blocks with an explicit error budget). Planted-bug suite
  tests/test_blocks_verify.py (wrong angle sign, every dropped gate, swapped qubits, relative phase,
  error-budget boundary, rules wrong only for some angle values, global-phase-only differences accepted,
  exact-mode cases, bqskit qubit-order convention, statevector check). 117/117 tests pass.
- 2026-10-11 — circuitevolve/blocks/ (new; not verifier except verify_block.py above): block optimizer v1.
  circuit_io (qseed import, phase-0 minrz lowering, eval circuits refused), classical (pyzx / TKET, lower
  T kept; baseline = min of phase-0 raw-angle count and [-pi, pi]-canonical count), partition
  (QuickPartitioner 3|2, <= 40-gate windows, structure signatures), program (literal ast-whitelist block
  program format, a_i exact rewrites, p_j fitted by Levenberg-Marquardt with pi/4 snapping), passes (phase
  folding, 1q minimal-RZ resynthesis), cost_model (gridsynth 1e-9, cached, serial; improves() = fewer
  synthesised rz without more T; gridsynth angle noise is not a gain), rules (JSON rule library), proposer
  (per-structure LLM loop, playbook reuse), pipeline (reassembly, whole-circuit check vs original, error
  bound; options global_fold, input_pipeline). pyproject optional extra `blocks`; bqskit 1.2.1, pytket
  2.18.5, pygridsynth 2.0.0, qiskit 2.5.2 installed in the repo .venv. Tests: tests/test_blocks.py,
  tests/test_blocks_verify.py; 119/119 pass. Smoke: results/blocks/SMOKE_REPORT.md (dev circuits only;
  35 proposer + 4 reflector + 1 connectivity call, ~138k tokens; 0 LLM rules found; hhl_8 -12.0 % T from the
  deterministic phase fold). results/blocks/smoke_v1 aborted before any LLM call (ABORTED.md).
- 2026-10-11 — circuitevolve/evolve_opt/ (new; not verifier): evolvable optimizer programs. split.py +
  benchmarks/split.json / SPLIT.md (17 dev circuits, FAST subset of 6, eval = add_17, hhl_6, mult_16, qft_32,
  shor_16 + the whole add family; shor_14 dropped: its best classical result has 1,072 rz, over the 1e-6
  budget at eps_rz 1e-9). toolbox.py (fixed toolbox: pyzx full/teleport/clifford/basic, 15 TKET passes,
  phase fold, 1q resynthesis, block_optimize via QuickPartitioner + frozen verify_instance, approx_round
  with an error ledger, gridsynth cost queries; deterministic tools cached on disk, cache hits charge the
  original CPU seconds). sandbox.py (ast static checks, restricted builtins, one subprocess per program and
  circuit, wall-time + RSS watchdog). evaluate.py (parent-side verification with the frozen
  verify_block.circuit_check against the ORIGINAL circuit; budget 1e-6 = ledger + 1e-8 numeric slack +
  #rz x 1e-9; lexicographic fitness valid -> geomean T/T_best_classical -> charged CPU; evaluation cache by
  source hash). evolve.py (MAP-Elites x 2 islands, diff/rewrite proposals parsed literally, FAST -> dev
  cascade at 2 %, calls.jsonl logging, playbook). control.py (random / greedy pass-sequence search through
  the same evaluator). Reference T: results/evolve_opt/baseline_dev.json. Docs: docs/EVOLVE_OPT.md.
  FINDING: running verify_block distance computations in parallel THREADS of one interpreter returned wrong
  distances (heisenberg_8 0.74 instead of 3.5e-14; tfim_8 2.3e-4), so evaluate.verify_output is serialised
  by a lock (eval cache version ev-v2; the ev-v1 cache was deleted). verify_block.py itself is unchanged;
  any caller that runs it in threads must serialise it.
- 2026-10-11 — search/playbook.py (not verifier): evidence gate switched from raw verifier passes to
  MEASURED IMPROVEMENT (new default `evidence="improvement"`): candidates are promoted / retired on the rate
  of prompts whose child beat its parent, shown vs hidden (new Rule fields with_prompts, without_prompts,
  without_improvements; settings key `evidence`, saved and loaded). `evidence="pass"` keeps the old gate.
  record() signature unchanged, so search/llm.py and blocks/proposer.py now use the improvement gate too.
  Tests: tests/test_evolve_opt.py (planted bad programs: forbidden import and 21 other static violations,
  infinite loop, memory hog, time budget, wrong outputs, illegal ops, error budget exceeded, statevector
  ledger lie; gate test showing the pass gate cannot separate a passing-but-not-improving rule).
- 2026-10-11 — evolve_opt evaluator fix (not verifier): the lock above was not enough. Forking a sandbox
  subprocess from one thread while another thread runs the numpy distance computation corrupts the result in
  the PARENT on this machine (.cache/evolve_opt/rep3.py: 30/30 wrong qft_8 distances with concurrent Popen,
  0/30 with pure-Python threads, psutil, or the lock). sandbox.NUMERIC_LOCK is now held around every Popen and
  every parent-side verification; eval cache version ev-v3. The LLM pilot run results/evolve_opt/evo_s0_120
  (and smoke_live_8) used ev-v2 and is INVALIDATED (evo_s0_120_INVALIDATED.md: 8 of the first 20 re-checked
  programs had flipped verdicts, all invalid -> valid); seed 0 re-run as evo_s0_v3_120. The classical
  control runs control_{random,greedy}_s{0,1,2}_120 used one evaluation thread (spawn and verify strictly
  sequential), so they were not exposed; their best programs are re-verified under ev-v3 in DEV_REPORT.md.
  playbook.py: new Rule field with_improvements (improving prompts while shown as a candidate) is the gate
  numerator; `improvements` keeps counting while active (display only). Gate decisions are unchanged for
  candidates. Tests: 2 regression tests added.

2026-10-12 (evaluation): first and only use of the evaluation circuits (add_17, hhl_6, mult_16, qft_32, shor_16, add_41,
  add_65). Frozen programs (seed, best classical, LLM v2 s2, LLM v1 s0, control greedy s2) run with the unchanged
  ev-v3 evaluator via the new runner experiments/evolve_opt_eval.py, which lifts the dev guards in its own process
  only; no verifier, evaluator or program file changed. Time limits raised identically for all programs: shor_16
  1200 s, add_41 1200 s, add_65 1800 s (300 s rows kept). Result: LLM v1 ties the control, LLM v2 is worse
  (hhl_6 6,568 vs 6,192 T); add_17 / mult_16 / qft_32 / add_41 equal best classical for every program;
  shor_16 / add_65 have no valid output within 1e-6. qft_32, add_41, add_65 (n > 20) are NOT numerically verified.
  Report: results/evolve_opt/EVAL_REPORT.md; data: eval_table.csv, eval_table_long.csv, eval_summary.json, eval/.
- 2026-10-13 — RESTRUCTURE (not verifier; frozen files and `integrity.frozen_digest()` untouched).
  Archived to `circuitevolve/legacy/`: `adder/{slice,evolve,llm}.py` (from `search/`), `blocks_v1/{program,
  rules,proposer,pipeline}.py` (from `blocks/`), `evolve_opt/` (whole package). Code moved verbatim except
  parent-relative imports made absolute and the evolve_opt child entry point
  (`python -m circuitevolve.legacy.evolve_opt.child`). Old import paths are sys.modules aliases of the SAME
  module objects (one NUMERIC_LOCK, one cache), so experiments/, notebooks and results/discovered/*.py run
  unchanged. LLM backends moved to `circuitevolve/llm_backends.py` (verbatim; re-exported by the legacy
  llm module); `NUMERIC_LOCK` moved to `circuitevolve/locks.py` (legacy sandbox imports it). Tests: whole
  legacy test files moved to `tests/legacy/` (imports updated, bodies unchanged); `test_blocks.py` and
  `test_playbook.py` split (shared-infrastructure / pure-playbook tests stay). All 169 original tests pass;
  the 71 tests of the four moved files also pass unmodified through the OLD import paths (run from copies).
- 2026-10-13 — NEW window core `circuitevolve/core/` (docs/CORE.md): circuit.py (Clifford+Rz object,
  multi-qreg QASM reader with literal `k*pi` angles, stage-1 TKET inputs - prefers the Baselines track's
  `results/bqskit_baselines/stage1/inputs/<name>_tket.qasm`, windows = QuickPartitioner(4) + <= 40 ops with
  QuickPartitioner's global `Bin.id` reset so partitions are deterministic), metric.py (T-count under
  BQSKit's convention from bqskit-ft algorithmic_error_dpf @ 2e99ba6 alg_err_workflow.py: gridsynth at
  eps_synth / N_Rz, one cache file per repr(eps)), ledger.py (v0: eps/2 windows charged measured distance,
  eps/2 synthesis; per-rewrite allowance min(remaining, W/4); bound <= eps), verifier.py (wraps frozen
  verify_block: exact-only for Clifford+T pairs, verify_instance(eps=allowance) otherwise; whole-circuit
  check vs the original), mutator.py (prompt + regex-only parsing, NONE = declined), loop.py (archive best + 3,
  playbook evidence = accepted AND T reduced, append-only JSONL per call, integrity digest at start/end).
  experiments/window_run.py (new). tests/test_core_window.py (11, fake LLM: planted wrong angle, dropped
  CNOT, over-allowance drop, out-of-range qubit rejected; lying window verifier caught by the whole-circuit
  check), tests/legacy/test_legacy_aliases.py (15). 195 tests pass.
- 2026-10-13 — smoke run `results/window_runs/smoke_heisenberg_6_e3*` (20 calls, 23,654 + 11,416 tokens):
  T 8600 -> 8600, nothing accepted; see `_NOTE.md` (19/20 replies were NONE, logged as parse errors by that
  run; the declined counter and a relabelled snap column were added after it).
- 2026-10-13 — window core, stage-1 changes (not verifier; frozen files and `integrity.frozen_digest()` untouched).
  (a) `core/ledger.py` rule **v1** (new default; v0 kept as `rule="v0"` for the smoke run): window pool capped at
  eps/4, unspent budget returns to synthesis - eps_synth = eps - d_input - ceil_q(sum d_w), q = eps * 2^-12
  (conservative rounding so nearby spends share one gridsynth cache file); per-rewrite allowance min(left, eps/16);
  bound d_input + sum d_w + N_Rz eps_rz <= eps. `core/loop.py` prices every circuit at its OWN ledger
  (eps_rz = eps_synth / N_Rz) for acceptance and reporting; the ledger check now precedes the metric (the candidate
  is costed at the post-charge ledger). With no accepted rewrite T equals B0's t_count_canon exactly
  (test on qft_8, tfim_6 at 1e-3). (b) New mutation action **fix-and-refit** (`core/refit.py`): the LLM writes a
  ```fix block (`op i -> target`, targets 0 / k*pi/4 / 2*pi*m/2^k with k <= 4, regex-parsed); the toolbox
  re-instantiates the window's other non-pi/4 rotations with BQSKit `Minimization` (Ceres LM, HS residuals; warm
  start + Pauli-informed merge start + 8 seeded random starts + up to 3 polish restarts) and the result goes to the
  frozen verifier at the allowance like any window. (c) `core/mutator.py`: prompt describes both actions; rotation
  table adds |angle - nearest pi/4| and each rotation's Pauli frame P (Cliffords of the window moved to its end,
  computed with the frozen `verify_block.unitary`) with the merge/commutation rule; window lines carry `# op i`;
  `extract_proposals` parses ```window and ```fix blocks (max 3 total). Loop stats split by action
  (`accepted_fix`, `accepted_window`, `rotations_removed_*`, `refit_failed`); summary gains
  `final_check_vs_original` (best circuit vs the ORIGINAL qseed circuit). New `experiments/window_stage1.py`,
  `tests/test_core_stage1.py` (10 tests). 205 tests pass. Dev run `results/window_runs/stage1/dev_qpe_8_e3*`
  (5 calls, before the Pauli column was added; nothing accepted).
- 2026-10-13 — stage-1 runs `results/window_runs/stage1/` (PRELIMINARY; SUMMARY.md, stage1_results.csv,
  stage1_figure.{png,pdf}): 11 runs (8 at 1e-3; qpe_8, qae_13, hhl_8 at 1e-5 - the other five 1e-5 runs dropped
  for the token budget), 484 LLM calls (458 proposer + 26 reflector), 1,624,660 tokens (+13,380 dev run; ~9 % over
  the ~1.5 M target). T vs B0: qft_8 -2.1 %, qpe_8 -3.6 % / -1.9 %, qae_13 -1.8 % / 0 %, hhl_8 -1.8 % / -2.0 %,
  Trotter circuits = B0 (= bar); +48 % to +87 % above the bar (best valid of B0, B1, B2, B3g) where it improved.
  36 of 37 accepts were fix-and-refit. New no-LLM control `experiments/window_pmerge_control.py`
  (control_pmerge.json, deterministic same-Pauli merges in windows) beats the LLM loop on every improved row.
  Playbook `playbooks/stage1.{json,md}`: 63 rules proposed, 3 active. All finals checked vs the original circuits;
  verifier digest unchanged (bc3eac23a403dbc5).
- 2026-10-13 — circuitevolve/blocks/runtime.py (not a verifier file): run_passes works inside a running event loop
  (Jupyter): the BQSKit workflow runs on a short-lived worker thread when asyncio.run would refuse. Fixes
  `RuntimeError: asyncio.run() cannot be called from a running event loop` in notebooks/group_meeting_demo.ipynb.
- 2026-10-14 — playbook ablation v1 (`results/window_runs/ablation_v1/`, REPORT.md, ablation_results.csv, paired_stats.json,
  ablation_figure.{png,pdf}, FROZEN.sha256). Code: `core/loop.py` gains `WindowLoop(seeded_ties=False)` (equal-T-cost
  windows ordered by sha1(seed:window key) when True; no RNG consumed; default keeps stage-1 order); new
  `tests/test_core_ablation.py` (3 tests: tie order, frozen playbook shows active rules only / consumes no RNG / is not
  modified, frozen-vs-none runs make identical call counts and RNG draws) - 208 tests pass; new
  `experiments/window_ablation.py`, `experiments/window_ablation_report.py`; new playbooks `playbooks/dev_v1.{json,md}`
  (learned on qft_4..7, qpe_6, qae_11, qae_15 only; 28 rules, 1 active; sha256 6e6b65fa4e40...) and
  `playbooks/placebo_v1.{json,md}` (1 generic rule; sha256 27162b1933a1...). Runs: 7 dev runs (231 calls, 685,358
  tokens), 24 held-out runs (qft_8, qpe_8, qae_13, hhl_8 x none/learned/placebo x seeds 0,1; 480 calls requested,
  1,329,504 tokens); seed 2 dropped for the ~2.5 M budget; ho_hhl_8_learned_s1 and ho_hhl_8_placebo_s1 invalid (per-frame
  host.llm token ceiling 2.0 M hit; 10/20 and 20/20 calls errored), hhl_8 seed-1 block excluded from paired stats. Result:
  NULL - learned - none +0.38 pp (95 % CI -1.21..+1.93), learned - placebo +0.66 pp (-0.60..+1.99). All finals checked
  vs the original circuits; verifier files untouched. No-LLM merge control re-run at 1e-3 (identical to stage 1).
- 2026-10-14 — v2 scaffold (two-tier direction; isolation: new code only in `circuitevolve/v2/`, results in
  `results/v2/`, docs in `docs/v2/`, tests in `tests/v2/`; no existing file edited except this CHANGELOG).
  `circuitevolve/v2/verify.py`: one entry point `verify(candidate, reference, mode, eps) -> Verdict` with modes
  `exact` (frozen sim.run over D[omega], exhaustive basis inputs up to 2^14 = proof; sampled inputs for larger
  permutation-like references, certified=False), `approx` (core/verifier.check_circuit -> frozen
  verify_block.circuit_check; two Clifford+T circuits are routed to exact, invariant 1), `relaxed` (clean ancillas,
  measurement + feed-forward, branch-wise exact, same c_m for all valid inputs, sum |c_m|^2 = 1) and `auto`;
  generic `ReferenceSpec` (circuit / basis-map function / numeric ops), `adder_reference(n, carry_in)`,
  `parse_qasm_ir` (parses all 102 files under benchmarks/nam_arith/upstream). `metric.py`: frozen cost.py on exact
  circuits, core/metric.BqskitTMetric (eps_rz = eps / N_Rz) on rotations; qubits, ancillas, measurements, T-depth;
  lexicographic `fitness_key`. `baselines.py`: `table()` / `best_classical(circuit, eps)` over the REUSED
  stage1_baselines_v2.csv (`t_count_canon`; valid = measured within eps and bound <= eps, B2 nominal-rounding
  exception; B3 and B2ft invalid), reference_pipelines.csv (key `eps_rz=1e-9`, never mixed with total eps),
  published_baselines.csv (copied byte-identical to `results/v2/reused/`, context only) and the merge hook for
  `results/v2/baselines_new.csv` (schema circuit, source, arm, eps, t_count, qubits, notes). 46 new tests in
  `tests/v2/` (Cuccaro exact vs carry-in adder permutation n = 1..4 and sampled at n = 9 / 20 qubits; Gidney
  relaxed n = 1..4, cross-checked with the frozen adder verifier; planted bugs rejected: T->Tdg, relative S phase,
  reversed CNOT, dirty ancilla, missing measurement fix-up CZ, missing conditional reset); 254 tests pass
  (208 existing + 46). Verifier digest unchanged (bc3eac23a403dbc5).
- 2026-10-14 — v2 benchmark track (folded from results/v2/CHANGELOG_bench.md, which is kept):
  # v2 Benchmarks track - changelog (append-only; kept separate from results/CHANGELOG.md to avoid concurrent edits
  # with the sibling v2 track - the parent should fold a one-line entry into results/CHANGELOG.md)
  
  - 2026-10-14 - new `benchmarks/nam_arith/` (fetch_suite.py, normalize.py, COMMIT, PROVENANCE.md, SPLIT.md,
    MANIFEST.csv, split_v2.json; upstream/, logical/, cliffordt/, nam/, generated/): 34 Nam et al. 2018 / T-par circuits
    pinned at quartz@ce31db1c, njross/optimizer@8cd55d50, feynman@d2c382a2; cuccaro_4/8/16 generated; qseed
    shor_12/14/16 by reference. Split: 17 dev / 22 held-out / 1 large_optional (gf2^32_mult).
  - 2026-10-14 - baselines (`experiments/v2_bench_*.py`): run1 (no QCEC, superseded), run2 (all but gf2^16/32;
    QCEC added, circuits saved), run3_large (gf2^16; gf2^32 produced no output; driver stopped at 01:57 after ~110 min, worker exited). Aggregates:
    baselines_new.csv / _detail.csv / _summary.md / baselines_consistency.json, published_arith.csv,
    rotations_gridsynth_run2_eps0.001.json. Finding: Nam et al. Heavy qcla_mod_7 (235 T) is not equivalent to its input.
  - 2026-10-14 - `docs/v2/cards/` 11 technique cards + INDEX.md + CITATIONS.md; worked examples in
    cards_worked_examples.json (note: `temporary_and.uncompute_branches_phase_consistent` is serialized as [1.0, 1.0],
    i.e. True for both branches - numpy bools went through the float fallback of json.dump).
  - No file under circuitevolve/, results/ (outside results/v2/), notebooks/ or benchmarks/bqskit_qseed/ was modified;
    the frozen verifier files were only imported.
- 2026-10-14 — v2 tier1 track (folded from results/v2/CHANGELOG_tier1.md, kept):
  # CHANGELOG - v2 tier 1 (compilation strategy)
  
  ## 2026-10-14 - tier 1 v1: recognizer, plan format, compiler, dev run `dev_v1`
  
  - Added `circuitevolve/v2/tier1/` (recognize, plan, compile, control, prompt, loop), `experiments/v2_tier1_dev.py`,
    `experiments/v2_tier1_report.py`, `tests/v2/test_tier1.py` (25 tests), `docs/v2/TIER1.md`. No existing file edited;
    frozen verifier digest unchanged before/after the run. Full suite: 295 passed.
  - Dev run `dev_v1` (16 DEV circuits; shor_12 skipped: rotation-dominated, no rotation route, no comparable baseline):
    8 LLM calls per circuit (128 calls, 905,089 input + 58,206 output tokens), control at the same evaluation budget.
    Result: LLM never beats the control (exact 16 equal; relaxed 13 equal, 2 worse, 1 no valid plan). Relaxed
    constructions beat the best classical exact T on 10/16 circuits (both arms). Outputs in `results/v2/tier1/`
    (DEV_REPORT.md, dev_results.csv, dev_v1_*.csv/json, logs/, plans/, circuits/, summaries/, FROZEN.md).
- 2026-10-14 — v2 tier2 track (folded from results/v2/CHANGELOG_tier2.md, kept):
  # CHANGELOG - v2 tier 2 track (to be folded into results/CHANGELOG.md by the parent)
  
  ## 2026-10-14 - tier-2 executable rule library + DEV evolution run1
  
  * New code (isolated): `circuitevolve/v2/tier2/{__init__,commute,rules,apply,circuits,enumerate_ids,evolve}.py`,
    `experiments/v2_tier2_evolve.py`, `experiments/v2_tier2_report.py`, tests `tests/v2/test_tier2_rules.py`,
    `tests/v2/test_tier2_evolve.py` (16 tests), doc `docs/v2/TIER2.md`. No existing file edited; frozen verifier digest
    checked unchanged at the start and end of both arms (`integrity.check_unchanged`).
  * Rules: literal DSL templates over <= 4 qubit variables, verified ONCE as exact identities (v2 exact verifier,
    exhaustive, certified); commutation-aware matching via a matrix-tested commutation table; fixpoint application with
    strict (T, gates) decrease; libraries JSON with SHA-256 and parent hash.
  * run1 (DEV, 16 circuits; shor_12 excluded - no exact Clifford+T form): LLM arm 18 generations x 2 calls = 36 calls
    (229,474 input + 68,095 output tokens), 149 rules proposed, 54 verified; no-LLM Quartz-style enumeration control with the
    same 117 verifications. Total DEV T 758 -> 758 in both arms; no library version accepted; frozen
    `library_final.json` = `library_control_final.json` = v0 (empty), SHA-256
    4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945.
  * Headroom probe: 0 of 8,833 enumerated T-reducing identities match any start circuit. Secondary (T, gates) replay: control
    30 rules, 2380 -> 2310 gates; LLM 1 rule, 2380 -> 2378; T unchanged.
  * Smoke test before run1: one LLM call (5,387 in + 1,670 out tokens) outside results/, not logged as a result.
- 2026-10-14 — v2 held-out evaluation (folded from results/v2/CHANGELOG_eval.md, kept):
  # CHANGELOG - v2 evaluation track
  
  ## 2026-10-14 - held-out evaluation `eval_v1` (no LLM arms, by user decision)
  
  - Added `experiments/v2_eval_heldout.py`, `experiments/v2_eval_report.py`, `experiments/v2_eval_figure.py`,
    `docs/v2/EVAL.md`, `results/v2/eval/` (EVAL_REPORT.md, eval_results.csv, eval_figure.png, README.md, per_circuit/,
    logs/, circuits/, run_logs/). No existing file edited; tier-1/tier-2 code untouched.
  - Freeze check before every circuit: 21 FROZEN.md hashes equal, verifier digest bc3eac23... unchanged before/after,
    tier-2 libraries v0 (0 rules, 4f53cda1...) and lex-secondary control (30 rules, 4bef8a90...) re-verified.
  - 22 held-out circuits: 18 evaluated; shor_14/shor_16 skipped (no rotation route in tier1-toolbox-v1);
    qcla_adder_10/qcla_com_7 blocked (recognizer normalization leaves unfused h/ccz -> exact check infeasible for n > 14).
  - Results: tier-1 control exact = best classical (our runs) on 17/18, worse on gf2^16_mult (pyzx-pass plans timed out
    in verification). Tier-2 v0: T unchanged everywhere (0 applications); lex-secondary: T unchanged, -361 / 17531 gates
    on classical starts, -1338 / 26671 on tier-1 exact outputs. Tier-1 control relaxed (Gidney temporary AND, Jones
    Toffoli, clean AND; always variant V2 + pyzx): below best classical on 15/18 (total 4968 vs 5728 T), at +1..+16 qubits
    and 9..241 measurements. LLM tokens used: 0.
  - Full test suite after the run: 295 passed.
- 2026-10-14 — notebooks/v2_group_meeting.ipynb (new, 24 cells, offline; builder scripts in notebooks/v2_assets/):
  v2 two-tier demo (tier-1 cached plan replay + live verification, tier-2 live rule proof, dev and held-out results).
  Existing notebooks untouched.
- 2026-10-14 — notebooks/group_meeting_demo.ipynb simplified: removed the no-LLM same-Pauli merge control from sections
  6c/6d/7 and the takeaways (result files unchanged; results/window_runs/stage1/control_pmerge.json kept). Section 3 gains a
  four-baseline plot; section 6d and 7 figures are now drawn in the notebook from the CSVs (old PNGs no longer displayed).
  Figures render via show_fig() (explicit PNG) because the in-process runner has no inline backend.

## 2026-10-18 engine refactor P1.0 (safety net)

- Pre-refactor snapshot commit 6c7d7ca (v2 stack, stage-1 runs, nam_arith, cvdv rulebook).
- Suites green before refactor: main 295 passed; cvdv acceptance 33 passed (env cvdv-opt).
- `results/engine/BASELINE_MANIFEST.json`: 126 baseline-critical files hashed (bqskit_baselines CSVs + stage-1 TKET inputs, v2 baselines/eval/frozen tier-2 libraries, stage-1 window-run outputs, ablation report, cvdv results + rulebook, all playbooks); dv frozen digest bc3eac23... and cvdv FROZEN.sha256 recorded. Permanent guard: `tests/engine/test_manifest.py`.
- Golden behavior fixture `tests/engine/golden_dv.json` (scripted-LLM WindowLoop run: 2 accepts T 242->202->200, 1 llm error, 1 decline, reflector add) + equivalence test `tests/engine/test_golden_dv.py` — the P1.2 gate.
- No frozen file, baseline, or result was modified.

## 2026-10-18 engine refactor P1.1 + P1.2 (extraction + dv_windows plugin)

- NEW `circuitevolve/engine/`: domain-blind EvolveLoop (exact extraction of core/loop.py control flow), DomainPlugin contract + Member, ledger/playbook re-exports (implementations stay at core/ledger.py and search/playbook.py — paths unchanged).
- NEW `circuitevolve/domains/dv_windows/`: the stage-1 window core as a plugin (select = T-cost-ranked windows, mutate = literal window/fix prompts, verify = frozen verify_window, measure = BqskitTMetric); verify/check callables late-bind through core/loop.py (monkeypatch surface preserved).
- `core/loop.py` is now a 4.5KB shim (was 22.7KB): WindowLoop(EvolveLoop) with identical constructor, run(), TASK_TEXT, RUNS, _choose_windows/_member/ledger0 surfaces.
- Gates: golden equivalence test PASSED unchanged (identical accepts/charges/prompt hashes/stats vs pre-refactor fixture); full suite 306 passed (300 + 6 new contract tests); dv frozen digest bc3eac23 unchanged; cvdv untouched.

## 2026-10-18 engine refactor P1.4 (router v0 + playbook tiers + optimize entry point)

- `engine/router.py`: deterministic tier-0 routing (literal QASM scan, no eval): terms -> cvdv.bosonic; 0 Toffolis + non-Clifford rz -> dv.windows; else NeedsTriage (LLM triage + arithmetic family land in point 3). Every decision appended to results/engine/routing_log.jsonl.
- `engine/run.py`: optimize(source, eps, complete) - stage-1 name / QASM / terms, no domain named; summary gains a routing section. B0-identity gate through the routed path: tests/engine/test_optimize_b0.py (qft_8, tfim_6 == B0 t_count_canon).
- Playbook tiers (machinery only, content copied verbatim): playbooks/router.json; families/dv.windows.json = byte-identical dev_v1.json copy; families/cvdv.bosonic.json = 6 cvdv rulebook insights as seed rules; graduated/index.json = EMPTY hash-checked library (tamper + file-drift tests).
- `engine/{graduate,reflector,recognize}.py`: graduation formats/provenance/loader, the point-2 reflector seam (AcceptAnatomy), recognizer re-export.
- Gates: engine suite 30 passed; full suite green; frozen digests unchanged; originals (dev_v1.json, cvdv rulebook) untouched.

### Correction to P1.1+P1.2 entry

The P1.1+P1.2 entry (and commit d25948f message) says "306 passed (300 + 6 new contract tests)"; the actual gate run printed **307 passed** - 300 baseline + 7 new tests in tests/engine/test_contract.py. Count error in the notes only; the gate itself was green as stated.

## 2026-10-18 engine refactor P1.3 (cvdv plugin, wrap-in-place)

- NEW `circuitevolve/domains/cvdv/`: CvdvRulesPlugin + benchmark_plugin — the frozen CV-DV certified compiler behind the engine contract. State = rule-library source; tasks = term kinds by certified-duration share; candidates = restricted-DSL rule functions (regex parse, frozen library.load path, evolve.py collision policy); verify = frozen per-instance certificate; measure = certified compile_step under the existing lexicographic metric; exact rules charge 0.
- optimize() cvdv branch wired: {"benchmark": <name>} input; raw term lists deferred to the first unified campaign.
- Gates (run in env cvdv-opt): engine loop ACCEPTS scripted rule_n2__parity_exact via the frozen certifier (3 two-op / 6 one-op per n2 term, charge 0); boseHubbard_small via the plugin measure path + Genesis routing reproduces the compare_isas hashseed-0 ours row EXACTLY (44/30/74/393, eps_bound 7.53e-15); cvdv acceptance 33 passed before AND after; check_frozen.sh all OK; venv suite 325 passed + 2 expected skips (qutip-gated); zero-accept optimize reproduces the rulebook compile.
- Documented deviations: existing cvdv metric has no ancilla component (followed the code); global/final check = bound_valid AND eps_bound <= eps_total (every compile re-certifies from scratch, so the windowed bound does not apply); input_check 0.0 (avoids double-counting the start certificate).
- Built by a sub-agent; files reviewed; no frozen/engine/dv_windows files touched.

## 2026-10-18 engine refactor P1.5 (docs + sweep) — POINT 1 COMPLETE

- `docs/ENGINE.md`: architecture, plugin contract, tiers, routing, run examples, deferred seams (points 2-3).
- CLAUDE.md: current-work section + layout updated for engine/ + domains/ + playbook tiers; window-core section unchanged and still accurate.
- Root-level exploratory PNGs (7) moved to results/figures_archive/ (git mv, history preserved).
- Final state: suite 325 passed + 2 qutip-gated skips; dv frozen digest bc3eac23 unchanged; cvdv FROZEN.sha256 all OK; BASELINE_MANIFEST guard green (126 files intact). Phases P1.0-P1.5 all complete.

## 2026-10-18 playbook overhaul P2.1 (accept-anatomy reflector input)

- `plugin.accept_anatomy()` hook (default: metric-level facts); DV impl: rotation multiset diff with Pauli frames (reuses core/mutator.rotation_paulis), removed/added angles, equal-frame-merge flag.
- Engine collects AcceptAnatomy per accept; the rendered anatomy block (action, mode, distance, charge, frames, deltas, rules shown) is appended to each accepted-improvement entry the reflector reads.
- Failure stream COMPRESSED at reflect time: rejections since the last reflection grouped by numeric-normalized reason class, <= 4 groups with counts + 1 example each (was: raw last-6 stream).
- Proposer prompts, acceptance, credit, and all pinned record fields untouched: golden fixture passes UNCHANGED. Gates: 5 new anatomy tests green (merge anatomy frames/angles, anatomy in reflect prompt, x5-grouped rejection line, compression bound, compact render); full suite green.

## 2026-10-18 playbook overhaul P2.2 (seeding: FTQC primer + certified literature harvest)

- dv.windows: 8 seed rules (R29-R36, origin=seed, status=candidate, marker "[seed 2026-10-18 FTQC primer]") via experiments/engine_seed_playbooks.py - equal-P merge + frame-preservation check + fix-and-refit, snap guard, pi/4 folds, no-zero-without-compensation, branch-phase discipline, one-change-per-candidate. Inherited dev_v1 rules byte-identical; A/B settings unweakened (guard test).
- cvdv.bosonic: budgeted literature harvest (sub-agent; arXiv:2407.10381 LaTeX source, sections VII.C.1-3 + VIII.C.5-7; 2/8 candidates, 6/12 LLM calls). BOTH candidates certified EXACT at n_max=3 through the frozen path (digest 0e83ded3): (R7) weight-2 Pauli gadget as 4-CD phase-space loop - 4 two-op/dur 80 vs incumbent 8 two-op + 4 one-op/dur 164, i.e. HALVES the 2-op cost on the known loss case vs Genesis; (R8) Z->X/Y basis conjugation of z_hop - first rule coverage for pauli_hop. Honest declines: n2 (BCH plateau, consistent with playbook #6), hop/disp (native gates optimal). Full record: results/engine/harvest_cvdv_2026-10-18.{md,json}; certified rule functions live in the report, rules.py untouched (appending is a campaign action).
- Seeds obey invariant 7: candidates under unchanged A/B machinery; credit only on measured improvement (tests). cvdv acceptance check_frozen OK; suite 333 passed.

## 2026-10-18 playbook overhaul P2.3 (graduation bridge + first graduation G1)

- engine/graduate.py: promote() (active-rule route, or candidate ONLY with documented evidence - silent promotion refused), hash-checked load_callable, apply_graduated for kind=pass. GraduatedRule gains an `evidence` field.
- FIRST GRADUATION G1: playbooks/graduated/same_pauli_merge.py - byte-level port of the ablation no-LLM control (experiments/window_pmerge_control.merge_once); every application re-verified by the frozen window verifier at 1e-12 (stricter than verify-once); provenance: dv.windows seed R29 + ablation control evidence (10.4-14.7% vs B0) recorded as an evidence-override in the index entry.
- Dev replay (results/engine/graduation_pmerge.json, verifier digest bc3eac23): stage-1 at 1e-3, total T 87821 -> 80555 (-8.27%); merge-rich circuits qft_8 2391->2115, qpe_8 14761->12597, qae_13 7821->6683, hhl_8 35450->31762 (-10.4..-14.7%, matching the ablation range); 0 merges on TKET-saturated heisenberg_6/tfim_6/hubbard_8/qml_13; max merge distance 1.4e-15; all whole-circuit checks ok; no risers -> KEEP.
- optimize() pre-opt stage: graduated passes run before the loop (default on; graduated=off for baseline-exact runs); gains reported in a separate pre_opt section, never as LLM gains; the loop input check charges the measured aggregate distance.
- Gates: B0 identity unchanged with graduated=off; graduated=on zero-accept == replay record exactly (qft_8, tfim_6); tamper/refusal tests; suite 340 passed.
