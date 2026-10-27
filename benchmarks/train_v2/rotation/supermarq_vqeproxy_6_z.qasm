// Generated from Cirq v1.7.0

OPENQASM 2.0;
include "qelib1.inc";


// Qubits: [q(0), q(1), q(2), q(3), q(4), q(5)]
qreg q[6];
creg m0[6];  // Measurement: q(0),q(1),q(2),q(3),q(4),q(5)


ry(pi*2.0180413533) q[0];
ry(pi*2.9306496736) q[1];
ry(pi*2.4501766711) q[2];
ry(pi*3.4777946075) q[3];
ry(pi*0.5402352948) q[4];
ry(pi*2.4617473501) q[5];
rz(pi*2.6980740837) q[0];
rz(pi*3.7676925002) q[1];
rz(pi*2.8219867903) q[2];
rz(pi*2.9661921742) q[3];
rz(pi*3.001284143) q[4];
rz(pi*1.999743602) q[5];
cx q[0],q[1];
cx q[1],q[2];
ry(pi*2.174998531) q[0];
cx q[2],q[3];
ry(pi*0.7789012547) q[1];
rz(pi*1.9942769306) q[0];
cx q[3],q[4];
ry(pi*2.6375071947) q[2];
rz(pi*3.0722936941) q[1];
cx q[4],q[5];
ry(pi*0.3044327222) q[3];
rz(pi*0.3781982267) q[2];
ry(pi*2.6904970304) q[4];
ry(pi*1.3199815647) q[5];
rz(pi*0.9911744964) q[3];
rz(pi*1.9986986312) q[4];
rz(pi*0.9996010168) q[5];

// Gate: cirq.MeasurementGate(6, cirq.MeasurementKey(name='q(0),q(1),q(2),q(3),q(4),q(5)'), ())
measure q[0] -> m0[0];
measure q[1] -> m0[1];
measure q[2] -> m0[2];
measure q[3] -> m0[3];
measure q[4] -> m0[4];
measure q[5] -> m0[5];
