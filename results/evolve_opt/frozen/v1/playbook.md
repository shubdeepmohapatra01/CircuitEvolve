# Playbook (open naming)

## active (2)

- **R3** Build a growing candidate pool with tools.best([...]) across all pipeline variants (pyzx full_reduce, pyzx teleport_reduce, pyzx clifford_simp, tket, each fold_resynth'd), then try block_optimize refinements guarded by tools.time_left() on top of the current best, returning tools.best of everything tried.  
  _shown 59, pass 30/30 with vs 43/44 without; improving prompts as candidate 17/31 shown vs 16/45 hidden; improvements while shown (any status) 27_ (z = +1.67 at call 92)
- **R8** Reusing the same literal-constant pattern (block_size=3,max_gates=40 etc.) is NOT sufficient: these have still ToolError'd on qft_8/qpe_8. The bound violation depends on the actual circuit, not just the literals. Prefer fewer, smaller block_optimize calls (max_gates<=30) or skip block_optimize entirely on branches reachable by every benchmark.  
  _shown 66, pass 8/8 with vs 8/8 without; improving prompts as candidate 5/8 shown vs 2/8 hidden; improvements while shown (any status) 29_ (z = +1.69 at call 62)

## candidate (8)

- **R10** block_optimize's max_gates bound is checked against the CURRENT candidate's gate count, which shrinks across chained calls. A max_gates=40 that was safe on the original circuit can exceed 200 or sit outside range after prior reductions. Clamp max_gates conservatively (e.g. 10-20) for any block_optimize called after earlier best()/block_optimize steps, not just the first one.  
  _shown 23, pass 23/23 with vs 29/30 without; improving prompts as candidate 11/23 shown vs 12/33 hidden; improvements while shown (any status) 11_ 
- **R11** Reusing the same literal-constant pattern (block_size=3,max_gates=40 etc.) is NOT sufficient: these have still ToolError'd on qft_8/qpe_8, including when max_gates was OMITTED entirely. Always pass explicit, small max_gates (<=30) and block_size in {2,3,4} on every block_optimize call, or skip block_optimize entirely on branches reachable by every benchmark.  
  _shown 26, pass 23/24 with vs 29/29 without; improving prompts as candidate 9/26 shown vs 14/30 hidden; improvements while shown (any status) 9_ 
- **R14** Before emitting a program, estimate its length against the output budget. If it would be truncated, do not let truncation land mid-statement: write fewer, complete if/time_left blocks (each with its full candidate=tools.best(...) line) rather than many blocks that risk being cut off. A program ending in a dangling call or incomplete assignment is a syntax error that scores zero.  
  _shown 14, pass 14/14 with vs 10/10 without; improving prompts as candidate 6/14 shown vs 4/10 hidden; improvements while shown (any status) 6_ 
- **R15** When proposing a diff against a parent program, the SEARCH block must be an exact, verbatim substring of the parent text shown to you (matching whitespace, quotes, and line breaks) and must appear exactly once. Do not paraphrase, re-indent, or reconstruct the parent from memory; copy the lines directly from the parent listing before editing them.  
  _shown 14, pass 14/14 with vs 10/10 without; improving prompts as candidate 5/14 shown vs 5/10 hidden; improvements while shown (any status) 5_ 
- **R16** Prefer emitting the full program body rather than a diff when the parent is short, a large fraction of it is changing, or you are not fully certain the SEARCH text matches the parent verbatim -- a full rewrite cannot fail on 'SEARCH text found 0 times', while a mismatched diff always does.  
  _shown 17, pass 17/17 with vs 7/7 without; improving prompts as candidate 6/17 shown vs 4/7 hidden; improvements while shown (any status) 6_ 
- **R17** Diff proposals keep failing with 'SEARCH text found 0 times': when editing a long parent, copy the SEARCH block directly from the shown parent text in one contiguous chunk (no re-wrapping lines, no trimming trailing whitespace, no omitting blank lines). If in doubt, use a shorter unique anchor line rather than a multi-line block you might misremember, or emit the full program body instead.  
  _shown 2, pass 2/2 with vs 6/6 without; improving prompts as candidate 1/2 shown vs 2/6 hidden; improvements while shown (any status) 1_ 
- **R18** Before returning the final program, check it ends with a complete 'return tools.best([...])' statement (or a fully assigned candidate variable). Several rejects were truncated mid-statement (e.g. ending in 'reclif = tools' or an unfinished call). If budget is tight, finish and return the current candidate early rather than starting another if-block you may not complete.  
  _shown 4, pass 4/4 with vs 4/4 without; improving prompts as candidate 2/4 shown vs 1/4 hidden; improvements while shown (any status) 2_ 
- **R19** Count parentheses/brackets before submitting: a syntax error on a late line (e.g. line 22) is usually an unclosed call opened many lines earlier (tools.best([... , tools.block_optimize(...). Keep each tools.best([...]) call's opening and closing brackets on lines you can visually verify match, especially when nesting fold_resynth(canonicalize(...)) calls.  
  _shown 6, pass 6/6 with vs 2/2 without; improving prompts as candidate 3/6 shown vs 0/2 hidden; improvements while shown (any status) 3_ 

## retired (9)

- **R1** block_optimize requires block_size in {2,3,4} and 4 <= max_gates <= 200. Never pass max_gates=40/60 etc below 4 or above 200 — an out-of-range value on ANY candidate branch invalidates the whole program even if unused in the final return.  
  _shown 42, pass 41/41 with vs 28/29 without; improving prompts as candidate 21/42 shown vs 12/30 hidden; improvements while shown (any status) 21_ (z = +1.03 at call 86)
- **R2** Guard every block_optimize call's kwargs with literal safe constants (e.g. block_size=3, max_gates=60) rather than scaling them from budget/time_left; computed or ad hoc values risk violating tool preconditions and zero out the score.  
  _shown 16, pass 16/16 with vs 12/12 without; improving prompts as candidate 6/16 shown vs 6/12 hidden; improvements while shown (any status) 6_ (z = -1.10 at call 42)
- **R4** Stacking fold_resynth/teleport_reduce on top of best() outputs grows the candidate pool but each extra block_optimize call is another chance to violate block_size/max_gates bounds (R1). Cap the total number of block_optimize calls per program (e.g. <=4) and keep every call's constants inside {2,3,4}/[4,200] literally, even in branches added for a single accepted edit.  
  _shown 10, pass 10/10 with vs 14/14 without; improving prompts as candidate 2/10 shown vs 6/14 hidden; improvements while shown (any status) 2_ (z = -1.39 at call 54)
- **R5** When truncating/editing a program for a child, finish every block_optimize call you add or keep: a cut-off call (e.g. 'max_gates=30)' missing its closing paren/candidate=tools.best(...) line) is a syntax error that invalidates the whole program, not just that branch. Always complete the full if/time_left block you introduce.  
  _shown 36, pass 34/34 with vs 30/31 without; improving prompts as candidate 12/36 shown vs 15/32 hidden; improvements while shown (any status) 12_ (z = -1.04 at call 99)
- **R6** Before adding a new block_optimize branch, check it reuses the same literal-constant pattern as existing branches (e.g. block_size=3, max_gates=40) rather than introducing a new untested combination; novel constants are a common source of out-of-range ToolErrors on specific benchmark circuits like qft_8/qpe_8.  
  _shown 22, pass 8/8 with vs 8/8 without; improving prompts as candidate 5/8 shown vs 0/8 hidden; improvements while shown (any status) 11_ (superseded by R8)
- **R7** Never end a program mid-expression (e.g. 'candidate = tools.f' or 'candidate ='). A truncated final statement is a syntax error that invalidates the whole program even if earlier branches were fine. Always finish the last assignment and end with 'return tools.best([...])'.  
  _shown 8, pass 8/8 with vs 12/12 without; improving prompts as candidate 2/8 shown vs 6/12 hidden; improvements while shown (any status) 2_ (z = -1.23 at call 65)
- **R9** Never call tools.block_optimize with method/block_size but no explicit max_gates: the implicit default can fall outside 4<=max_gates<=200 on some circuits (e.g. qft_8, qpe_8), raising ToolError and invalidating the whole program. Always pass an explicit max_gates in [4,200] on every block_optimize call.  
  _shown 22, pass 20/20 with vs 12/13 without; improving prompts as candidate 8/22 shown vs 7/14 hidden; improvements while shown (any status) 8_ (z = -1.06 at call 97)
- **R12** When editing/truncating a program, count open parens on every line you keep or cut; if truncation is forced by length limits, cut entire top-level statements (whole if-block or whole assignment), never mid-call. A dangling '(' or missing ')' is a syntax error that invalidates the whole program.  
  _shown 20, pass 17/17 with vs 8/8 without; improving prompts as candidate 5/20 shown vs 3/8 hidden; improvements while shown (any status) 5_ (z = -1.06 at call 105)
- **R13** On qft_8/qpe_8 specifically, candidates shrink fast after pyzx_full_reduce/fold_resynth; a later block_optimize call (2nd+ in the chain) frequently sees <20 gates. Use max_gates<=12 and block_size=2 for every block_optimize after the first, or skip later block_optimize calls on branches every benchmark reaches.  
  _shown 9, pass 6/6 with vs 11/11 without; improving prompts as candidate 1/9 shown vs 4/11 hidden; improvements while shown (any status) 1_ (z = -1.59 at call 97)
