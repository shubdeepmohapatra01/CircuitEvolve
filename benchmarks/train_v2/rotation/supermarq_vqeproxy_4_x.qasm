// Generated from Cirq v1.7.0

OPENQASM 2.0;
include "qelib1.inc";


// Qubits: [q(0), q(1), q(2), q(3)]
qreg q[4];
creg m0[4];  // Measurement: q(0),q(1),q(2),q(3)


ry(pi*0.9672134449) q[0];
ry(pi*2.0556918527) q[1];
ry(pi*3.8611755219) q[2];
ry(pi*1.3817732398) q[3];
rz(pi*1.8548417004) q[0];
rz(pi*4.0867330523) q[1];
rz(pi*0.0675451409) q[2];
rz(pi*3.9934160285) q[3];
cx q[0],q[1];
cx q[1],q[2];
ry(pi*1.8262128438) q[0];
cx q[2],q[3];
ry(pi*0.1628340897) q[1];
rz(pi*0.0049169222) q[0];
ry(pi*1.9388314737) q[2];
ry(pi*1.20634031) q[3];
rz(pi*1.0116758171) q[1];
h q[0];
rz(pi*2.0460094928) q[2];
rz(pi*4.0108286696) q[3];
h q[1];
h q[2];
h q[3];

// Gate: cirq.MeasurementGate(4, cirq.MeasurementKey(name='q(0),q(1),q(2),q(3)'), ())
measure q[0] -> m0[0];
measure q[1] -> m0[1];
measure q[2] -> m0[2];
measure q[3] -> m0[3];
