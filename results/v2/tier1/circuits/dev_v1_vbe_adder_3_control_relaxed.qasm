OPENQASM 3.0;
include "stdgates.inc";
qubit[13] q;
bit[8] c;
h q[10];
t q[10];
cx q[1], q[10];
cx q[2], q[10];
cx q[10], q[1];
cx q[10], q[2];
tdg q[1];
tdg q[2];
t q[10];
cx q[10], q[1];
cx q[10], q[2];
h q[10];
s q[10];
cx q[10], q[3];
h q[10];
c[0] = measure q[10];
if (c[0]) { cz q[1], q[2]; }
if (c[0]) { x q[10]; }
cx q[1], q[2];
h q[10];
t q[10];
cx q[0], q[10];
cx q[2], q[10];
cx q[10], q[0];
cx q[10], q[2];
tdg q[0];
tdg q[2];
t q[10];
cx q[10], q[0];
cx q[10], q[2];
h q[10];
s q[10];
cx q[10], q[3];
h q[11];
t q[11];
cx q[4], q[11];
cx q[5], q[11];
cx q[11], q[4];
cx q[11], q[5];
tdg q[4];
tdg q[5];
t q[11];
cx q[11], q[4];
cx q[11], q[5];
h q[11];
s q[11];
cx q[11], q[6];
h q[11];
c[1] = measure q[11];
if (c[1]) { cz q[4], q[5]; }
if (c[1]) { x q[11]; }
cx q[4], q[5];
h q[11];
t q[11];
cx q[3], q[11];
cx q[5], q[11];
cx q[11], q[3];
cx q[11], q[5];
tdg q[3];
tdg q[5];
t q[11];
cx q[11], q[3];
cx q[11], q[5];
h q[11];
s q[11];
cx q[11], q[6];
h q[12];
t q[12];
cx q[7], q[12];
cx q[8], q[12];
cx q[12], q[7];
cx q[12], q[8];
tdg q[7];
tdg q[8];
t q[12];
cx q[12], q[7];
cx q[12], q[8];
h q[12];
s q[12];
cx q[12], q[9];
h q[12];
c[2] = measure q[12];
if (c[2]) { cz q[7], q[8]; }
if (c[2]) { x q[12]; }
cx q[7], q[8];
h q[12];
t q[12];
cx q[6], q[12];
cx q[8], q[12];
cx q[12], q[6];
cx q[12], q[8];
tdg q[6];
tdg q[8];
t q[12];
cx q[12], q[6];
cx q[12], q[8];
h q[12];
s q[12];
cx q[12], q[9];
h q[12];
c[3] = measure q[12];
if (c[3]) { cz q[6], q[8]; }
if (c[3]) { x q[12]; }
cx q[6], q[8];
cx q[11], q[6];
h q[11];
c[4] = measure q[11];
if (c[4]) { cz q[3], q[5]; }
if (c[4]) { x q[11]; }
cx q[4], q[5];
h q[11];
t q[11];
cx q[4], q[11];
cx q[5], q[11];
cx q[11], q[4];
cx q[11], q[5];
tdg q[4];
tdg q[5];
t q[11];
cx q[11], q[4];
cx q[11], q[5];
h q[11];
s q[11];
cx q[11], q[6];
h q[11];
c[5] = measure q[11];
if (c[5]) { cz q[4], q[5]; }
if (c[5]) { x q[11]; }
cx q[3], q[5];
cx q[4], q[5];
cx q[10], q[3];
h q[10];
c[6] = measure q[10];
if (c[6]) { cz q[0], q[2]; }
if (c[6]) { x q[10]; }
cx q[1], q[2];
h q[10];
t q[10];
cx q[1], q[10];
cx q[2], q[10];
cx q[10], q[1];
cx q[10], q[2];
tdg q[1];
tdg q[2];
t q[10];
cx q[10], q[1];
cx q[10], q[2];
h q[10];
s q[10];
cx q[10], q[3];
h q[10];
c[7] = measure q[10];
if (c[7]) { cz q[1], q[2]; }
if (c[7]) { x q[10]; }
cx q[0], q[2];
cx q[1], q[2];
