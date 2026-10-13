# Playbook (open naming)

## active (4)

- **R2** tket's native gateset (H,CX,Z,CY,X,S,PauliExpBox,CZ,...) excludes Rz/U3; never pass tools.tket(...) output directly into tools.pyzx_* or tools.block_optimize without first converting with tools.lower(...) or tools.canonicalize(...), or you get 'Predicate requirements are not satisfied: GateSetPredicate' errors.  
  _shown 96, pass 7/9 with vs 5/11 without, improvements 36/9 with vs 1/11 without_ (z = +1.70 at call 33)
- **R4** tools.best only ranks by T-count/cost; it does not catch unitary-mismatch bugs. When chaining tools.pyzx_clifford_simp or tools.block_optimize(method='pyzx'/'fold_resynth') on a candidate, always keep the pre-transform canonicalized candidate as one of the arguments to the following tools.best(...) call so a broken transform cannot silently become the returned result.  
  _shown 60, pass 15/16 with vs 23/27 without, improvements 26/16 with vs 7/28 without_ (z = +1.67 at call 76)
- **R8** When budgeting allowance = tools.error_left(pre) * k for tools.approx_round, k close to 1.0 or applied after several prior lossy stages (fold_resynth, block_optimize with approx methods) can exceed the true remaining budget because error accumulates non-additively on some circuits (qft_8, mult_8 seen failing at k=0.2). Use k <= 0.1 and only call approx_round once per optimize() run.  
  _shown 48, pass 9/9 with vs 9/11 without, improvements 21/9 with vs 2/11 without_ (z = +1.70 at call 81)
- **R11** tools.block_optimize requires block_size in {2,3,4} AND max_gates >= 4*block_size roughly; max_gates=40 can fail validation paired with some block_size values. Use safe defaults block_size=3, max_gates>=60, or block_size=2, max_gates>=20, and never reuse the same block_size/max_gates pair blindly across multiple block_optimize calls.  
  _shown 35, pass 8/9 with vs 7/7 without, improvements 14/9 with vs 3/7 without_ (z = +2.11 at call 94)

## candidate (6)

- **R7** Deeply nested time_left() guarded chains (5+ sequential block_optimize/fold_resynth stages) that end mid-expression or omit a final return risk returning a stale or undefined 'result'/'cs' variable. Always end optimize() with an explicit `return result` after the last guarded block, and ensure every branch assigns back into canonicalize(tools.best(pre, candidate)) before falling through.  
  _shown 39, pass 35/38 with vs 29/33 without, improvements 18/39 with vs 12/33 without_ 
- **R12** Two accepted children in the log end with a truncated line (e.g. 'result = tools.can' or 're' mid-statement) and would be unparseable. Before finishing, re-read your full response: every added stage must have a complete, syntactically closed statement, and the function body must literally end with `return result` as the last line, not mid-assignment.  
  _shown 12, pass 9/12 with vs 10/11 without, improvements 3/12 with vs 3/12 without_ 
- **R13** block_optimize raises ToolError unless 4 <= max_gates <= 200 AND block_size in {2,3,4}; seen failing on qft_8/qpe_8. Never pass max_gates=40 with block_size=4 or any pair you haven't checked against both bounds. Safe pairs: (block_size=2,max_gates=20-60), (block_size=3,max_gates=60-120); keep max_gates<=200 always.  
  _shown 15, pass 12/14 with vs 7/9 without, improvements 3/15 with vs 3/9 without_ 
- **R14** Verifier errors of ~1.0-1.73 (not a small overrun) on qft_8/mult_8 indicate a broken transform returned directly, not a budget issue: never let a bare tools.block_optimize(...) or tools.pyzx_clifford_simp(...) call become 'result' without wrapping it in tools.best(pre, candidate) first, since on these circuits a single bad transform can silently invalidate the whole output.  
  _shown 4, pass 3/3 with vs 3/4 without, improvements 2/4 with vs 1/4 without_ 
- **R15** Writing a long chain of guarded stages (fold_resynth/block_optimize/clifford_simp) risks the response being cut off mid-statement, leaving 'result' assigned to a stale or undefined value (e.g. 'result = tools.can'). Keep optimize() under ~6 guarded stages and write the final 'return result' line first in your draft, then add stages before it, never after.  
  _shown 7, pass 5/6 with vs 1/1 without, improvements 2/7 with vs 1/1 without_ 
- **R16** On qft_8 and mult_8, chains that pass a tools.best(...) result into another tools.best(...) across multiple time_left() blocks without re-canonicalizing each time have produced error bounds near 1.0-1.7. Always call tools.canonicalize(...) on both the previous result and the new candidate before every tools.best(...) comparison, not just before block_optimize.  
  _shown 5, pass 4/5 with vs 2/2 without, improvements 2/5 with vs 1/3 without_ 

## retired (6)

- **R1** Always run candidates through tools.canonicalize(...) before tools.best(...) comparisons and before returning; mixing raw tket/pyzx outputs with canonicalized ones in tools.best() has produced error bounds up to 1.0-1.4, i.e. wrong-unitary outputs, not just suboptimal ones.  
  _shown 11, pass 6/11 with vs 3/5 without, improvements 2/11 with vs 2/5 without_ (z = -1.08 at call 29)
- **R3** After tools.block_optimize or any chained tools.fold_resynth, re-verify by wrapping the result in tools.canonicalize(...) before the final tools.best(...) comparison and return -- comparing/returning an un-canonicalized intermediate is a common source of invalid-output rejections.  
  _shown 8, pass 3/8 with vs 9/12 without, improvements 1/8 with vs 4/12 without_ (z = -1.19 at call 34)
- **R5** If a circuit has many parametrised/controlled phase rotations (QFT/QPE-style), prefer tools.fold_resynth over tools.pyzx_clifford_simp for merging phases; clifford_simp is only safe on near-Clifford circuits and has produced large verifier error bounds (>1.0) when applied broadly in recent rejections.  
  _shown 9, pass 5/9 with vs 3/3 without, improvements 1/9 with vs 2/3 without_ (z = -2.41 at call 42)
- **R6** Every diff must contain a SEARCH block whose text matches the parent program exactly once, verbatim (same whitespace/indentation). Truncated or reformatted parent snippets, or edits touching code that appears more than once, cause 'SEARCH text found 0 times' parse errors. Copy the exact lines from the shown parent before editing.  
  _shown 16, pass 15/16 with vs 8/8 without, improvements 5/16 with vs 5/8 without_ (z = -1.04 at call 69)
- **R9** Before submitting a diff, re-copy the SEARCH block from the exact parent text shown in this prompt, including the docstring line and blank lines; do not reuse a SEARCH block from a different accepted child or an edited mental version, since any mismatch (even trailing whitespace) causes 'SEARCH text found 0 times'.  
  _shown 8, pass 6/8 with vs 8/8 without, improvements 1/8 with vs 4/8 without_ (z = -1.55 at call 80)
- **R10** Always write optimize() to completion in one response: every branch must end with a full `result = tools.canonicalize(tools.best(pre, ...))` statement, and the function must finish with an explicit `return result`. A truncated body (dangling `tools.time` or missing return) is an unparseable/invalid program and scores zero.  
  _shown 9, pass 7/9 with vs 11/11 without, improvements 3/9 with vs 7/11 without_ (z = -1.09 at call 99)
