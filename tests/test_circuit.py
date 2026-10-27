"""circuit.py parsing."""
from circuitevolve.circuit import Circuit, Gate, from_qasm, to_qasm


def test_two_qregs_are_concatenated():
    c = from_qasm('OPENQASM 2.0; include "qelib1.inc"; qreg eval[2]; qreg q[1]; cx eval[1],q[0]; h q[0];')
    assert c.n == 3 and c.gates == [Gate("cx", (1, 2)), Gate("h", (2,))]


def test_roundtrip_with_measurement_and_condition():
    c = Circuit(2, [Gate("h", (1,)), Gate("measure", (1,), cbit=0), Gate("cz", (0, 1), cond=0),
                    Gate("rz", (0,), theta=0.123)], nc=1)
    assert from_qasm(to_qasm(c)).gates == c.gates
