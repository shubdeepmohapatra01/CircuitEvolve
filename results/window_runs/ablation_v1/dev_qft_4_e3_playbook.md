# Playbook (open naming)

## candidate (5)

- **R1** Before proposing a fix that deletes or replaces an rz(angle), check the resulting unitary matches the original to within allowance (eps_synth/N_Rz), not just approximately. A distance of ~0.2 vs required ~6e-5 means the replacement gate/angle is wrong, not just imprecise synthesis. Recompute the exact matrix product by hand or re-derive the angle algebraically before submitting.  
  _shown 9, pass 0/0 with vs 1/1 without; improving prompts as candidate 0/9 shown vs 1/12 hidden; improvements while shown (any status) 0_ 
- **R2** When collapsing or merging rotations (e.g. fix op replacing gate at index 11 with identity/op0), verify the merged angle equals the sum/difference of the original rotation angles exactly (mod 2pi), including sign flips from any intervening h/s/x/z conjugations on that qubit.  
  _shown 10, pass 0/0 with vs 1/1 without; improving prompts as candidate 0/10 shown vs 1/11 hidden; improvements while shown (any status) 0_ 
- **R3** A 'fix' proposal that removes a single rz without compensating for the Clifford gates around it on the same qubit will fail the operator-norm verifier; track the full Pauli-frame/basis change across the window before deleting or merging any rotation gate.  
  _shown 8, pass 1/1 with vs 0/0 without; improving prompts as candidate 1/8 shown vs 0/13 hidden; improvements while shown (any status) 1_ 
- **R4** When a fix removes one rz on a qubit (e.g. op N->0), check whether OTHER rz gates on that same qubit later in the window need their angles updated too (not just the one adjacent to the deletion) -- the accepted q3/q1/q0 example changed three separate downstream rz angles, including sign flips, to compensate for deleting a single rz at index 25.  
  _shown 8, pass 0/0 with vs 0/0 without; improving prompts as candidate 0/8 shown vs 0/3 hidden; improvements while shown (any status) 0_ 
- **R5** Before submitting fix op N->0 for a lone rz with no other rotation on that qubit in the window, compute the full window unitary with and without that gate; if they differ by more than eps_synth/N_Rz, the fix is invalid outright (not a candidate for later angle patching) -- do not propose bare deletions without first checking for compensating rz gates elsewhere on the same qubit.  
  _shown 5, pass 0/0 with vs 0/0 without; improving prompts as candidate 0/5 shown vs 0/6 hidden; improvements while shown (any status) 0_ 
