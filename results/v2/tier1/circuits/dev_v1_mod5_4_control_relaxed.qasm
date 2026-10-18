OPENQASM 3.0;
include "stdgates.inc";
qubit[6] q;
bit[4] c;
x q[4];
h q[5];
t q[5];
cx q[0], q[5];
cx q[3], q[5];
cx q[5], q[0];
cx q[5], q[3];
tdg q[0];
tdg q[3];
t q[5];
cx q[5], q[0];
cx q[5], q[3];
h q[5];
s q[5];
cx q[5], q[4];
h q[5];
c[0] = measure q[5];
if (c[0]) { cz q[0], q[3]; }
if (c[0]) { x q[5]; }
h q[5];
t q[5];
cx q[2], q[5];
cx q[3], q[5];
cx q[5], q[2];
cx q[5], q[3];
tdg q[2];
tdg q[3];
t q[5];
cx q[5], q[2];
cx q[5], q[3];
h q[5];
s q[5];
cx q[5], q[4];
h q[5];
c[1] = measure q[5];
if (c[1]) { cz q[2], q[3]; }
if (c[1]) { x q[5]; }
cx q[3], q[4];
h q[5];
t q[5];
cx q[1], q[5];
cx q[2], q[5];
cx q[5], q[1];
cx q[5], q[2];
tdg q[1];
tdg q[2];
t q[5];
cx q[5], q[1];
cx q[5], q[2];
h q[5];
s q[5];
cx q[5], q[4];
h q[5];
c[2] = measure q[5];
if (c[2]) { cz q[1], q[2]; }
if (c[2]) { x q[5]; }
cx q[2], q[4];
h q[5];
t q[5];
cx q[0], q[5];
cx q[1], q[5];
cx q[5], q[0];
cx q[5], q[1];
tdg q[0];
tdg q[1];
t q[5];
cx q[5], q[0];
cx q[5], q[1];
h q[5];
s q[5];
cx q[5], q[4];
h q[5];
c[3] = measure q[5];
if (c[3]) { cz q[0], q[1]; }
if (c[3]) { x q[5]; }
cx q[1], q[4];
cx q[0], q[4];
