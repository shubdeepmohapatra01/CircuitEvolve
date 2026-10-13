# LLM-assisted circuit optimizer: top-level pipeline

*Saved 2026-10-06. Diagram artifact: `circuit_optimizer_pipeline.png` (artifact id db549c97-b65a-425a-a92f-f08b169b8081).*

![Pipeline](/Users/shubdeepmohapatra/.claude-science/orgs/4f2e4147-ba5e-4b44-8499-c19c4f626162/artifacts/proj_a726946937e5/db549c97-b65a-425a-a92f-f08b169b8081/vea08ab56_circuit_optimizer_pipeline.png)

## Contract
`optimize(circuit) -> optimized_circuit + equivalence certificate + report`.
The LLM appears in exactly one box (stage 4, "LLM proposes"). Everything else is harness code.
The LLM never edits the user's circuit directly: it writes rewrite rules / passes, which the
harness applies only after proving them correct.

## Stages
1. **Ingest & normalize** - parse QASM/Qiskit; record T-count, T-depth, CNOT count.
   *Refinement (2026-10-06):* do NOT discretize everything up front. Decompose high-level gates
   (Toffoli -> 7 T exactly) to CNOT + single-qubit rotations, **merge rotations while angles are
   still symbolic**, classify angles (multiples of pi/4 -> exact Clifford+T), and only then send the
   remaining arbitrary angles to a synthesizer (gridsynth, ~3 log2(1/eps) T per rotation). Once a
   rotation is turned into ~100 T gates, merging it is nearly impossible.
2. **Classical baseline** - `pyzx.full_reduce` + extract. Bar to beat AND fallback answer
   (output is never worse than baseline). Equivalence-check the baseline too
   (`basic_optimization` returns a non-equivalent circuit on XPhase input).
3. **Analyze & partition** - split into blocks, rank T-count hotspots.
4. **Agent search loop** (until budget or plateau):
   Context builder (hotspot, T-count, best rules, recent failures + error messages)
   -> LLM proposes a rule/pass as a code diff (not a circuit)
   -> Apply in sandbox (enforce edit region; time + memory limits)
   -> Verify exactly (small-unitary equality over Z[1/sqrt2, i])
   -> Score (fail -> 0, else T-count reduction; lexicographic, never a blend)
   -> Archive & select (MAP-Elites, lineage, dedup) -> back to context.
   Verified rules persist in a **rule library** across circuits (learned memory).
5. **Reassemble & global check** - apply best rules to full circuit; equivalence via unitary
   (small n) or ZX (reduce C . C'^dagger to identity) + randomized simulation tests; keep the
   better of {agent, baseline}.

**Output:** optimized QASM + certificate + report (T-count: input / baseline / agent).

## Responsibility split
| | LLM | Harness |
|---|---|---|
| Propose new rewrite ideas | yes | |
| Decide what context the model sees | | yes |
| Execute code | | yes (sandboxed) |
| Decide correct? | | yes (exact verifier) |
| Decide better? | | yes (scorer, baseline) |
| Remember what worked | | yes (archive, rule library) |
| Produce final circuit | | yes |

## Open design choices
- What the LLM edits: rules/passes (verifiable once, reusable) vs per-block replacement circuits
  (k=3 blocks measured zero headroom on 29/29 blocks - use larger windows or program level).
- Per-circuit vs cross-circuit learning (the persistent rule library).
- Go/no-go gate (milestone M3): classical search must beat greedy/pyzx before adding the LLM.

## Prior art to position against (found 2026-10-06; verify before citing)
- VarTODD + GigaEvo (Fisher et al. 2026, arXiv 2603.29894): LLM-guided evolution of the *search
  policy* of an algebraic T-count optimizer, with the rewrite system held fixed.
- QSA (arXiv 2609.38883): quantum-aware harness for LLM-guided evolution on top of OpenEvolve
  (compiler/runtime optimization; uses depth/CNOT proxies).
- QuantumEvo (arXiv 2609.05327): LLM-evolved BDD variable-ordering heuristics for synthesis.
- AlphaTensor-Quantum (Ruiz et al.): RL + tensor decomposition for T-count; strong arithmetic results.
- Quartz / Queso (Xu et al.): automatic generation + verification of rewrite rules by enumeration.
- OmniQEC (arXiv 2607.25865): LLM "AI scientist" for qLDPC code discovery, fast loop on code-level
  proxies + slow loop on circuit-level logical error rates.
