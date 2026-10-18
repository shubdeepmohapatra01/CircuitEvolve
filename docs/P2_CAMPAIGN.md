# First unified campaign — protocol (PLAN_P2 phase P2.4)

The contract for the first real-LLM campaign on the unified engine. Written and frozen BEFORE
the campaign; the campaign is a separate, budget-approved step. Everything here binds the
campaign runner; deviations invalidate the comparison and must be reported as such.

## Question under test

Does the P2 feedback stack (accept-anatomy reflector + seeded playbook) produce rules with
measured transfer, where the P1-era stack measurably did not (ablation v1: learned - none
= +0.38 pp, CI -1.21..+1.93, placebo p = 1.0)?

## Split (dv.windows family)

- DEV (learning allowed): qft_8, heisenberg_6, hubbard_8, qml_13, hhl_8 @ 1e-3
- HELD-OUT (frozen eval only): qpe_8, qae_13, tfim_6 @ 1e-3; secondary arm @ 1e-5
- The split balances merge-rich (qft/hhl | qpe/qae) and TKET-saturated (heis/hubbard/qml | tfim)
  circuits so neither side is all-headroom or all-floor.
- Contamination note: G1's freeze replay used ALL 8 circuits — fine for the PASS column (it is
  deterministic and attributed separately) but G1 gains may NEVER be credited to the playbook.

## Arms (mirrors ablation v1, so the null result is the comparator)

| arm | playbook | reflector |
|---|---|---|
| A seeded-learning | families/dv.windows.json (8 seeds + inherited) | ON (anatomy input) |
| B placebo | same rule COUNT, shuffled/neutral texts | ON |
| C none | no playbook | OFF |

G1 pre-opt pass ON in every arm (its gains cancel in all comparisons). Same windows, same
budgets, same backend and model pin across arms. Reflector calls count against each arm's call
budget (CLAUDE.md invariant 7).

## Power (the ablation postmortem, applied)

- Ablation v1 was underpowered: 7 blocks x 20 calls; observed spread implied an MDE of several
  pp while plausible effects were ~1-3 pp.
- Budget floor here: >= 40 proposer calls per circuit per arm on DEV (learning), >= 40 per
  held-out circuit per arm (frozen); bootstrap CI over circuits; paired per-circuit deltas.
- HONEST MDE: with 3 held-out circuits only effects >= ~5 pp are individually resolvable;
  smaller effects require the paired 1e-5 arm to corroborate direction. State this in the
  report; do not claim smaller wins.
- No promote/freeze claim for any rule below min_exposure (8) with-pass evidence (playbook
  settings are the arbiter; they are not weakened for the campaign).

## Freeze procedure (before touching held-out)

1. SHA-256 of families/*.json, graduated/index.json + referenced files, router.json — recorded
   in the campaign log; playbooks loaded frozen=True on held-out.
2. Reflector OFF on held-out; routing decisions logged; integrity digests checked start/end.
3. LLM backend + model id pinned and recorded; one seed per run recorded.

## Reporting columns (append-only, results/engine/<campaign>/)

1. B0 floor (TKET+gridsynth) and PER-CIRCUIT BEST VALID ARM of {B1 pyzx, B2, B3g} — the bar is
   the best arm, never B0 (worst case we return the input unchanged).
2. G1 pass column: deterministic, zero-LLM, reported alone.
3. In-loop LLM column per arm: accepts, T delta vs post-pass input, charges, calls spent.
4. Playbook outcome: rules promoted/retired on DEV, then FROZEN transfer on held-out.
5. Contract column: exact/approx per circuit (relaxed never mixes with unitary-preserving).

## Stop conditions

Budget exhausted, or a verifier-integrity failure (digest drift aborts the run), or DEV shows
arm A <= arm C by more than the MDE at half budget (futility stop; report as such).
