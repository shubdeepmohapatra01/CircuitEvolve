# Playbook (open naming)

## candidate (3)

- **R1** tools.block_optimize requires block_size in {2,3,4} and 4 <= max_gates <= 200 (default max_gates may be too low for block_size=4). When calling block_optimize with block_size>2, pass an explicit max_gates>=4*block_size to avoid ToolError.  
  _shown 0, pass 0/0 with vs 0/0 without, improvements 0/0 with vs 0/0 without_ 
- **R2** Before submitting a diff, ensure the SEARCH block text appears verbatim exactly once in the parent program; copy it character-for-character from the parent rather than retyping from memory.  
  _shown 0, pass 0/0 with vs 0/0 without, improvements 0/0 with vs 0/0 without_ 
- **R3** Stacking many best-of candidates (fa,fb,fc,fd,fbest...) rarely beats a focused chain of fold_resynth -> block_optimize(fold_resynth) -> block_optimize(pyzx) on the single running best; prefer narrowing to the current best before branching further.  
  _shown 0, pass 0/0 with vs 0/0 without, improvements 0/0 with vs 0/0 without_ 
