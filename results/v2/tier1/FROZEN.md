# Tier 1 - FROZEN prompt, plan format and toolbox (from run `dev_v1`)

The held-out evaluation must reuse these files unchanged; re-check every SHA-256 below before running (`shasum -a 256 <file>`). A changed hash = a different method; record it as a new version.

- prompt template version: `tier1-prompt-v1`; SHA-256 of the template string: `9856fc66985fb32c6c64df29de592901fe1c4c6816d5d3c9fcb29721504064da`
- toolbox version: `tier1-toolbox-v1`; routes: toffoli_7T, relative_phase_toffoli, temporary_and, clean_and, jones_toffoli, ancilla_mcx, barenco_mcx, custom; global passes: pyzx, tket, none, pyzx_then_tket
- model: `claude-sonnet-5` via `make_api_backend(host.llm, model=host.reasoning_model(), max_tokens=4000, max_concurrency=1)`, thinking disabled
- budget: 8 LLM calls per circuit, target schedule relaxed/exact alternating (call 0 relaxed); control budget = number of LLM evaluations
- verifier limits (compile.DEFAULT_LIMITS): {'branch_budget': 131072, 'time_limit_s': 240.0}; verify.Limits defaults otherwise
- card selection: `prompt.select_cards` (3 by recognizer features + up to 2 requested)
- frozen verifier digest (circuitevolve.integrity): `bc3eac23a403dbc594265a91ebb9f0ff12672dc913c56c5cf5d9d950c2a242c6`

## Prompt assembly

`prompt.build_prompt(summary, lc, target, best, feedback, cards, classical)` fills `prompt.TEMPLATE` with: the recognizer summary (`Summary.text(lc)`: qubit roles, Toffoli list, pairs with class, unpaired Toffolis, multi-controlled-X cascades, repeated blocks, rotation content, normalized gate list if <= 120 gates), `plan.toolbox_text()`, the card INDEX table, the selected full cards, the naive 7 T/Toffoli cost, the best classical exact T-count string, the best verified plan per leaderboard so far, and the last 4 results (verified metrics or verifier/plan rejection reasons). Reply = one JSON plan (`plan.parse_plan`; literal json + regex, no exec/eval).

## File hashes

| file | sha256 |
|---|---|
| `circuitevolve/v2/tier1/recognize.py` | `5b528fd31e525a266c27f356fef241be2f3b4c7c0a10659683d4ad7223ee8284` |
| `circuitevolve/v2/tier1/plan.py` | `bf501f87e90e25c3786c57056d3391602164aa7e3382865da695a72303cf3212` |
| `circuitevolve/v2/tier1/compile.py` | `d342ceb4fc5543738e48c7e4a6dea3ddd5c7c488d37172d19e4db5aa11f7e40e` |
| `circuitevolve/v2/tier1/prompt.py` | `c5a166b2e7c5e3f53d2cf17feabd6bee12056dbe87d8f6ddf4f623d8770b168e` |
| `circuitevolve/v2/tier1/loop.py` | `3feb93a0fbbde960e93815f34ad9891476f0417ce117e318fc31f45b7ffade03` |
| `circuitevolve/v2/tier1/control.py` | `4ef29254e94e4c451cac33b9de292f095a8e8b2e1e4091875f110ac6abfcd555` |
| `circuitevolve/v2/verify.py` | `68b3c9cb2af9dc5dc76226172fbe5a49c0d05447745d9ab6c7a19745b9f0705c` |
| `circuitevolve/v2/metric.py` | `4b4990cbc9c3198377013bae1c30e3cd97f3cbb1dc5ed9c4e953cb59fc276445` |
| `experiments/v2_tier1_dev.py` | `12286e117fa594ffcb02171a02cf2590e44b044a163816bf595401553d2ce313` |
| `docs/v2/cards/INDEX.md` | `5e770724780e91ba82f2eee2436fae19518901414086063a2bbcbdb672b761a8` |
| `docs/v2/cards/01_gidney_temporary_and.md` | `c5e5fc912528dd419f4c635e6f5c1544c672389a235d9673ce859e03b76b6efe` |
| `docs/v2/cards/02_jones_toffoli_measurement.md` | `d4a9f5fafc262e35de1a52e5067018dfc753fdd707ba73c469de1aff217b588e` |
| `docs/v2/cards/03_relative_phase_toffoli.md` | `8db7c4d4170bdeb90138115f7d2728a184308cfe247073ed48ed7207665dc0b3` |
| `docs/v2/cards/04_selinger_tdepth_one.md` | `7741fb37047a722ce02aead7360925d96450f6268ad8d81cf114014eb2594a4c` |
| `docs/v2/cards/05_barenco_multicontrolled.md` | `5b7a0ef77f1b078d3b0dfb40053431c2c028eca5fb5953eae435b6233ad30dd1` |
| `docs/v2/cards/06_cuccaro_ripple_carry.md` | `b942ab9b4aa67696587f15a135520a7dc40071271da5577e42672accfdbf69c2` |
| `docs/v2/cards/07_phase_folding_tpar.md` | `dedf5938601170560f7ccde879fad052541485608ebfebebedec349272724b0b` |
| `docs/v2/cards/08_pyzx_zx_simplification.md` | `886d739c94b7b51d9af8cd7bd72de47a020e3e82bb5d40d603a0b0d76757a1d7` |
| `docs/v2/cards/09_nam_rotation_merging.md` | `598b6b360214b0dd22ffc819fcce3972db7b977815b9f5bd059cf6c914725a47` |
| `docs/v2/cards/10_dyadic_phase_fixing.md` | `288030227b8da00ca2c274d75d2f2088de4b87aecea5460547653a0b05e0f596` |
| `docs/v2/cards/11_qft_approximation.md` | `2d11d9a7de6fa5a9899efd0d827d7c23dfe11b6789934eb63b4f8fa0388bda73` |
