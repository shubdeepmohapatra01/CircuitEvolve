# Placebo playbook placebo_v1 (FROZEN control)

SHA-256 of `playbooks/placebo_v1.json`: `27162b1933a1aaad9b7ffb2401a0ca26a41d9fd9ff22da6429e19a84c0bdbffb`.

Hand-written, generic and task-agnostic: no circuit-, gate- or rotation-specific advice. Same number of ACTIVE rules as `dev_v1` (1; the brief asked for at least 3, which cannot also match the learned playbook's single active rule — matching was preferred), similar length (292 vs 255 characters), stored in the same JSON format and rendered into the prompt by the identical code path (`Playbook.load(..., frozen=True).select` -> `Playbook.render` in `core/mutator.build_prompt`).

---

# Playbook (open naming)

## active (1)

- **R1** Before you answer, read your reply once more and check that every line follows the exact output format given in the instructions (names, labels, number format, block markers); a malformed line wastes the attempt. Keep the answer concise and do not add commentary outside the requested blocks.  
  _shown 0, pass 0/0 with vs 0/0 without; improving prompts as candidate 0/0 shown vs 0/0 hidden; improvements while shown (any status) 0_ (placebo control: generic, task-agnostic; hand-written, no evidence)

