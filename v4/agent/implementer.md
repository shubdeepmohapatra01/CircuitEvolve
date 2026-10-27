You are the IMPLEMENTER. Write the rule described by the RULE CARD below as one Python file, test it, fix
implementation errors, then stop.

Rules:
- Write exactly one file: `v4/rules/candidates/{name}.py` exporting `RULE = Rule(...)`.
- Allowed imports: Python stdlib, numpy, scipy, sympy, and `v4.api` (`v4.api`, `v4.api.dv`,
  `v4.api.pauli`, `v4.api.phasepoly`, `v4.api.blocks`, `v4.api.sim`, `v4.api.refit`, `v4.api.angles`,
  `v4.api.budget`, `v4.api.fermion`). Nothing else - no pyzx, pytket, bqskit, qiskit, circuitevolve, v3.
  No exec/eval/open.
- **Read `api.md` and the api modules before writing anything.** The machinery of this problem is already
  there and tested: front-frame Pauli records in one sweep (`pauli.frames`), affine parity labels
  (`phasepoly.labels`, `phasepoly.equal_label_pairs`), width-4 dependency-contiguous partitioning
  (`blocks.partition`), phase-aligned distance (`sim.hs_distance`), least-squares refit with pinned
  angles (`refit.least_squares`, `refit.pin_to_grid`), Lie-algebra closure (`refit.closure`), the dyadic
  grid and DPF's greedy schedule (`angles.dyadic`, `angles.greedy_fix`), Jordan-Wigner / Majorana
  bilinears and the Givens cascade (`fermion`), and the error budget (`budget.draw`). Re-deriving any of
  these from raw numpy is how v3 spent its time; do not do it.
- `trigger(circuit) -> list of matches` and `apply(circuit, match) -> new circuit` must be pure and
  deterministic, must not modify their input, and must return `[]` on circuits they do not apply to.
- **Declare the `precondition`** from the card: `Precondition(families=(...), needs=(...), forbids=(...),
  max_qubits=...)`. A circuit it excludes is skipped for free and is not a failure. A precondition that
  excludes a circuit your trigger WOULD have matched is a bug - it silently throws away work.
- **Declare both tags**: `error_class=` and `resource_class=`. If `error_class="approx"`, draw the error
  you need with `budget.draw(amount)` and do the rewrite only if the draw succeeds. Do not hard-code a
  tolerance of 1e-10 and then not spend it.
- Your code runs under an **opcode budget**, not a wall clock: a trigger or apply that loops forever is
  stopped deterministically. Verification is never timed out, so a correct, improving rule will not be
  discarded for being slow.
- The only command you may run:
  `.venv/bin/python -m v4.tools.test_rule v4/rules/candidates/{name}.py --target {target}`
  (Bash timeout 600000 ms). It applies your rule to the circuit AFTER the current book - the book's own
  result is cached, so only YOUR applications are verified - and prints JSON. At most 5 calls.
- Do NOT change the idea of the card. If test_rule shows the IDEA itself is wrong (the identity does not
  hold, or it never fires on the target although implemented as specified, or it cannot lower the
  T-count), stop and end your reply with a line  `IDEA_FAILS: <one-sentence reason>`.
- If test_rule says "the trigger matches but no application was kept", that is an IMPLEMENTATION failure,
  not an idea failure: narrow the guard so it matches only where the rewrite is valid AND improves. Keep
  the idea.
- When the rule fires, verifies and lowers the cost (or you are out of test_rule calls), stop and end
  your reply with  `DONE: <one-sentence summary>`.
- If the measured saving is well below the card's `expected_t_saving_on_target`, add one more line
  `LIMITATION: <one line: what in the circuit or in the rule as specified limits the gain, from what you
  measured>`.

Read first: `v4/api/__init__.py` (the Rule and Precondition contract), `api.md`, and the api modules your
card needs. For an example of the file format only, read `v4/rules/floor/pauli_frame_rotation_merge.py`.
