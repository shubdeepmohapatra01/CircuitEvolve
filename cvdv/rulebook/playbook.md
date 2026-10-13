# CV-DV rulebook playbook (insights for the mutator; append-only, curated)

1. Conventions: R(θ)=e^{-iθn}, CR(θ)=e^{-iθ/2 σz n}, CP=CR(π), D(α)=e^{αa†-α*a}, CD(α)=e^{σz(αa†-α*a)},
   BS(θ,φ)=e^{-iθ/2(e^{iφ}a†b+h.c.)}. Rules are executed in time order (first call acts first).
2. Conjugation by W = exp(-iπ/2 σx n) = H·CP·H maps σz -> (-1)^n σz exactly; it lets diagonal ancilla phases
   become parity-weighted functions of n (basis of rule_n2__parity_exact).
3. Group commutators e^{A}e^{B}e^{-A}e^{-B} of σ·n generators give σz n² only to first order; certified
   error falls as r^{-1/2} with r repetitions, which is far too slow at n_max >= 7.
4. The certificate is worst-case over all states with total photon number <= n_max, ancilla must return to |0>.
   Exploit exactness on a bounded subspace; do not rely on small-n behaviour only.
5. [RETRACTED by curator 2026-10-13: the seed group commutator is algebraically correct (verified, error ∝ r^{-1/2} at small θ·n²); the plateau at n_max >= 5 is the x·n_max effect described in 6.]
6. For n² group-commutator schemes, the failure isn't slow convergence but an O(1) BCH expansion parameter x·n_max (x=sqrt(|θ|/2r)): since all higher-order terms scale as (x·n_max)^k, reaching small eps requires r ~ n_max², making the ~20-latency-per-rep cost explode — symmetrization/sign-fixes that only kill the x³ term don't help because x·n_max itself isn't small at realistic n_max, r budgets.  [auto, 2026-10-13]
