# recon_campaign1 — overnight sweep + reserved frozen evaluation

Learning sweep (opus-5-5 proposer, sonnet-5-5 reflector) over 23 circuits in 4 sequential
sub-sessions; then FROZEN evaluation (12 calls, no learning, no playbook saves — sha
9d4793075fc3a87b…) on the 4 reserved circuits, with deterministic control bars computed fresh.
All numbers RELAXED column, frozen v2 verifier (digest bc3eac23) checked per run.

## Sweep (learning ON)

| circuit | T before | T after | accepts | note |
|---|---|---|---|---|
| tof_3 | 21 | **8** | 3 |  |
| barenco_tof_3 | 28 | **8** | 5 |  |
| mod5_4 | 28 | **4** | 1 |  |
| tof_4 | 35 | **12** | 5 |  |
| mod_mult_55 | 49 | **24** | 2 |  |
| barenco_tof_4 | 56 | **12** | 4 |  |
| vbe_adder_3 | 70 | **24** | 5 |  |
| csla_mux_3 | 70 | **40** | 5 |  |
| gf2^4_mult | 112 | **36** | 5 |  |
| tof_10 | 119 | **36** | 6 |  |
| ham15-low | 161 | **68** | 4 |  |
| gf2^5_mult | 175 | **56** | 5 |  |
| csum_mux_9 | 196 | **56** | 3 |  |
| grover_5 | 336 | **144** | 8 |  |
| gf2^7_mult | 343 | **196** | 5 |  |
| adder_8 | 399 | **168** | 7 |  |
| gf2^8_mult | 448 | **256** | 8 |  |
| gf2^9_mult | 567 | **312** | 5 |  |
| gf2^10_mult | 700 | **400** | 6 |  |
| mod_adder_1024 | 1995 | **628** | 3 |  |
| ham15-high | 2457 | **824** | 4 | rerun (sweep2) after token-ceiling kill; first-row artifact superseded |
| gf2^16_mult | 1792 | **1008** | 3 |  |
| gf2^32_mult | 7168 | **7168** | 0 | no parseable plans (1024-decision JSON exceeds reply cap) — honestly unchanged |

## Reserved frozen transfer test (never trained; control computed fresh here)

| circuit | naive | control exact | control relaxed | LLM frozen | accepts | vs control |
|---|---|---|---|---|---|---|
| ham15-med | 574 | 212 | 220 | **208** | 3 | **-12 (-5%)** |
| gf2^6_mult | 252 | 150 | 144 | **144** | 5 | MATCH |
| hwb6 | 105 | 75 | 56 | **52** | 5 | **-4 (-7%)** |
| mod_red_21 | 119 | 73 | 56 | **44** | 4 | **-12 (-21%)** |

## Playbook after the sweep

- 97 rules total; 15 active: R4, R9, R23, R28, R35, R36, R42, R44, R46, R59, R70, R71, R73, R78, R79; 71 retired.
- Frozen sha for the reserved evaluation: 9d4793075fc3a87b821e9885456f0973a28bad56f1c9bb10620399d2a3c87f37

## Disclosures
- gf2^32_mult spent 8 calls with zero parseable candidates: whole-circuit plan JSON for
  1024 elements exceeds the 16k reply cap. A chunked/segmented plan format is the fix,
  not more calls. Recorded unchanged.
- ham15-high's first sweep row is a token-ceiling artifact (16 instant errors); the
  sweep2 rerun (2457 -> 824) supersedes it. Both logs kept (append-only).
- adder_8 trained to 168 here vs 160 in its earlier frozen eval: independent runs,
  different trajectories; the 160 frozen record stands.
