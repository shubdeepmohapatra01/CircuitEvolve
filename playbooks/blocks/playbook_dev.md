# Playbook (open naming)

## active (1)

- **R8** Wrapping a single rz(a_k) in h...h or sdg...h...rz...h...sdg only changes its axis/adds free gates; it never removes the rz or reduces T count. Only an exact angle merge (two rz on the same tracked parity summing, or a multiple-of-pi/4 result) reduces the non-Clifford count.  
  _shown 12, pass 8/13 with vs 4/13 without, improvements 0_ (z = +1.86 at call 2)

## candidate (13)

- **R1** Phase-polynomial view: between H gates every rz acts on a parity (XOR) of wires, tracked through the CNOTs; rz gates on the same parity merge into one rz(sum), and an rz on a parity that is later recreated can be moved there.  
  _shown 8, pass 5/8 with vs 13/31 without, improvements 0_ 
- **R2** If angles coincide numerically in every instance (e.g. a0 == a1), an exact rewrite in a_i cannot use that (it is checked on random angles); write a template with free parameters p_j instead, which is fitted per instance.  
  _shown 11, pass 8/15 with vs 10/24 without, improvements 0_ 
- **R3** A 2-qubit unitary needs at most 3 cx; with p_j parameters a template 'Euler(q0) Euler(q1) cx rz rz cx ...' can replace a 2-qubit stretch that currently holds more rotations than the template.  
  _shown 17, pass 11/20 with vs 7/19 without, improvements 0_ 
- **R5** Before submitting, recount: removing an rz line must not change the count of surviving non-Clifford rz without a matching angle merge elsewhere. Two rejects kept 5 rz/460T unchanged while only reordering/adding free Cliffords (sdg->s, extra h h) -- that is not a reduction; merge or cancel an actual rz(a_i) pair via R1 before resubmitting.  
  _shown 7, pass 6/7 with vs 9/22 without, improvements 0_ 
- **R6** When deleting an rz(p_k) line relative to the parent, you must also fix the global phase/basis on the wire it sat on (e.g. insert s/sdg/x/z or adjust a neighboring Euler angle) or the unitary changes; two rejects with 3-qubit templates failed verification (distance 0.25-0.76) exactly from dropping rz(p3)/rz(p1) without compensating.  
  _shown 8, pass 7/10 with vs 8/19 without, improvements 0_ 
- **R7** 0 improving out of 10 calls: proposers are producing verified-but-equal-count rewrites. Before submitting, compare new non-Clifford rz count to the parent's; if not strictly lower, do not submit -- instead find one more R1 merge (same parity) or R3 template swap first.  
  _shown 9, pass 6/11 with vs 8/17 without, improvements 0_ 
- **R9** Before proposing, list each rz's parity (the XOR of wires it effectively acts on, tracked through all cx between it and the previous/next H). Only submit if two rz share a parity and you replace them with one rz(sum); otherwise the T-count will be unchanged like the last two rejections.  
  _shown 12, pass 9/19 with vs 5/9 without, improvements 0_ 
- **R10** cz q_i q_j does NOT change the parity an rz on q_i or q_j tracks the way cx does: cz is diagonal, so it commutes through rz freely but does not XOR wires together. Only cx (and the implicit CNOT in h-cz-h) merges parities; do not treat cz as a parity-combining gate when hunting for R1 merges.  
  _shown 7, pass 5/6 with vs 5/11 without, improvements 0_ 
- **R11** Before submitting, write out the parity of every rz as a bitstring over all qubits (not just the two touched by the most recent cx). If no two rz in the whole program share an identical parity bitstring, no R1 merge exists yet -- adding/moving h, s, cz, or re-labeling a0..a4 cannot create one; you must change the cx wiring itself first.  
  _shown 3, pass 3/3 with vs 7/14 without, improvements 0_ 
- **R12** A rejected-as-improvement resubmission with the same rz count but a different cx pattern (e.g. cx q2 q0 vs cx q0 q1 first) is still a reject even if distance passes; check new_rz_count < parent_rz_count as a hard integer comparison before calling submit, not just 'looks simplified'.  
  _shown 4, pass 4/5 with vs 6/12 without, improvements 0_ 
- **R13** Output must be only circuit lines (gate name + args, e.g. 'rz(a0) q0', 'cx q1 q2'). Never submit a bare dict, bool, float, or debug value as a line -- that is a parse error, not a verified reject. Strip all print/debug output before submitting.  
  _shown 1, pass 1/1 with vs 1/1 without, improvements 0_ 
- **R14** rz(a0) q0 / cz q0 q1 / rz(a1) q1 has no shared parity (cz doesn't XOR, R10) and no cx to recreate one (R11) -- it cannot be reduced by rewiring alone. Before touching such a stretch, check if a0/a1 are structurally forced equal elsewhere in the parent; if not, this stretch is already minimal and should not be resubmitted under a different cx order.  
  _shown 0, pass 0/0 with vs 2/2 without, improvements 0_ 
- **R15** If a 2-rz stretch has distinct parities and no available cx merge, do not resubmit it with reordered cx (e.g. 'cx q2 q1' vs 'cx q1 q2') hoping distance-equivalence counts as progress -- per R12 this is rejected. Spend the call on a different stretch of the circuit that still has an un-exploited R1/R9 parity match instead.  
  _shown 2, pass 2/2 with vs 0/0 without, improvements 0_ 

## retired (1)

- **R4** Output format: emit only gate lines (e.g. 'cx q0 q1', 'rz(a0) q1'), one per line, no matrix dumps, no tuples like '(8, 8)', no numpy array text. The verifier parses each line as a gate instruction; any non-gate line is a parse error.  
  _shown 9, pass 6/17 with vs 7/10 without, improvements 0_ (z = -1.08 at call 1)
