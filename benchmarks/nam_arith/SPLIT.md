# v2 arithmetic suite: development / held-out split (`split_v2.json`, version v2-nam-arith-1, 2026-10-14)

Machine-readable: `split_v2.json`; per-circuit `split` column in `MANIFEST.csv` (both written by
`experiments/v2_bench_manifest.py`). 40 circuits: 34 from the Nam et al. 2018 / T-par suite, 3 generated
Cuccaro adders, 3 qseed Shor circuits by reference. **Dev 17, held-out 22, large-optional 1** (dev = 17/39 = 43.6 %
of the split circuits). gf2^32_mult (96 qubits) is `large_optional`: its baseline run produced no output and was stopped after ~110 min,
so it is outside the dev/held-out split; only the published Nam et al. 2018 Table 4 numbers exist for it.
This split is independent of the v1 split in `benchmarks/SPLIT.md` (qseed optimizer-evolution), which is unchanged.

## Rules

1. Dev = the smallest instances of each family that has a scaling series; held-out = the larger instances
   of the same families plus every circuit of a family that has no dev member.
2. A family appears on both sides only with strictly larger held-out sizes: every held-out adder has more
   qubits (>= 24) than every dev adder (<= 18); same for mcx (dev m <= 5 controls, held-out m = 10), gf2_mult
   (dev n <= 6, held-out 7 <= n <= 16) and modular (dev <= 9 qubits, held-out >= 11 qubits), shor (dev 12, held-out 14, 16).
3. Families with no dev member (pure transfer): comparator (qcla_com_7), hamming (ham15-low/med/high),
   hidden_weighted_bit (hwb6), grover_oracle (grover_5).
4. Rule libraries, playbooks and prompts may be tuned on dev only; held-out circuits are evaluated with
   frozen artifacts (CLAUDE.md invariant 7).

## Dev (17)

| family | circuits | qubits |
|---|---|---|
| mcx_toffoli | tof_3, tof_4, tof_5, barenco_tof_3, barenco_tof_4, barenco_tof_5 | 5-9 |
| adder | cuccaro_4, cuccaro_8, vbe_adder_3, rc_adder_6, csla_mux_3 | 10-18 |
| gf2_mult | gf2^4_mult, gf2^5_mult, gf2^6_mult | 12-18 |
| modular | mod5_4, mod_mult_55 | 5-9 |
| shor (qseed, by reference) | shor_12 | 12 |

## Held-out (22)

| family | circuits | qubits |
|---|---|---|
| mcx_toffoli | tof_10, barenco_tof_10 | 19 |
| adder | adder_8, csum_mux_9, cuccaro_16, qcla_adder_10 | 24-36 |
| gf2_mult | gf2^7, ^8, ^9, ^10, ^16 _mult | 21-48 |
| modular | mod_red_21, qcla_mod_7, mod_adder_1024 | 11-28 |
| comparator | qcla_com_7 | 24 |
| hamming | ham15-low, ham15-med, ham15-high | 17-20 |
| hidden_weighted_bit | hwb6 | 7 |
| grover_oracle | grover_5 | 9 |
| shor (qseed, by reference) | shor_14, shor_16 | 14, 16 |

shor_12 is dev and shor_16 held-out as in the v1 split (`benchmarks/split.json`); shor_14 (excluded in v1 for the
old 1e-9-per-rotation budget) is held-out here because v2 uses the BQSKit eps convention (1e-3 / 1e-5 total).
