# Self-evolving harness (2026-10-11)

The model weights are fixed, so we adapt what we control: the context the proposer sees, and later the
search code around it. This is the same idea as evolving-context methods (ACE: generator / reflector /
curator with incremental "delta" updates to a playbook, Zhang et al., ICLR 2026) and self-improving
harness work. One finding from that literature matters for us: *updating* a harness and *benefiting* from
the update are different things, so every change must be measured.

## Level 1 — playbook (implemented: `circuitevolve/search/playbook.py`)

| Role | Who | What it does |
|---|---|---|
| Generator | proposer LLM (`search/llm.py`) | Writes programs; ACTIVE rules (and A/B-sampled CANDIDATE rules) are shown in its prompt |
| Reflector | LLM, every `reflect_every` batches | Reads recent improvements (parent → child) and rejections (exact verifier reason); returns ≤ 3 JSON deltas: add / edit / retire |
| Curator | deterministic code | Validates deltas (literal JSON, ≤ 400 chars, no duplicates, ≤ 40 rules, cue words refused in blinded runs) and merges them |
| Gate | deterministic code | A candidate is shown in a random half of prompts. It becomes ACTIVE only if its raw verifier pass rate when shown is higher than when hidden (z ≥ 1.64 on Beta posteriors, ≥ 3 passes, ≥ 8 exposures). It is RETIRED if credibly worse or after 40 exposures without benefit. The reflector can retire candidates; it can only *demote* active rules back to candidate. |

Guards:
- **Verifier.** The verifier is frozen. `integrity.py` hashes the verifier files at the start and end of every run (invariant 7).
- **Evidence.** There is no reflection without evidence: if a batch evaluated no new proposals, the reflection is skipped. In the first smoke run the reflector wrote rules from prior knowledge alone, and one of them named Gidney.
- **Train/test split.** Learn on development rows, then evaluate with `--freeze-playbook` on held-out rows.
- **Budget.** Reflector calls are LLM calls and count toward the budget.

Usage:
```
.venv/bin/python experiments/search_llm.py --row cuccaro_B --arm evo --repair 300 --calls 120 \
    --playbook playbooks/dev.json --reflect-every 2          # learn
.venv/bin/python experiments/search_llm.py --row toffoli_carry_B --arm evo --calls 120 \
    --playbook playbooks/dev.json --freeze-playbook          # evaluate, no updates
```

## Level 2 — evolved search code (not implemented; proposed)

The LLM edits harness *code* outside the frozen verifier:
- mutation operators;
- the repair strategy;
- prompt templates;
- for the BQSKit track, the partitioning policy.

Each edited harness is scored by running it on a development set at a fixed budget, as in the Darwin-Gödel-Machine and ADAS designs. This is more expensive: each fitness evaluation is a whole search run. It is worth doing only after Level 1 shows a measurable effect.

## How to show the playbook helps

Arms at a matched LLM-call budget (proposer + reflector calls), 3 or more seeds each:
1. no playbook;
2. a learning playbook;
3. a playbook frozen after learning on other rows;
4. a shuffled-rule control (same rule count, rules from an unrelated task).

Metrics: raw pass rate per proposal, calls to reach the best T/bit, and final best.
