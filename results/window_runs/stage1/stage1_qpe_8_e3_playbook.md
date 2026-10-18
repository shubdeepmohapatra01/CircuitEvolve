# Playbook (open naming)

## candidate (14)

- **R1** Rz angle merges: combining two rz(a) on the same qubit (removing a cx-conjugation pair) only preserves the unitary if the merged angle equals the sum/difference consistent with the sign flip the cx conjugation applies, not just one of the two original angles. Check both +a and -a combinations against the full matrix before fixing an op to 0.  
  _shown 30, pass 4/8 with vs 3/8 without; improving prompts as candidate 3/30 shown vs 3/29 hidden; improvements while shown (any status) 3_ 
- **R3** Replacing rz(angle) with rz(-angle) ('fix op i->-angle') is only correct if an odd number of X/CX-like sign flips act on that qubit between the original definition and this site; verify qubit parity along the circuit, since two such flips (e.g. q1) failed at distance 1.96e-01.  
  _shown 25, pass 4/8 with vs 3/8 without; improving prompts as candidate 3/25 shown vs 3/34 hidden; improvements while shown (any status) 3_ 
- **R4** cx q1 q0; rz(angle) q0; cx q1 q0 conjugation does NOT change sign or commute trivially when q1 (control) is untouched between: only rz on the TARGET qubit of a cx is invariant under that cx-conjugation; verify by matrix, since rz(-0.3927) q0 wrapped this way failed at distance 1.96e-01, same magnitude as R3's example.  
  _shown 25, pass 3/7 with vs 3/8 without; improving prompts as candidate 3/25 shown vs 3/25 hidden; improvements while shown (any status) 3_ 
- **R6** Large rz(angle) values (|angle| > 2*pi) found far from gate boundaries often just need modular reduction: angle_eff = angle mod 2*pi (choosing representative in (-pi,pi]) before any sign-flip analysis. e.g. rz(10.8596) q0 reduced correctly to rz(-1.7068) q0 (10.8596 - 4*pi), not a conjugation-derived sign change.  
  _shown 13, pass 2/5 with vs 2/8 without; improving prompts as candidate 2/13 shown vs 2/17 hidden; improvements while shown (any status) 2_ 
- **R7** When two rz(angle) on the same qubit are separated only by gates on OTHER qubits (no cx touching this qubit between them), they commute freely: fixing one to angle mod 2*pi or merging is safe without checking any cx-conjugation parity, since no sign flip can occur without a cx/X touching that qubit.  
  _shown 13, pass 2/8 with vs 2/5 without; improving prompts as candidate 2/13 shown vs 2/17 hidden; improvements while shown (any status) 2_ 
- **R8** When proposing fixes to multiple rz ops in one patch, always re-simulate the FULL circuit with all proposed fixes applied together before submitting; per-op plausibility (angle mod 2*pi, double/half relation, sign flip) does not guarantee the joint unitary matches, as combining independently-valid-looking fixes can push distance from <1e-2 to >3e-1.  
  _shown 17, pass 3/7 with vs 1/6 without; improving prompts as candidate 3/17 shown vs 1/13 hidden; improvements while shown (any status) 3_ 
- **R9** Before proposing 'fix op i->0', first compute angle mod 2*pi in (-pi,pi]: if the reduced magnitude is not near 0 (e.g. within ~1e-3), zeroing is wrong. Recent rejects (dist 0.12-0.27) all zeroed ops whose true reduced angle was nonzero; compare against R6's successful mod-2*pi reduction pattern instead of guessing 0.  
  _shown 13, pass 2/4 with vs 1/3 without; improving prompts as candidate 2/13 shown vs 1/7 hidden; improvements while shown (any status) 2_ 
- **R10** A single 'fix op i->X' rarely suffices when op i's angle depends on upstream cx/X parity AND modular reduction together: both the accepted examples that succeeded recompute angle via (mod 2*pi) THEN sign-flip from conjugation, not either alone. Isolated single-op zeroing fixes are the dominant rejected pattern (5/5 recent rejections).  
  _shown 6, pass 0/2 with vs 3/5 without; improving prompts as candidate 0/6 shown vs 3/14 hidden; improvements while shown (any status) 0_ 
- **R11** cx q1 q0; rz(angle) q0; cx q1 q0 with q1 untouched between: rz on q0 is the TARGET, so this conjugation is the identity (no sign flip) only if q0 itself has no intervening X/cx; verify by matrix since naive 'target is invariant' assumptions still failed at distance 1.96e-01 in two cases.  
  _shown 4, pass 0/2 with vs 3/5 without; improving prompts as candidate 0/4 shown vs 3/16 hidden; improvements while shown (any status) 0_ 
- **R12** Multi-op patches like 'fix op i->0, op j->0' fail more often than single-op fixes (R8): each zeroed op must independently satisfy the mod-2*pi-near-zero precondition (R9). If either op's reduced angle is not within ~1e-3 of 0 or pi-multiple matching a Clifford, do not include it in the batch even if the other op looks valid; test each op's fix alone first.  
  _shown 5, pass 1/2 with vs 1/1 without; improving prompts as candidate 1/5 shown vs 1/5 hidden; improvements while shown (any status) 1_ 
- **R13** When an rz(angle) q_k appears with |angle - m*pi| < 1e-3 for integer m (i.e. reduces to 0 or pi after mod 2*pi), check whether m is even (angle~0, safe to drop) or odd (angle~pi, must become z q_k, not fix->0) before proposing a zero-fix; dropping an rz(pi) entirely was behind several 0.1+ distance rejects.  
  _shown 5, pass 1/1 with vs 1/2 without; improving prompts as candidate 1/5 shown vs 1/5 hidden; improvements while shown (any status) 1_ 
- **R14** Before 'fix op i->0', do not rely on the raw literal angle alone: many angles in these circuits are far from their reduced form (e.g. rz(8.23...)) and only look small/droppable after mod 2*pi. Compute angle mod 2*pi explicitly in code/matrix form, not by eyeballing the printed value, then apply R9's near-0 check.  
  _shown 0, pass 0/0 with vs 0/0 without; improving prompts as candidate 0/0 shown vs 0/0 hidden; improvements while shown (any status) 0_ 
- **R15** Repeated rejects show the same op index (e.g. op 9) zeroed twice in separate proposals with no new angle analysis. If a 'fix op i->0' was already rejected by the verifier, do not resubmit it unchanged or with only a different partner op added; recompute that op's true mod-2*pi angle and conjugation parity from scratch before reusing it.  
  _shown 0, pass 0/0 with vs 0/0 without; improving prompts as candidate 0/0 shown vs 0/0 hidden; improvements while shown (any status) 0_ 
- **R16** When a patch zeroes 2 ops together (e.g. 'op i->0, op j->0') and fails at distance >0.1, suspect that at least one op's angle is a nonzero pi-multiple (R13) or depends on cx-parity (R3/R4) rather than both being droppable; verify each op's reduced angle and parity independently, not just jointly as R8 recommends.  
  _shown 0, pass 0/0 with vs 0/0 without; improving prompts as candidate 0/0 shown vs 0/0 hidden; improvements while shown (any status) 0_ 

## retired (2)

- **R2** When deleting an rz(angle) q between two cx q_c q_t conjugations (cx; rz; cx with same control/target), the deletion is only valid if the angle is 0 or the rz actually commutes trivially (angle encodes a global phase only on |1> of control-affected subspace); e.g. 'fix op N->0' failed at distance 9.8e-2, so verify commutation algebraically, not by pattern match alone.  
  _shown 16, pass 1/1 with vs 3/4 without; improving prompts as candidate 0/16 shown vs 3/18 hidden; improvements while shown (any status) 0_ (z = -1.42 at call 16)
- **R5** When proposing 'fix op i->X, op j->Y' for a pair of rz angles that look related (e.g. one is roughly double or half the other, or negatives), test the combined effect on the full circuit unitary, not each op independently; two internally-plausible single-op fixes combined (e.g. -2*pi/8 and 2*pi/8) produced distance 3.9e-01, far worse than either alone.  
  _shown 9, pass 0/0 with vs 3/4 without; improving prompts as candidate 0/9 shown vs 3/16 hidden; improvements while shown (any status) 0_ (z = -1.04 at call 16)
