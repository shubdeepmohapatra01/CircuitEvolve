# Playbook (open naming)

## active (4)

- **R3** Gate each successive tools.block_optimize stage on tools.time_left() with strictly decreasing thresholds (e.g. 40,25,15,10) and always re-seed from tools.best(candidates) so far, not from a fixed variable, to avoid wasting budget refining an already-dominated candidate.  
  _shown 92, pass 10/10 with vs 12/12 without; improving prompts as candidate 8/10 shown vs 1/14 hidden; improvements while shown (any status) 28_ (z = +4.66 at call 38)
- **R5** When adding block_optimize stages, raise thresholds as you add more stages (e.g. 50,35,20) rather than reusing the previous program's thresholds unchanged; extra stages inserted before existing ones shift effective time budgets and can starve the final stages, hurting score even when each stage individually looks sound.  
  _shown 77, pass 14/14 with vs 12/12 without; improving prompts as candidate 5/14 shown vs 3/14 hidden; improvements while shown (any status) 22_ (z = +1.69 at call 57)
- **R10** R11 [candidate] Before emitting a diff, copy the SEARCH block directly from the shown parent text (including the leading docstring and blank lines) rather than retyping it from memory; retyped whitespace/line-break mismatches are the main cause of 'SEARCH text found 0 times'. If unsure, make the SEARCH block the entire parent file text and the REPLACE block the entire new file text.  
  _shown 49, pass 10/10 with vs 9/9 without; improving prompts as candidate 5/10 shown vs 1/10 hidden; improvements while shown (any status) 13_ (z = +1.70 at call 81)
- **R12** Each candidate added via tools.block_optimize should be built by re-canonicalizing the CURRENT best (tools.canonicalize(best)) at the point of the call, not a stale candidate captured earlier in the function; stale inputs to later stages silently waste budget on an already-dominated circuit even when thresholds are correctly staggered per R3/R5.  
  _shown 33, pass 8/8 with vs 8/8 without; improving prompts as candidate 4/8 shown vs 0/8 hidden; improvements while shown (any status) 8_ (z = +2.15 at call 95)

## candidate (7)

- **R7** When emitting a SEARCH/REPLACE diff, the SEARCH block must match the parent program's text byte-for-byte exactly once (same whitespace, blank lines, comments). Prefer rewriting the whole function body as one SEARCH block (e.g. the full 'def optimize(...):...return ...' text) rather than a small fragment, since partial-line fragments are the usual cause of 'found 0 times' failures.  
  _shown 37, pass 37/37 with vs 33/34 without; improving prompts as candidate 9/37 shown vs 9/35 hidden; improvements while shown (any status) 9_ 
- **R8** Every branch added inside a tools.time_left() gate must still update `best` with tools.best(candidates) AND the function must end with an unconditional `return best` (or equivalent) after all gates. A program that appends candidates but falls through without a final return, or returns early inside a gate, produces no score even if individual stages are sound.  
  _shown 38, pass 37/37 with vs 33/34 without; improving prompts as candidate 12/38 shown vs 6/34 hidden; improvements while shown (any status) 12_ 
- **R13** When adding a new pyzx/tket reduction variant (e.g. pyzx_clifford_simp, pyzx_teleport_reduce) feeding into fold_resynth, append both the raw and folded result to candidates before calling tools.best, so a stage that folds poorly doesn't discard a raw reduction that was already better than the prior best.  
  _shown 21, pass 20/21 with vs 19/19 without; improving prompts as candidate 4/21 shown vs 4/19 hidden; improvements while shown (any status) 4_ 
- **R14** Before emitting a SEARCH/REPLACE diff, count occurrences of the exact SEARCH string in the shown parent text yourself (mentally scan start-to-end once); if it is not exactly 1, widen the SEARCH block (add surrounding lines) or switch to whole-file SEARCH/REPLACE rather than submitting a guessed fragment.  
  _shown 15, pass 15/15 with vs 8/9 without; improving prompts as candidate 3/15 shown vs 1/9 hidden; improvements while shown (any status) 3_ 
- **R15** Before emitting a diff, copy the SEARCH block directly from the parent text shown in THIS turn (not memory, not a prior accepted diff's summary), including the leading docstring, blank lines, and exact indentation. Default to making SEARCH the entire parent file and REPLACE the entire new file unless the change is a single isolated line.  
  _shown 10, pass 10/10 with vs 13/14 without; improving prompts as candidate 2/10 shown vs 2/14 hidden; improvements while shown (any status) 2_ 
- **R16** R16 [candidate] Chained block_optimize stages each cost real wall-time beyond tools.time_left() budget checks (block_size/max_gates scale cost). If adding a new gated stage, also shrink max_gates or block_size on later stages, or add a tools.time_left() margin (e.g. require >2x the stage's typical cost) to avoid wall-time-limit verifier failures on large circuits like qpe_8.  
  _shown 5, pass 5/5 with vs 3/3 without; improving prompts as candidate 0/5 shown vs 0/3 hidden; improvements while shown (any status) 0_ 
- **R17** R18 [candidate] When a program already has 5+ staged tools.block_optimize calls, prefer editing thresholds/adding candidates to tools.best rather than appending yet another stage; each extra stage increases wall-time risk on large benchmarks without proportionally improving the geometric-mean score.  
  _shown 5, pass 5/5 with vs 3/3 without; improving prompts as candidate 0/5 shown vs 0/3 hidden; improvements while shown (any status) 0_ 

## retired (6)

- **R1** Build a wide candidate pool cheaply: run each base reducer (pyzx_full_reduce, tket FullPeepholeOptimise, pyzx_teleport_reduce, pyzx_clifford_simp) both on the lowered circuit AND cross-applied to each other's output (e.g. pyzx_full_reduce(tket(...))) before folding; cross terms often beat either alone.  
  _shown 8, pass 6/6 with vs 12/12 without; improving prompts as candidate 1/8 shown vs 6/12 hidden; improvements while shown (any status) 1_ (z = -1.19 at call 34)
- **R2** Always pair every reducer output with tools.fold_resynth(tools.canonicalize(x)) as a separate candidate rather than only folding the single current best; phase folding gains are not monotonic across reducers so folding only the winner misses cheaper folded alternatives.  
  _shown 11, pass 10/10 with vs 5/5 without; improving prompts as candidate 2/11 shown vs 3/5 hidden; improvements while shown (any status) 2_ (z = -1.22 at call 29)
- **R4** More candidate branches is not free: each extra tools.pyzx_full_reduce/fold_resynth/block_optimize call burns charged CPU time and risks pushing past budget, which can cost more than it gains. Before adding a new candidate source, check it beats an existing one on at least one real benchmark, not just 'more diversity'.  
  _shown 23, pass 22/22 with vs 19/19 without; improving prompts as candidate 5/23 shown vs 8/21 hidden; improvements while shown (any status) 5_ (z = -1.07 at call 75)
- **R6** Diffs must contain the exact parent text verbatim for the SEARCH block to match (whitespace, line breaks, docstring included) — do not paraphrase or drop the docstring/comments when quoting the parent snippet, or the edit is rejected as unparseable.  
  _shown 9, pass 8/8 with vs 6/6 without; improving prompts as candidate 2/9 shown vs 3/7 hidden; improvements while shown (any status) 2_ (z = -1.08 at call 47)
- **R9** Before adding a 4th/5th raw candidate source (teleport_reduce, extra fold_resynth passes, etc.), verify each adds distinct value: fold_resynth on near-identical inputs (e.g. fold_resynth(a) and fold_resynth(lowered) when a already dominates lowered) rarely changes the winner and just burns CPU time charged against the tie-break.  
  _shown 9, pass 9/9 with vs 10/10 without; improving prompts as candidate 2/9 shown vs 5/11 hidden; improvements while shown (any status) 2_ (z = -1.02 at call 68)
- **R11** The 4 parse_errors this round were all 'SEARCH text found 0 times'. Before emitting the diff, re-read the exact parent text shown in this turn (not a remembered/earlier version) and copy the SEARCH block verbatim from it, character-for-character, including docstring, blank lines, and trailing whitespace; do not reconstruct it from the diff summary of a prior accepted change.  
  _shown 9, pass 9/9 with vs 7/7 without; improving prompts as candidate 3/9 shown vs 1/7 hidden; improvements while shown (any status) 3_ (retired by reflector at call 96: duplicates R10's guidance on verbatim-copying the SEARCH block from the current turn's parent text; keeping both as separate near-identical rules dilutes playbo)
