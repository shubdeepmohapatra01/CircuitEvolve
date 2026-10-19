# CircuitEvolve — recon_campaign1 results (group-meeting one-pager)

**One sentence:** An LLM used strictly as a *proposal generator* inside a verifier-first search
loop matches or beats our deterministic tier-1 compilation planner on all 14 verifiable
benchmark circuits — including 9 evaluated with the learned playbook FROZEN (true transfer) —
with every accepted circuit certified by exact D[omega] arithmetic, never floats.

## Setup
- **Loop:** LLM (claude-opus-5-5) proposes whole-circuit compilation plans (temporary-AND /
  Jones / RCCX / MCX-ladder routes per recognized element); a frozen exact verifier accepts or
  rejects; fitness is lexicographic (T, then qubits, then T-depth), relaxed contract column
  (clean ancillas + measurement fix-ups allowed, every branch verified exactly).
- **Learning:** a reflector (claude-sonnet-5-5) compiles rules from accept/reject evidence every
  8 calls; rules earn/lose status only through A/B exposure statistics (never trusted on sight).
- **Control:** the scripted deterministic planner using the SAME toolbox — the no-LLM arm.

## Results (see recon_campaign_results.png)
- Trained circuits: matches the 4T/pair floor where the control is optimal; **-56%**
  (barenco_tof_5 36->16) and **-40%** (rc_adder_6 40->24) where pairing is irregular.
- **Frozen transfer (never trained): beats control on 7/9, matches 2/9** — gf2^4_mult -44%,
  mod_red_21 -21%, adder_8 -11%, hwb6 -7%, ham15-med/mod_adder_1024 -5%.
- Overnight sweep additionally trained 22 more circuits (e.g. ham15-high 2457->824).

## What the LLM actually discovered
1. **Circuit re-identification** (barenco_tof_5): recognized 12 Toffolis as one C5X with dirty
   ancillas restored; rebuilt as a 4-AND clean-ancilla ladder (16 T, the 4k-4 formula).
2. **AND-preserving pairing** (rc_adder_6): paired Toffolis our recognizer rejects because a
   control is rewritten in between — but only as c -> NOT(c xor a), preserving a AND c.
   Candidate for graduation into the deterministic recognizer as exact code.
3. **Floor discipline**: the reflector independently derived the relaxed lower bound
   (4T/pair + 4T/unpaired) from rejection evidence and learned to decline at the floor.

## Honest caveats
- Relaxed-contract numbers: T is bought partly with ancillas + measurement (qubit counts rise).
- Single seed per circuit, no variance estimates; qcla family blocked by verifier coverage;
  gf2^32_mult unparseable (plan JSON exceeds reply cap - format fix pending).
- Deterministic pass gains (TKET entry, graduated G1) are accounted separately, never credited
  to the LLM.

## Cost
~630 Opus proposer calls + ~60 Sonnet reflections across campaign + overnight sweep; verifier
digest bc3eac23 unchanged through all runs; every result append-only in
results/engine/recon_campaign1/ (DEV_REPORT.md, HELDOUT_REPORT.md, SWEEP_REPORT.md).
