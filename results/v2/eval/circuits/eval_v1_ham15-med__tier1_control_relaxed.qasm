OPENQASM 3.0;
include "stdgates.inc";
qubit[18] q;
bit[55] c;
cx q[14], q[9];
cx q[13], q[14];
h q[16];
t q[16];
cx q[11], q[16];
cx q[12], q[16];
cx q[16], q[11];
cx q[16], q[12];
tdg q[11];
tdg q[12];
t q[16];
cx q[16], q[11];
cx q[16], q[12];
h q[16];
s q[16];
h q[15];
t q[15];
cx q[16], q[15];
cx q[13], q[15];
cx q[15], q[16];
cx q[15], q[13];
tdg q[16];
tdg q[13];
t q[15];
cx q[15], q[16];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[4];
h q[17];
c[0] = measure q[17];
if (c[0]) { cz q[15], q[14]; }
if (c[0]) { x q[17]; }
h q[15];
c[1] = measure q[15];
if (c[1]) { cz q[16], q[13]; }
if (c[1]) { x q[15]; }
h q[16];
c[2] = measure q[16];
if (c[2]) { cz q[11], q[12]; }
if (c[2]) { x q[16]; }
cx q[14], q[11];
h q[17];
t q[17];
cx q[12], q[17];
cx q[13], q[17];
cx q[17], q[12];
cx q[17], q[13];
tdg q[12];
tdg q[13];
t q[17];
cx q[17], q[12];
cx q[17], q[13];
h q[17];
s q[17];
cx q[17], q[14];
h q[17];
c[3] = measure q[17];
if (c[3]) { cz q[12], q[13]; }
if (c[3]) { x q[17]; }
h q[17];
t q[17];
cx q[11], q[17];
cx q[14], q[17];
cx q[17], q[11];
cx q[17], q[14];
tdg q[11];
tdg q[14];
t q[17];
cx q[17], q[11];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[13];
h q[17];
c[4] = measure q[17];
if (c[4]) { cz q[11], q[14]; }
if (c[4]) { x q[17]; }
h q[16];
t q[16];
cx q[11], q[16];
cx q[12], q[16];
cx q[16], q[11];
cx q[16], q[12];
tdg q[11];
tdg q[12];
t q[16];
cx q[16], q[11];
cx q[16], q[12];
h q[16];
s q[16];
h q[15];
t q[15];
cx q[16], q[15];
cx q[13], q[15];
cx q[15], q[16];
cx q[15], q[13];
tdg q[16];
tdg q[13];
t q[15];
cx q[15], q[16];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[1];
h q[17];
c[5] = measure q[17];
if (c[5]) { cz q[15], q[14]; }
if (c[5]) { x q[17]; }
h q[15];
c[6] = measure q[15];
if (c[6]) { cz q[16], q[13]; }
if (c[6]) { x q[15]; }
h q[16];
c[7] = measure q[16];
if (c[7]) { cz q[11], q[12]; }
if (c[7]) { x q[16]; }
cx q[14], q[10];
h q[15];
t q[15];
cx q[11], q[15];
cx q[12], q[15];
cx q[15], q[11];
cx q[15], q[12];
tdg q[11];
tdg q[12];
t q[15];
cx q[15], q[11];
cx q[15], q[12];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[13], q[17];
cx q[17], q[15];
cx q[17], q[13];
tdg q[15];
tdg q[13];
t q[17];
cx q[17], q[15];
cx q[17], q[13];
h q[17];
s q[17];
cx q[17], q[14];
h q[17];
c[8] = measure q[17];
if (c[8]) { cz q[15], q[13]; }
if (c[8]) { x q[17]; }
h q[15];
c[9] = measure q[15];
if (c[9]) { cz q[11], q[12]; }
if (c[9]) { x q[15]; }
h q[17];
t q[17];
cx q[11], q[17];
cx q[14], q[17];
cx q[17], q[11];
cx q[17], q[14];
tdg q[11];
tdg q[14];
t q[17];
cx q[17], q[11];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[9];
h q[17];
c[10] = measure q[17];
if (c[10]) { cz q[11], q[14]; }
if (c[10]) { x q[17]; }
h q[16];
t q[16];
cx q[11], q[16];
cx q[12], q[16];
cx q[16], q[11];
cx q[16], q[12];
tdg q[11];
tdg q[12];
t q[16];
cx q[16], q[11];
cx q[16], q[12];
h q[16];
s q[16];
h q[15];
t q[15];
cx q[16], q[15];
cx q[13], q[15];
cx q[15], q[16];
cx q[15], q[13];
tdg q[16];
tdg q[13];
t q[15];
cx q[15], q[16];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[5];
h q[17];
c[11] = measure q[17];
if (c[11]) { cz q[15], q[14]; }
if (c[11]) { x q[17]; }
h q[15];
c[12] = measure q[15];
if (c[12]) { cz q[16], q[13]; }
if (c[12]) { x q[15]; }
h q[16];
c[13] = measure q[16];
if (c[13]) { cz q[11], q[12]; }
if (c[13]) { x q[16]; }
h q[17];
t q[17];
cx q[12], q[17];
cx q[14], q[17];
cx q[17], q[12];
cx q[17], q[14];
tdg q[12];
tdg q[14];
t q[17];
cx q[17], q[12];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[0];
h q[17];
c[14] = measure q[17];
if (c[14]) { cz q[12], q[14]; }
if (c[14]) { x q[17]; }
h q[17];
t q[17];
cx q[13], q[17];
cx q[14], q[17];
cx q[17], q[13];
cx q[17], q[14];
tdg q[13];
tdg q[14];
t q[17];
cx q[17], q[13];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[0];
h q[17];
c[15] = measure q[17];
if (c[15]) { cz q[13], q[14]; }
if (c[15]) { x q[17]; }
h q[16];
t q[16];
cx q[11], q[16];
cx q[12], q[16];
cx q[16], q[11];
cx q[16], q[12];
tdg q[11];
tdg q[12];
t q[16];
cx q[16], q[11];
cx q[16], q[12];
h q[16];
s q[16];
h q[15];
t q[15];
cx q[16], q[15];
cx q[13], q[15];
cx q[15], q[16];
cx q[15], q[13];
tdg q[16];
tdg q[13];
t q[15];
cx q[15], q[16];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[0];
h q[17];
c[16] = measure q[17];
if (c[16]) { cz q[15], q[14]; }
if (c[16]) { x q[17]; }
h q[15];
c[17] = measure q[15];
if (c[17]) { cz q[16], q[13]; }
if (c[17]) { x q[15]; }
h q[16];
c[18] = measure q[16];
if (c[18]) { cz q[11], q[12]; }
if (c[18]) { x q[16]; }
cx q[14], q[12];
h q[16];
t q[16];
cx q[11], q[16];
cx q[12], q[16];
cx q[16], q[11];
cx q[16], q[12];
tdg q[11];
tdg q[12];
t q[16];
cx q[16], q[11];
cx q[16], q[12];
h q[16];
s q[16];
h q[15];
t q[15];
cx q[16], q[15];
cx q[13], q[15];
cx q[15], q[16];
cx q[15], q[13];
tdg q[16];
tdg q[13];
t q[15];
cx q[15], q[16];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[3];
h q[17];
c[19] = measure q[17];
if (c[19]) { cz q[15], q[14]; }
if (c[19]) { x q[17]; }
h q[15];
c[20] = measure q[15];
if (c[20]) { cz q[16], q[13]; }
if (c[20]) { x q[15]; }
h q[16];
c[21] = measure q[16];
if (c[21]) { cz q[11], q[12]; }
if (c[21]) { x q[16]; }
h q[17];
t q[17];
cx q[12], q[17];
cx q[14], q[17];
cx q[17], q[12];
cx q[17], q[14];
tdg q[12];
tdg q[14];
t q[17];
cx q[17], q[12];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[9];
h q[17];
c[22] = measure q[17];
if (c[22]) { cz q[12], q[14]; }
if (c[22]) { x q[17]; }
h q[17];
t q[17];
cx q[12], q[17];
cx q[14], q[17];
cx q[17], q[12];
cx q[17], q[14];
tdg q[12];
tdg q[14];
t q[17];
cx q[17], q[12];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[2];
h q[17];
c[23] = measure q[17];
if (c[23]) { cz q[12], q[14]; }
if (c[23]) { x q[17]; }
h q[16];
t q[16];
cx q[11], q[16];
cx q[12], q[16];
cx q[16], q[11];
cx q[16], q[12];
tdg q[11];
tdg q[12];
t q[16];
cx q[16], q[11];
cx q[16], q[12];
h q[16];
s q[16];
h q[15];
t q[15];
cx q[16], q[15];
cx q[13], q[15];
cx q[15], q[16];
cx q[15], q[13];
tdg q[16];
tdg q[13];
t q[15];
cx q[15], q[16];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[2];
h q[17];
c[24] = measure q[17];
if (c[24]) { cz q[15], q[14]; }
if (c[24]) { x q[17]; }
h q[15];
c[25] = measure q[15];
if (c[25]) { cz q[16], q[13]; }
if (c[25]) { x q[15]; }
h q[16];
c[26] = measure q[16];
if (c[26]) { cz q[11], q[12]; }
if (c[26]) { x q[16]; }
h q[15];
t q[15];
cx q[11], q[15];
cx q[12], q[15];
cx q[15], q[11];
cx q[15], q[12];
tdg q[11];
tdg q[12];
t q[15];
cx q[15], q[11];
cx q[15], q[12];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[13];
h q[17];
c[27] = measure q[17];
if (c[27]) { cz q[15], q[14]; }
if (c[27]) { x q[17]; }
h q[15];
c[28] = measure q[15];
if (c[28]) { cz q[11], q[12]; }
if (c[28]) { x q[15]; }
h q[15];
t q[15];
cx q[12], q[15];
cx q[13], q[15];
cx q[15], q[12];
cx q[15], q[13];
tdg q[12];
tdg q[13];
t q[15];
cx q[15], q[12];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[2];
h q[17];
c[29] = measure q[17];
if (c[29]) { cz q[15], q[14]; }
if (c[29]) { x q[17]; }
h q[15];
c[30] = measure q[15];
if (c[30]) { cz q[12], q[13]; }
if (c[30]) { x q[15]; }
h q[15];
t q[15];
cx q[12], q[15];
cx q[13], q[15];
cx q[15], q[12];
cx q[15], q[13];
tdg q[12];
tdg q[13];
t q[15];
cx q[15], q[12];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[11];
h q[17];
c[31] = measure q[17];
if (c[31]) { cz q[15], q[14]; }
if (c[31]) { x q[17]; }
h q[15];
c[32] = measure q[15];
if (c[32]) { cz q[12], q[13]; }
if (c[32]) { x q[15]; }
h q[17];
t q[17];
cx q[11], q[17];
cx q[14], q[17];
cx q[17], q[11];
cx q[17], q[14];
tdg q[11];
tdg q[14];
t q[17];
cx q[17], q[11];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[0];
h q[17];
c[33] = measure q[17];
if (c[33]) { cz q[11], q[14]; }
if (c[33]) { x q[17]; }
h q[16];
t q[16];
cx q[11], q[16];
cx q[12], q[16];
cx q[16], q[11];
cx q[16], q[12];
tdg q[11];
tdg q[12];
t q[16];
cx q[16], q[11];
cx q[16], q[12];
h q[16];
s q[16];
h q[15];
t q[15];
cx q[16], q[15];
cx q[13], q[15];
cx q[15], q[16];
cx q[15], q[13];
tdg q[16];
tdg q[13];
t q[15];
cx q[15], q[16];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[6];
h q[17];
c[34] = measure q[17];
if (c[34]) { cz q[15], q[14]; }
if (c[34]) { x q[17]; }
h q[15];
c[35] = measure q[15];
if (c[35]) { cz q[16], q[13]; }
if (c[35]) { x q[15]; }
h q[16];
c[36] = measure q[16];
if (c[36]) { cz q[11], q[12]; }
if (c[36]) { x q[16]; }
h q[17];
t q[17];
cx q[11], q[17];
cx q[14], q[17];
cx q[17], q[11];
cx q[17], q[14];
tdg q[11];
tdg q[14];
t q[17];
cx q[17], q[11];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[13];
h q[17];
c[37] = measure q[17];
if (c[37]) { cz q[11], q[14]; }
if (c[37]) { x q[17]; }
h q[17];
t q[17];
cx q[13], q[17];
cx q[14], q[17];
cx q[17], q[13];
cx q[17], q[14];
tdg q[13];
tdg q[14];
t q[17];
cx q[17], q[13];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[11];
h q[17];
c[38] = measure q[17];
if (c[38]) { cz q[13], q[14]; }
if (c[38]) { x q[17]; }
h q[16];
t q[16];
cx q[11], q[16];
cx q[12], q[16];
cx q[16], q[11];
cx q[16], q[12];
tdg q[11];
tdg q[12];
t q[16];
cx q[16], q[11];
cx q[16], q[12];
h q[16];
s q[16];
h q[15];
t q[15];
cx q[16], q[15];
cx q[13], q[15];
cx q[15], q[16];
cx q[15], q[13];
tdg q[16];
tdg q[13];
t q[15];
cx q[15], q[16];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[7];
h q[17];
c[39] = measure q[17];
if (c[39]) { cz q[15], q[14]; }
if (c[39]) { x q[17]; }
h q[15];
c[40] = measure q[15];
if (c[40]) { cz q[16], q[13]; }
if (c[40]) { x q[15]; }
h q[16];
c[41] = measure q[16];
if (c[41]) { cz q[11], q[12]; }
if (c[41]) { x q[16]; }
h q[15];
t q[15];
cx q[11], q[15];
cx q[13], q[15];
cx q[15], q[11];
cx q[15], q[13];
tdg q[11];
tdg q[13];
t q[15];
cx q[15], q[11];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[12];
h q[17];
c[42] = measure q[17];
if (c[42]) { cz q[15], q[14]; }
if (c[42]) { x q[17]; }
h q[15];
c[43] = measure q[15];
if (c[43]) { cz q[11], q[13]; }
if (c[43]) { x q[15]; }
h q[16];
t q[16];
cx q[11], q[16];
cx q[12], q[16];
cx q[16], q[11];
cx q[16], q[12];
tdg q[11];
tdg q[12];
t q[16];
cx q[16], q[11];
cx q[16], q[12];
h q[16];
s q[16];
h q[15];
t q[15];
cx q[16], q[15];
cx q[13], q[15];
cx q[15], q[16];
cx q[15], q[13];
tdg q[16];
tdg q[13];
t q[15];
cx q[15], q[16];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[9];
h q[17];
c[44] = measure q[17];
if (c[44]) { cz q[15], q[14]; }
if (c[44]) { x q[17]; }
h q[15];
c[45] = measure q[15];
if (c[45]) { cz q[16], q[13]; }
if (c[45]) { x q[15]; }
h q[16];
c[46] = measure q[16];
if (c[46]) { cz q[11], q[12]; }
if (c[46]) { x q[16]; }
h q[16];
t q[16];
cx q[11], q[16];
cx q[12], q[16];
cx q[16], q[11];
cx q[16], q[12];
tdg q[11];
tdg q[12];
t q[16];
cx q[16], q[11];
cx q[16], q[12];
h q[16];
s q[16];
h q[15];
t q[15];
cx q[16], q[15];
cx q[13], q[15];
cx q[15], q[16];
cx q[15], q[13];
tdg q[16];
tdg q[13];
t q[15];
cx q[15], q[16];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[10];
h q[17];
c[47] = measure q[17];
if (c[47]) { cz q[15], q[14]; }
if (c[47]) { x q[17]; }
h q[15];
c[48] = measure q[15];
if (c[48]) { cz q[16], q[13]; }
if (c[48]) { x q[15]; }
h q[16];
c[49] = measure q[16];
if (c[49]) { cz q[11], q[12]; }
if (c[49]) { x q[16]; }
h q[17];
t q[17];
cx q[11], q[17];
cx q[12], q[17];
cx q[17], q[11];
cx q[17], q[12];
tdg q[11];
tdg q[12];
t q[17];
cx q[17], q[11];
cx q[17], q[12];
h q[17];
s q[17];
cx q[17], q[14];
h q[17];
c[50] = measure q[17];
if (c[50]) { cz q[11], q[12]; }
if (c[50]) { x q[17]; }
h q[17];
t q[17];
cx q[11], q[17];
cx q[13], q[17];
cx q[17], q[11];
cx q[17], q[13];
tdg q[11];
tdg q[13];
t q[17];
cx q[17], q[11];
cx q[17], q[13];
h q[17];
s q[17];
cx q[17], q[10];
h q[17];
c[51] = measure q[17];
if (c[51]) { cz q[11], q[13]; }
if (c[51]) { x q[17]; }
cx q[14], q[13];
h q[16];
t q[16];
cx q[11], q[16];
cx q[12], q[16];
cx q[16], q[11];
cx q[16], q[12];
tdg q[11];
tdg q[12];
t q[16];
cx q[16], q[11];
cx q[16], q[12];
h q[16];
s q[16];
h q[15];
t q[15];
cx q[16], q[15];
cx q[13], q[15];
cx q[15], q[16];
cx q[15], q[13];
tdg q[16];
tdg q[13];
t q[15];
cx q[15], q[16];
cx q[15], q[13];
h q[15];
s q[15];
h q[17];
t q[17];
cx q[15], q[17];
cx q[14], q[17];
cx q[17], q[15];
cx q[17], q[14];
tdg q[15];
tdg q[14];
t q[17];
cx q[17], q[15];
cx q[17], q[14];
h q[17];
s q[17];
cx q[17], q[8];
h q[17];
c[52] = measure q[17];
if (c[52]) { cz q[15], q[14]; }
if (c[52]) { x q[17]; }
h q[15];
c[53] = measure q[15];
if (c[53]) { cz q[16], q[13]; }
if (c[53]) { x q[15]; }
h q[16];
c[54] = measure q[16];
if (c[54]) { cz q[11], q[12]; }
if (c[54]) { x q[16]; }
cx q[12], q[13];
cx q[10], q[9];
cx q[9], q[13];
cx q[13], q[12];
cx q[12], q[8];
cx q[8], q[12];
cx q[11], q[14];
cx q[12], q[11];
cx q[14], q[11];
cx q[10], q[14];
cx q[9], q[11];
cx q[11], q[7];
cx q[7], q[11];
cx q[10], q[13];
cx q[7], q[10];
cx q[10], q[6];
cx q[6], q[10];
cx q[6], q[9];
cx q[9], q[5];
cx q[5], q[8];
cx q[8], q[4];
cx q[4], q[7];
cx q[7], q[3];
cx q[3], q[6];
cx q[6], q[2];
cx q[2], q[6];
cx q[5], q[9];
cx q[2], q[5];
cx q[5], q[1];
cx q[4], q[8];
cx q[1], q[4];
cx q[1], q[5];
cx q[4], q[0];
cx q[3], q[7];
cx q[0], q[3];
cx q[0], q[4];
