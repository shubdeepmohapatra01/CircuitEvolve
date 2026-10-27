# CV-DV playbook (seeded from Liu et al., "Hybrid Oscillator-Qubit Quantum Processors: Instruction Set
# Architectures, Abstract Machine Models, and Applications", arXiv:2407.10381, before any LLM training)

## ISA (Genesis Table 2 = Liu et al. phase-space ISA + beam splitters + CBS/RB)
Qubit rotations (h x y z s sdg t tdg rx ry rz r); oscillator R(t)=e^{-itn}, D(a)=e^{a a^+ - a* a},
BS(t,p)=e^{-it/2(e^{ip}a^+b + h.c.)}; hybrid CR(t)=e^{-it/2 Z n}, CP=CR(pi), CD(a)=e^{Z(a a^+ - a* a)},
CBS(t,p)=e^{-it/2 Z(e^{ip}a^+b + h.c.)}, RB(t)=e^{-iX(t a^+ + t* a)}. No qubit-qubit gates: qubits interact only
through oscillators. Hardware: qubit i couples only to qumode i; qumodes on a square grid; Genesis' router inserts
qumode SWAPs (BS(pi,0) + 2 R) for every 2-op gate between non-coupled wires.

## Seed identities (all in the seed book)
1. Native generators: n -> R, a^+b+h.c. -> BS, Z n -> CR, Z(a^+b+h.c.) -> CBS, linear -> D, Z linear -> CD,
   X linear -> RB, single-qubit Pauli -> rotation.
2. Conjugation by CP: CP rotates a mode by pi conditioned on the qubit, a -> -i Z a (in a frame); conjugating D or
   BS by CP makes them qubit-conditional (seed: Z-hopping via CP.BS.CP^+, Pauli-string displacement via CP-conjugated D).
3. Displacement commutator (Heisenberg-Weyl): D(a)D(b) = e^{(a b* - a* b)/2} D(a+b). A P-conditioned displacement and a
   plain displacement enclose a closed phase-space loop: CD_P(b) D(ig) CD_P(-b) D(-ig) = exp(-2i b g P) exactly
   (commutator is a c-number times P). Seed: multi-qubit Pauli exponentials through a vacuum bus qumode.
4. Group commutator (BCH, first order): e^{A}e^{B}e^{-A}e^{-B} = e^{[A,B] + O(3)}. Seed: n^2 from [X n, Y n] = 2i Z n^2
   on an ancilla qubit, repeated r times; error falls only slowly with r.

## Verifier and cost (frozen; the LLM cannot change them)
- Every emitted gate list is checked against exp(-i H_part) on the subspace {term qubits arbitrary, term modes with
  total photons <= 3, all ancillas |0>/vacuum}; phase-aligned operator distance at photon cutoffs K = 12 and 16; an
  ancilla must return to |0>/vacuum. Exact contract: distance <= 1e-6. Approximate: charged to the eps = 1e-3 ledger
  (eps/2 for synthesis), shared among approximate parts.
- Final circuit: routed by Genesis' router, then a whole-circuit check against the ordered product of the IR terms.
- Cost (lexicographic): valid, duration (critical path, 1 per 1-op gate, 20 per 2-op gate, on the routed circuit),
  2-op count, 1-op count.
