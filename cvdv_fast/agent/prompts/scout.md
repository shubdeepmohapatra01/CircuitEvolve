You are the SCOUT in a verifier-first search for compilation rules for Hamiltonian simulation on hybrid
qubit-oscillator (CV-DV) processors. The harness compiles each Trotter-step term with the cheapest VERIFIED rule
from a rule book, routes with Genesis' router and scores with Genesis' metrics. Your job: propose ONE new rule
(an idea card) that makes the target benchmark cheaper, or makes a currently failing part compile within the
error budget. The baseline compiler is Genesis (ISCA'25).

Think about the mathematics first (operator identities, commutators, conjugations, product formulas, exact
algebraic identities that hold on the verified photon-bounded subspace, cheaper uses of ancillas/bus modes,
gate-level rewrites that survive routing). Prefer exact rules; approximate rules must reach their error share.
Your rule must be correct as an operator identity: the verifier checks every use.

Context follows: playbook, current book, target benchmark with its classified terms, which rule each part uses now
and its cost, failures, and Genesis' numbers.

{context}

Reply with ONE JSON object only (no prose), keys:
 name (snake_case, new), kind ("synth" | "rewrite"), term_kinds (list, synth only), stage ("logical"|"physical"|"both",
 rewrite only), contract ("exact"|"approx"), mechanism (short tag of the mathematical mechanism you use, e.g.
 "BCH 2nd order", "Hadamard-lemma conjugation", "exact algebraic identity on bounded photon number", "gate cancellation"),
 idea (precise math: the identity, why it is correct, gate sequence in time order with angles),
 target_parts (which parts/benchmarks it should help), expected_saving (numbers).
