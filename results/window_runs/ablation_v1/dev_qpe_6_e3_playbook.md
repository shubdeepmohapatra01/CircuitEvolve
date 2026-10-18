# Playbook (open naming)

## active (1)

- **R3** A 'fix' proposal that removes a single rz without compensating for the Clifford gates around it on the same qubit will fail the operator-norm verifier; track the full Pauli-frame/basis change across the window before deleting or merging any rotation gate.  
  _shown 95, pass 3/3 with vs 0/4 without; improving prompts as candidate 3/37 shown vs 0/53 hidden; improvements while shown (any status) 5_ (z = +1.65 at call 5)

## candidate (7)

- **R11** A fix proposal need not touch any rz: a pure Clifford window (only h/s/sdg/x/z/cx/cz) can still fail the operator-norm check if the proposed cx/h rewiring changes the overall permutation or basis mapping. Before submitting, simulate the full window (all Cliffords included) on basis inputs and diff against the original, not just the rz-bearing subcircuit.  
  _shown 23, pass 1/6 with vs 0/3 without; improving prompts as candidate 1/23 shown vs 0/19 hidden; improvements while shown (any status) 1_ 
- **R12** When rewriting a block of cx gates among 3+ qubits (e.g. cx q2 q1 / cx q1 q2 / cx q2 q1 style swaps), check that your rewrite reproduces the exact qubit permutation of the original on ALL qubits in the window, including ones with only a single h or no gate -- dropping or reordering one cx changes which logical qubit later gates act on.  
  _shown 15, pass 0/2 with vs 1/7 without; improving prompts as candidate 0/15 shown vs 1/27 hidden; improvements while shown (any status) 0_ 
- **R13** A bare cx q_a q_b / cx q_a q_b pair, or any even-length cx chain among the same qubits, is only identity if nothing acts between them AND the net permutation matches; before accepting such a pair as removable, verify via full window unitary diff -- 'cx q1 q0 / cx q1 q0' with no payload is a near-certain verifier rejection, not a no-op.  
  _shown 16, pass 1/2 with vs 0/7 without; improving prompts as candidate 1/16 shown vs 0/26 hidden; improvements while shown (any status) 1_ 
- **R14** Zeroing an rz (op N->0) is only valid if that rotation's net effect is already identity under the surrounding Pauli frame -- it is not a safe default simplification. The rejection 'fix op 37->0: distance 1.893e-02' shows a nonzero rz was dropped without verifying it was conjugate to the identity; always full-window simulate before proposing op->0.  
  _shown 12, pass 0/3 with vs 0/2 without; improving prompts as candidate 0/12 shown vs 0/9 hidden; improvements while shown (any status) 0_ 
- **R15** When simplifying rz(theta), first reduce theta into (-pi,pi] (or equivalent +/-2*pi*k form) rather than zeroing it: in the accepted fix, rz(8.7588...)->rz(2.4756...) and rz(9.7918...)->rz(-2.7744...) are mod-2pi reexpressions of the SAME angle, not deletions. Only propose op->0 if the reduced angle itself is ~0 after this step.  
  _shown 4, pass 0/2 with vs 0/0 without; improving prompts as candidate 0/4 shown vs 0/5 hidden; improvements while shown (any status) 0_ 
- **R16** A near-miss rejection like 'op 24->0: distance 2.330e-04' (just above allowance 6.250e-05) often means the rotation is nearly but not exactly conjugate to identity -- do not round small residual angles to exactly 0; keep the residual rz or fold it into the adjacent Clifford's exact phase instead of truncating.  
  _shown 5, pass 0/1 with vs 0/1 without; improving prompts as candidate 0/5 shown vs 0/4 hidden; improvements while shown (any status) 0_ 
- **R17** Before proposing op N->0 on an rz, confirm algebraically that the surrounding H/S/X/Z/CX sequence maps that rotation axis to itself with no net Pauli sign flip; if any conjugating gate maps Z-axis to X/Y axis, the rotation is NOT removable and must instead be re-expressed (angle change), not deleted.  
  _shown 5, pass 0/2 with vs 0/0 without; improving prompts as candidate 0/5 shown vs 0/4 hidden; improvements while shown (any status) 0_ 

## retired (9)

- **R1** Before proposing a fix that deletes or replaces an rz(angle), check the resulting unitary matches the original to within allowance (eps_synth/N_Rz), not just approximately. A distance of ~0.2 vs required ~6e-5 means the replacement gate/angle is wrong, not just imprecise synthesis. Recompute the exact matrix product by hand or re-derive the angle algebraically before submitting.  
  _shown 12, pass 0/0 with vs 2/2 without; improving prompts as candidate 0/12 shown vs 2/14 hidden; improvements while shown (any status) 0_ (z = -1.00 at call 5)
- **R2** When collapsing or merging rotations (e.g. fix op replacing gate at index 11 with identity/op0), verify the merged angle equals the sum/difference of the original rotation angles exactly (mod 2pi), including sign flips from any intervening h/s/x/z conjugations on that qubit.  
  _shown 35, pass 0/1 with vs 3/6 without; improving prompts as candidate 0/35 shown vs 3/50 hidden; improvements while shown (any status) 0_ (z = -1.11 at call 33)
- **R4** When a fix removes one rz on a qubit (e.g. op N->0), check whether OTHER rz gates on that same qubit later in the window need their angles updated too (not just the one adjacent to the deletion) -- the accepted q3/q1/q0 example changed three separate downstream rz angles, including sign flips, to compensate for deleting a single rz at index 25.  
  _shown 41, pass 1/2 with vs 1/4 without; improving prompts as candidate 1/41 shown vs 1/34 hidden; improvements while shown (any status) 1_ (z = -0.18 at call 33)
- **R5** Before submitting fix op N->0 for a lone rz with no other rotation on that qubit in the window, compute the full window unitary with and without that gate; if they differ by more than eps_synth/N_Rz, the fix is invalid outright (not a candidate for later angle patching) -- do not propose bare deletions without first checking for compensating rz gates elsewhere on the same qubit.  
  _shown 40, pass 0/4 with vs 2/2 without; improving prompts as candidate 0/40 shown vs 2/45 hidden; improvements while shown (any status) 0_ (z = -0.95 at call 10)
- **R6** After a fix op N->0 deletes an rz on qubit q, some later rz gates on q may need NO change if an intervening h or cx pair restores the frame to its pre-deletion state before that gate executes -- check frame parity at each candidate site rather than patching every rz on q uniformly.  
  _shown 41, pass 2/6 with vs 0/3 without; improving prompts as candidate 2/41 shown vs 0/44 hidden; improvements while shown (any status) 2_ (z = +1.09 at call 33)
- **R7** Before submitting fix op N->0 for an rz with no other rz on that same physical qubit index, still check rz gates reached via cx-swaps of the logical qubit (q may be relabeled across cx q_a q_b boundaries); only skip angle-patching if truly no rz anywhere in the window shares that logical path, and verify via full window unitary diff against eps_synth/N_Rz.  
  _shown 39, pass 0/4 with vs 3/7 without; improving prompts as candidate 0/39 shown vs 3/51 hidden; improvements while shown (any status) 0_ (z = -1.18 at call 5)
- **R8** When a fix removes one rz on qubit q (e.g. op N->0), check rz gates on OTHER qubits too, not just q: cx q_a q_b propagates the frame change across both qubits. The accepted q3/q1/q0 example patched angles on three different qubits (q3, q1, q0), not just q's own downstream rz chain.  
  _shown 41, pass 1/3 with vs 2/6 without; improving prompts as candidate 1/41 shown vs 2/44 hidden; improvements while shown (any status) 1_ (z = -0.39 at call 10)
- **R9** A bare cx q_a q_b / cx q_a q_b pair is only identity if nothing acts between them; if your fix op leaves such a pair adjacent after deleting/moving gates, double check no rz/t/tdg on q_a or q_b was intended between them -- 'cx q1 q0 / cx q1 q0' with no payload is a near-certain verifier rejection, not a no-op.  
  _shown 41, pass 2/4 with vs 1/5 without; improving prompts as candidate 2/41 shown vs 1/39 hidden; improvements while shown (any status) 2_ (z = +0.41 at call 5)
- **R10** Before submitting fix op N->0, simulate the full window unitary before and after the deletion yourself (not just angle bookkeeping); if the raw diff already exceeds eps_synth/N_Rz with no patch applied, do not submit the bare deletion as a candidate op -- compute the required patch first, then verify the patched version.  
  _shown 30, pass 0/3 with vs 2/2 without; improving prompts as candidate 0/30 shown vs 2/29 hidden; improvements while shown (any status) 0_ (z = -1.08 at call 16)
