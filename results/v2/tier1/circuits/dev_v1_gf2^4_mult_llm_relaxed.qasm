OPENQASM 3.0;
include "stdgates.inc";
qubit[13] q;
bit[16] c;
h q[12];
t q[12];
cx q[3], q[12];
cx q[5], q[12];
cx q[12], q[3];
cx q[12], q[5];
tdg q[3];
tdg q[5];
t q[12];
cx q[12], q[3];
cx q[12], q[5];
h q[12];
s q[12];
cx q[12], q[8];
h q[12];
c[0] = measure q[12];
if (c[0]) { cz q[3], q[5]; }
if (c[0]) { x q[12]; }
h q[12];
t q[12];
cx q[2], q[12];
cx q[6], q[12];
cx q[12], q[2];
cx q[12], q[6];
tdg q[2];
tdg q[6];
t q[12];
cx q[12], q[2];
cx q[12], q[6];
h q[12];
s q[12];
cx q[12], q[8];
h q[12];
c[1] = measure q[12];
if (c[1]) { cz q[2], q[6]; }
if (c[1]) { x q[12]; }
h q[12];
t q[12];
cx q[1], q[12];
cx q[7], q[12];
cx q[12], q[1];
cx q[12], q[7];
tdg q[1];
tdg q[7];
t q[12];
cx q[12], q[1];
cx q[12], q[7];
h q[12];
s q[12];
cx q[12], q[8];
h q[12];
c[2] = measure q[12];
if (c[2]) { cz q[1], q[7]; }
if (c[2]) { x q[12]; }
h q[12];
t q[12];
cx q[3], q[12];
cx q[6], q[12];
cx q[12], q[3];
cx q[12], q[6];
tdg q[3];
tdg q[6];
t q[12];
cx q[12], q[3];
cx q[12], q[6];
h q[12];
s q[12];
cx q[12], q[9];
h q[12];
c[3] = measure q[12];
if (c[3]) { cz q[3], q[6]; }
if (c[3]) { x q[12]; }
h q[12];
t q[12];
cx q[2], q[12];
cx q[7], q[12];
cx q[12], q[2];
cx q[12], q[7];
tdg q[2];
tdg q[7];
t q[12];
cx q[12], q[2];
cx q[12], q[7];
h q[12];
s q[12];
cx q[12], q[9];
h q[12];
c[4] = measure q[12];
if (c[4]) { cz q[2], q[7]; }
if (c[4]) { x q[12]; }
h q[12];
t q[12];
cx q[3], q[12];
cx q[7], q[12];
cx q[12], q[3];
cx q[12], q[7];
tdg q[3];
tdg q[7];
t q[12];
cx q[12], q[3];
cx q[12], q[7];
h q[12];
s q[12];
cx q[12], q[10];
h q[12];
c[5] = measure q[12];
if (c[5]) { cz q[3], q[7]; }
if (c[5]) { x q[12]; }
cx q[10], q[11];
cx q[9], q[10];
cx q[8], q[9];
h q[12];
t q[12];
cx q[3], q[12];
cx q[4], q[12];
cx q[12], q[3];
cx q[12], q[4];
tdg q[3];
tdg q[4];
t q[12];
cx q[12], q[3];
cx q[12], q[4];
h q[12];
s q[12];
cx q[12], q[11];
h q[12];
c[6] = measure q[12];
if (c[6]) { cz q[3], q[4]; }
if (c[6]) { x q[12]; }
h q[12];
t q[12];
cx q[2], q[12];
cx q[5], q[12];
cx q[12], q[2];
cx q[12], q[5];
tdg q[2];
tdg q[5];
t q[12];
cx q[12], q[2];
cx q[12], q[5];
h q[12];
s q[12];
cx q[12], q[11];
h q[12];
c[7] = measure q[12];
if (c[7]) { cz q[2], q[5]; }
if (c[7]) { x q[12]; }
h q[12];
t q[12];
cx q[1], q[12];
cx q[6], q[12];
cx q[12], q[1];
cx q[12], q[6];
tdg q[1];
tdg q[6];
t q[12];
cx q[12], q[1];
cx q[12], q[6];
h q[12];
s q[12];
cx q[12], q[11];
h q[12];
c[8] = measure q[12];
if (c[8]) { cz q[1], q[6]; }
if (c[8]) { x q[12]; }
h q[12];
t q[12];
cx q[0], q[12];
cx q[7], q[12];
cx q[12], q[0];
cx q[12], q[7];
tdg q[0];
tdg q[7];
t q[12];
cx q[12], q[0];
cx q[12], q[7];
h q[12];
s q[12];
cx q[12], q[11];
h q[12];
c[9] = measure q[12];
if (c[9]) { cz q[0], q[7]; }
if (c[9]) { x q[12]; }
h q[12];
t q[12];
cx q[2], q[12];
cx q[4], q[12];
cx q[12], q[2];
cx q[12], q[4];
tdg q[2];
tdg q[4];
t q[12];
cx q[12], q[2];
cx q[12], q[4];
h q[12];
s q[12];
cx q[12], q[10];
h q[12];
c[10] = measure q[12];
if (c[10]) { cz q[2], q[4]; }
if (c[10]) { x q[12]; }
h q[12];
t q[12];
cx q[1], q[12];
cx q[5], q[12];
cx q[12], q[1];
cx q[12], q[5];
tdg q[1];
tdg q[5];
t q[12];
cx q[12], q[1];
cx q[12], q[5];
h q[12];
s q[12];
cx q[12], q[10];
h q[12];
c[11] = measure q[12];
if (c[11]) { cz q[1], q[5]; }
if (c[11]) { x q[12]; }
h q[12];
t q[12];
cx q[0], q[12];
cx q[6], q[12];
cx q[12], q[0];
cx q[12], q[6];
tdg q[0];
tdg q[6];
t q[12];
cx q[12], q[0];
cx q[12], q[6];
h q[12];
s q[12];
cx q[12], q[10];
h q[12];
c[12] = measure q[12];
if (c[12]) { cz q[0], q[6]; }
if (c[12]) { x q[12]; }
h q[12];
t q[12];
cx q[1], q[12];
cx q[4], q[12];
cx q[12], q[1];
cx q[12], q[4];
tdg q[1];
tdg q[4];
t q[12];
cx q[12], q[1];
cx q[12], q[4];
h q[12];
s q[12];
cx q[12], q[9];
h q[12];
c[13] = measure q[12];
if (c[13]) { cz q[1], q[4]; }
if (c[13]) { x q[12]; }
h q[12];
t q[12];
cx q[0], q[12];
cx q[5], q[12];
cx q[12], q[0];
cx q[12], q[5];
tdg q[0];
tdg q[5];
t q[12];
cx q[12], q[0];
cx q[12], q[5];
h q[12];
s q[12];
cx q[12], q[9];
h q[12];
c[14] = measure q[12];
if (c[14]) { cz q[0], q[5]; }
if (c[14]) { x q[12]; }
h q[12];
t q[12];
cx q[0], q[12];
cx q[4], q[12];
cx q[12], q[0];
cx q[12], q[4];
tdg q[0];
tdg q[4];
t q[12];
cx q[12], q[0];
cx q[12], q[4];
h q[12];
s q[12];
cx q[12], q[8];
h q[12];
c[15] = measure q[12];
if (c[15]) { cz q[0], q[4]; }
if (c[15]) { x q[12]; }
