"""v2 verifier: accepts the reference adders, rejects planted bugs in every mode."""
import math

import pytest

from circuitevolve import spec as frozen_spec
from circuitevolve import verify as frozen_verify
from circuitevolve.baselines import cuccaro, gidney
from circuitevolve.core.circuit import Circuit as CoreCircuit
from circuitevolve.ir import TIER_A, TIER_B, Circuit, Gate
from circuitevolve.v2.verify import (Limits, ReferenceSpec, Verdict, adder_reference, parse_qasm_ir, verify)

NS = (1, 2, 3, 4)


def _first(c, pred):
    return next(i for i, g in enumerate(c.gates) if pred(g))


# ---------------------------------------------------------------------------------------- accepted
@pytest.mark.parametrize("n", NS)
def test_cuccaro_exact_vs_reference_adder(n):
    # Clifford+T expansion (7 T per Toffoli) vs the full carry-in adder permutation on all 2^(2n+2) inputs
    v = verify(cuccaro.construct(n).expand("clifford_t"), adder_reference(n, carry_in=True), "exact")
    assert v.ok and v.mode == "exact" and v.certified and v.unitary_preserving, v.reason
    assert v.method == "basis-exhaustive" and v.n_inputs == 1 << (2 * n + 2) and v.distance == 0.0
    # Toffoli-level form against the same reference, and Clifford+T against the Toffoli-level circuit
    assert verify(cuccaro.construct(n), adder_reference(n, carry_in=True), "exact").ok
    assert verify(cuccaro.construct(n).expand("clifford_t"), ReferenceSpec.from_circuit(cuccaro.construct(n)),
                  "exact").ok


@pytest.mark.parametrize("n", NS)
def test_gidney_relaxed_vs_reference_adder(n):
    for cand in (gidney.construct(n), gidney.construct_tier_b(n)):
        v = verify(cand, adder_reference(n), "relaxed")
        assert v.ok and v.mode == "relaxed" and not v.unitary_preserving and v.certified, v.reason
        assert v.n_branches == 1 << (n - 1) and len(v.details["ancillas"]) == n - 1
    # the same contract as the frozen adder verifier
    assert frozen_verify.verify(gidney.construct, frozen_spec.AdderSpec(), [n], TIER_A).ok


@pytest.mark.parametrize("n", (1, 2, 3))
def test_cuccaro_relaxed_with_carry_in_ancilla(n):
    # against the z = |0> adder spec, Cuccaro's c0 is a clean ancilla
    v = verify(cuccaro.construct(n), adder_reference(n), "relaxed")
    assert v.ok and v.details["ancillas"] == [0]


def test_gidney_needs_relaxed_mode():
    v = verify(gidney.construct(3), adder_reference(3), "exact")
    assert not v.ok and v.mode == "exact" and "relaxed" in v.reason


def test_auto_mode_labels():
    assert verify(gidney.construct(2), adder_reference(2), "auto").mode == "relaxed"
    v = verify(cuccaro.construct(2), adder_reference(2, carry_in=True), "auto")
    assert v.ok and v.mode == "exact" and v.requested == "auto"


def test_global_phase_is_ignored():
    c = cuccaro.construct(2).expand("clifford_t")
    c.add("x", 0).add("z", 0).add("x", 0).add("z", 0)          # = -I
    v = verify(c, adder_reference(2, carry_in=True), "exact")
    assert v.ok and abs(v.details["global_phase"] + 1) < 1e-12


# ---------------------------------------------------------------------------------------- planted bugs
def test_bug_wrong_phase_t_vs_tdg():
    c = cuccaro.construct(2).expand("clifford_t")
    i = _first(c, lambda g: g.name == "t")
    c.gates[i] = Gate("tdg", c.gates[i].qubits)
    assert not verify(c, adder_reference(2, carry_in=True), "exact").ok


def test_bug_relative_phase_on_data_qubit():
    c = cuccaro.construct(2).expand("clifford_t")
    c.add("s", c.registers["a"][0])
    v = verify(c, adder_reference(2, carry_in=True), "exact")
    assert not v.ok and "relative phase" in v.reason


def test_bug_wrong_permutation():
    c = cuccaro.construct(3)
    j = _first(c, lambda g: g.name == "cx")
    a, b = c.gates[j].qubits
    c.gates[j] = Gate("cx", (b, a))
    v = verify(c, adder_reference(3, carry_in=True), "exact")
    assert not v.ok and "wrong output" in v.reason


def test_bug_dirty_ancilla():
    g = gidney.construct(3)
    del g.gates[_first(g, lambda x: x.name == "and_uncompute")]
    v = verify(g, adder_reference(3), "relaxed")
    assert not v.ok and "ancilla" in v.reason


def test_bug_dirty_ancilla_exact_extra_qubit():
    c = cuccaro.construct(2)
    c2 = Circuit(c.n_qubits + 1, gates=list(c.gates) + [Gate("cx", (c.registers["a"][0], c.n_qubits))],
                 registers=c.registers)
    v = verify(c2, adder_reference(2, carry_in=True), "relaxed")   # extra ancilla left holding a_0
    assert not v.ok and "ancilla" in v.reason


def test_bug_measurement_fixup_missing():
    g = gidney.construct_tier_b(3)
    del g.gates[_first(g, lambda x: x.name == "cz" and x.cond is not None)]
    v = verify(g, adder_reference(3), "relaxed")
    assert not v.ok and "phase" in v.reason
    assert not frozen_verify.verify(lambda n: g, frozen_spec.AdderSpec(), [3], TIER_B).ok


def test_bug_measurement_reset_missing():
    g = gidney.construct_tier_b(3)
    del g.gates[_first(g, lambda x: x.name == "x" and x.cond is not None)]
    v = verify(g, adder_reference(3), "relaxed")
    assert not v.ok and "ancilla" in v.reason


def test_bug_gadget_precondition():
    # and_compute onto a target that is not |0> (b_0 holds data)
    c = Circuit(3, registers={"a": [0], "b": [1], "z": [2]})
    c.add("and_compute", 0, 2, 1)
    assert not verify(c, adder_reference(1), "relaxed").ok


# ---------------------------------------------------------------------------------------- large / sampled
def test_large_permutation_sampled():
    n = 9                                                       # 20 qubits
    c = cuccaro.construct(n).expand("clifford_t")
    ref = adder_reference(n, carry_in=True)
    v = verify(c, ref, "exact")
    assert v.ok and v.method == "basis-sampled" and not v.certified and v.n_inputs == Limits().sampled_inputs
    bad = c.copy()
    bad.add("s", c.registers["b"][5])
    assert not verify(bad, ref, "exact").ok
    bad = cuccaro.construct(n)
    j = _first(bad, lambda g: g.name == "cx")
    a, b = bad.gates[j].qubits
    bad.gates[j] = Gate("cx", (b, a))
    assert not verify(bad, ref, "exact").ok


def test_relaxed_sampled_branches_flag():
    v = verify(gidney.construct(4), adder_reference(4), "relaxed", limits=Limits(branch_budget=100))
    assert v.ok and "sampled-branches" in v.method and not v.certified


# ---------------------------------------------------------------------------------------- approx
def _ops():
    return [("h", (0,), None), ("cx", (0, 1), None), ("rz", (1,), 0.3), ("cx", (0, 1), None),
            ("rz", (0,), math.pi / 4), ("h", (2,), None), ("cx", (1, 2), None), ("rz", (2,), 1.1)]


def test_approx_within_and_outside_eps():
    ref = CoreCircuit(3, _ops())
    cand = CoreCircuit(3, [o if o[2] != 0.3 else ("rz", (1,), 0.3 + 2e-6) for o in _ops()])
    v = verify(cand, ref, "approx", eps=1e-5)
    assert v.ok and v.mode == "approx" and v.certified and v.method == "unitary" and 0 < v.distance < 1e-5
    w = verify(cand, ref, "approx", eps=1e-8)
    assert not w.ok and w.distance == v.distance
    assert verify(ref, ref, "approx", eps=1e-12).ok


def test_approx_routes_clifford_t_to_exact():
    c = CoreCircuit(2, [("h", (0,), None), ("cx", (0, 1), None), ("t", (1,), None)])
    d = CoreCircuit(2, [("h", (0,), None), ("cx", (0, 1), None), ("tdg", (1,), None)])
    v = verify(c, c, "approx", eps=1e-3)
    assert v.ok and v.mode == "exact" and v.requested == "approx"
    assert not verify(d, c, "approx", eps=10.0).ok          # floating point never accepts a Clifford+T candidate


def test_approx_against_function_reference():
    ref = adder_reference(1, carry_in=True)                   # 4 qubits, numeric permutation matrix
    cand = CoreCircuit(4, [(g.name, g.qubits, None) for g in cuccaro.construct(1).expand("clifford_t").gates]
                       + [("rz", (0,), 1e-7)])
    v = verify(cand, ref, "approx", eps=1e-6)
    assert v.ok and v.mode == "approx" and v.distance < 1e-6
    assert not verify(cand, ref, "approx", eps=1e-9).ok


# ---------------------------------------------------------------------------------------- io
def test_parse_qasm_ir():
    text = ('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[3];\nccx q[0],q[1],q[2];\nrz(pi*-0.25) q[0];\n'
            'rz(0.5*pi) q[1];\nh q[2];\n')
    c = parse_qasm_ir(text)
    assert [g.name for g in c.gates] == ["ccx", "tdg", "s", "h"]
    assert isinstance(verify(c.expand("clifford_t"), ReferenceSpec.from_circuit(c), "exact"), Verdict)
    assert verify(c.expand("clifford_t"), ReferenceSpec.from_circuit(c), "exact").ok
