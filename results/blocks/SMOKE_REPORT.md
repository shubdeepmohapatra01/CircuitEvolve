# Block pipeline v1 — end-to-end smoke (dev circuits only)

Date 2026-10-11. Code: `circuitevolve/blocks/` (docs: `docs/BLOCK_PIPELINE.md`). Runs:
`results/blocks/smoke_v2/` (tfim_4, heisenberg_4, qft_5) and `results/blocks/smoke_v3_hhl8/` (hhl_8).
`smoke_v1/` was aborted before any LLM call (`ABORTED.md`). No evaluation circuit (add_*, hhl_6,
mult_16, qft_32, shor_16) was loaded: `circuit_io.bench_path` refuses them. Every number below is copied
from the `summary.csv` / `summary.json` / `calls.jsonl` files in those directories.

Settings: QuickPartitioner(3), windows of at most 40 gates, eps_block = 1e-8 (phase-aligned operator norm,
`verify_block.py`, frozen digest `bc3eac23a403dbc5…` checked at start and end of each run), gridsynth at
eps_rz = 1e-9, k = 3 programs per call. Proposer model: in-platform `host.reasoning_model()`, thinking off.
smoke_v2: batches of 4, max_tokens 4000, playbook with 3 hand-written seed rules + reflector every 8 calls.
smoke_v3: batch 5, max_tokens 6000, no playbook, whole-circuit phase fold before partitioning (`global_fold=True`).

## T-count: best classical input vs pipeline output

The input is the lower-T of pyzx and TKET (the baseline is also the lower of phase-0 raw-angle counting and
canonical [-pi, pi] counting; both were equal on all four circuits).

| circuit | input (best classical) | input T | input rz | after deterministic passes T | output T | output rz | T saved | LLM calls (+reflector) | programs | verified | improving | whole-circuit check (unitary) | error bound |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tfim_4 | tket | 9,200 | 100 | 9,200 | 9,200 | 100 | 0 | 10 (+2) | 11 | 4 | 0 | 1.8e-14 | 1.0e-07 |
| heisenberg_4 | pyzx | 8,340 | 90 | 8,340 | 8,340 | 90 | 0 | 14 (+1) | 21 | 10 | 0 | 1.2e-14 | 9.0e-08 |
| qft_5 | pyzx | 1,124 | 12 | 1,124 | 1,124 | 12 | 0 | 6 (+1) | 7 | 4 | 0 | 3.5e-12 | 1.2e-08 |
| hhl_8 | tket | 54,914 | 587 | 48,307 | 48,307 | 517 | 6,607 (12.0 %) | 5 (+0) | 4 | 0 | 0 | 2.8e-13 | 5.2e-07 |

* **Rules found: 0. LLM-attributable T saved: 0.** No proposal was both verified and an improvement on
  any block. The only gain is hhl_8, and all of it comes from the deterministic phase fold (no LLM).
  It reduces TKET's 587 synthesised rz to 517 (and explicit T from 202 to 139).
  The per-block pass alone (the v1 default, no-LLM run, `deterministic_dev.csv`) gives 51,810 T / 554 rz on hhl_8. On the other
  circuits the passes change nothing, because pyzx `full_reduce` already does the phase folding.
* 18 of the 43 extracted programs verified, and every one of them kept the block's number of
  synthesised rz (verified-but-not-improving). Rejected proposals had distances 1e-2 to 2.0, i.e. wrong algebra and not
  near-misses. Eight programs were parse errors; all eight in smoke_v2 were the model printing simulated
  "tool output" (`(8, 8)`, matrices, dicts) in bare code fences. Since then, bare fences that do not
  look like programs are skipped and counted separately.
* 11 of 34 smoke_v2 responses hit max_tokens = 4000, and the truncated responses produced no program.
  The prompt now caps the reasoning at about 250 words and smoke_v3 used 6000 tokens: there, 0 of 5 were
  truncated, but the model also proposed very little (4 programs for 5 calls).
* Structure grouping (QuickPartitioner is occasionally nondeterministic: 38 or 40 blocks for tfim_4): tfim_4 has 38 blocks in 8 structures (top groups of 8–9 instances). In the other
  circuits almost every block is its own structure (heisenberg_4 46/43, qft_5 12/12, hhl_8 84/42).
  So the "one call per structure" scaling helps only for Trotter-type circuits.

## LLM cost (all backend calls in this phase)

| run | calls | proposer | reflector | input tokens | output tokens |
|---|---|---|---|---|---|
| connectivity check (1 prompt "Reply with exactly: ok") | 1 | 0 | 0 | 14 | 4 |
| smoke_v2 | 34 | 30 | 4 | 50,512 | 77,431 |
| smoke_v3_hhl8 | 5 | 5 | 0 | 6,603 | 3,648 |
| **total** | **40** | **35** | **4** | **57,129** | **81,083** |

Total ≈ 138k model tokens (budget: ≤ 40 proposer calls, ≈ 300k tokens).

## Verification records

Every accepted block change (the deterministic passes only) has its own `verify_instance` record
(≤ 1e-15). The whole-circuit unitary distance against the ORIGINAL qseed circuit is in the table. The error
bound = measured d(input, original) + Σ accepted block distances + #rz·1e-9. The pyzx inputs carry ~1e-11
from pyzx's Fraction angle conversion; this is measured and included. Playbook (smoke_v2): 15 rules
(3 seed, 12 reflector), 1 promoted to active (R8, on raw verifier pass rate), 1 retired. No rule was
associated with an improvement. Snapshot: `smoke_v2/playbook.md`, mutable copy `playbooks/blocks/`.

## What this says about v1, and next steps

1. On pyzx/TKET outputs of these small dev circuits, 3-qubit windows have almost no slack in
   rz count that a text-level LLM rewrite can find. Every rz in the Trotter circuits is a distinct
   Pauli rotation. The model mostly re-derived equivalent programs or made algebra errors.
2. The measurable gain (hhl_8) is structural and classical: TKET leaves phase-polynomial merges
   across CNOT networks. A whole-circuit fold is stronger than the per-block fold (517 vs 554 rz). The
   "best classical" baseline should arguably include it (decision for the user before the eval phase).
3. Candidate improvements for v2: numerical template resynthesis of windows with many rz (hhl_8 has
   3-qubit windows with 13–15 rz, where a parametric template could plausibly need fewer). This could run
   with LLM-proposed templates (p_j) or deterministically, e.g. KAK templates. Also: score the playbook A/B
   on *improvements*, not raw verifier passes (R8 was promoted for producing equivalent programs); and
   re-partition after accepted rewrites so that cross-window merges become visible.
