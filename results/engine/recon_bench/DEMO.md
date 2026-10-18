# Method cascade demo (P3.6) — zero LLM

Reproduce: `.venv/bin/python experiments/engine_cascade_demo.py` (delete nothing; the
script refuses to overwrite — this file documents the run that produced it).

No LLM anywhere: reconstruction = scripted deterministic control route (v2/tier1),
angle = declining backend (TKET entry + graduated G1 still run, both deterministic).

CONTRACT COLUMNS ARE SEPARATE (CLAUDE.md invariant: relaxed never mixes with
unitary-preserving): 'relaxed' rows use measurement-based uncompute, verified by the
frozen v2 relaxed verifier; 'approx'/'exact' rows are unitary-preserving. The mixed
circuit's angle numbers are in the angle METRIC column (named T + gridsynth estimate
for general-angle rotations at eps_rz); reconstruction rows count named T only.

### cuccaro_8 (raw, benchmarks/nam_arith/generated/cuccaro_8.qasm)

| arm | contract | T after | notes |
|---|---|---|---|
| best classical B0 (TKET) | exact | 96 | committed baseline (decomposed twin) |
| best classical B1 (pyzx) | exact | 64 | committed baseline (v2 record) |
| angle-only | approx | 96 | TKET entry fired; declining loop (0 accepts); metric = named T + rotation synthesis estimate |
| reconstruction-only (control) | relaxed | 32 | deterministic control route; named T; measurements allowed (relaxed verifier) |
| cascade | relaxed | 32 | per-stage: reconstruction(112->32) -> angle(32->32) |

Per-stage attribution (cascade):

- reconstruction [relaxed]: 112 -> 32 (verified: yes)
- angle [approx]: 32 -> 32 (verified: whole-circuit check skipped (size cap))
- deterministic TKET entry pass (staged input): 32 -> 32 named T (never sold as LLM gains)
- graduated pass G1 (same_pauli_merge): 0 merges


### mixed: cuccaro_4 + 5-rotation payload (benchmarks/mixed/cuccaro_4_rot.qasm, sha256 b6e93d1487875b5b...)

| arm | contract | T after | notes |
|---|---|---|---|
| angle-only | approx | 162 | TKET entry fired; declining loop (0 accepts); metric = named T + rotation synthesis estimate |
| reconstruction-only (control) | relaxed | 16 | deterministic control route; named T; measurements allowed (relaxed verifier) |
| cascade | relaxed | 130 | per-stage: reconstruction(56->16) -> angle(130->130) |

Per-stage attribution (cascade):

- reconstruction [relaxed]: 56 -> 16 (verified: yes)
- angle [approx]: 130 -> 130 (verified: yes)
- deterministic TKET entry pass (staged input): 0 -> 0 named T (never sold as LLM gains)
- graduated pass G1 (same_pauli_merge): 0 merges


Mixed-input semantics (P3.6): reconstruction operates on the largest Toffoli-bearing
grid segment through the frozen verifier and passes rotation segments through
untouched; the angle stage receives the rotation-richest measurement-free segment.
Stage rows therefore do not form one monotone T chain for mixed input - the columns
differ by design and are never summed across contracts.