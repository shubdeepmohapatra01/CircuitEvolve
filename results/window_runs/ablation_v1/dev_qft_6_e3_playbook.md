# Playbook (open naming)

## candidate (7)

- **R3** A 'fix' proposal that removes a single rz without compensating for the Clifford gates around it on the same qubit will fail the operator-norm verifier; track the full Pauli-frame/basis change across the window before deleting or merging any rotation gate.  
  _shown 36, pass 3/3 with vs 0/4 without; improving prompts as candidate 3/36 shown vs 0/49 hidden; improvements while shown (any status) 3_ 
- **R5** Before submitting fix op N->0 for a lone rz with no other rotation on that qubit in the window, compute the full window unitary with and without that gate; if they differ by more than eps_synth/N_Rz, the fix is invalid outright (not a candidate for later angle patching) -- do not propose bare deletions without first checking for compensating rz gates elsewhere on the same qubit.  
  _shown 35, pass 0/4 with vs 2/2 without; improving prompts as candidate 0/35 shown vs 2/40 hidden; improvements while shown (any status) 0_ 
- **R6** After a fix op N->0 deletes an rz on qubit q, some later rz gates on q may need NO change if an intervening h or cx pair restores the frame to its pre-deletion state before that gate executes -- check frame parity at each candidate site rather than patching every rz on q uniformly.  
  _shown 24, pass 1/2 with vs 0/3 without; improving prompts as candidate 1/24 shown vs 0/29 hidden; improvements while shown (any status) 1_ 
- **R7** Before submitting fix op N->0 for an rz with no other rz on that same physical qubit index, still check rz gates reached via cx-swaps of the logical qubit (q may be relabeled across cx q_a q_b boundaries); only skip angle-patching if truly no rz anywhere in the window shares that logical path, and verify via full window unitary diff against eps_synth/N_Rz.  
  _shown 25, pass 0/1 with vs 1/4 without; improving prompts as candidate 0/25 shown vs 1/28 hidden; improvements while shown (any status) 0_ 
- **R8** When a fix removes one rz on qubit q (e.g. op N->0), check rz gates on OTHER qubits too, not just q: cx q_a q_b propagates the frame change across both qubits. The accepted q3/q1/q0 example patched angles on three different qubits (q3, q1, q0), not just q's own downstream rz chain.  
  _shown 23, pass 1/1 with vs 0/2 without; improving prompts as candidate 1/23 shown vs 0/20 hidden; improvements while shown (any status) 1_ 
- **R9** A bare cx q_a q_b / cx q_a q_b pair is only identity if nothing acts between them; if your fix op leaves such a pair adjacent after deleting/moving gates, double check no rz/t/tdg on q_a or q_b was intended between them -- 'cx q1 q0 / cx q1 q0' with no payload is a near-certain verifier rejection, not a no-op.  
  _shown 22, pass 1/2 with vs 0/1 without; improving prompts as candidate 1/22 shown vs 0/21 hidden; improvements while shown (any status) 1_ 
- **R10** Before submitting fix op N->0, simulate the full window unitary before and after the deletion yourself (not just angle bookkeeping); if the raw diff already exceeds eps_synth/N_Rz with no patch applied, do not submit the bare deletion as a candidate op -- compute the required patch first, then verify the patched version.  
  _shown 24, pass 0/2 with vs 1/1 without; improving prompts as candidate 0/24 shown vs 1/19 hidden; improvements while shown (any status) 0_ 

## retired (3)

- **R1** Before proposing a fix that deletes or replaces an rz(angle), check the resulting unitary matches the original to within allowance (eps_synth/N_Rz), not just approximately. A distance of ~0.2 vs required ~6e-5 means the replacement gate/angle is wrong, not just imprecise synthesis. Recompute the exact matrix product by hand or re-derive the angle algebraically before submitting.  
  _shown 12, pass 0/0 with vs 2/2 without; improving prompts as candidate 0/12 shown vs 2/14 hidden; improvements while shown (any status) 0_ (z = -1.00 at call 5)
- **R2** When collapsing or merging rotations (e.g. fix op replacing gate at index 11 with identity/op0), verify the merged angle equals the sum/difference of the original rotation angles exactly (mod 2pi), including sign flips from any intervening h/s/x/z conjugations on that qubit.  
  _shown 35, pass 0/1 with vs 3/6 without; improving prompts as candidate 0/35 shown vs 3/50 hidden; improvements while shown (any status) 0_ (z = -1.11 at call 33)
- **R4** When a fix removes one rz on a qubit (e.g. op N->0), check whether OTHER rz gates on that same qubit later in the window need their angles updated too (not just the one adjacent to the deletion) -- the accepted q3/q1/q0 example changed three separate downstream rz angles, including sign flips, to compensate for deleting a single rz at index 25.  
  _shown 41, pass 1/2 with vs 1/4 without; improving prompts as candidate 1/41 shown vs 1/34 hidden; improvements while shown (any status) 1_ (z = -0.18 at call 33)
