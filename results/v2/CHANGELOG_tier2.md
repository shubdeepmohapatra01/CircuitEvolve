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
