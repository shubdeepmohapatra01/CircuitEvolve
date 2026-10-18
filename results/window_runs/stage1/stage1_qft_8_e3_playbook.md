# Playbook (open naming)

## candidate (5)

- **R1** Rz angle merges: combining two rz(a) on the same qubit (removing a cx-conjugation pair) only preserves the unitary if the merged angle equals the sum/difference consistent with the sign flip the cx conjugation applies, not just one of the two original angles. Check both +a and -a combinations against the full matrix before fixing an op to 0.  
  _shown 11, pass 1/1 with vs 0/0 without; improving prompts as candidate 0/11 shown vs 0/8 hidden; improvements while shown (any status) 0_ 
- **R2** When deleting an rz(angle) q between two cx q_c q_t conjugations (cx; rz; cx with same control/target), the deletion is only valid if the angle is 0 or the rz actually commutes trivially (angle encodes a global phase only on |1> of control-affected subspace); e.g. 'fix op N->0' failed at distance 9.8e-2, so verify commutation algebraically, not by pattern match alone.  
  _shown 11, pass 1/1 with vs 0/0 without; improving prompts as candidate 0/11 shown vs 0/8 hidden; improvements while shown (any status) 0_ 
- **R3** Replacing rz(angle) with rz(-angle) ('fix op i->-angle') is only correct if an odd number of X/CX-like sign flips act on that qubit between the original definition and this site; verify qubit parity along the circuit, since two such flips (e.g. q1) failed at distance 1.96e-01.  
  _shown 6, pass 1/1 with vs 0/0 without; improving prompts as candidate 0/6 shown vs 0/13 hidden; improvements while shown (any status) 0_ 
- **R4** cx q1 q0; rz(angle) q0; cx q1 q0 conjugation does NOT change sign or commute trivially when q1 (control) is untouched between: only rz on the TARGET qubit of a cx is invariant under that cx-conjugation; verify by matrix, since rz(-0.3927) q0 wrapped this way failed at distance 1.96e-01, same magnitude as R3's example.  
  _shown 6, pass 0/0 with vs 0/0 without; improving prompts as candidate 0/6 shown vs 0/4 hidden; improvements while shown (any status) 0_ 
- **R5** When proposing 'fix op i->X, op j->Y' for a pair of rz angles that look related (e.g. one is roughly double or half the other, or negatives), test the combined effect on the full circuit unitary, not each op independently; two internally-plausible single-op fixes combined (e.g. -2*pi/8 and 2*pi/8) produced distance 3.9e-01, far worse than either alone.  
  _shown 4, pass 0/0 with vs 0/0 without; improving prompts as candidate 0/4 shown vs 0/6 hidden; improvements while shown (any status) 0_ 
