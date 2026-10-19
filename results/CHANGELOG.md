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

## 2026-10-18 playbook overhaul P2.4 (campaign protocol + end-to-end dry run)

- docs/P2_CAMPAIGN.md: the binding contract for the first real-LLM campaign (run separately, budget-approved). Dev {qft_8, heisenberg_6, hubbard_8, qml_13, hhl_8} / held-out {qpe_8, qae_13, tfim_6} at 1e-3 (+1e-5 corroboration arm); arms A seeded-learning / B placebo / C none mirroring ablation v1 as comparator; G1 pass ON in all arms, gains attributed separately and NEVER to the playbook (its replay touched all 8 circuits); power floor >=40 calls/circuit/arm with honest MDE ~5pp on 3 held-out circuits; freeze procedure (SHA playbooks+graduated, reflector off on held-out, model pinned); futility stop.
- tests/engine/test_p2_dryrun.py: ONE fake-LLM optimize() run exercising the whole P2 stack - G1 pre-opt merge (rz 3->2), seeded rules in proposer prompts (A/B-sampled), scripted t;t->s accept on the post-pass circuit (approx path, q-grid dust charge), anatomy block in the reflector prompt, family playbook file untouched (tmp copy), ledger bound holds.
- Suite 341 passed.

## 2026-10-18 playbook overhaul P2.5 (docs + close) - POINT 2 COMPLETE

- ENGINE.md: point-2 section (anatomy, seeds incl. harvest numbers, G1 graduation, campaign contract); phase log updated. CLAUDE.md layout line updated.
- Final state: suite 341 passed + 2 qutip-gated skips; dv frozen digest bc3eac23 unchanged; cvdv FROZEN.sha256 all OK; BASELINE_MANIFEST guard green. Phases P2.1-P2.5 complete.
- What point 2 changed, in one line each: the reflector reads accept anatomy + grouped rejections; both family playbooks are seeded (primer + certified literature); the first rule graduated to verified code (G1, -8.27% dev T, separate attribution); the first-campaign contract is frozen in docs/P2_CAMPAIGN.md.

## 2026-10-18 method cascade P3.0 (plan start-state record)

- PLAN_P3 (docs/PLAN_P3.md, commit 4af6778) execution starts here. Start state verified:
  - circuitevolve suite (.venv): 341 passed + 2 skipped.
  - cvdv suite (conda env cvdv-opt): 33 passed; `bash cvdv/scripts/check_frozen.sh` OK.
  - `circuitevolve.integrity.frozen_digest()` = bc3eac23a403dbc594265a91ebb9f0ff12672dc913c56c5cf5d9d950c2a242c6 (unchanged).
  - tests/engine/test_manifest.py green (runs inside the full suite).
- Housekeeping: 7 routing-log rows appended by post-P2 dry runs (results/engine/routing_log.jsonl)
  were sitting uncommitted; committed here unmodified (append-only, no existing row touched).
- No code changes in this commit.

## 2026-10-18 method cascade P3.1 (reconstruction benchmark suite)

- experiments/engine_recon_bench.py (deterministic, no LLM) scanned 48 candidates (40 nam_arith
  MANIFEST rows incl. generated cuccaro_* + 8 stage-1 rotation inputs); 40 fire the predicate
  `pairs>=1 OR mcx>=1 OR naive_t_share>=0.2` (naive_t_share = 7*toffolis/(7*toffolis+t_like), raw
  form); suite = the 11 plan-named circuits (all fire). Evidence for every candidate (incl. the
  29 firing-but-uncurated and the 8 non-firing stage-1 inputs) preserved in
  results/engine/recon_bench/MANIFEST.json with source sha256s.
- Open decision 2 settled: tof_5, rc_adder_6, qcla_adder_10, mod_adder_1024, gf2^4_mult all enter
  from benchmarks/nam_arith/logical/ (present there; provenance = MANIFEST.csv rows).
- Decomposed twins (lifting stress set): TKET pass sequence of blocks/classical.tket_optimise via
  the v2_bench_common.tket_arm adapter (ccz -> h ccx h; FullPeepholeOptimise -> AutoRebase{CX,H,Rz}
  -> RemoveRedundancies) + emit_rz lowering to named Clifford+T gates; every twin equivalence-
  checked (sparse 24-trial pair check; ZX identity where sparse support exceeded the cap:
  cuccaro_16, qcla_adder_10). Twin T-counts match recorded v2 tket_fpo_logical where available
  (adder_8 361, cuccaro_16 192, barenco_tof_10 192, mod_adder_1024 1711).
- baselines.csv (54 rows): naive_T computed; B0_tket = twin T-count (computed, cross-referenced);
  B1_pyzx + deterministic-control exact/relaxed rows COPIED from verified v2 records
  (results/v2/tier1/dev_results.csv, results/v2/eval/eval_results.csv, bench_runs JSON fallback),
  per-row provenance; relaxed column separate. qcla_adder_10 control bar recorded as BLOCKED
  (v2 verifier coverage), not invented - circuit stays in the suite (twin + features valid).
- Stage-1 and general-angle candidates (shor_12 u1 angles) scanned counts-only (exact-IR parser
  is pi/4-grid); recorded with reason, kept=false.
- Gate: tests/engine/test_recon_bench.py (6 tests: feature reproduction on cuccaro_4 + rc_adder_6,
  suite membership, twin + source sha256, baselines shape); suite 347 passed + 2 skips; digest
  bc3eac23 unchanged; no existing file modified.

## 2026-10-18 method cascade P3.2 (router v1: method predicates + cascade)

- playbooks/router.json migrated /0 'families' -> /1 'methods' (reconstruction | angle | cvdv),
  each row: predicate parameters, contract, plugin id, playbook path, cascade rank, frozen
  family label. Frozen names kept per plan section 2: angle keeps playbook
  playbooks/families/dv.windows.json + graduated_family 'dv.windows' (G1 entry untouched); cvdv
  keeps cvdv.bosonic.json. The /0 'arithmetic' reserved row is superseded by the reconstruction
  method. /0 table preserved in git history; pre-migration routing_log rows reference router/0.
- engine/router.py: route() now returns an ordered list[MethodBinding] (open decision 3 settled:
  MethodBinding = own dataclass, FamilyBinding fields + method/rank/status/evidence; FamilyBinding
  kept for pre-/1 consumers). Predicates (open decision 1 settled): reconstruction fires at
  toffolis>=1 AND (pairs>=1 OR mcx>=1 OR toffoli_naive_t_share>=0.2), pair/MCX evidence from the
  v2 recognizer on the RAW input (counts-only fallback outside the exact-IR grid); angle fires at
  >=1 non-Clifford rotation where t/tdg AND Toffolis count as non-Clifford rotation content
  (a Toffoli-bearing circuit always has an angle stage - its T content is what angle polishes).
  Pure Clifford -> empty cascade. NO LLM in routing; manifest {family|method} override = single-
  stage cascade (legacy names dv.windows/cvdv.bosonic map to angle/cvdv). Log rows now carry the
  cascade + predicate evidence (router/1 tag).
- engine/run.py: optimize() executes the cascade, threading each stage's verified output into the
  next ({'ops','n','name'} payload seam; producer lands in P3.3) and emitting per-stage sections
  (stages: [{method, family, contract, t_before/t_after, verified, reason}]). Single-stage runs
  keep the pre-/1 top-level summary shape BIT-EXACT; pure-Clifford input returns
  status='unchanged' with an explanatory summary (not an error). Reserved reconstruction method
  routes but refuses execution with a clear NotImplementedError until P3.3.
- engine/tketpass.py: the angle method's TKET entry pass (frozen Baselines sequence:
  FullPeepholeOptimise -> replace_implicit_wire_swaps -> AutoRebase{CX,H,Rz} ->
  RemoveRedundancies + emit_rz lowering) + angle-tolerant literal QASM reader. 'auto' semantics
  SETTLED to honor both section 1.3 and the bit-exact gate: the pass fires only when the stage
  input contains Toffolis (the window core takes CORE_GATES only) or arrived from a previous
  cascade stage; stage-1 named inputs and first-stage pure-rotation QASM keep today's path
  byte-identical. Never before reconstruction (cascade order enforces it). Entry-pass gains are
  reported in their own tket_entry section - deterministic, never sold as LLM gains.
- Tests: test_router.py rewritten for /1 (9 -> 10 tests; log test now writes to tmp);
  test_cascade.py new (4 gates: pure-Clifford pass-through, cuccaro_4 refusal until P3.3,
  TKET entry on a sub-threshold-share Toffoli input incl. final check vs the decomposed entry
  form, stage-1 summary-shape guard). Gates: (a) B0 identity / graduated on-off / golden /
  dry-run pass UNCHANGED; (b) pure-Clifford unchanged; (c) cuccaro_4 raw routes
  [reconstruction, angle] (recognizer pairs evidence); (d) log rows carry evidence.
  Suite 352 passed + 2 skips; digest bc3eac23 unchanged; cvdv untouched.
- routing_log.jsonl rows appended by this suite run committed (append-only; tests that exercise
  optimize() log real decisions - pre-existing behavior).

## 2026-10-18 method cascade P3.3 (reconstruction method plugin)

- circuitevolve/domains/reconstruction/plugin.py: v2/tier1 behind the DomainPlugin contract,
  wrapping recognize/plan/compile UNCHANGED and calling the FROZEN v2 relaxed verifier through
  compile.evaluate + verify.check_integrity (never reimplemented; same frozen digest as the DV
  stack, checked at plugin construction and by the engine at loop start/end). Mapping: state =
  current best verified compilation (start = input, naive frozen cost); task = ONE whole-circuit
  planning problem (the recognizer element menu; key = parent digest); candidate = one literal
  JSON plan (v2 parse_plan, no exec/eval); measure = (T, qubits, T-depth) lexicographic in the
  RELAXED column, verdict_mode recorded per accept; ledger untouched (charge 0, exact branch-wise
  per v2 conventions). The deterministic control route (v2/tier1/control.py) is the no-LLM arm,
  fed through the SAME engine path as scripted completions.
- cascade_payload(): hands the angle stage the largest measurement-free Clifford+T segment +
  fixed-T remainder; run.py staged branch reports WHOLE-stage totals (segment_loop section keeps
  the loop's own numbers) so per-stage attribution never hides the unoptimized remainder. A
  zero-accept reconstruction stage threads the ORIGINAL source onward (angle then runs its
  normal raw path).
- run.py: _run_reconstruction (relaxed contract tag, declared_zero from the caller's manifest,
  runs under results/engine/recon_runs when tagged); router.json reconstruction row flipped
  reserved -> active (plugin 'reconstruction').
- playbooks/families/reconstruction.json seeded (6 rules, origin=seed, status=candidate,
  provenance-tagged '[seed 2026-10-18 tier-1 toolbox]' like P2.2): temporary AND (Gidney 2018),
  Jones Toffoli / measurement-based uncompute (Jones 2013), clean-AND compute-only,
  relative-phase Toffoli pairing (Maslov 2016), the dev routing lesson 'mirror pair into
  declared-zero target => temporary-AND first', MCX cascades (Barenco 1995 + Maslov). Credit
  accrues only under the unchanged A/B machinery (invariant 7).
- Gates: (a) scripted control plans through the ENGINE loop reproduce the v2 deterministic-
  control numbers on 4 suite circuits (cuccaro_4 16T/14q, rc_adder_6 40T/16q, tof_5 16T/10q,
  barenco_tof_5 36T/13q - equal T AND qubits vs results/v2/tier1/dev_results.csv best rows),
  ledger spend 0; (b) zero-accept run returns the input unchanged (56T cuccaro_4, explicit
  reason); bad plan rejected, never silently accepted; (c) fake-LLM cascade e2e on cuccaro_4:
  reconstruction (control V1/V2) then angle (G1 + declining loop) = 16T final, strictly below
  the angle-only arm (48T twin after TKET entry), per-stage attribution 56->16->16 with
  contracts separated (relaxed | approx); (d) suite 358 passed + 2 skips, digest bc3eac23
  unchanged, cvdv frozen OK.

## 2026-10-18 method cascade P3.4 (structure lifting, deterministic core)

- engine/lift.py: exact span matcher for the standard 7-T Toffoli network and the Maslov RCCX
  over {h,s,sdg,x,z,t,tdg,cx,cz}. Candidate spans are per-qubit projected subsequences on a
  3-qubit support (minimal op span), and EVERY claim is verified EXACTLY before substitution:
  the span's 8 basis columns are computed in D[omega] (the frozen sparse simulator sim.py) and
  compared to the CCX/RCCX reference columns up to one global unit phase omega^j (recorded per
  claim). Soundness rules: an op straddling the support ends the window; a BYSTANDER rule
  rejects claims whose support grew onto a qubit that skipped ops already touched (substitution
  at span start would reorder non-commuting ops - caught by a whole-circuit exact test during
  development and fixed before commit). RCCX claims are REPORTED, not substituted by default
  (a lone relative-phase Toffoli is not a ccx; no rccx gate downstream). LLM spotter =
  call-site stub behind lift_llm=False raising NotImplementedError (budget-gated, outside P3).
- Wiring: route() pre-recognition fires ONLY at toffolis==0 AND t+tdg>=7; on recovery the
  cascade routes AND EXECUTES on the lifted form (MethodBinding.lifted_source, excluded from
  log rows; lift counts logged in evidence).
- results/engine/recon_bench/lifting_report.json + decomposed_plain/ twins (sha256'd):
  * DOCUMENTED DEVIATION from the P3.1-twin-only reading of the gate: the FullPeepholeOptimise
    stress twins carry NO exact CCX/RCCX projected spans anywhere (verified by exhaustive
    per-triple search): global peephole optimization absorbs Toffoli-local Cliffords into
    neighbours and cancels T across construction boundaries. Stress recovery = 0/11 circuits,
    recorded honestly (plan: no minimum imposed) with the finding in the report.
  * decomposed_plain/ = macro-expanded base set (standard qelib 7-T splice of every ccx/ccz in
    the RAW suite circuits - the realistic lift target: toolchain-expanded, not re-optimized).
    Base recovery 11/11 circuits at 100% (285/285 on mod_adder_1024), naive-T conserved
    (7*ccx + t_left == naive) on every circuit.
- Gates: (a) lifting_report.json per-circuit rates; zero false structures re-verified by a
  whole-circuit exact D[omega] comparison on basis probes (barenco_tof_5, nested/macro-claim
  shape) + roundtrip lift(expand(cuccaro_4)) == raw op-for-op; (b) decomposed_plain cuccaro_4
  lifts (8/8), routes [reconstruction, angle] with lift evidence, and the cascade (16T) beats
  the angle-only arm on the same decomposed input; (c) lift NEVER fires when ccx is present
  (raw path routes without lift evidence, bit-identical behavior). Suite 366 passed + 2 skips;
  digest bc3eac23 unchanged.

## 2026-10-18 method cascade P3.5 (candidates-per-call knob + 3v5 A/B harness)

- max_candidates threaded end to end on the proposal side ONLY (invariant 7: acceptance,
  verification and the ledger untouched): core/mutator.py already parameterized the prompt
  text ({maxc}) and both parser caps; dv_windows plugin now carries the knob
  (DvWindowsPlugin(max_candidates=...), used in build_prompt + extract_proposals) and
  WindowLoop exposes it as a constructor kwarg (default 3). Fixed within any run/arm.
- Gates: golden fixture byte-identical at default 3 (test_golden_dv, unchanged, in suite);
  tests/engine/test_max_candidates.py (4 tests): default cap 3; 5-cap parses 5 of 6 blocks;
  prompt wording moves 'at most 3 blocks' -> 'at most 5 blocks' and differs in NOTHING else;
  WindowLoop threads the knob into the live plugin. Suite 370 passed + 2 skips; digest
  bc3eac23 unchanged.
- experiments/engine_ab_candidates.py: 3v5 A/B harness per docs/P2_CAMPAIGN.md conventions
  (arms fixed per run, P2 dev set qft_8/heisenberg_6/hubbard_8/qml_13/hhl_8 @ 1e-3, shared
  per-circuit seeds across arms, playbook FROZEN during the A/B, graduated ON both arms,
  >= 12 calls/circuit/arm, paired per-circuit report appended under
  results/engine/ab_candidates/). BUDGET-GATED: the script refuses to run without
  --yes-i-have-approval; real-LLM execution requires explicit user approval and is NOT part
  of P3 execution (committed not run).

## 2026-10-18 method cascade P3.6 (cascade demo + docs + close)

- results/engine/recon_bench/DEMO.md (zero LLM, reproduces from experiments/engine_cascade_demo.py):
  * raw cuccaro_8: cascade 32 T (relaxed, per-stage 112->32->32) vs angle-only 96 (approx) vs
    best classical B0 96 / B1 64 (exact) - contract columns separated, per-stage attribution
    shown incl. the deterministic TKET entry and G1 rows (never sold as LLM gains).
  * mixed circuit (open decision 4 settled: benchmarks/mixed/cuccaro_4_rot.qasm = cuccaro_4
    body + 5-rotation payload, built by the demo script, sha256 recorded): cascade 130
    (16 named T relaxed + rotation estimate) vs angle-only 162. MIXED-INPUT SEMANTICS added to
    _run_reconstruction: general-angle rotations cannot enter the v2 exact-IR pipeline, so
    reconstruction rewrites the largest Toffoli-bearing grid segment through the FROZEN
    verifier, passes rotation segments through untouched, and hands the rotation-richest
    measurement-free segment to the angle stage; named-T and rotation-estimate columns are
    never summed across contracts (documented in DEMO.md).
- Whole-circuit check honesty: stage records now distinguish verified=None (size-capped check
  SKIPPED, e.g. n=26 cuccaro_8 angle stage) from False (FAILED); DEMO prints the distinction.
- Staged angle totals made metric-consistent: t_before/t_after = fixed named T + the LOOP's
  own segment numbers (one column; the pre-entry named count stays in the staged section).
- tests/engine/test_cascade.py +1 (mixed e2e: routes [reconstruction, angle], 56->16 relaxed
  verified, rotations passed through, cascade beats angle-only).
- docs/ENGINE.md: routing section rewritten for the /1 method cascade (+ lifting + mixed
  semantics); point-3 section now records what P3 delivered; phase log updated. CLAUDE.md:
  engine summary + layout lines (router /1, tketpass.py, lift.py, domains/reconstruction,
  playbooks reconstruction seeds).
- CLOSE: PLAN_P3 executed end to end, 7 commits (eb71a4d e749f52 9797117 94a8311 47868ff
  e8eb845 + this one). Final state: circuitevolve suite 371 passed + 2 skipped (started
  341+2); cvdv suite 33 passed; dv frozen digest bc3eac23 UNCHANGED; cvdv FROZEN.sha256
  UNCHANGED; results/ append-only throughout (the one documented deviation: P3.4 stress-twin
  recovery is 0 - recorded as a finding, with the macro-expanded base set added for the
  realistic lift target). All real-LLM work remains budget-gated and NOT executed
  (engine_ab_candidates.py refuses without explicit approval; lift_llm spotter is a stub).

## 2026-10-18 post-P3 fix: per-stage tags for tagged cascade runs

- Tagged multi-stage runs collided on the append-only run log (both stages opened
  <tag>.jsonl; the second refused). optimize() now logs one file per STAGE:
  <tag>_s<i>_<method>.jsonl. Single-stage tagged runs keep the bare tag (pre-/1 behavior
  bit-exact; golden/B0 untouched). Found during a demo dry run. Suite 371+2; digest
  bc3eac23 unchanged.

## 2026-10-19 recon_campaign1 P0 (literature seed harvest)

- Approved campaign plan: reconstruction-method training (dev learning + frozen held-out),
  literature harvest first; models pinned by the user: proposer = claude-opus-5-5,
  reflector/rule-compiler = claude-sonnet-5-5 (user: "opus for reasoning, sonnet for
  compiling rules"). The dv.windows 3-arm P2 campaign is DEFERRED (not run).
- playbooks/families/reconstruction.json +4 seeds (R7-R10, next_id 11): whole-adder pairing
  strategy + compute/uncompute asymmetry (Gidney arXiv:1709.06648), ancilla-vs-T tradeoff
  (Barenco 1995; ICCS 2022 4n-4 survey), floor awareness (arXiv:2610.01024 isotropy bound,
  2026). playbooks/families/dv.windows.json +2 seeds (R37-R38, next_id 39): parity-phase
  fusion + distinct-odd-parity lessons (de Beaudrap et al. TQC 2020; Heyfron-Campbell TODD;
  Vandaele arXiv:2407.08695) for the deferred angle campaign.
- All origin=seed, zero counters, provenance in note fields: credit only accrues through the
  unchanged A/B machinery (invariant 7). Suite 371 passed + 2 skips after seeding; digest
  bc3eac23 unchanged.

## 2026-10-19 recon_campaign1 start record (P1 backend pin)

- Campaign driver committed: experiments/engine_recon_campaign.py (driven from the platform
  kernel; host.llm backend). Models PINNED: proposer claude-opus-5-5, reflector
  claude-sonnet-5-5, thinking disabled, max_tokens 8000, retries 3.
- Protocol: single-stage reconstruction (manifest method override); DEV learning ON
  (20 calls/circuit, batch 1, seed 0, reflect_every 8): cuccaro_4 cuccaro_8 barenco_tof_5
  tof_5 rc_adder_6. HELD-OUT frozen (12 calls/circuit, playbook_frozen=True - new freeze
  kwarg on the reconstruction runner, loop gates reflector+save on pb.frozen): cuccaro_16
  adder_8 qcla_adder_10 barenco_tof_10 mod_adder_1024 gf2^4_mult.
- Zero-LLM comparators: deterministic control, naive_T, committed B0/B1 (recon_bench).
- Pre-campaign playbook sha256 (post-P0 seeds): 06d015e65b213c9cc47b77b18461d984a835de582bf3bc17200c11b23e5865ca
- Start state: suite 371 passed + 2 skipped; digest bc3eac23 unchanged; commit 481f9ac.

## 2026-10-19 recon_campaign1 pin amendment (adaptive thinking)

- The pinned 5-5 generation models reject thinking=disabled (API: use adaptive).
  llm_backends.make_api_backend now accepts a thinking DICT passed through verbatim
  (default False -> disabled unchanged, bit-exact for existing callers). Campaign pins
  amended: both backends thinking={"type":"adaptive"}, max_tokens 16000 (thinking tokens
  count toward the cap). Recorded BEFORE any campaign proposer call: the failed first launch
  spent 1 call that errored at request validation (0 tokens).
