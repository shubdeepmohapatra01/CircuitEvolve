// Generated from Cirq v1.7.0

OPENQASM 2.0;
include "qelib1.inc";


// Qubits: [q(0), q(1), q(2), q(3), q(4), q(5)]
qreg q[6];
creg m0[6];  // Measurement: q(0),q(1),q(2),q(3),q(4),q(5)


h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
h q[5];
cx q[0],q[1];
cx q[2],q[3];
cx q[4],q[5];
rz(pi*3.8524135654) q[1];
rz(pi*-3.8524135654) q[3];
rz(pi*-3.8524135654) q[5];
cx q[1],q[0];
cx q[3],q[2];
cx q[5],q[4];
cx q[0],q[1];
cx q[2],q[3];
cx q[4],q[5];
cx q[1],q[2];
cx q[3],q[4];
rz(pi*3.8524135654) q[2];
rz(pi*3.8524135654) q[4];
cx q[2],q[1];
cx q[4],q[3];
cx q[1],q[2];
cx q[3],q[4];
cx q[0],q[1];
cx q[2],q[3];
cx q[4],q[5];
rz(pi*3.8524135654) q[1];
rz(pi*-3.8524135654) q[3];
rz(pi*3.8524135654) q[5];
cx q[1],q[0];
cx q[3],q[2];
cx q[5],q[4];
cx q[0],q[1];
cx q[2],q[3];
cx q[4],q[5];
cx q[1],q[2];
cx q[3],q[4];
rz(pi*-3.8524135654) q[2];
rz(pi*3.8524135654) q[4];
cx q[2],q[1];
cx q[4],q[3];
cx q[1],q[2];
cx q[3],q[4];
cx q[0],q[1];
cx q[2],q[3];
cx q[4],q[5];
rz(pi*3.8524135654) q[1];
rz(pi*3.8524135654) q[3];
rz(pi*3.8524135654) q[5];
cx q[1],q[0];
cx q[3],q[2];
cx q[5],q[4];
cx q[0],q[1];
cx q[2],q[3];
cx q[4],q[5];
cx q[1],q[2];
cx q[3],q[4];
rx(pi*1.2499816289) q[0];
rx(pi*1.2499816289) q[5];
rz(pi*3.8524135654) q[2];
rz(pi*-3.8524135654) q[4];
cx q[2],q[1];
cx q[4],q[3];
cx q[1],q[2];
cx q[3],q[4];
rx(pi*1.2499816289) q[1];
rx(pi*1.2499816289) q[2];
rx(pi*1.2499816289) q[3];
rx(pi*1.2499816289) q[4];

// Gate: cirq.MeasurementGate(6, cirq.MeasurementKey(name='q(0),q(1),q(2),q(3),q(4),q(5)'), ())
measure q[0] -> m0[0];
measure q[1] -> m0[1];
measure q[2] -> m0[2];
measure q[3] -> m0[3];
measure q[4] -> m0[4];
measure q[5] -> m0[5];
