You are the IMPLEMENTER. Write ONE Python rule file for the rule card below, against this API (read carefully,
conventions matter: CR(t) = exp(-i t/2 Z n), so exp(-i theta Z n) = CR(2 theta); time order = emission order).

=== cvdv_fast/api.py ===
{api}

=== two example rule files from the book ===
{examples}

=== rule card ===
{card}
{feedback}
Rules: the file may import only from cvdv_fast.api, math, cmath, itertools, functools. No file/OS access, no exec/eval.
It must define RULE = Rule(...) with the card's name. A synth function receives (t, g, r) and emits gates via g;
it should return None (emit nothing) to decline parts it does not handle. Use g.anc_qubit(k) / g.anc_mode(k) for
ancillas (they start in |0> / vacuum and MUST be returned there). Rewrite rules: trigger(ops) -> list of matches,
apply(ops, m) -> (i0, i1, new_ops) replacing ops[i0..i1] inclusive; ops are cvdv.qasm.Op(name, params, wires).
Reply with the complete file in one ```python code block and nothing else.
