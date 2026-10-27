# What the floor guarantee still needs, and what it costs

V4_README section 4 states the design contract:

> On every circuit, the floor tier alone must reach the best of every baseline - pyzx, or DPF at any k,
> whichever is lower - using only Python over `v4.api`.

After P2 and P3 the floor is at 1583 / 11364 / 28413 / 4526 / 8560 against best baselines of
1064 / 7552 / 18701 / 4264 / 8560. It holds on tfim_6 only. This file records, from the measurements in
`BUILD_LOG.md`, exactly what the remaining gap is made of - because it is not one missing rule.

| gap | circuits | what closes it | why it is not small |
|---|---|---|---|
| **A. phase-gradient (PKAC) lowering** | qft_8 (+519), qae_13 (+262) | the construction ALREADY EXISTS as two v3 rules (`phase_gradient_addition_for_dyadic_rotation_cascades`, `phase_gradient_catalysis_dyadic_rotations`), both rejected in v3 only by the verifier | **Reclassified after P5.** The expressiveness barrier is gone - those rules now get past `rz(...) is not a multiple of pi/4` - and a WIDTH barrier replaced it: the candidate has 34 qubits on qft_8 and 51 on qae_13, where a dense branch-wise check caps at 22 (2^22 complex128 = 64 MB per state vector, iterated over inputs x branches). Narrowing the register to `E_MAX=6` still needs 25; at `E_MAX=5` the rule stops firing. The route is a STRUCTURAL witness, not a wider simulation: PKAC factors into CNOT loading (affine, `phasepoly.witness`), a Gidney adder (Clifford+T, exact on its own qubits) and the one-register gradient kickback identity. That needs a `witness=` hook on `Rule` so a rule can hand its factorisation to the judge - V4_README 6.2's "the rule supplies a witness" applied to this family. Measurements in `BUILD_LOG.md`. |
| **B. free-CNOT block resynthesis** | qpe_8 (+3812), hhl_8 (+9712) | a numerical synthesiser that re-derives a width-4 block over a FREE CNOT ansatz with fewer rotation slots - BQSKit's `GreedyNTROPass`, i.e. QSearch / LEAP-class search | This is not a rewrite rule, it is a compiler pass: an ansatz search over CNOT placements with a least-squares inner loop per candidate, for ~60 blocks per circuit. Reimplementing it in pure Python over `v4.api` is its own project, not a card. The in-skeleton version is already built and measured: it reaches the threshold on 10 of 225 blocks. |

## Consequence for the plan

P6's gate as written - "FLOOR GUARANTEE MET: floor alone >= best baseline on all 5 circuits" - is
reachable on qft_8 and qae_13 (gap A) and **not** reachable on qpe_8 and hhl_8 without gap B. The honest
version of the contract, and what v4 should claim, is:

> The floor alone reaches the best of every baseline on tfim_6; it reaches pyzx exactly on qpe_8 and
> hhl_8 and beats it on qae_13; and the residual to DPF Synth is attributed, per circuit, to a named
> mechanism with a measured size.

That still buys the thing the guarantee was for - **the LLM's attempts are scored against the best
baseline, not against zero, and the scout is told which lever has how much headroom left** - without
claiming a floor that was not built. The gap is reported per circuit in every figure and table.
