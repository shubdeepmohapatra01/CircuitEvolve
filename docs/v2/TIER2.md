# Tier 2 - executable, verified rewrite-rule library (unitary-preserving)

Code: `circuitevolve/v2/tier2/`. Experiments: `experiments/v2_tier2_evolve.py` (evolution, both arms),
`experiments/v2_tier2_report.py` (freeze + report). Tests: `tests/v2/test_tier2_rules.py`, `tests/v2/test_tier2_evolve.py`.
Results: `results/v2/tier2/` (DEV_REPORT.md first).

## Scope
Exact Clifford+T circuits over {h s sdg t tdg x z cx cz}; no measurement, no ancillas, no ccx/ccz (expanded on load).
Every rewrite preserves the unitary up to one global phase.

## Rules (`rules.py`)
A rule is a literal template over qubit variables a, b, c, d (k <= 4):

    RULE merge_tt
    PATTERN: t a; t a
    REPLACE: s a
    SIDE: commute        # or 'contiguous' (fixed set)
    MEANING: two T on one wire make S
    END

Parsed with regexes (never exec/eval). Well-formedness: allowed gates and arities, distinct variables per gate, connected
pattern (each gate after the first shares a variable with an earlier one), <= 20 gates per side, and (T, gates) of the
replacement strictly below the pattern's (lexicographic) - this is the termination measure.

**Verified once.** `verify_rule` proves PATTERN == c * REPLACE on the k rule qubits with `v2.verify(mode='exact')`
(frozen D[omega] simulator, exhaustive over 2^k basis inputs with one global phase c: `certified=True`). Only verified
rules enter a library; a library loaded from JSON is re-verified and its SHA-256 re-checked (`Library.load`).

**Libraries** are JSON (`format circuitevolve.v2.tier2.library/1`) with the ordered rule list, the SHA-256 of the canonical
content (variable names canonicalized, so renaming does not change the hash), the parent's SHA-256 and metadata. v0 = empty.

## Commutation table (`commute.py`)
Per qubit a gate is 'Z' (z s sdg t tdg, both qubits of cz, cx control), 'X' (x, cx target) or 'O' (h). Two gates commute
if disjoint, identical, or every shared qubit has the same role in both and the role is Z or X. Tested against dense
matrices for all ordered pairs of gates on 3 qubits (no false positive).

## Matching and application (`apply.py`)
Deterministic greedy matcher: pattern gate 0 at position i binds variables; each further pattern gate is the first matching
gate among the next 24 gates on the already-bound qubits. The candidate match p0 < ... < pL is valid if every unmatched gate
between p0 and pL that touches a matched qubit either commutes with all matched gates before it (it moves left; the
replacement goes after it) or commutes with all matched gates after it (moves right). `contiguous` forbids any such gate.
`apply_library` runs passes over positions (rules in library order) until a pass changes nothing; every application lowers
(T, gates), so it terminates. Guards: `numeric_guard` (random statevectors, n <= 22; not a proof) and `exact_guard`
(v2 exact verifier, exhaustive, n <= 10 by default).

## Evolution (`evolve.py`)
Per generation: propose -> verify each new rule once (the budgeted evaluation) -> candidate = current + verified rules ->
apply to all DEV start circuits (`circuits.py`: best verified exact classical output per DEV circuit) -> KEEP iff total DEV T
drops and no circuit's T rises; kept libraries are pruned to rules that applied. LLM arm: prompts with DSL + matching
semantics, technique cards 07/09/03/08, 6 T-containing convex windows (<= 4 qubits, <= 20 gates) and verifier feedback.
No-LLM control (`enumerate_ids.py`): Quartz/RepGen-style enumeration of minimal identities (fingerprinted unitaries for
proposal only; each used rule is verified exactly like LLM rules), given the same number of verifications per generation.

## Result (run1, DEV)
Null for both arms: total DEV T 758 -> 758; frozen primary library = v0 (empty). No T-reducing enumerated identity
(8,833 of them) matches the phase-folded start circuits. Details and the secondary gate-count replay:
`results/v2/tier2/DEV_REPORT.md`.
