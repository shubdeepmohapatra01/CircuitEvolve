# The unified engine (point 1 of the 2026-10 overhaul)

One domain-blind pipeline; domains are plugins. The user never names a regime: input type +
deterministic recognizer features pick the family, the family binds the four components, the
contract, and the playbook. Built 2026-10-18 (commits 9c14c13 .. this one); design documents:
the dry run (DRY_RUN.md, session artifact) and PLAN_P1 (session artifact). Every phase was
gated on the full suite, both frozen digests, and the 126-file baseline manifest
(`results/engine/BASELINE_MANIFEST.json`, guard test `tests/engine/test_manifest.py`).

## Architecture

```
            optimize(source, eps, complete)          engine/run.py
                         |
                 tier-0 ROUTER (deterministic)       engine/router.py, playbooks/router.json
         terms -> cvdv.bosonic | QASM 0-Toffoli,rz>0 -> dv.windows | else NeedsTriage
                         |
                  FamilyBinding(plugin, contract, playbook, graduated)
                         |
                  EvolveLoop (engine/loop.py, domain-blind)
      select -> mutate(LLM) -> verify(FROZEN) -> measure -> lexicographic accept
                         |                                    |
            DomainPlugin (engine/plugin.py)          Ledger + archive + playbook credit
      dv_windows | cvdv | dv_arith(reserved)         + JSONL logs (ALL engine-owned)
```

**Engine-owned, never plugin-overridable** (CLAUDE.md invariants 3-5, 7): the acceptance rule
(verdict.ok AND ledger-can-pay AND plugin.improves AND global check), archive ranking, playbook
credit (only accepted + primary-metric-reduced prompts), reflector cadence/budget, append-only
JSONL logging with tag refusal, frozen-digest check at run start and end.

**A domain plugin supplies** (`engine/plugin.py`, ~15 methods, half with defaults):
`start_state/flat_state/digest`, `select_tasks`, `build_prompt/parse/materialize` (literal
parsing only — never exec/eval), `verify/global_check/input_check/frozen_digest` (frozen
machinery only), `apply/cost/cost_key/improves`, plus reporting hooks. Tasks are opaque to the
engine except `key` (tried-marking), `order` (in-batch evaluation order), `index` (ledger
records).

## The two plugins

| | dv_windows | cvdv |
|---|---|---|
| wraps | `core/{circuit,mutator,verifier,metric,refit}` | `cvdv/src/cvdv` in place (sys.path shim) |
| state | flat Clifford+Rz op list | rule-library source text |
| task | window by T-cost (round-robin) | term kind by certified-duration share |
| candidate | `window`/`fix` literal blocks | restricted-DSL rule function |
| verify | frozen `verify_block` + whole-circuit check | frozen per-instance certificate |
| measure | BqskitTMetric (T, rz, cx, gates) | certified compile: (duration, 2-op, 1-op) |
| equivalence gate | golden fixture `tests/engine/golden_dv.json` | parity_exact accept + compare_isas row reproduction |

Back-compat: `core/loop.py` = `WindowLoop(EvolveLoop)` shim with the original constructor,
`run()`, `TASK_TEXT`, `RUNS`, monkeypatchable module-level `verify_window`/`check_circuit`
(late-bound into the plugin), and `_member`/`_choose_windows`/`ledger0` for the ablation
harness. All stage-1/ablation/v2 results remain statements about the current code.

## Playbook tiers

```
playbooks/router.json            tier 0: families, contracts, preconditions (NO optimization knowledge)
playbooks/families/<family>.json tier 1: Playbook files (A/B machinery unchanged)
playbooks/graduated/index.json   tier 2: EXECUTABLE rules - empty until the first graduation
```

Tier-1 content at creation (P1.4, verbatim copies): `dv.windows.json` = byte-identical
`dev_v1.json`; `cvdv.bosonic.json` = the 6 numbered cvdv rulebook insights as seed rules.
The graduated library is hash-checked at load (index entry hash + per-file sha256); loading the
empty library is a verified no-op. Formats/provenance schema: `engine/graduate.py`
(`GraduatedRule`: id, family, kind in {dsl, pass, cvdv_rule}, path, sha256, provenance_rule_id,
verified_by).

## Routing

Deterministic v0 (literal QASM scan, no eval): Hamiltonian terms -> `cvdv.bosonic`
(certified-subspace contract); 0 Toffolis + >= 1 non-Clifford rz -> `dv.windows` (approx);
everything else -> `NeedsTriage` (the run refuses politely). Every decision — including
NeedsTriage and manifest overrides — is appended to `results/engine/routing_log.jsonl` with the
feature vector, so routing is auditable and A/B-testable. The LLM triage fallback and the
`arithmetic` family (relaxed contract, tier-1 recognizer) land in point 3.

## Running

```python
from circuitevolve.engine.run import optimize
# DV (stage-1 name or QASM path/text); zero accepts == B0 exactly (tests/engine/test_optimize_b0.py)
s = optimize("heisenberg_6", 1e-3, complete, tag="demo1", n_calls=20)
# CV-DV (cvdv deps required, e.g. env cvdv-opt)
s = optimize({"benchmark": "boseHubbard_small"}, 1e-3, complete, n_calls=8)
s["routing"]   # {'family': ..., 'contract': ..., 'reason': ..., 'playbook': ...}
```

## Deferred seams (built as interfaces, implemented later)

- **Point 2**: accept-anatomy reflector input (`engine/reflector.py: AcceptAnatomy`,
  `build_reflector_input`), graduation authoring + dev-replay promotion (`engine/graduate.py`),
  playbook seeding campaigns, the offline literature harvester.
- **Point 3**: LLM triage fallback on NeedsTriage, the `arithmetic` family (`domains/dv_arith`
  wrapping v2/tier1), per-family dev/held-out splits sized for power.

## Phase log (gates in results/CHANGELOG.md)

P1.0 safety net 9c14c13 | P1.1+P1.2 extraction + dv_windows d25948f | P1.4 router + tiers
7286dd0 | P1.3 cvdv plugin + P1.5 docs: this commit. Suite growth 295 -> 325+ tests; dv frozen
digest bc3eac23 and cvdv FROZEN.sha256 unchanged throughout.
