# What a rule program can use (`v4.api`)

A rule is one Python file exporting

    RULE = Rule(name, domain="dv", kind, source, idea, trigger, apply,
                error_class="exact"|"approx", resource_class="unitary"|"ancilla"|"measured",
                precondition=Precondition(...))

`trigger(circuit) -> list of matches`; `apply(circuit, match) -> new circuit`. Pure and deterministic.
The runner applies matches one at a time, **prices the candidate first** and drops it without
verification if the cost does not fall, then verifies every application it keeps with the frozen judge
(exact D[omega] on the changed window when both sides are Clifford+T; phase-aligned operator distance
otherwise; a branch-wise specification check for ancilla / measurement constructions), plus one
whole-circuit check per rule pass against the ORIGINAL circuit. Cost order is lexicographic:
(T-count, qubits, CNOT).

Imports allowed: stdlib, numpy, scipy, sympy, `v4.api`. Never pyzx, pytket, bqskit, qiskit,
circuitevolve or v3.

## `v4.api` - the contract

`Rule`, `Precondition(families, needs, forbids, min_qubits, max_qubits, note)`, `describe(circuit)`.
`needs` / `forbids` take: `rotations`, `nonclifford_rz`, `toffoli`, `hadamard`, `two_qubit`,
`measurement_free`, `ancilla_room`.

## `v4.api.dv` - circuits

`Circuit(n, ops)` for Clifford+Rz; ops are `(name, qubits, angle)` over `h s sdg x z t tdg cx cz rz`.
`rotation(op)` -> the Z-angle of t/tdg/rz else None. `on_grid(theta)` -> is it a multiple of pi/4 (so
gridsynth pays nothing). `reduce_angle`, `is_clifford`, `is_rotation`, `is_diagonal`, `commutes(a, b)`,
`touched(ops)`, `segments(ops, cut=("h",))` -> Hadamard-free index ranges. `with_ops(c, ops)` builds the
result (rz at pi/4 multiples become Clifford/T gates).
`IRCircuit` / `IRGate` for Toffoli-level circuits (`x z h s sdg t tdg cx cz ccx ccz`, `measure`,
classically controlled gates, and the gadgets `and_compute` (4 T) / `and_uncompute` (0 T)).

**READ THE GATE LIST THE RIGHT WAY - the two circuit types are different objects.** NEITHER is
iterable, so `for op in c` raises `TypeError: 'Circuit' object is not iterable`. Two independent
implementer attempts lost their whole try to exactly that, so this is spelled out:

| family | type you are handed | gate list | width | build the result |
|---|---|---|---|---|
| `dv_angle` | `Circuit` | `c.ops` - tuples `(name, qubits, angle)` | `c.n` | `with_ops(c, new_ops)` |
| `dv_recon` | `IRCircuit` | `c.gates` - `IRGate` objects, use `g.name` | `c.n_qubits` | `ir_with_gates(c, new_gates)` |

So a reconstruction rule starts `gates = list(c.gates)` and an angle rule starts `ops = list(c.ops)`.
Reading `c.ops` off an `IRCircuit` raises `AttributeError`, and so does `c.n`; the IR spells them
`c.gates` and `c.n_qubits`. Check your rule's `Precondition(families=...)` to know which one you get.
`ir_with_gates(c, gates, n_qubits=...)`, `append_ancillas(c, k)` -> extra qubits appended as n, n+1, ...
(they must start and end in |0>). `count_t(c)` for an exact circuit.

## `v4.api.pauli` - Pauli frames

A Pauli is `(x, z, sign)` with int bitmasks. `z_on(q)`, `x_on(q)`, `y_on(q)`,
`conjugate(P, gate, qubits)` (P -> C P C^dag), `commutes(P, Q)` (general), `commutes_with_z(P, q)`,
`is_z(P, q)`, `key(P)`, `axis_eq(P, Q)`, `weight(P)`, `pauli_string(P, n)`.
**`frames(ops)`** -> `[Record(pos, theta, x, z, sign, on_grid)]`: every rotation of the circuit as the
signed multi-qubit Pauli exponential it is in the front frame, in ONE forward sweep over a Clifford
tableau. Two records with the same axis merge if their Paulis commute with everything between them. Use
this instead of conjugating each rotation back through the prefix yourself: on hhl_8 it is 2.4 ms against
174 ms. `residual_clifford(ops)` is the Clifford that follows the exponential product.

## `v4.api.phasepoly` - phase polynomials

`labels(ops)` -> per-wire affine parity label `(mask, const)` after a Hadamard-free op list, by
`cx a,b: p[b] ^= p[a]` and `x a: c[a] ^= 1`. `rotation_labels(ops)` -> `[(pos, theta, label)]`.
`equal_label_pairs(ops)` -> rotations that provably merge. `polynomial(ops)` -> the phase polynomial plus
the label map. `witness(old, new, n)` -> `(ok, reason)`: a PROOF of equivalence in O(ops) with no
matrices, for the Hadamard-free class.

## `v4.api.blocks` - partitioning

`partition(circuit, width=4, max_gates=40)` -> `[Block]`, dependency-contiguous, so splicing a block's
replacement back in is always a valid rewrite. `Block.local_ops / .qubits / .k / .to_global(ops) /
.rotations()`. `splice(ops, block, new_local)`, `blocks_with_rotations(c, minimum=2)`.

## `v4.api.sim` - small unitaries

`unitary(ops, n)` (n <= 14), `hs_distance(U, V)` -> `{'op', 'fro'}` phase-aligned,
`distance(a_ops, b_ops, n)`, `phase_align(U, V)`, `hs_cost(U, V)`. `op` is the quantity the judge charges
to the ledger, so a rewrite you keep below the error you drew will be accepted.

## `v4.api.refit` - least squares and algebra

`least_squares(template, target, x0, n=, pinned=)` -> `Fit(angles, distance, success, nfev)`, minimising
the phase-aligned operator distance. `pin_to_grid(template, target, x0, n, budget)` greedily pins angles
to the pi/4 grid while the distance stays inside `budget` - each pinned angle is one rotation gridsynth
no longer pays for. `euler_template(k, pattern)` builds a template from a gate pattern with `rz` slots.
`closure(generators)` -> the Lie algebra generated by Hermitian matrices (its DIMENSION bounds how many
rotations a run really needs). `rank(matrices)`.

## `v4.api.angles` - the dyadic grid

`dyadic(theta, m)` -> `Dyadic(k, m, angle, distance, delta)`, the nearest k*pi/2^m. `nearest(theta, kmax)`
finds the coarsest level that point lies on (coarser = cheaper to lower). `rz_distance(dtheta)` =
|sin(dtheta/2)|, exactly what the judge measures on a one-rotation window. `fixable(angles, kmax, budget)`,
`greedy_fix(angles, kmax, budget)` = DPF's own schedule.

## `v4.api.fermion` - free fermions

`majorana_pauli(j, n)`, `bilinear_of(P, n)` -> `(a, b)` if P is i g_a g_b, `is_gaussian(ops)`,
`orthogonal_of(ops)` -> the single R in O(2n) a Gaussian circuit acts as, `givens(R)` -> adjacent-plane
rotations plus the residual sign diagonal, `emit(rotations, n)` -> back to an op list,
`majorana_rank(ops)`, `plane_rotation(a, b, theta, m)`.

## `v4.api.budget` - the error ledger

`remaining()`, `total()`, `spent()`, `draw(amount) -> bool`, `refund(amount)`, `with trial(amount) as ok`.
Total eps = 1e-3; rule rewrites share eps/2 = 5e-4 and final synthesis gets eps/2. If `draw` refuses,
do the exact rewrite or nothing - never snap an angle you did not pay for.
