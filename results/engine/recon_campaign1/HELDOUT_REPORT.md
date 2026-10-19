# recon_campaign1 — HELD-OUT report (frozen transfer)

Playbook FROZEN at sha256 111ab24a5e4f5f436d5b0b93db31d9deed8c8ef5779d60dbc1506f2f4db15e49
(post-dev state: 28 rules, R4+R9 active), reflector OFF, 12 proposer calls/circuit,
proposer claude-opus-5-5. RELAXED column; frozen v2 verifier; digest bc3eac23 all runs.

| circuit | naive | B1 pyzx | control exact | control relaxed | LLM frozen (relaxed) | accepts | vs control |
|---|---|---|---|---|---|---|---|
| cuccaro_16 | 224 | 128 | 128 | 64 | **64** | 5 | MATCH |
| adder_8 | 399 | 173 | 173 | 180 | **160** | 5 | **-20 (-11%)** |
| qcla_adder_10 | 238 | 162 | - | BLOCKED (v2 coverage) | 238 = input (0 accepts) | 0 | same coverage block |
| barenco_tof_10 | 224 | 100 | 100 | 96 | **96** | 4 | MATCH |
| mod_adder_1024 | 1995 | 1011 | 1011 | 660 | **628** | 2 | **-32 (-5%)** |
| gf2^4_mult | 112 | 68 | 68 | 64 | NOT EVALUATED | - | budget ceiling |

## Disclosures

- gf2^4_mult: ALL 12 calls failed INSTANTLY on the platform per-conversation LLM token
  ceiling (2.0M) reached at campaign end - zero proposals were evaluated. Recorded as a
  GAP, not a zero-accept result. mod_adder_1024 call 10 errored once (same-run retries
  continued; 2 accepts stand).
- qcla_adder_10: 12 plans proposed, 0 verified - the SAME verifier-coverage block v2 hit
  (recognizer-normalized circuit keeps unfused h/ccz). Not a refutation; parity with the
  blocked control bar.
- Frozen playbook exposure: in frozen mode ACTIVE rules (R4 Maslov RCCX pairing, R9
  ancilla-vs-T) are injected into EVERY prompt unconditionally (verified in the cuccaro_16
  log prompts); the per-call rules_shown field logs only A/B-selected candidate rules and is
  empty by design when frozen.
- Single seed per circuit; 12 calls each; honest MDE caveat: per-circuit results only,
  no cross-circuit significance claim from n=6.

## Addendum (2026-10-19): gf2^4_mult frozen slot completed

Run with the post-dev frozen playbook (phase held2, 12 calls) before any learning
touched the circuit: **T 112 -> 36 (relaxed), 6 accepts, verified** — vs control
relaxed 64 (**-44%**), control exact 68, B1 pyzx 68. The 'budget ceiling' gap row in
the table above is closed by this result.
