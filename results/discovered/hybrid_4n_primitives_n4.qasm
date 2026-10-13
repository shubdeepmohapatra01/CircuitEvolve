OPENQASM 3.0;
include "stdgates.inc";
qubit[14] q;
bit[4] c;
// register a: q[0] q[1] q[2] q[3]
// register b: q[4] q[5] q[6] q[7]
// register z: q[8]
cx q[0], q[4];
cx q[0], q[9];
h q[10];
t q[10];
cx q[4], q[10];
tdg q[10];
cx q[9], q[10];
t q[10];
cx q[4], q[10];
tdg q[10];
cx q[9], q[10];
h q[10];
cx q[10], q[0];
cx q[1], q[5];
cx q[1], q[0];
h q[11];
t q[11];
cx q[5], q[11];
tdg q[11];
cx q[0], q[11];
t q[11];
cx q[5], q[11];
tdg q[11];
cx q[0], q[11];
h q[11];
cx q[11], q[1];
cx q[2], q[6];
cx q[2], q[1];
h q[12];
t q[12];
cx q[6], q[12];
tdg q[12];
cx q[1], q[12];
t q[12];
cx q[6], q[12];
tdg q[12];
cx q[1], q[12];
h q[12];
cx q[12], q[2];
cx q[3], q[7];
cx q[3], q[2];
h q[13];
t q[13];
cx q[7], q[13];
tdg q[13];
cx q[2], q[13];
t q[13];
cx q[7], q[13];
tdg q[13];
cx q[2], q[13];
h q[13];
cx q[13], q[3];
cx q[3], q[8];
cx q[13], q[3];
s q[13];
h q[13];
c[0] = measure q[13];
if (c[0]) { cz q[7], q[2]; }
if (c[0]) { x q[13]; }
cx q[3], q[2];
cx q[2], q[7];
cx q[12], q[2];
s q[12];
h q[12];
c[1] = measure q[12];
if (c[1]) { cz q[6], q[1]; }
if (c[1]) { x q[12]; }
cx q[2], q[1];
cx q[1], q[6];
cx q[11], q[1];
s q[11];
h q[11];
c[2] = measure q[11];
if (c[2]) { cz q[5], q[0]; }
if (c[2]) { x q[11]; }
cx q[1], q[0];
cx q[0], q[5];
cx q[10], q[0];
s q[10];
h q[10];
c[3] = measure q[10];
if (c[3]) { cz q[4], q[9]; }
if (c[3]) { x q[10]; }
cx q[0], q[9];
cx q[9], q[4];
