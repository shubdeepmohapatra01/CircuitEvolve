# CV-DV literature harvest — 2026-10-18 (PLAN_P2 phase P2.2b)

Budgeted harvest of candidate compilation rules from the published oscillator-qubit ISA literature,
certified through the frozen cvdv certifier (plugin `CvdvRulesPlugin`, n_max=3, allowance 0.001,
EXACT_TOL 1e-9, frozen digest `0e83ded36fec00ab`), over synthetic instances:
pauli (XX/YY/ZZ at θ=0.05, ZZ at θ=-0.07), pauli_hop (X, θ=0.05, φ=0), hop, disp, n2.

## Source

Yuan Liu et al., *Hybrid Oscillator-Qubit Quantum Processors: Instruction Set Architectures,
Abstract Machine Models, and Applications*, arXiv:2407.10381. Fetched as arXiv e-print LaTeX
source (the DOI 10.48550/arXiv.2407.10381 is not registered in CrossRef and the arXiv HTML render
is a stub). Sections excerpted verbatim into prompts:

- VII.C.1 Useful Primitives (20,387 chars)
- VII.C.2 Compilation of Entangling Gates between Physical Qubits (20,023 chars)
- VII.C.3 Compilation of Entangling Gates between Oscillators (5,940 chars)
- VIII.C.5 Many Modes: Bose-Hubbard / FQHE (6,468 chars)
- VIII.C.6 Large Spin Models: Transverse-field Ising (9,577 chars)
- VIII.C.7 Many Qubits, Many Modes: Z2 gauge theory (6,359 chars)

## Budget and call log

Hard budget: ≤ 8 candidates, ≤ 12 LLM calls. Used: **2 candidates, 6 LLM calls**
(model `claude-sonnet-5`; calls 1-2 were empty max_tokens failures at 6000 tokens, retried once at 20000).

| # | call | prompt SHA-1 | outcome |
|---|------|--------------|---------|
| 1 | call1_pauli/attempt1 | `0a27bcb7716cc2369b0024d949178b933db5870d` | empty response (stop_reason=max_tokens at 6000; reasoning consumed the cap) |
| 2 | call2_hop_family/attempt1 | `41394ad514e995fd4f8a18f7a1353b9fce2dfb04` | empty response (stop_reason=max_tokens at 6000) |
| 3 | call3_n2 | `da232b85807e0d66559b19c14d63199a3b009361` | NONE (model declined to propose n2 candidates) |
| 4 | call1_pauli/attempt2 | `0a27bcb7716cc2369b0024d949178b933db5870d` | 1 candidate: rule_pauli__cd_loop_2q |
| 5 | call2_hop_family/attempt2 | `41394ad514e995fd4f8a18f7a1353b9fce2dfb04` | 1 candidate: rule_pauli_hop__basis_conj; explicit decline for hop/disp |
| 6 | repair/cd_loop_builtin | `9f995efec09f403a09ad96fd3e42611d67032855` | repaired any() -> sum() guard; nothing else changed |

## Candidates

### Candidate 1: `rule_pauli__cd_loop_2q` (kind `pauli`) — **CERTIFIED EXACT**

- Paper location: arXiv:2407.10381 §VII.C.2 'Compilation of Entangling Gates between Physical Qubits' / 'Two-Qubit Entangling Gates', eq:RZZ (+ eq:beamsplitter_conjugation remark); label verified present in source
- Extraction: call1_pauli/attempt2; repair: 1 repair call: `any` is not in SAFE_BUILTINS (NameError in restricted exec); guard rewritten with sum()
- Certificate: worst-case eps = 9.445e-16 at n_max=3, ancilla back to |0>/vacuum (frozen `certify` via `Compiler.evaluate`/`best_r`)
- Model's stated insight (verbatim header):

> CANDIDATE 1: kind=pauli; source=§VII.C.2 "Two-Qubit Entangling Gates", Eq. (RZZ) R_ZZ(θ)=D_c^{(1,2)}(-iα,+iα)D_c^{(1,1)}(α,-α)D_c^{(1,2)}(+iα,-iα)D_c^{(1,1)}(-α,α), θ=4α² (with the beam-splitter-conjugation remark of Eq. beamsplitter_conjugation showing the "remote" CD is just a CD between an ancilla mode and whichever qubit is addressed); insight=The paper's two-qubit gate is built from *two* conditional displacements on a *single shared ancilla mode*, one controlled by each qubit, forming a closed phase-space loop whose enclosed area is proportional to Z1Z2 — algebraically this is exactly our native `CD(alpha,q,md)` gate applied twice per qubit, so on our ISA (where CD already connects *any* qubit to *any* mode) the beam-splitter SWAP network the paper needs for its fixed local connectivity is unnecessary, collapsing the gate to 4 hybrid CD ops total instead of the existing rule's 8 CR/CP ops; the net oscillator displacement sums to exactly zero for every joint qubit eigenvalue so the ancilla provably returns to vacuum (certified exact), and basis changes (H for X, Sdg·H for Y) reduce XX/YY to the same ZZ loop at the cost of a few extra 1-op gates; sign of theta is handled by taking the Hermitian conjugate (reverse order + negate amplitudes) of the θ≥0 sequence.

| instance | certified eps | cost (dur, 2-op, 1-op) | current best |
|---|---|---|---|
| `pauli(('q', 0), ('q', 1))(0.05,) XX` | 5.83e-16 | dur 82, 2-op 4, 1-op 4 | dur 165, 2-op 8, 1-op 8 (qumode_commutator) |
| `pauli(('q', 0), ('q', 1))(0.05,) YY` | 5.83e-16 | dur 84, 2-op 4, 1-op 8 | dur 167, 2-op 8, 1-op 12 (qumode_commutator) |
| `pauli(('q', 0), ('q', 1))(0.05,) ZZ` | 1.37e-16 | dur 80, 2-op 4, 1-op 0 | dur 164, 2-op 8, 1-op 4 (qumode_commutator) |
| `pauli(('q', 0), ('q', 1))(-0.07,) ZZ` | 9.44e-16 | dur 80, 2-op 4, 1-op 0 | dur 164, 2-op 8, 1-op 4 (qumode_commutator) |

Certified rule function (final form; lives in this report — NOT appended to the rulebook, per harvest scope):

```python
def rule_pauli__cd_loop_2q(t, g, r):
    if len(t.q) != 2:
        raise ValueError("weight-2 only")
    if sum(1 for s in t.label if s not in ("X", "Y", "Z")) > 0:
        raise ValueError("unsupported label")
    q1, q2 = t.q
    for q, s in zip(t.q, t.label):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.sdg(q)
            g.h(q)
    md = g.anc_mode()
    a = m.sqrt(abs(t.theta) / 2)
    if t.theta >= 0:
        g.CD(-a, q1, md)
        g.CD(1j * a, q2, md)
        g.CD(a, q1, md)
        g.CD(-1j * a, q2, md)
    else:
        g.CD(1j * a, q2, md)
        g.CD(-a, q1, md)
        g.CD(-1j * a, q2, md)
        g.CD(a, q1, md)
    for q, s in zip(t.q, t.label):
        if s == "X":
            g.h(q)
        elif s == "Y":
            g.h(q)
            g.s(q)
```

### Candidate 2: `rule_pauli_hop__basis_conj` (kind `pauli_hop`) — **CERTIFIED EXACT**

- Paper location: arXiv:2407.10381 §VII.C.1 'Useful Primitives', eq:cparity_conj + eq:cond_disp_compilation (Z→P conjugation); labels verified present in source
- Extraction: call2_hop_family/attempt2; repair: none
- Certificate: worst-case eps = 2.468e-16 at n_max=3, ancilla back to |0>/vacuum (frozen `certify` via `Compiler.evaluate`/`best_r`)
- Model's stated insight (verbatim header):

> CANDIDATE 1: kind=pauli_hop; source=arXiv:2407.10381 §VII.C.1 "Synthesizing Hybrid Oscillator-Qubit Gates", Eq. (cparity_conj) and Eq. (cond_disp_compilation) [the $Z\to P$ conjugation identity], combined with the existing `rule_z_hop__cp_conj` CP/BS/CR sequence; insight=For any unitary $V$ on the ancilla with $VZV^\dagger=P$, $V\,e^{-i\theta Z(\text{op})}\,V^\dagger = e^{-i\theta P(\text{op})}$ exactly, since $V$ acts only on the qubit wire and commutes with the mode operator — so sandwiching the certified `z_hop` sequence with $H$ (for $X$, since $HZH=X$) or with $H$ then $S$ (for $Y$, since $S(HZH)S^\dagger=Y$) gives an exact rule for weight-1 Pauli-hop with zero added entangling gates, only 2 (X) or 4 (Y) extra 1-op gates.

| instance | certified eps | cost (dur, 2-op, 1-op) | current best |
|---|---|---|---|
| `pauli_hop(('q', 0), ('qm', 0), ('qm', 1))(0.05, 0.0) X` | 2.47e-16 | dur 62, 2-op 3, 1-op 2 | dur inf, 2-op inf, 1-op inf (none) |

Certified rule function (final form; lives in this report — NOT appended to the rulebook, per harvest scope):

```python
def rule_pauli_hop__basis_conj(t, g, r):
    if t.label == 'X':
        g.h(t.q[0])
        g.CP(t.q[0], t.m[1])
        g.BS(2 * t.theta, t.phi + m.pi / 2, t.m[0], t.m[1])
        g.CR(-m.pi, t.q[0], t.m[1])
        g.h(t.q[0])
    elif t.label == 'Y':
        g.sdg(t.q[0])
        g.h(t.q[0])
        g.CP(t.q[0], t.m[1])
        g.BS(2 * t.theta, t.phi + m.pi / 2, t.m[0], t.m[1])
        g.CR(-m.pi, t.q[0], t.m[1])
        g.h(t.q[0])
        g.s(t.q[0])
    else:
        g.CP(t.q[0], t.m[1])
        g.BS(2 * t.theta, t.phi + m.pi / 2, t.m[0], t.m[1])
        g.CR(-m.pi, t.q[0], t.m[1])
```

## Declined kinds (valid outcomes)

- **n2**: call 3 answered `NONE` — nothing in the Bose-Hubbard / Useful-Primitives excerpts beats
  `parity_exact` (65, 3, 6) without re-entering the group-commutator/BCH plateau (playbook #3/#6).
- **hop / disp**: the model explicitly declined — one native `BS` / `D` per term is already
  cost-optimal under the lexicographic metric.

## Summary

2 candidates extracted, **2/2 certified exact** at n_max=3, both appended to
`playbooks/families/cvdv.bosonic.json` as seed rules:

1. `pauli` weight-2 gadget via conditional-displacement phase-space loop (§VII.C.2, eq:RZZ):
   4 CD two-op gates vs the incumbent qumode_commutator's 8 two-op — halves the 2-op count and
   duration (164→80 for ZZ) on the known loss case vs Genesis.
2. `pauli_hop` via Z→P basis conjugation of the z_hop CP·BS·CR sequence (§VII.C.1,
   eq:cparity_conj): new kind coverage (previously no rule existed), 3 two-op / 2 one-op, exact.

No forced successes: n2, hop and disp produced no candidates. Certified functions are recorded
here only; appending them to `cvdv/rulebook/rules.py` is a campaign action, out of harvest scope.
