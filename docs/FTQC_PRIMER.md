# Circuit optimization for fault-tolerant quantum computing: a working primer

*Project: LLM-assisted circuit optimization. Written 2026-10-06. All numbers in the "measured" boxes were
computed in this session with pyzx and pygridsynth; citations are from memory and should be checked
before they go into a paper.*


## 0. What "cost" means in the FTQC era

On an error-corrected machine the logical gate set is finite: **Clifford gates (H, S, CNOT and their
products) plus T**. Cliffords are implemented cheaply (transversally or by lattice surgery). Each T gate
consumes a distilled magic state, and magic-state factories dominate qubit count and runtime. Hence the
cost hierarchy most papers use:

1. **T-count** (or Toffoli/CCZ count, since CCZ states can be distilled directly; Gidney & Fowler 2019).
2. **T-depth** - sets runtime when factories can feed T gates in parallel.
3. **Qubit count** - logical qubits, including ancillas.
4. **CNOT / Clifford count** - secondary, but not free in every architecture.
5. The true objective is **spacetime volume** (qubits x time) of the full fault-tolerant layout; items 1-4
   are proxies for it.

## 1. Peephole and rewrite-rule optimization (gate level, exact unitary)

**Idea.** Slide a window over the circuit; cancel inverse pairs (T T-dagger, CNOT CNOT), commute gates
past each other to bring cancellable pairs together, replace known patterns (templates) with cheaper
equivalents.

**Representative work.** Template matching (Maslov et al.); Nam, Ross, Su, Childs, Maslov (2018) -
rotation merging and commutation rules, scales to large circuits; VOQC (formally verified version);
**Quartz / Queso** (Xu et al., 2022/2023) - *automatically generate* every small equivalent pair by
enumeration and verify it, producing rule sets with thousands of rules; GUOQ (2025) - combines rewriting
with resynthesis.

**Limit.** Rules are local and preserve the full unitary. Enumeration already covers the small-rule space
exhaustively, which is why "an LLM that writes rules" adds little at this level.

## 2. Phase polynomials and rotation merging (CNOT+T sub-circuits)

**Idea.** A circuit made only of CNOT, X and phase gates acts on a basis state |x> as
`|x> -> e^{i (pi/4) f(x)} |Ax + b>`, where `f(x) = sum_i c_i * (parity_i of x)`. Each T gate contributes
one term c_i = 1 on whichever parity its qubit holds at that moment. **Two T gates on the same parity
merge** (T.T = S, a Clifford), even if they sit on different qubits far apart in the circuit.

> **Measured.** Two T gates, one on qubit 1 and one on qubit 0, each applied when that qubit holds
> x0 XOR x1, reached via different CNOT routes: T-count **2 -> 0** after pyzx (equivalence verified).
> A peephole optimizer sees no adjacent pair to cancel.

**Representative work.** Tpar (Amy, Maslov, Mosca 2014) - T-count and T-depth via matroid partitioning;
Gray-synth (Amy, Azimzadeh, Mosca 2018) - resynthesize the CNOT part. Hadamard gates break the
representation, so circuits are cut into H-free regions (or H is "gadgetized" with ancillas).

## 3. ZX-calculus (graph rewriting, exact unitary)

**Idea.** Translate the circuit into a ZX-diagram (a graph of Z- and X-spiders with phases). Clifford
spiders can be eliminated by local complementation and pivoting; the remaining non-Clifford phases become
**phase gadgets** that fuse when they act on the same parity - phase-polynomial merging generalized
across Hadamards. Then extract a circuit back out (the hard step).

**Representative work.** Kissinger & van de Wetering (2020) - "phase teleportation": reduce T-count
without changing circuit structure; Duncan et al. (2020) - graph-theoretic simplification; **pyzx**
(`full_reduce` + `extract_circuit`).

> **Measured - Cuccaro ripple-carry adder** (n-bit, 2n Toffolis, 2n+2 qubits):
>
> | n | naive T (7 per Toffoli) | pyzx full_reduce T | equivalence checked |
> |---|---|---|---|
> | 1 | 14 | 8 | yes |
> | 2 | 28 | 16 | yes |
> | 4 | 56 | 32 | yes |
> | 8 | 112 | 64 | (too large for tensor check) |
>
> pyzx consistently reaches **8n**, down from 14n. Remember this floor - see section 6.

## 4. T-count as a coding / tensor problem (TODD family, AlphaTensor-Quantum)

**Idea.** For a phase polynomial with pi/4 phases, minimizing the number of T gates is equivalent to
**decoding a punctured Reed-Muller code** (Amy & Mosca), or equivalently to finding a **minimal
symmetric tensor decomposition** of a 3-index "signature tensor" over GF(2). Better decompositions mean
fewer T gates.

**Representative work.** TODD (Heyfron & Campbell 2018); FastTODD; **AlphaTensor-Quantum** (Ruiz et al.,
2024/25) - RL over tensor decompositions, found constructions on GF(2^n) multiplication beating prior
best; **VarTODD + GigaEvo** (2026) - LLM-guided evolution of the *search policy* inside TODD, with the
algebraic moves held fixed.

**Limit.** Still exact-unitary; the transformations are fixed algebra. LLM involvement so far is at the
policy level.

## 5. Rotation synthesis (approximate, within error budget eps)

**Idea.** Angles that are not multiples of pi/4 must be approximated by an H/S/T word. Optimal
single-qubit synthesis (Ross & Selinger, **gridsynth**) needs about **3 log2(1/eps)** T gates.

> **Measured (pygridsynth, Rz(0.3)).** eps = 1e-2 -> 20 T; 1e-4 -> 38 T; 1e-6 -> 66 T; 1e-10 -> 102 T.
> Rz(pi/4) passed in blindly -> 136 T, although it is a single T up to global phase.

**Refinements.** Repeat-until-success circuits and fallback schemes (Bocharov, Roetteler, Svore);
probabilistic mixing of two approximations, which roughly halves the T-count for a given error (Campbell
2017; Hastings 2017); phase-gradient states, which turn many rotations into additions.

**Pipeline rule.** Merge rotations *before* synthesis, classify exact angles first, and split the total
error budget across rotations deliberately.

## 6. Relaxed-specification constructions (beyond exact unitary)

**Idea.** A circuit only needs to be correct **on the inputs that actually occur** and only up to what is
observable. If an ancilla is guaranteed to start in |0> and is discarded afterwards, the circuit may
behave arbitrarily on ancilla = |1>. Measurement plus classical feed-forward can replace unitary
uncomputation.

**Key constructions.**
- **Temporary logical AND** (Gidney 2018): compute t = a AND b into a clean ancilla with **4 T**;
  uncompute by an X-basis measurement and a classically controlled CZ with **0 T**. A Toffoli
  compute + uncompute pair costs 14 T naively.
- **Gidney adder**: about **4n** T, at the cost of roughly n extra clean ancillas.
- **T-depth-1 Toffoli** using 4 ancillas (Selinger 2013): trades qubits for depth.

> **Measured.** Compute t = a AND b, use t once, uncompute: naive 14 T -> pyzx **8 T** (exact,
> verified). Temporary-AND construction: **4 T**. For the adder: naive 14n -> pyzx 8n -> Gidney ~4n.
> No exact-unitary optimizer can cross the 8 -> 4 gap: it must preserve behaviour on t = |1>, an input
> that never occurs, and measurement-based uncomputation is not a unitary.

## 7. Algorithm-level resource optimization

**Idea.** Change *how* the computation is done: table lookup instead of arithmetic (QROM, unary
iteration; Babbush et al. 2018), trading T gates for dirty qubits (select-swap; Low, Kliuchnikov,
Schaeffer 2018), windowed arithmetic (Gidney 2019), qubitization for Hamiltonian simulation. These
changes produce the largest reductions in published resource estimates, and they are done by hand.

## 8. Fault-tolerant layout and scheduling

**Idea.** Rewrite the Clifford+T circuit as a sequence of **Pauli product rotations** (pi/8 rotations for T,
Cliffords commuted to the end and absorbed into measurements; Litinski, "A Game of Surface Codes", 2019).
Then schedule these on a lattice-surgery layout with magic-state factories. The cost becomes
**spacetime volume**: T-count sets the number of magic states, T-depth and routing set the time, factory
count and layout set the qubits.

**Consequence.** Circuits with equal T-count can have different spacetime cost, so T-count-optimal is not
necessarily cost-optimal.

## 9. The pattern to take away

Moving **up** the stack (from Clifford+T toward algorithm level):
- the notion of equivalence **widens** (exact unitary -> approximate -> correct on reachable inputs ->
  same observable channel);
- the space of transformations becomes **too large to enumerate** and **too irregular for algebra**;
- the existing state of the art is **hand-designed** constructions in papers.

Those three properties together are where an LLM proposing *programs*, filtered by an exact verifier of
the right (relaxed) spec, can plausibly do something enumeration and algebra cannot.
