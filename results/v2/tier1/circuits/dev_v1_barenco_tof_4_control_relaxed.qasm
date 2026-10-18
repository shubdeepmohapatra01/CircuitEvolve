OPENQASM 3.0;
include "stdgates.inc";
qubit[10] q;
bit[6] c;
h q[7];
t q[7];
cx q[3], q[7];
cx q[5], q[7];
cx q[7], q[3];
cx q[7], q[5];
tdg q[3];
tdg q[5];
t q[7];
cx q[7], q[3];
cx q[7], q[5];
h q[7];
s q[7];
cx q[7], q[6];
h q[7];
c[0] = measure q[7];
if (c[0]) { cz q[3], q[5]; }
if (c[0]) { x q[7]; }
h q[7];
t q[7];
cx q[2], q[7];
cx q[4], q[7];
cx q[7], q[2];
cx q[7], q[4];
tdg q[2];
tdg q[4];
t q[7];
cx q[7], q[2];
cx q[7], q[4];
h q[7];
s q[7];
cx q[7], q[5];
h q[7];
c[1] = measure q[7];
if (c[1]) { cz q[2], q[4]; }
if (c[1]) { x q[7]; }
h q[7];
t q[7];
cx q[0], q[7];
cx q[1], q[7];
cx q[7], q[0];
cx q[7], q[1];
tdg q[0];
tdg q[1];
t q[7];
cx q[7], q[0];
cx q[7], q[1];
h q[7];
s q[7];
cx q[7], q[4];
h q[8];
t q[8];
cx q[2], q[8];
cx q[4], q[8];
cx q[8], q[2];
cx q[8], q[4];
tdg q[2];
tdg q[4];
t q[8];
cx q[8], q[2];
cx q[8], q[4];
h q[8];
s q[8];
cx q[8], q[5];
h q[9];
t q[9];
cx q[3], q[9];
cx q[5], q[9];
cx q[9], q[3];
cx q[9], q[5];
tdg q[3];
tdg q[5];
t q[9];
cx q[9], q[3];
cx q[9], q[5];
h q[9];
s q[9];
cx q[9], q[6];
h q[9];
c[2] = measure q[9];
if (c[2]) { cz q[3], q[5]; }
if (c[2]) { x q[9]; }
cx q[8], q[5];
h q[8];
c[3] = measure q[8];
if (c[3]) { cz q[2], q[4]; }
if (c[3]) { x q[8]; }
cx q[7], q[4];
h q[7];
c[4] = measure q[7];
if (c[4]) { cz q[0], q[1]; }
if (c[4]) { x q[7]; }
h q[7];
t q[7];
cx q[2], q[7];
cx q[4], q[7];
cx q[7], q[2];
cx q[7], q[4];
tdg q[2];
tdg q[4];
t q[7];
cx q[7], q[2];
cx q[7], q[4];
h q[7];
s q[7];
cx q[7], q[5];
h q[7];
c[5] = measure q[7];
if (c[5]) { cz q[2], q[4]; }
if (c[5]) { x q[7]; }
