# Playbook (open naming)

## active (1)

- **R14** Before submitting, scan every block_optimize call site in the final text for its two literal args (block_size, max_gates) independently—growing a program by appending new tiers often reuses a copy-pasted block whose block_size or max_gates was edited for one call but not a later duplicate, causing a ToolError that invalidates all circuits.  
  _shown 30, pass 9/9 with vs 11/11 without; improving prompts as candidate 4/9 shown vs 0/11 hidden; improvements while shown (any status) 5_ (z = +2.54 at call 99)

## candidate (10)

- **R4** tools.best accepts EITHER a single list arg OR multiple loose args, both consistently, e.g. tools.best(a, b) and tools.best([a, b, c]) both work. Never mix: don't append to a list and then also pass extra loose args in the same call.  
  _shown 39, pass 39/39 with vs 47/48 without; improving prompts as candidate 7/39 shown vs 11/49 hidden; improvements while shown (any status) 7_ 
- **R7** When editing via diff, copy the SEARCH block by selecting a short, unique, unmodified contiguous slice of the parent (e.g. one full if-block) rather than reconstructing the whole function from memory; retyping the entire body risks whitespace drift that makes SEARCH match 0 times.  
  _shown 30, pass 29/30 with vs 42/42 without; improving prompts as candidate 6/30 shown vs 8/42 hidden; improvements while shown (any status) 6_ 
- **R8** Before returning/finishing an edit, re-read your own output: a program ending mid-line (e.g. 'top = tools.best(candidate') is truncated and will be rejected. If adding a new tail block, keep it short and complete, or trim an earlier low-value branch to make room.  
  _shown 34, pass 34/34 with vs 37/38 without; improving prompts as candidate 6/34 shown vs 8/38 hidden; improvements while shown (any status) 6_ 
- **R12** If a diff SEARCH block fails to match, don't retry by retyping the same remembered body a second time with small edits guessed at whitespace—re-fetch/quote the parent's literal text for that region verbatim, or switch to a full-file replacement instead of a diff.  
  _shown 21, pass 20/21 with vs 35/35 without; improving prompts as candidate 4/21 shown vs 6/35 hidden; improvements while shown (any status) 4_ 
- **R15** When a diff SEARCH fails once, do not resubmit a second diff guessing at the parent text again; switch that turn to a full-file replacement of the whole program body, since repeated diff retries on the same mismatch keep producing 'found 0 times' parse errors.  
  _shown 19, pass 19/19 with vs 21/21 without; improving prompts as candidate 3/19 shown vs 2/21 hidden; improvements while shown (any status) 3_ 
- **R16** When a tail block gets cut by the response length limit (program ends mid-statement like 'blocked4 = t'), don't add another tier to an already-long program; truncation is a length problem, not a missing-feature problem. Finish the current tier cleanly and stop, or trim an earlier tier first.  
  _shown 10, pass 10/10 with vs 14/14 without; improving prompts as candidate 0/10 shown vs 1/14 hidden; improvements while shown (any status) 0_ 
- **R18** Before submitting a diff, verify the exact SEARCH text exists by locating it in the parent text you were given, not a paraphrase; if the parent was itself produced by truncation (ends mid-statement), a full-file replacement is safer than a diff against it.  
  _shown 10, pass 10/10 with vs 14/14 without; improving prompts as candidate 1/10 shown vs 0/14 hidden; improvements while shown (any status) 1_ 
- **R19** Before submitting, count the time_left() thresholds used to gate tiered block_optimize/fold tiers you added in this turn: each new tier needs a strictly smaller threshold than the previous one and a complete body. If you can't finish writing and wiring a new tier within the remaining response length, don't start it—stop after the last complete tier instead of truncating mid-statement.  
  _shown 6, pass 6/6 with vs 2/2 without; improving prompts as candidate 0/6 shown vs 0/2 hidden; improvements while shown (any status) 0_ 
- **R20** block_optimize requires max_gates in [4,200] and block_size in {2,3,4} for EVERY call site, not just the first. When copy-pasting a block_optimize line to add a new tier, explicitly re-check the new max_gates/block_size values against these bounds (e.g. max_gates must be >=4 even if you shrink block_size to 2) before submitting.  
  _shown 3, pass 3/3 with vs 5/5 without; improving prompts as candidate 0/3 shown vs 0/5 hidden; improvements while shown (any status) 0_ 
- **R21** When growing a program with a diff, re-copy the SEARCH block from the literal parent text shown this turn, not from a previous turn's child you recall from memory—parents change between turns and a stale remembered body gives 'found 0 times'. If unsure the text matches exactly, use a full-file replacement instead.  
  _shown 3, pass 3/3 with vs 5/5 without; improving prompts as candidate 0/3 shown vs 0/5 hidden; improvements while shown (any status) 0_ 

## retired (10)

- **R1** block_optimize requires block_size in {2,3,4} AND 4 <= max_gates <= 200. Calls with max_gates=40/60 but block_size outside {2,3,4}, or max_gates<4 or >200, raise ToolError and invalidate the whole run. Validate both bounds before calling.  
  _shown 41, pass 41/41 with vs 45/46 without; improving prompts as candidate 9/41 shown vs 13/47 hidden; improvements while shown (any status) 9_ (z = -0.36 at call 102)
- **R2** Build candidates as a flat list via repeated .append(...), then call tools.best(candidates) once with that list, not tools.best(x, y, z) with loose args mixed with tools.best(list). Keep call shape consistent to avoid parse/signature errors.  
  _shown 11, pass 11/11 with vs 9/9 without; improving prompts as candidate 1/11 shown vs 3/9 hidden; improvements while shown (any status) 1_ (z = -1.02 at call 34)
- **R3** Diff-style replies must contain the literal SEARCH block text copied exactly (verbatim whitespace/newlines) from the parent program exactly once; paraphrasing or re-indenting the SEARCH snippet causes 'unparseable response' rejection.  
  _shown 20, pass 20/20 with vs 15/15 without; improving prompts as candidate 3/20 shown vs 5/16 hidden; improvements while shown (any status) 3_ (z = -1.04 at call 51)
- **R5** block_optimize's block_size/max_gates bounds (block_size in {2,3,4}, 4<=max_gates<=200) are checked on EVERY call, not just the first; a later call that reuses hardcoded literals (e.g. block_size=4, max_gates=60) can still fail if those literals drift out of range when edited. Re-verify both bounds at each call site, not just once at the top.  
  _shown 24, pass 24/24 with vs 18/19 without; improving prompts as candidate 5/24 shown vs 6/20 hidden; improvements while shown (any status) 5_ (z = -1.02 at call 73)
- **R6** Diff-style replies must contain the literal SEARCH block text copied exactly (verbatim whitespace/newlines, including trailing lines) from the parent program exactly once, and the SEARCH block must end on a complete statement (not mid-line, e.g. not cut off after a trailing comma like 'block_size=4, '). Truncated or re-indented SEARCH snippets cause 'unparseable response' rejection.  
  _shown 8, pass 7/7 with vs 4/4 without; improving prompts as candidate 0/8 shown vs 2/4 hidden; improvements while shown (any status) 0_ (z = -1.37 at call 43)
- **R9** If copying a block_optimize(...) call to a new call site, re-check its literal block_size/max_gates against {2,3,4} and [4,200] at that exact line; a previously-valid literal pasted into a new branch is still checked fresh and raises ToolError if out of range.  
  _shown 8, pass 8/8 with vs 8/8 without; improving prompts as candidate 1/8 shown vs 3/8 hidden; improvements while shown (any status) 1_ (z = -1.05 at call 64)
- **R10** Growing a candidates list with tools.best(candidates) calls tends to truncate near the token limit (seen ending mid-line 'if tools'). Cap the chain: after ~5-6 if-blocks, stop adding new stages and just return tools.best(candidates); don't keep appending one more block 'just in case'.  
  _shown 8, pass 8/8 with vs 3/4 without; improving prompts as candidate 1/8 shown vs 2/4 hidden; improvements while shown (any status) 1_ (z = -1.34 at call 76)
- **R11** block_optimize bound violations keep recurring even with literals in {2,3,4}/4-200: double-check the actual values at the call site you just wrote (not a remembered-safe pair) before submitting, especially when copy-pasting a block and changing one argument but not the other.  
  _shown 18, pass 18/18 with vs 17/18 without; improving prompts as candidate 3/18 shown vs 6/18 hidden; improvements while shown (any status) 3_ (z = -1.01 at call 99)
- **R13** When appending multiple tiered candidates (tr/blocked/blocked2/blocked3) to a growing `candidates` list, call tools.best(candidates) again after each append and reuse that running `top` as input to the next tool call, not the original `best`/`top` captured earlier—otherwise later blocks optimize a stale candidate and the extra tiers add runtime without improving the score.  
  _shown 9, pass 9/9 with vs 15/15 without; improving prompts as candidate 1/9 shown vs 4/15 hidden; improvements while shown (any status) 1_ (z = -1.47 at call 102)
- **R17** Growing programs via repeated tiered if-blocks (tr/cs/blocked/blocked2/blocked3/blocked4...) tends to hit the output-length limit and truncate mid-line. Past ~5-6 tiers, prefer collapsing older tiers into a single tools.best(candidates) call rather than appending another near-duplicate if-block.  
  _shown 8, pass 8/8 with vs 8/8 without; improving prompts as candidate 0/8 shown vs 1/8 hidden; improvements while shown (any status) 0_ (z = -1.01 at call 109)
