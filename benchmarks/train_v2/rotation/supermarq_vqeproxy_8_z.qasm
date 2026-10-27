// Generated from Cirq v1.7.0

OPENQASM 2.0;
include "qelib1.inc";


// Qubits: [q(0), q(1), q(2), q(3), q(4), q(5), q(6), q(7)]
qreg q[8];
creg m0[8];  // Measurement: q(0),q(1),q(2),q(3),q(4),q(5),q(6),q(7)


ry(pi*0.2304778506) q[0];
ry(pi*3.4458709407) q[1];
ry(pi*3.542425389) q[2];
ry(pi*1.5426428157) q[3];
ry(pi*3.5426603442) q[4];
ry(pi*2.4574308361) q[5];
ry(pi*2.4582883539) q[6];
ry(pi*3.5394370432) q[7];
rz(pi*4.3073659314) q[0];
rz(pi*2.0290860122) q[1];
rz(pi*0.0038530578) q[2];
rz(pi*2.9998764687) q[3];
rz(pi*8.05947e-05) q[4];
rz(pi*3.9997247309) q[5];
rz(pi*3.9998431977) q[6];
rz(pi*3.9999953039) q[7];
cx q[0],q[1];
cx q[1],q[2];
ry(pi*2.1197041297) q[0];
cx q[2],q[3];
ry(pi*1.2674014483) q[1];
rz(pi*2.5407500434) q[0];
cx q[3],q[4];
ry(pi*0.7010407916) q[2];
rz(pi*3.037901978) q[1];
cx q[4],q[5];
ry(pi*2.6969148164) q[3];
rz(pi*1.9990237855) q[2];
cx q[5],q[6];
ry(pi*2.6960431557) q[4];
rz(pi*4.0003149888) q[3];
cx q[6],q[7];
ry(pi*3.3049345014) q[5];
rz(pi*3.9998131025) q[4];
ry(pi*2.6920335272) q[6];
ry(pi*2.6826520674) q[7];
rz(pi*3.0002194525) q[5];
rz(pi*3.9995506743) q[6];
rz(pi*-0.0006534013) q[7];

// Gate: cirq.MeasurementGate(8, cirq.MeasurementKey(name='q(0),q(1),q(2),q(3),q(4),q(5),q(6),q(7)'), ())
measure q[0] -> m0[0];
measure q[1] -> m0[1];
measure q[2] -> m0[2];
measure q[3] -> m0[3];
measure q[4] -> m0[4];
measure q[5] -> m0[5];
measure q[6] -> m0[6];
measure q[7] -> m0[7];
