"""Tier 2 of v2: an executable, verified rewrite-rule library for exact Clifford+T circuits (unitary-preserving only).

Modules: commute (fixed commutation table), rules (DSL, one-time exact verification, versioned libraries with SHA-256),
apply (commutation-aware matching, fixpoint application, whole-circuit guards), enumerate_ids (no-LLM Quartz-style
identity enumeration control), evolve (library evolution loop with the keep-only-if-better acceptance rule).
See docs/v2/TIER2.md.
"""
