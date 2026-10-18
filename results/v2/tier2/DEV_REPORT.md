# Tier 2 (executable rule library) - DEV report, run `run1`

Date 2026-10-14. Scope: UNITARY-PRESERVING rewrite rules on exact Clifford+T circuits (no measurement, no ancillas).
DEV circuits only (split v2-nam-arith-1); held-out circuits were not loaded, read or run. Code:
`circuitevolve/v2/tier2/`, `experiments/v2_tier2_evolve.py`, `experiments/v2_tier2_report.py`; design in
`docs/v2/TIER2.md`. Raw logs: `results/v2/tier2/run1/` (one JSON line per generation, per proposed rule, per LLM call).

## Verdict

**Null result for both arms.** In 18 generations neither the LLM arm (36 LLM calls, 54 rules
verified) nor the no-LLM enumeration control (same 117 rule verifications) lowered the total
DEV T-count: it stays at 758 (the best computed classical outputs) on every generation for both arms. No library
version beat v0, so the frozen primary library is **v0 = empty** for both arms
(`library_final.json`, SHA-256 `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`; `library_control_final.json`, same content hash).
Diagnosis: the start circuits (pyzx full_reduce / Nam et al. Light outputs) are locally T-optimal with respect to every
short identity we can enumerate: none of the 8833 T-reducing identities in the control pool
(1 qubit <= 8 gates, 2 qubits <= 6, 3 qubits <= 4, plus 20k random 5-7-gate lookups per width) matches anywhere in the
16 start circuits (0 matches). The remaining gap to the best published numbers
(758 vs 652, from pyzx+TODD in Kissinger & van de Wetering 2020) comes from non-local
(Reed-Muller / TODD) phase-polynomial optimization, which <= 4-qubit templates cannot express.

## Setup

* **Start circuits** (`circuitevolve/v2/tier2/circuits.py`): per DEV circuit, the verified exact Clifford+T output with the
  lowest (T, gates) among pyzx_fr, tket_fpo, tket_fpo_logical (`results/v2/bench_runs/run2/circuits/`) and the Nam et al.
  Light file (`benchmarks/nam_arith/nam/`); eligibility = `verified=True` in `results/v2/baselines_new.csv` and our T-count
  equal to the CSV value (checked on load). TKET outputs with non-pi/4 rotations are not exact and were skipped.
  16 circuits; **shor_12 excluded** (continuous cp/ccp rotations, no exact Clifford+T output exists).
* **Rules**: pattern -> replacement over variables a-d, gates h s sdg t tdg x z cx cz; side condition `commute`
  (commutation-aware matching through a fixed, matrix-tested commutation table) or `contiguous`. Each rule is verified
  ONCE as an exact unitary identity up to global phase (v2 `verify(mode='exact')`, frozen D[omega] simulator, exhaustive
  over 2^k inputs, certified). Rules must strictly lower (T, gates) lexicographically, so fixpoint application terminates.
* **Acceptance** (both arms): candidate library = current + newly verified rules; applied to all 16 start circuits to a
  fixpoint (numeric whole-circuit guard vs the start circuit on every changed circuit); KEPT only if total DEV T drops and no
  circuit's T rises.
* **LLM arm**: 18 generations x 2 prompts (36 calls, `host.reasoning_model()` via `host.llm`, thinking disabled,
  max_tokens 6000). Each prompt: DSL + matching semantics, per-circuit T, current library, technique cards 07 (phase folding /
  T-par), 09 (Nam rotation merging), 03 (relative-phase Toffoli), 08 (pyzx), 6 T-containing windows (<= 4 qubits,
  <= 20 gates, convex, with neighbouring gates) from different circuits, and the last 14 verifier/evaluation outcomes.
  Tokens: 229,474 in + 68,095 out (2 responses hit max_tokens).
* **No-LLM control**: Quartz-style RepGen enumeration (42,270 minimal candidate identities,
  8,833 T-reducing); per generation it verifies exactly as many rules as the LLM arm did in that
  generation (schedule [3, 4, 10, 16, 6, 9, 7, 10, 2, 6, 6, 6, 6, 6, 1, 11, 4, 4]), choosing T-reducing rules that match the current circuits first, then
  rules by match count, then T-reducing rules, then the rest (seeded random tie-break).

## Per generation (total DEV T; 16 circuits)

| gen | LLM proposed | LLM verify calls | LLM verified | LLM total T | control verified | control total T | library (LLM / control) |
|---|---|---|---|---|---|---|---|
| 0 |  |  |  | 758 |  | 758 | v0 / v0 |
| 1 | 3 | 3 | 0 | 758 | 3 | 758 | v0 / v0 |
| 2 | 5 | 4 | 0 | 758 | 4 | 758 | v0 / v0 |
| 3 | 11 | 10 | 6 | 758 | 10 | 758 | v0 / v0 |
| 4 | 16 | 16 | 10 | 758 | 16 | 758 | v0 / v0 |
| 5 | 6 | 6 | 3 | 758 | 6 | 758 | v0 / v0 |
| 6 | 10 | 9 | 4 | 758 | 9 | 758 | v0 / v0 |
| 7 | 9 | 7 | 3 | 758 | 7 | 758 | v0 / v0 |
| 8 | 12 | 10 | 6 | 758 | 10 | 758 | v0 / v0 |
| 9 | 6 | 2 | 0 | 758 | 2 | 758 | v0 / v0 |
| 10 | 7 | 6 | 0 | 758 | 6 | 758 | v0 / v0 |
| 11 | 8 | 6 | 4 | 758 | 6 | 758 | v0 / v0 |
| 12 | 9 | 6 | 3 | 758 | 6 | 758 | v0 / v0 |
| 13 | 6 | 6 | 2 | 758 | 6 | 758 | v0 / v0 |
| 14 | 8 | 6 | 0 | 758 | 6 | 758 | v0 / v0 |
| 15 | 5 | 1 | 0 | 758 | 1 | 758 | v0 / v0 |
| 16 | 14 | 11 | 7 | 758 | 11 | 758 | v0 / v0 |
| 17 | 9 | 4 | 4 | 758 | 4 | 758 | v0 / v0 |
| 18 | 5 | 4 | 2 | 758 | 4 | 758 | v0 / v0 |

Every candidate library in both arms was rejected with "total dev T unchanged"; reasons per generation are in
`generations.csv`.

## Fate of proposed rules

| | proposed | not an identity | malformed | duplicate | parse error (blocks) | verified | verified T-reducing | verified & matched >= 1x on DEV |
|---|---|---|---|---|---|---|---|---|
| LLM | 149 | 48 | 15 | 32 | 4 | 54 | 35 | 1 |
| control | 117 | 0 | 0 | 0 | 0 | 117 | 47 | 52 |

Malformed LLM rules were mostly cost-neutral reorderings (11 rejected by the strict-decrease rule), three disconnected
patterns and one over-length rule; parse errors were uses of the context marker `o` inside rules. The 35 verified T-reducing LLM rules
are restatements of phase merging (e.g. `t a; cx a b; tdg a -> cx a b`, `t a; cz a b; t a -> s a; cz a b`, `t^4 -> z`,
`h a; t a; h a; cx b a; h a; tdg a; h a -> cx b a`), i.e. local identities that the start circuits no longer contain;
the only LLM rule that ever matched is `cx b a; cx b a -> id` (1 application, -2 gates, 0 T). Full list with the LLM's
one-line meanings: `rules_verified.csv`.

**Rules accepted into the primary library: none (both arms).** T saved per rule: 0 for every rule.

## Per circuit (T before/after; best classical = `v2.baselines.best_classical(c, 0)`, incl. published rows)

| circuit | n | start (best computed) | start T | best classical T (arm) | LLM final T | control final T | T saved | start gates | LLM lex gates | control lex gates | check (control lex) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| barenco_tof_3 | 5 | nam_light_file | 16 | 16 (best_prev_as_reported_by_kvdw2020) | 16 | 16 | 0 | 42 | 42 | 40 | exact:basis-exhaustive:True |
| barenco_tof_4 | 7 | nam_light_file | 28 | 28 (best_prev_as_reported_by_kvdw2020) | 28 | 28 | 0 | 78 | 78 | 74 | exact:basis-exhaustive:True |
| barenco_tof_5 | 9 | nam_light_file | 40 | 40 (best_prev_as_reported_by_kvdw2020) | 40 | 40 | 0 | 114 | 114 | 108 | exact:basis-exhaustive:True |
| csla_mux_3 | 15 | pyzx_fr | 62 | 45 (kvdw2020_pyzx_todd) | 62 | 62 | 0 | 261 | 261 | 241 | numeric:statevector-3:True |
| cuccaro_4 | 10 | pyzx_fr | 32 | 32 (pyzx_fr) | 32 | 32 | 0 | 160 | 160 | 150 | exact:basis-exhaustive:True |
| cuccaro_8 | 18 | pyzx_fr | 64 | 64 (pyzx_fr) | 64 | 64 | 0 | 301 | 299 | 284 | numeric:statevector-3:True |
| gf2^4_mult | 12 | nam_light_file | 68 | 52 (kvdw2020_pyzx_todd) | 68 | 68 | 0 | 187 | 187 | 187 | unchanged |
| gf2^5_mult | 15 | nam_light_file | 115 | 86 (kvdw2020_pyzx_todd) | 115 | 115 | 0 | 296 | 296 | 295 | numeric:statevector-3:True |
| gf2^6_mult | 18 | nam_light_file | 150 | 122 (kvdw2020_pyzx_todd) | 150 | 150 | 0 | 403 | 403 | 402 | numeric:statevector-3:True |
| mod5_4 | 5 | pyzx_fr | 8 | 7 (kvdw2020_pyzx_todd) | 8 | 8 | 0 | 51 | 51 | 48 | exact:basis-exhaustive:True |
| mod_mult_55 | 9 | nam_light_file | 35 | 20 (kvdw2020_pyzx_todd) | 35 | 35 | 0 | 91 | 91 | 91 | unchanged |
| rc_adder_6 | 14 | nam_light_file | 47 | 47 (best_prev_as_reported_by_kvdw2020) | 47 | 47 | 0 | 142 | 142 | 142 | unchanged |
| tof_3 | 5 | nam_light_file | 15 | 15 (best_prev_as_reported_by_kvdw2020) | 15 | 15 | 0 | 35 | 35 | 35 | unchanged |
| tof_4 | 7 | nam_light_file | 23 | 23 (best_prev_as_reported_by_kvdw2020) | 23 | 23 | 0 | 55 | 55 | 55 | unchanged |
| tof_5 | 9 | nam_light_file | 31 | 31 (best_prev_as_reported_by_kvdw2020) | 31 | 31 | 0 | 75 | 75 | 75 | unchanged |
| vbe_adder_3 | 10 | nam_light_file | 24 | 24 (best_prev_as_reported_by_kvdw2020) | 24 | 24 | 0 | 89 | 89 | 83 | exact:basis-exhaustive:True |
| **total** | | | **758** | **652** | **758** | **758** | **0** | **2380** | **2378** | **2310** | |

`best_prev_as_reported_by_kvdw2020` and `kvdw2020_pyzx_todd` are published values (Kissinger & van de Wetering 2020,
Table 1), not runs of ours; the best computed-and-verified value equals our start T on every circuit. The final libraries
are empty, so the LLM / control final circuits are the start circuits (no change to verify).

## Secondary analyses (not used for acceptance or freezing as primary)

1. **Gate-count replay** (`library_lex_secondary_{llm,control}.json`): replaying the RECORDED verified proposals with
   (T, gates) lexicographic acceptance (no new proposals or LLM calls). LLM: 1 rule kept, total gates
   2380 -> 2378. Control: 30 rules kept, 2380 -> 2310
   (-70 gates, -2.9 %); T unchanged in both. Changed circuits
   pass the exact whole-circuit check (frozen D[omega], exhaustive) for n <= 10 and the 3-state numeric guard above.
   The control's gate-saving rules are mostly CNOT-network identities, e.g.:

| # | pattern | replacement | applications | gates saved |
|---|---|---|---|---|
| 1 | `cx a b; cx c b; cx c a` | `cx c a; cx a b` | 7 | 7 |
| 2 | `cx a b; cx c b; cx a c` | `cx a c; cx c b` | 9 | 9 |
| 3 | `tdg a; cx b a; cx c a; cx c b; t b` | `tdg a; cx c b; t b; cx b a` | 6 | 6 |
| 4 | `s a; t a; cx b a; s a; t a` | `tdg a; z b; cx b a; tdg a` | 4 | 4 |
| 5 | `cx a b; cx b c; cx a b` | `cx b c; cx a c` | 5 | 5 |
| 6 | `cx a b; cx a c; cx c b` | `cx c b; cx a c` | 2 | 2 |
| 7 | `cx a b; cz c a; cz b c` | `cz b c; cx a b` | 2 | 2 |
| 8 | `s a; t a; cx a b; s b; t b` | `tdg a; z b; cx a b; tdg b` | 3 | 3 |
| 9 | `s a; t a; cx b a; z a` | `z b; tdg a; cx b a` | 2 | 2 |
| 10 | `tdg a; cx b a; s a; sdg b` | `t a; cz a b; cx b a` | 1 | 1 |
| 11 | `cx a b; cx c b; tdg b; cx a c` | `cx a c; cx c b; tdg b` | 0 | 0 |
| 12 | `z a; cx b a; s a; t a` | `z b; cx b a; tdg a` | 3 | 3 |
| 13 | `cz a b; cz c b; cx c a` | `cx c a; cz a b` | 2 | 2 |
| 14 | `cx a b; cx c a; cx a b` | `cx c b; cx c a` | 1 | 1 |
| 15 | `cx a b; t b; cx b c; cx a c` | `cx b c; cx a b; t b` | 0 | 0 |
| 16 | `s a; t a; cx a b; z b` | `tdg a; z b; cx a b` | 2 | 2 |
| 17 | `cx a b; cx c a; cx c b` | `cx c a; cx a b` | 2 | 2 |
| 18 | `cx a b; cx a c; cx b c` | `cx b c; cx a b` | 2 | 2 |
| 19 | `z a; cz a b; cx a b` | `cx a b; cz a b` | 1 | 1 |
| 20 | `cx a b; s b; cz a c; cz b c` | `cz b c; cx a b; s b` | 1 | 1 |
| 21 | `cx a b; cz c b; cz c a` | `cz c b; cx a b` | 1 | 1 |
| 22 | `tdg a; cx b a; s a; s b` | `t a; cx b a; cz b a` | 1 | 1 |
| 23 | `cx a b; cx c a; t a; cx a b` | `cx c a; t a; cx c b` | 1 | 1 |
| 24 | `cx a b; cx c a; tdg a; cx a b` | `cx c a; tdg a; cx c b` | 1 | 1 |
| 25 | `z a; cx a b; s b; t b` | `z b; cx a b; tdg b` | 1 | 1 |
| 26 | `cx a b; cx b a; cx a b; cx b a` | `cx b a; cx a b` | 2 | 4 |
| 27 | `cz a b; cz a c; cx c b` | `cx c b; cz a b` | 2 | 2 |
| 28 | `z a; cx b a; h b; z a` | `z b; cx b a; h b` | 1 | 1 |
| 29 | `cx a b; cx a c; t c; cx c b` | `cx c b; cx a c; t c` | 1 | 1 |
| 30 | `cx a b; cx a b` | `id` | 1 | 2 |

2. **Headroom probe**: 8,833 T-reducing enumerated identities, 0 of them match any start
   circuit.
3. **Non-best inputs** (`transfer_nonbest_dev.csv`): all verified rules of each arm applied to the 43 other
   verified exact classical DEV outputs (TKET, pyzx, Nam where not best). T saved: LLM 0, control
   0; gates saved: LLM 154, control 297; numeric guards all pass:
   True. Even on TKET outputs (up to 2.3x the best T-count, vbe_adder_3 tket_fpo_logical 56 vs 24) the remaining T is not reachable by
   these local templates: what pyzx/Nam remove is non-local.

## Interpretation

* At the same verification budget the LLM did not beat the enumeration control on T (both 0), and the control was better on
  the secondary gate metric (-70 vs -2 gates). This repeats the stage-1 lesson.
* The negative result is structural, not a budget problem: local exact templates (<= 4 qubits, commutation-aware) have no
  T-reducing match on phase-folded circuits. T reductions on these inputs need non-local methods (TODD / Reed-Muller
  decoding: published gap 106 T on DEV, concentrated in gf2 multipliers, csla_mux_3, mod_mult_55, mod5_4) or a
  different contract (tier 1 relaxed constructions with ancillas / measurement).
* Tier 2 can still matter downstream of tier 1: tier-1 constructions produce new local structure that pyzx/Nam have not
  seen; the frozen v0 library plus the secondary gate library are what the held-out evaluation should use.

## Caveats

* Greedy matching without backtracking; the commutation table is sufficient, not necessary (e.g. phase gadgets through
  CNOT targets are not commuted); patterns must be connected and in circuit order. A smarter matcher could find a few more
  matches, but the headroom probe (no T-reducing identity matches even once) bounds what it could gain for short rules.
* Whole-circuit guards: exact (certified) only for n <= 10; numeric random-statevector (not a proof) for 12-18 qubits. Rule
  soundness rests on the one-time exact proof of each rule plus the commutation table test.
* LLM proposals depend on the sampled windows (6 per prompt, seed 0); one run, one seed.
