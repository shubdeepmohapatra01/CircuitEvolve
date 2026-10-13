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
