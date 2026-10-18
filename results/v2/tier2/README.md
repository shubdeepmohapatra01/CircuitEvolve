# results/v2/tier2 - tier-2 rule library (append-only)

Start with [DEV_REPORT.md](DEV_REPORT.md). Design: [docs/v2/TIER2.md](../../../docs/v2/TIER2.md).

| file | content |
|---|---|
| `library_final.json` / `.sha256` / `.md` | FROZEN primary library, LLM arm (run1): v0 = empty (no version beat v0) |
| `library_control_final.json` / `.sha256` / `.md` | FROZEN primary library, no-LLM control (run1): v0 = empty |
| `library_lex_secondary_{llm,control}.json` | SECONDARY replay with (T, gates) acceptance (gate-count only; not primary) |
| `dev_results.csv` | per DEV circuit: start arm/T/gates, best classical, final T both arms, secondary gates, checks |
| `generations.csv` | per generation and arm: proposals, verifications, candidate totals, accepted, library SHA, reason |
| `rules_verified.csv` | every verified rule (both arms): pattern, replacement, dT, dgates, applications, meaning, outcome |
| `transfer_nonbest_dev.csv` | verified rules applied to the other (non-best) verified classical DEV outputs |
| `diagnostics.json` | pool sizes, headroom probe, outcome counts, tokens, frozen SHAs |
| `tier2_dev_summary.png` | figure: total DEV T per generation, fate of rules, secondary gate replay |
| `run1/` | raw logs: `{llm,control}_generations.jsonl`, `{llm,control}_rules.jsonl`, `llm_llm_calls.jsonl` (prompts' SHA + full responses), `libraries/` |
