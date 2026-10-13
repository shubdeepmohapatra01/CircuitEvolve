# CircuitEvolve → hybrid CV-DV: Genesis as baseline (design memo, draft 2026-10-13)

Sources read: Genesis paper (Chen et al., ISCA '25, arXiv:2505.13683), Genesis repo
`ruadapt/Genesis-CVDV-Compiler` (cloned HEAD, `src/pattern_match*.py`, `benchmark/`), Liu et al.,
*Hybrid Oscillator-Qubit Quantum Processors: ISAs, AMMs, and Applications* (arXiv:2407.10381, §E
"Instruction Sets for Universal Control"), and the current CircuitEvolve tree.

## 1. What Genesis does

| Level | Mechanism | Where |
|---|---|---|
| L1 synthesis | Hamiltonian DSL → IR (Pauli strings + boson/fermion operator expressions) → recursive template matching with 16 rules (Table 3) into the Table 2 basis gates, emitted as CVDV-QASM | `pattern_match.py`, `pattern_match_rules.py` |
| L2 mapping/routing | Qumode/qubit placement on a sparse coupling graph; beam-splitter SWAP insertion; Pauli-string ordering via Christofides (baseline) or threshold accepting | `circuits.py`, `graph_mapping.py`, `main.py` |

Table 2 basis gates: qubit rotations; qumode R(θ), D(α), BS(θ,φ); hybrid CR(θ), CP, CD(α), CBS(θ,φ),
RB(θ) (Rabi). No qubit–qubit gates: multi-qubit Pauli exponentials are mediated by an ancilla qumode
(Rule 15). Table 3 rules: 1 Trotter (approx), 2 BCH group commutator (approx), 3–11 exact
commutator/anticommutator/conjugation identities, 12–13 block-encoding/σx-dressed (approx),
14 multi-qubit-controlled displacement, 15 multi-Pauli exponential, 16 native gate match.

### Properties of the implementation that matter for us

1. **Rules are already data.** Each rule is `Rule(parse_str(LHS s-expr), params, parse_str(RHS s-expr),
   condition_lambda, derived_params)`. ~86 `Rule(` constructions grouped in lists
   (`commute_rules_list`, `gate_cancel_rules`, `basic_rules_list`, `exp_misc_rules`,
   `branching_rules_list`, `decomp_rules_list`, `sigma_z_rules`). An LLM can emit new rules in this
   exact s-expression format; conditions should be restricted to a whitelisted predicate set.
2. **Path selection is first-found, not cost-optimal.** `apply_rules_list_full_search` (DFS with
   backtracking) `break`s on the first path satisfying `end_condition` (`pattern_match.py:593-597`).
   The paper states that choosing among pathways by latency/gate count/error is future work (§3.1
   Discussion).
3. **Post-synthesis cleanup is qubit-only.** `gate_cancel_rules` has 4 rules (HH, XX, S S†, S† S).
   There are no CV merge rules (D(α)D(β) → phase·D(α+β), R(θ)R(φ) → R(θ+φ), CD/CR merges,
   BS·BS on the same pair, BS-SWAP cancellation across routing boundaries).
4. **No correctness check.** Neither paper nor repo verifies the compiled circuit against
   exp(-iHt); approximation error of Rules 1, 2, 12, 13 is not reported.
5. Build needs Java (ANTLR 4.13 → `generated/`). This machine has no Java runtime; use conda `openjdk`.

## 2. Genesis metrics (to be reproduced exactly)

From §4.1 "Metrics": **1-op gate count**, **2-op gate count** (qubit–qumode or qumode–qumode), and
**Depth/Duration** with latency 1 unit (20 ns) per 1-op gate and 20 units per 2-op / hybrid /
multi-qumode gate; depth is taken on the final *physical* (connectivity-compliant) circuit.
Table 5 additionally reports #qubits, #qumodes, #Pauli strings in IR, #gates in IR, final gate count.
Table 6 reports rule hit rates (success / total); Table 7 compile time.

Genesis Table 5 (final gate count / duration), the numbers to beat:

| Model | qubits | qumodes | IR gates | final gates | duration |
|---|---|---|---|---|---|
| Kerr | 19 (anc) | 1 | 409 | 595 | 3,032 |
| Z2-Higgs L=20/40/60 | 20/40/60 | 20/40/60 | 419/839/1259 | 696/1472/2263 | 943/1797/2721 |
| Bose-Hubbard 20/40/60 | 20/40/60 (anc) | 20/40/60 | 820/2440/4860 | 2935/15313/36705 | 15353/62548/155872 |
| Hubbard-Holstein | 40 | 20 | 100 (+3100 Pauli) | 688,011 | 4,509,157 |
| Electron-vibration 20/40/60 | 20/40/60 | 40/80/120 | 1392/2852/4312 | 5635/12655/19684 | 28551/54952/81729 |
| Heisenberg 20/40/60 | 20/40/60 | 0 | 0 (77/157/237 Pauli) | 2218/4676/7200 | 4122/4398/7074 |

Table 4 (20 molecular Pauli-string benchmarks, LiH…C2, JW/BK) is a routing study: threshold
accepting vs Christofides: the qumode-SWAP threshold variant reduces duration by 3.2–6.6 % on all 20 rows,
while the floating-qubit variant ranges from +5.1 % to −21.9 % (often worse than Christofides). It exercises L2 only; low value for a rule-
discovery study.

### Our fitness (lexicographic, CLAUDE.md invariant 3 carried over)

1. Valid: ISA membership + connectivity (L0) and verified within error budget ε at the benchmark's
   (t, Trotter order, step count) — see §4.
2. Duration (Genesis 1/20 latency model) — primary, matches their headline.
3. 2-op gate count, then 1-op gate count.
4. Ancilla qubits/qumodes.

Report Genesis' three metrics verbatim *and* the approximation error they omit. Without (1), a rule
library can trivially "win" by dropping Trotter steps or using a lower BCH order.

## 3. ISA choice (Liu et al. §E)

| ISA (Liu et al.) | Native set | Genesis coverage |
|---|---|---|
| Phase-space | CD(β) (ECD) + qubit rotations | CD, rotations in Table 2 |
| Fock-space | SNAP(θ⃗) + D(α) | no SNAP in Table 2 |
| Sideband | red/blue sideband (JC / anti-JC) + qubit rotations | RB only |
| Gaussian / Cubic | D, R, S, BS (+ cubic phase) | no squeezing / cubic |

Recommendation: **Phase-space ISA extended with BS for multimode** (= Genesis Table 2 restricted to
{qubit rot, R, D, BS, CD, CR, CP}). It is Genesis' own evaluation platform (superconducting,
§2.4), so the comparison is like-for-like, and CD is the single hybrid entangler, which keeps the
cost model honest. Secondary (transfer) experiment: Fock-space ISA, where Genesis has no rules at
all — a from-scratch rule-discovery test analogous to the DV "tier B" row.

## 4. The four stages for the CV-DV domain

| Stage | Content | Mutable? |
|---|---|---|
| Mutator | LLM proposes (a) new rewrite rules in Genesis s-expression form, (b) CV peephole/merge rules, (c) a cost-guided path-selection policy replacing first-found DFS. The existing ACE-style playbook (`search/playbook.py`) steers the prompts. | yes |
| Verifier | L0 parse/ISA/connectivity; L1 symbolic: exact rules checked as operator identities in the Heisenberg–Weyl × Pauli algebra (normal-ordered polynomials, exact rationals); L2 numerical: truncated-Fock check at cutoffs N and 2N on an energy-bounded subspace (catches truncation-edge artifacts); L3 whole circuit vs exp(-iHt) on the `*_small.ham` instances. Approx rules carry an explicit error bound, accounted like `blocks/verify_block.py`. | **frozen** |
| Metrics | Genesis 1-op / 2-op / duration on the physical circuit + approximation error + ancillas | frozen |
| Selector | MAP-Elites over rule libraries (features: library size, rule-hit diversity), fitness = geomean duration ratio vs Genesis over the dev set, gated on all-valid; islands as in `evolve_opt/evolve.py` | yes |

Split by Hamiltonian family (dev: Kerr, Bose-Hubbard, Z2-Higgs; held-out: Hubbard-Holstein,
electron-vibration, Heisenberg). Rules are learned on dev and evaluated frozen on held-out.

Arms (matched evaluation budget):
1. Genesis as published.
2. Genesis + hand-written CV peephole (D/R/CD/BS merges) + cost-optimal path choice — **the honest
   classical bar** (analogue of pyzx in the DV track). Gains here are not LLM gains.
3. Classical search over rule compositions/orderings (no LLM).
4. LLM rule mutator, no playbook / with playbook / frozen playbook / shuffled-rule control.

## 5. Repository restructuring

Current invariants 1–2 are Clifford+T-specific (exact Z[ω] ring, adder spec). Generalize to a
domain plugin: `circuitevolve/core/` (loop, selector, playbook, sandbox, integrity) and
`circuitevolve/domains/{ftqc_ct, cvdv}/` each supplying `ir`, `isa`, `verifier` (frozen, hashed),
`cost`, `baselines`, `benchmarks`. The DV results stay valid; the CV domain gets its own frozen
files and acceptance suite (planted bugs: wrong BCH sign, dropped phase in D·D merge, truncation-
edge-only identity, wrong BS angle convention).

Note: `git log` in CircuitEvolve reports no commits on `main`. Commit the current tree before the
refactor.

## 6. Open risks

- Verification of CV circuits is approximate by construction (Fock truncation); the error budget
  and cutoff policy must be fixed before any search.
- The largest numbers (Hubbard-Holstein 688k gates) may be dominated by L2 routing and multi-Pauli
  synthesis rather than L1 rules; profile Genesis output by gate origin before choosing targets.
- Rules 1–2 are 28.8 % of successful hits; some gains may come from Trotter grouping/ordering,
  which is a classical problem.
