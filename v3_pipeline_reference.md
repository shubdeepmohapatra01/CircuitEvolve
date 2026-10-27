# v3 pipeline reference sheet — measured, not quoted

All numbers below were recomputed from `v3/suite/inputs/`, `v3/baselines/baselines.csv`
and `circuitevolve/blocks/cost_model.py` on 2026-10-24. Nothing here is from memory.

## 1. Gate inventory of the inputs (counts from the QASM text)

| file | total ops | gate histogram | distinct angle strings |
|---|---|---|---|
| qft_8.qasm | 139 | cx 68, rz 63, h 8 | 21 |
| qpe_8.qasm | 1034 | rz 508, cx 268, h 258 | 63 |
| hhl_8.qasm | 2205 | rz 1101, h 607, cx 497 | 541 |
| qae_13.qasm | 461 | rz 231, cx 156, h 74 | 59 |
| tfim_6.qasm | 675 | rz 303, h 192, cx 180 | 10 |
| adder_6.qasm | 68 | cx 27, h 22, ccz 11, x 8 | 0 |
| adder_8.qasm | 216 | h 80, cx 67, ccz 57, x 12 | 0 |
| mult_4.qasm | 33 | ccz 16, h 14, cx 3 | 0 |
| mcx_10.qasm | 66 | h 34, ccz 32 | 0 |
| modred_21.qasm | 74 | h 30, x 24, ccz 17, cx 3 | 0 |
| adder_6.cliffordt.qasm | 200 | cx 93, t 43, tdg 34, h 22, x 8 | 0 |

Three distinct gate-set levels appear in the suite:
- **L-A logical / Toffoli level**: `h, x, cx, ccz` (header defines `ccz a,b,c { h c; ccx a,b,c; h c; }`). No angles. All five reconstruction circuits.
- **L-B Clifford+Rz level**: `h, cx, rz(theta)` only. All five angle circuits (these are TKET FullPeepholeOptimise outputs).
- **L-C Clifford+T level**: `h, x, cx, t, tdg` (+ s/sdg/z). The `.cliffordt.qasm` companions; what every method must eventually emit.

## 2. qft_8 angle spectrum (rz angles as multiples of pi)

| theta / pi | exact fraction | count | status |
|---|---|---|---|
| 0.00390625 | 1/256 | 1 | gridsynth |
| 0.0078125 | 1/128 | 2 | gridsynth |
| 0.015625 | 1/64 | 3 | gridsynth |
| 0.03125 | 1/32 | 4 | gridsynth |
| 0.0625 | 1/16 | 5 | gridsynth |
| 0.125 | 1/8 | 6 | gridsynth |
| 0.25 | 1/4 | 1 | free (1 T) |
| 0.375 | 3/8 | 1 | gridsynth |
| 0.4375 | 7/16 | 1 | gridsynth |
| 0.46875 | 15/32 | 1 | gridsynth |
| 0.484375 | 31/64 | 1 | gridsynth |
| 0.4921875 | 63/128 | 1 | gridsynth |
| 2.25 | 9/4 | 7 | free (1 T) |
| 2.49609375 | 639/256 | 1 | gridsynth |
| 3.75 | 15/4 | 7 | free (1 T) |
| 3.875 | 31/8 | 6 | gridsynth |
| 3.9375 | 63/16 | 5 | gridsynth |
| 3.96875 | 127/32 | 4 | gridsynth |
| 3.984375 | 255/64 | 3 | gridsynth |
| 3.9921875 | 511/128 | 2 | gridsynth |
| 3.99609375 | 1023/256 | 1 | gridsynth |

63 rz total; **15 are odd multiples of pi/4 (1 T each); 48 require gridsynth.**
Every angle is a dyadic multiple of pi, i.e. k*pi/2^m. This is exactly the structure
DPF's phase-kickback branch is designed to exploit.

## 3. Reproducing the T-count metric (qft_8 @ eps = 1e-3)

eps_synth = 1e-3, N_Rz = 48 -> eps_rz = 2.083e-05. Measured gridsynth T per rotation
(`circuitevolve/blocks/cost_model.Gridsynth.t`): 44-52, modal value 50.

    sum over the 48 synthesized rotations  = 2376 T
    + 15 pi/4-multiple rz at 1 T each      =   15 T
    TOTAL                                  = 2391 T   == frozen TKET baseline. Exact match.

**Consequence: on L-B circuits T-count is approximately 50 x (number of non-Clifford rotations)
at eps 1e-3.** The cost per rotation scales as ~3*log2(1/eps_rz) and is nearly angle-independent.
Only two levers exist: (a) reduce the rotation count, (b) move angles onto the pi/4 (or dyadic
phase-gradient) grid so they cost O(1) instead of ~50.

## 4. Frozen baseline matrix at eps 1e-3 (t_count / qubits / cx)

### Angle family (L-B input)
| circuit | TKET | pyzx | BQSKit-FT | BQSKit-DPF | v3 ours (P2) |
|---|---|---|---|---|---|
| qft_8 | 2391 | **1577** | 2391 | 2029 | 1583 (+0.4% vs pyzx) |
| qpe_8 | 14761 | 11485 | 14761 | **8020** | 11485 (= pyzx exactly) |
| hhl_8 | 35450 | 29205 | 35450 | **19443** | 28509 (-2.4% vs pyzx) |
| qae_13 | 7821 | **4527** | 7821 | 6909 | 4526 (-0.0% vs pyzx) |
| tfim_6 | 8560 | 8560 | 8560 | 9600 | **3354** (-60.8%) |

Notes: BQSKit-FT == TKET on every angle circuit (its Clifford+Rz retarget changes nothing
on an input that is already Clifford+Rz, then it calls the same gridsynth). pyzx cx count
rises while T falls: qft_8 68->90, qpe_8 268->323, hhl_8 497->663, tfim_6 180->490.

### Reconstruction family (L-A input)
| circuit | TKET (eps 0) | pyzx (eps 0) | BQSKit-FT | BQSKit-DPF | v3 ours (P2) | ours qubits |
|---|---|---|---|---|---|---|
| adder_6 | 59 | 47 | 77 | 77 | **44** | 15 (vs 14) |
| adder_8 | 361 | **173** | 399 | 399 | 216 | 25 (vs 24) |
| mult_4 | 96 | 68 | 112 | 112 | **36** | 13 (vs 12) |
| mcx_10 | 192 | **100** | 224 | 224 | 128 | 20 (vs 19) |
| modred_21 | 107 | 73 | 119 | 119 | **68** | 12 (vs 11) |

**BQSKit-FT and BQSKit-DPF are vacuous on this family.** Per baselines.csv note, they are fed
the Nam Clifford+T files, leave `ccx` undecomposed, report `n_rz=0`, and return the input
T-count unchanged (7 T per Toffoli). They are not competitors here; only TKET and pyzx are.

## 5. P2 run cost (from v3/results/p2/state.json and attempts.jsonl)

- Wall-clock span: start 1792540704.56 -> finish 1792745522.09 = **56.9 h (2.4 days)**.
- Sum of per-attempt durations: 53.9 h over 39 attempts (3 attempts have no duration field).
- 119 LLM calls, $59.14 total.

| decision | n | hours | mean per attempt |
|---|---|---|---|
| reject | 13 | 25.02 | 115.5 min |
| never_fires | 13 | 20.86 | 96.3 min |
| admit | 8 | 7.91 | 59.3 min |
| scout_failed | 2 | 0.08 | 2.5 min |

**85% of the wall time (45.9 h of 53.9 h) was spent on the 26 attempts that produced nothing.**
Slowest single attempts: modred_21 a1 (reject) 3.01 h, qpe_8 a5 (reject) 2.90 h,
qft_8 a2 (reject) 2.76 h, qpe_8 a4 (never_fires) 2.62 h, mcx_10 a2 (reject) 2.49 h.
