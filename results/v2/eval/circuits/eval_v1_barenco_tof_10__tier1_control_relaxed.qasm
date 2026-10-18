OPENQASM 3.0;
include "stdgates.inc";
qubit[28] q;
bit[24] c;
h q[19];
t q[19];
cx q[9], q[19];
cx q[17], q[19];
cx q[19], q[9];
cx q[19], q[17];
tdg q[9];
tdg q[17];
t q[19];
cx q[19], q[9];
cx q[19], q[17];
h q[19];
s q[19];
cx q[19], q[18];
h q[19];
c[0] = measure q[19];
if (c[0]) { cz q[9], q[17]; }
if (c[0]) { x q[19]; }
h q[19];
t q[19];
cx q[8], q[19];
cx q[16], q[19];
cx q[19], q[8];
cx q[19], q[16];
tdg q[8];
tdg q[16];
t q[19];
cx q[19], q[8];
cx q[19], q[16];
h q[19];
s q[19];
cx q[19], q[17];
h q[19];
c[1] = measure q[19];
if (c[1]) { cz q[8], q[16]; }
if (c[1]) { x q[19]; }
h q[19];
t q[19];
cx q[7], q[19];
cx q[15], q[19];
cx q[19], q[7];
cx q[19], q[15];
tdg q[7];
tdg q[15];
t q[19];
cx q[19], q[7];
cx q[19], q[15];
h q[19];
s q[19];
cx q[19], q[16];
h q[19];
c[2] = measure q[19];
if (c[2]) { cz q[7], q[15]; }
if (c[2]) { x q[19]; }
h q[19];
t q[19];
cx q[6], q[19];
cx q[14], q[19];
cx q[19], q[6];
cx q[19], q[14];
tdg q[6];
tdg q[14];
t q[19];
cx q[19], q[6];
cx q[19], q[14];
h q[19];
s q[19];
cx q[19], q[15];
h q[19];
c[3] = measure q[19];
if (c[3]) { cz q[6], q[14]; }
if (c[3]) { x q[19]; }
h q[19];
t q[19];
cx q[5], q[19];
cx q[13], q[19];
cx q[19], q[5];
cx q[19], q[13];
tdg q[5];
tdg q[13];
t q[19];
cx q[19], q[5];
cx q[19], q[13];
h q[19];
s q[19];
cx q[19], q[14];
h q[19];
c[4] = measure q[19];
if (c[4]) { cz q[5], q[13]; }
if (c[4]) { x q[19]; }
h q[19];
t q[19];
cx q[4], q[19];
cx q[12], q[19];
cx q[19], q[4];
cx q[19], q[12];
tdg q[4];
tdg q[12];
t q[19];
cx q[19], q[4];
cx q[19], q[12];
h q[19];
s q[19];
cx q[19], q[13];
h q[19];
c[5] = measure q[19];
if (c[5]) { cz q[4], q[12]; }
if (c[5]) { x q[19]; }
h q[19];
t q[19];
cx q[3], q[19];
cx q[11], q[19];
cx q[19], q[3];
cx q[19], q[11];
tdg q[3];
tdg q[11];
t q[19];
cx q[19], q[3];
cx q[19], q[11];
h q[19];
s q[19];
cx q[19], q[12];
h q[19];
c[6] = measure q[19];
if (c[6]) { cz q[3], q[11]; }
if (c[6]) { x q[19]; }
h q[19];
t q[19];
cx q[2], q[19];
cx q[10], q[19];
cx q[19], q[2];
cx q[19], q[10];
tdg q[2];
tdg q[10];
t q[19];
cx q[19], q[2];
cx q[19], q[10];
h q[19];
s q[19];
cx q[19], q[11];
h q[19];
c[7] = measure q[19];
if (c[7]) { cz q[2], q[10]; }
if (c[7]) { x q[19]; }
h q[19];
t q[19];
cx q[0], q[19];
cx q[1], q[19];
cx q[19], q[0];
cx q[19], q[1];
tdg q[0];
tdg q[1];
t q[19];
cx q[19], q[0];
cx q[19], q[1];
h q[19];
s q[19];
cx q[19], q[10];
h q[20];
t q[20];
cx q[2], q[20];
cx q[10], q[20];
cx q[20], q[2];
cx q[20], q[10];
tdg q[2];
tdg q[10];
t q[20];
cx q[20], q[2];
cx q[20], q[10];
h q[20];
s q[20];
cx q[20], q[11];
h q[21];
t q[21];
cx q[3], q[21];
cx q[11], q[21];
cx q[21], q[3];
cx q[21], q[11];
tdg q[3];
tdg q[11];
t q[21];
cx q[21], q[3];
cx q[21], q[11];
h q[21];
s q[21];
cx q[21], q[12];
h q[22];
t q[22];
cx q[4], q[22];
cx q[12], q[22];
cx q[22], q[4];
cx q[22], q[12];
tdg q[4];
tdg q[12];
t q[22];
cx q[22], q[4];
cx q[22], q[12];
h q[22];
s q[22];
cx q[22], q[13];
h q[23];
t q[23];
cx q[5], q[23];
cx q[13], q[23];
cx q[23], q[5];
cx q[23], q[13];
tdg q[5];
tdg q[13];
t q[23];
cx q[23], q[5];
cx q[23], q[13];
h q[23];
s q[23];
cx q[23], q[14];
h q[24];
t q[24];
cx q[6], q[24];
cx q[14], q[24];
cx q[24], q[6];
cx q[24], q[14];
tdg q[6];
tdg q[14];
t q[24];
cx q[24], q[6];
cx q[24], q[14];
h q[24];
s q[24];
cx q[24], q[15];
h q[25];
t q[25];
cx q[7], q[25];
cx q[15], q[25];
cx q[25], q[7];
cx q[25], q[15];
tdg q[7];
tdg q[15];
t q[25];
cx q[25], q[7];
cx q[25], q[15];
h q[25];
s q[25];
cx q[25], q[16];
h q[26];
t q[26];
cx q[8], q[26];
cx q[16], q[26];
cx q[26], q[8];
cx q[26], q[16];
tdg q[8];
tdg q[16];
t q[26];
cx q[26], q[8];
cx q[26], q[16];
h q[26];
s q[26];
cx q[26], q[17];
h q[27];
t q[27];
cx q[9], q[27];
cx q[17], q[27];
cx q[27], q[9];
cx q[27], q[17];
tdg q[9];
tdg q[17];
t q[27];
cx q[27], q[9];
cx q[27], q[17];
h q[27];
s q[27];
cx q[27], q[18];
h q[27];
c[8] = measure q[27];
if (c[8]) { cz q[9], q[17]; }
if (c[8]) { x q[27]; }
cx q[26], q[17];
h q[26];
c[9] = measure q[26];
if (c[9]) { cz q[8], q[16]; }
if (c[9]) { x q[26]; }
cx q[25], q[16];
h q[25];
c[10] = measure q[25];
if (c[10]) { cz q[7], q[15]; }
if (c[10]) { x q[25]; }
cx q[24], q[15];
h q[24];
c[11] = measure q[24];
if (c[11]) { cz q[6], q[14]; }
if (c[11]) { x q[24]; }
cx q[23], q[14];
h q[23];
c[12] = measure q[23];
if (c[12]) { cz q[5], q[13]; }
if (c[12]) { x q[23]; }
cx q[22], q[13];
h q[22];
c[13] = measure q[22];
if (c[13]) { cz q[4], q[12]; }
if (c[13]) { x q[22]; }
cx q[21], q[12];
h q[21];
c[14] = measure q[21];
if (c[14]) { cz q[3], q[11]; }
if (c[14]) { x q[21]; }
cx q[20], q[11];
h q[20];
c[15] = measure q[20];
if (c[15]) { cz q[2], q[10]; }
if (c[15]) { x q[20]; }
cx q[19], q[10];
h q[19];
c[16] = measure q[19];
if (c[16]) { cz q[0], q[1]; }
if (c[16]) { x q[19]; }
h q[19];
t q[19];
cx q[2], q[19];
cx q[10], q[19];
cx q[19], q[2];
cx q[19], q[10];
tdg q[2];
tdg q[10];
t q[19];
cx q[19], q[2];
cx q[19], q[10];
h q[19];
s q[19];
cx q[19], q[11];
h q[19];
c[17] = measure q[19];
if (c[17]) { cz q[2], q[10]; }
if (c[17]) { x q[19]; }
h q[19];
t q[19];
cx q[3], q[19];
cx q[11], q[19];
cx q[19], q[3];
cx q[19], q[11];
tdg q[3];
tdg q[11];
t q[19];
cx q[19], q[3];
cx q[19], q[11];
h q[19];
s q[19];
cx q[19], q[12];
h q[19];
c[18] = measure q[19];
if (c[18]) { cz q[3], q[11]; }
if (c[18]) { x q[19]; }
h q[19];
t q[19];
cx q[4], q[19];
cx q[12], q[19];
cx q[19], q[4];
cx q[19], q[12];
tdg q[4];
tdg q[12];
t q[19];
cx q[19], q[4];
cx q[19], q[12];
h q[19];
s q[19];
cx q[19], q[13];
h q[19];
c[19] = measure q[19];
if (c[19]) { cz q[4], q[12]; }
if (c[19]) { x q[19]; }
h q[19];
t q[19];
cx q[5], q[19];
cx q[13], q[19];
cx q[19], q[5];
cx q[19], q[13];
tdg q[5];
tdg q[13];
t q[19];
cx q[19], q[5];
cx q[19], q[13];
h q[19];
s q[19];
cx q[19], q[14];
h q[19];
c[20] = measure q[19];
if (c[20]) { cz q[5], q[13]; }
if (c[20]) { x q[19]; }
h q[19];
t q[19];
cx q[6], q[19];
cx q[14], q[19];
cx q[19], q[6];
cx q[19], q[14];
tdg q[6];
tdg q[14];
t q[19];
cx q[19], q[6];
cx q[19], q[14];
h q[19];
s q[19];
cx q[19], q[15];
h q[19];
c[21] = measure q[19];
if (c[21]) { cz q[6], q[14]; }
if (c[21]) { x q[19]; }
h q[19];
t q[19];
cx q[7], q[19];
cx q[15], q[19];
cx q[19], q[7];
cx q[19], q[15];
tdg q[7];
tdg q[15];
t q[19];
cx q[19], q[7];
cx q[19], q[15];
h q[19];
s q[19];
cx q[19], q[16];
h q[19];
c[22] = measure q[19];
if (c[22]) { cz q[7], q[15]; }
if (c[22]) { x q[19]; }
h q[19];
t q[19];
cx q[8], q[19];
cx q[16], q[19];
cx q[19], q[8];
cx q[19], q[16];
tdg q[8];
tdg q[16];
t q[19];
cx q[19], q[8];
cx q[19], q[16];
h q[19];
s q[19];
cx q[19], q[17];
h q[19];
c[23] = measure q[19];
if (c[23]) { cz q[8], q[16]; }
if (c[23]) { x q[19]; }
