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

## Point 2 (built 2026-10-18): the feedback stack

- **Accept anatomy** (`engine/reflector.py`): every accept yields an `AcceptAnatomy` record
  (DV: rotation multiset diff with Pauli frames, equal-frame-merge flag); the rendered block is
  appended to the improvement entries the reflector reads, and rejections are COMPRESSED into
  <= 4 reason-class groups with counts. Proposer prompts and acceptance untouched.
- **Seeds** (P2.2): dv.windows has 8 FTQC-primer seeds (R29-R36); cvdv.bosonic has 6 rulebook
  seeds + 2 literature-harvest seeds (R7 CD-loop Pauli gadget — halves 2-op cost on the Genesis
  loss case; R8 pauli_hop basis conjugation), both certified EXACT through the frozen path
  before entry (results/engine/harvest_cvdv_2026-10-18.{md,json}). Seeds are candidates under
  the unchanged A/B machinery — they earn ACTIVE or retire like any rule.
- **Graduation** (`engine/graduate.py`): promote() freezes an executable rule (active rule, or
  candidate ONLY with documented independent evidence); hash-checked load; kind="pass" applies
  in optimize()'s pre-opt stage. **G1 = same_pauli_merge** (from seed R29 + ablation-control
  evidence): dev replay total T 87821 -> 80555 (-8.27%; -10.4..-14.7% on merge-rich circuits,
  0 merges on TKET-saturated ones), every application re-verified at 1e-12. `graduated="off"`
  keeps baseline-exact runs; pre_opt gains are reported in their own section, never as LLM
  gains.
- **Campaign contract**: docs/P2_CAMPAIGN.md (dev/held-out split, arms, power floor, freeze
  procedure). The first real-LLM campaign is a separate budget-approved step.

## Deferred to point 3

LLM triage fallback on NeedsTriage, the `arithmetic` family (`domains/dv_arith` wrapping
v2/tier1), raw term-list CV-DV input, per-family splits beyond dv.windows.

## Phase log (gates in results/CHANGELOG.md)

P1: safety net 9c14c13 | extraction + dv_windows d25948f | router + tiers 7286dd0 | cvdv plugin
b1abf1f | docs 08bcb28. P2: anatomy 0510056 | seeds 8ddfe12 | graduation 85d707c | campaign +
dry run 3ff350d | docs: this commit. Suite growth 295 -> 341+ tests; dv frozen digest bc3eac23
and cvdv FROZEN.sha256 unchanged throughout.
