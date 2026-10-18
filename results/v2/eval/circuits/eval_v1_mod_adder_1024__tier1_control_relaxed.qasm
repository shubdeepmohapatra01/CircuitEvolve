OPENQASM 3.0;
include "stdgates.inc";
qubit[29] q;
bit[165] c;
cx q[9], q[19];
h q[28];
t q[28];
cx q[8], q[28];
cx q[18], q[28];
cx q[28], q[8];
cx q[28], q[18];
tdg q[8];
tdg q[18];
t q[28];
cx q[28], q[8];
cx q[28], q[18];
h q[28];
s q[28];
cx q[28], q[19];
h q[28];
c[0] = measure q[28];
if (c[0]) { cz q[8], q[18]; }
if (c[0]) { x q[28]; }
cx q[8], q[18];
h q[20];
t q[20];
cx q[7], q[20];
cx q[17], q[20];
cx q[20], q[7];
cx q[20], q[17];
tdg q[7];
tdg q[17];
t q[20];
cx q[20], q[7];
cx q[20], q[17];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[18], q[28];
cx q[28], q[20];
cx q[28], q[18];
tdg q[20];
tdg q[18];
t q[28];
cx q[28], q[20];
cx q[28], q[18];
h q[28];
s q[28];
cx q[28], q[19];
h q[28];
c[1] = measure q[28];
if (c[1]) { cz q[20], q[18]; }
if (c[1]) { x q[28]; }
h q[20];
c[2] = measure q[20];
if (c[2]) { cz q[7], q[17]; }
if (c[2]) { x q[20]; }
h q[28];
t q[28];
cx q[7], q[28];
cx q[17], q[28];
cx q[28], q[7];
cx q[28], q[17];
tdg q[7];
tdg q[17];
t q[28];
cx q[28], q[7];
cx q[28], q[17];
h q[28];
s q[28];
cx q[28], q[18];
h q[28];
c[3] = measure q[28];
if (c[3]) { cz q[7], q[17]; }
if (c[3]) { x q[28]; }
cx q[7], q[17];
h q[21];
t q[21];
cx q[6], q[21];
cx q[16], q[21];
cx q[21], q[6];
cx q[21], q[16];
tdg q[6];
tdg q[16];
t q[21];
cx q[21], q[6];
cx q[21], q[16];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[17], q[20];
cx q[20], q[21];
cx q[20], q[17];
tdg q[21];
tdg q[17];
t q[20];
cx q[20], q[21];
cx q[20], q[17];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[18], q[28];
cx q[28], q[20];
cx q[28], q[18];
tdg q[20];
tdg q[18];
t q[28];
cx q[28], q[20];
cx q[28], q[18];
h q[28];
s q[28];
cx q[28], q[19];
h q[28];
c[4] = measure q[28];
if (c[4]) { cz q[20], q[18]; }
if (c[4]) { x q[28]; }
h q[20];
c[5] = measure q[20];
if (c[5]) { cz q[21], q[17]; }
if (c[5]) { x q[20]; }
h q[21];
c[6] = measure q[21];
if (c[6]) { cz q[6], q[16]; }
if (c[6]) { x q[21]; }
h q[20];
t q[20];
cx q[6], q[20];
cx q[16], q[20];
cx q[20], q[6];
cx q[20], q[16];
tdg q[6];
tdg q[16];
t q[20];
cx q[20], q[6];
cx q[20], q[16];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[17], q[28];
cx q[28], q[20];
cx q[28], q[17];
tdg q[20];
tdg q[17];
t q[28];
cx q[28], q[20];
cx q[28], q[17];
h q[28];
s q[28];
cx q[28], q[18];
h q[28];
c[7] = measure q[28];
if (c[7]) { cz q[20], q[17]; }
if (c[7]) { x q[28]; }
h q[20];
c[8] = measure q[20];
if (c[8]) { cz q[6], q[16]; }
if (c[8]) { x q[20]; }
h q[28];
t q[28];
cx q[6], q[28];
cx q[16], q[28];
cx q[28], q[6];
cx q[28], q[16];
tdg q[6];
tdg q[16];
t q[28];
cx q[28], q[6];
cx q[28], q[16];
h q[28];
s q[28];
cx q[28], q[17];
h q[28];
c[9] = measure q[28];
if (c[9]) { cz q[6], q[16]; }
if (c[9]) { x q[28]; }
cx q[6], q[16];
h q[22];
t q[22];
cx q[5], q[22];
cx q[15], q[22];
cx q[22], q[5];
cx q[22], q[15];
tdg q[5];
tdg q[15];
t q[22];
cx q[22], q[5];
cx q[22], q[15];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[16], q[21];
cx q[21], q[22];
cx q[21], q[16];
tdg q[22];
tdg q[16];
t q[21];
cx q[21], q[22];
cx q[21], q[16];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[17], q[20];
cx q[20], q[21];
cx q[20], q[17];
tdg q[21];
tdg q[17];
t q[20];
cx q[20], q[21];
cx q[20], q[17];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[18], q[28];
cx q[28], q[20];
cx q[28], q[18];
tdg q[20];
tdg q[18];
t q[28];
cx q[28], q[20];
cx q[28], q[18];
h q[28];
s q[28];
cx q[28], q[19];
h q[28];
c[10] = measure q[28];
if (c[10]) { cz q[20], q[18]; }
if (c[10]) { x q[28]; }
h q[20];
c[11] = measure q[20];
if (c[11]) { cz q[21], q[17]; }
if (c[11]) { x q[20]; }
h q[21];
c[12] = measure q[21];
if (c[12]) { cz q[22], q[16]; }
if (c[12]) { x q[21]; }
h q[22];
c[13] = measure q[22];
if (c[13]) { cz q[5], q[15]; }
if (c[13]) { x q[22]; }
h q[21];
t q[21];
cx q[5], q[21];
cx q[15], q[21];
cx q[21], q[5];
cx q[21], q[15];
tdg q[5];
tdg q[15];
t q[21];
cx q[21], q[5];
cx q[21], q[15];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[16], q[20];
cx q[20], q[21];
cx q[20], q[16];
tdg q[21];
tdg q[16];
t q[20];
cx q[20], q[21];
cx q[20], q[16];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[17], q[28];
cx q[28], q[20];
cx q[28], q[17];
tdg q[20];
tdg q[17];
t q[28];
cx q[28], q[20];
cx q[28], q[17];
h q[28];
s q[28];
cx q[28], q[18];
h q[28];
c[14] = measure q[28];
if (c[14]) { cz q[20], q[17]; }
if (c[14]) { x q[28]; }
h q[20];
c[15] = measure q[20];
if (c[15]) { cz q[21], q[16]; }
if (c[15]) { x q[20]; }
h q[21];
c[16] = measure q[21];
if (c[16]) { cz q[5], q[15]; }
if (c[16]) { x q[21]; }
h q[20];
t q[20];
cx q[5], q[20];
cx q[15], q[20];
cx q[20], q[5];
cx q[20], q[15];
tdg q[5];
tdg q[15];
t q[20];
cx q[20], q[5];
cx q[20], q[15];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[16], q[28];
cx q[28], q[20];
cx q[28], q[16];
tdg q[20];
tdg q[16];
t q[28];
cx q[28], q[20];
cx q[28], q[16];
h q[28];
s q[28];
cx q[28], q[17];
h q[28];
c[17] = measure q[28];
if (c[17]) { cz q[20], q[16]; }
if (c[17]) { x q[28]; }
h q[20];
c[18] = measure q[20];
if (c[18]) { cz q[5], q[15]; }
if (c[18]) { x q[20]; }
h q[28];
t q[28];
cx q[5], q[28];
cx q[15], q[28];
cx q[28], q[5];
cx q[28], q[15];
tdg q[5];
tdg q[15];
t q[28];
cx q[28], q[5];
cx q[28], q[15];
h q[28];
s q[28];
cx q[28], q[16];
h q[28];
c[19] = measure q[28];
if (c[19]) { cz q[5], q[15]; }
if (c[19]) { x q[28]; }
cx q[5], q[15];
h q[23];
t q[23];
cx q[4], q[23];
cx q[14], q[23];
cx q[23], q[4];
cx q[23], q[14];
tdg q[4];
tdg q[14];
t q[23];
cx q[23], q[4];
cx q[23], q[14];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[15], q[22];
cx q[22], q[23];
cx q[22], q[15];
tdg q[23];
tdg q[15];
t q[22];
cx q[22], q[23];
cx q[22], q[15];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[16], q[21];
cx q[21], q[22];
cx q[21], q[16];
tdg q[22];
tdg q[16];
t q[21];
cx q[21], q[22];
cx q[21], q[16];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[17], q[20];
cx q[20], q[21];
cx q[20], q[17];
tdg q[21];
tdg q[17];
t q[20];
cx q[20], q[21];
cx q[20], q[17];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[18], q[28];
cx q[28], q[20];
cx q[28], q[18];
tdg q[20];
tdg q[18];
t q[28];
cx q[28], q[20];
cx q[28], q[18];
h q[28];
s q[28];
cx q[28], q[19];
h q[28];
c[20] = measure q[28];
if (c[20]) { cz q[20], q[18]; }
if (c[20]) { x q[28]; }
h q[20];
c[21] = measure q[20];
if (c[21]) { cz q[21], q[17]; }
if (c[21]) { x q[20]; }
h q[21];
c[22] = measure q[21];
if (c[22]) { cz q[22], q[16]; }
if (c[22]) { x q[21]; }
h q[22];
c[23] = measure q[22];
if (c[23]) { cz q[23], q[15]; }
if (c[23]) { x q[22]; }
h q[23];
c[24] = measure q[23];
if (c[24]) { cz q[4], q[14]; }
if (c[24]) { x q[23]; }
h q[22];
t q[22];
cx q[4], q[22];
cx q[14], q[22];
cx q[22], q[4];
cx q[22], q[14];
tdg q[4];
tdg q[14];
t q[22];
cx q[22], q[4];
cx q[22], q[14];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[15], q[21];
cx q[21], q[22];
cx q[21], q[15];
tdg q[22];
tdg q[15];
t q[21];
cx q[21], q[22];
cx q[21], q[15];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[16], q[20];
cx q[20], q[21];
cx q[20], q[16];
tdg q[21];
tdg q[16];
t q[20];
cx q[20], q[21];
cx q[20], q[16];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[17], q[28];
cx q[28], q[20];
cx q[28], q[17];
tdg q[20];
tdg q[17];
t q[28];
cx q[28], q[20];
cx q[28], q[17];
h q[28];
s q[28];
cx q[28], q[18];
h q[28];
c[25] = measure q[28];
if (c[25]) { cz q[20], q[17]; }
if (c[25]) { x q[28]; }
h q[20];
c[26] = measure q[20];
if (c[26]) { cz q[21], q[16]; }
if (c[26]) { x q[20]; }
h q[21];
c[27] = measure q[21];
if (c[27]) { cz q[22], q[15]; }
if (c[27]) { x q[21]; }
h q[22];
c[28] = measure q[22];
if (c[28]) { cz q[4], q[14]; }
if (c[28]) { x q[22]; }
h q[21];
t q[21];
cx q[4], q[21];
cx q[14], q[21];
cx q[21], q[4];
cx q[21], q[14];
tdg q[4];
tdg q[14];
t q[21];
cx q[21], q[4];
cx q[21], q[14];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[15], q[20];
cx q[20], q[21];
cx q[20], q[15];
tdg q[21];
tdg q[15];
t q[20];
cx q[20], q[21];
cx q[20], q[15];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[16], q[28];
cx q[28], q[20];
cx q[28], q[16];
tdg q[20];
tdg q[16];
t q[28];
cx q[28], q[20];
cx q[28], q[16];
h q[28];
s q[28];
cx q[28], q[17];
h q[28];
c[29] = measure q[28];
if (c[29]) { cz q[20], q[16]; }
if (c[29]) { x q[28]; }
h q[20];
c[30] = measure q[20];
if (c[30]) { cz q[21], q[15]; }
if (c[30]) { x q[20]; }
h q[21];
c[31] = measure q[21];
if (c[31]) { cz q[4], q[14]; }
if (c[31]) { x q[21]; }
h q[20];
t q[20];
cx q[4], q[20];
cx q[14], q[20];
cx q[20], q[4];
cx q[20], q[14];
tdg q[4];
tdg q[14];
t q[20];
cx q[20], q[4];
cx q[20], q[14];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[15], q[28];
cx q[28], q[20];
cx q[28], q[15];
tdg q[20];
tdg q[15];
t q[28];
cx q[28], q[20];
cx q[28], q[15];
h q[28];
s q[28];
cx q[28], q[16];
h q[28];
c[32] = measure q[28];
if (c[32]) { cz q[20], q[15]; }
if (c[32]) { x q[28]; }
h q[20];
c[33] = measure q[20];
if (c[33]) { cz q[4], q[14]; }
if (c[33]) { x q[20]; }
h q[28];
t q[28];
cx q[4], q[28];
cx q[14], q[28];
cx q[28], q[4];
cx q[28], q[14];
tdg q[4];
tdg q[14];
t q[28];
cx q[28], q[4];
cx q[28], q[14];
h q[28];
s q[28];
cx q[28], q[15];
h q[28];
c[34] = measure q[28];
if (c[34]) { cz q[4], q[14]; }
if (c[34]) { x q[28]; }
cx q[4], q[14];
h q[24];
t q[24];
cx q[3], q[24];
cx q[13], q[24];
cx q[24], q[3];
cx q[24], q[13];
tdg q[3];
tdg q[13];
t q[24];
cx q[24], q[3];
cx q[24], q[13];
h q[24];
s q[24];
h q[23];
t q[23];
cx q[24], q[23];
cx q[14], q[23];
cx q[23], q[24];
cx q[23], q[14];
tdg q[24];
tdg q[14];
t q[23];
cx q[23], q[24];
cx q[23], q[14];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[15], q[22];
cx q[22], q[23];
cx q[22], q[15];
tdg q[23];
tdg q[15];
t q[22];
cx q[22], q[23];
cx q[22], q[15];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[16], q[21];
cx q[21], q[22];
cx q[21], q[16];
tdg q[22];
tdg q[16];
t q[21];
cx q[21], q[22];
cx q[21], q[16];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[17], q[20];
cx q[20], q[21];
cx q[20], q[17];
tdg q[21];
tdg q[17];
t q[20];
cx q[20], q[21];
cx q[20], q[17];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[18], q[28];
cx q[28], q[20];
cx q[28], q[18];
tdg q[20];
tdg q[18];
t q[28];
cx q[28], q[20];
cx q[28], q[18];
h q[28];
s q[28];
cx q[28], q[19];
h q[28];
c[35] = measure q[28];
if (c[35]) { cz q[20], q[18]; }
if (c[35]) { x q[28]; }
h q[20];
c[36] = measure q[20];
if (c[36]) { cz q[21], q[17]; }
if (c[36]) { x q[20]; }
h q[21];
c[37] = measure q[21];
if (c[37]) { cz q[22], q[16]; }
if (c[37]) { x q[21]; }
h q[22];
c[38] = measure q[22];
if (c[38]) { cz q[23], q[15]; }
if (c[38]) { x q[22]; }
h q[23];
c[39] = measure q[23];
if (c[39]) { cz q[24], q[14]; }
if (c[39]) { x q[23]; }
h q[24];
c[40] = measure q[24];
if (c[40]) { cz q[3], q[13]; }
if (c[40]) { x q[24]; }
h q[23];
t q[23];
cx q[3], q[23];
cx q[13], q[23];
cx q[23], q[3];
cx q[23], q[13];
tdg q[3];
tdg q[13];
t q[23];
cx q[23], q[3];
cx q[23], q[13];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[14], q[22];
cx q[22], q[23];
cx q[22], q[14];
tdg q[23];
tdg q[14];
t q[22];
cx q[22], q[23];
cx q[22], q[14];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[15], q[21];
cx q[21], q[22];
cx q[21], q[15];
tdg q[22];
tdg q[15];
t q[21];
cx q[21], q[22];
cx q[21], q[15];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[16], q[20];
cx q[20], q[21];
cx q[20], q[16];
tdg q[21];
tdg q[16];
t q[20];
cx q[20], q[21];
cx q[20], q[16];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[17], q[28];
cx q[28], q[20];
cx q[28], q[17];
tdg q[20];
tdg q[17];
t q[28];
cx q[28], q[20];
cx q[28], q[17];
h q[28];
s q[28];
cx q[28], q[18];
h q[28];
c[41] = measure q[28];
if (c[41]) { cz q[20], q[17]; }
if (c[41]) { x q[28]; }
h q[20];
c[42] = measure q[20];
if (c[42]) { cz q[21], q[16]; }
if (c[42]) { x q[20]; }
h q[21];
c[43] = measure q[21];
if (c[43]) { cz q[22], q[15]; }
if (c[43]) { x q[21]; }
h q[22];
c[44] = measure q[22];
if (c[44]) { cz q[23], q[14]; }
if (c[44]) { x q[22]; }
h q[23];
c[45] = measure q[23];
if (c[45]) { cz q[3], q[13]; }
if (c[45]) { x q[23]; }
h q[22];
t q[22];
cx q[3], q[22];
cx q[13], q[22];
cx q[22], q[3];
cx q[22], q[13];
tdg q[3];
tdg q[13];
t q[22];
cx q[22], q[3];
cx q[22], q[13];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[14], q[21];
cx q[21], q[22];
cx q[21], q[14];
tdg q[22];
tdg q[14];
t q[21];
cx q[21], q[22];
cx q[21], q[14];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[15], q[20];
cx q[20], q[21];
cx q[20], q[15];
tdg q[21];
tdg q[15];
t q[20];
cx q[20], q[21];
cx q[20], q[15];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[16], q[28];
cx q[28], q[20];
cx q[28], q[16];
tdg q[20];
tdg q[16];
t q[28];
cx q[28], q[20];
cx q[28], q[16];
h q[28];
s q[28];
cx q[28], q[17];
h q[28];
c[46] = measure q[28];
if (c[46]) { cz q[20], q[16]; }
if (c[46]) { x q[28]; }
h q[20];
c[47] = measure q[20];
if (c[47]) { cz q[21], q[15]; }
if (c[47]) { x q[20]; }
h q[21];
c[48] = measure q[21];
if (c[48]) { cz q[22], q[14]; }
if (c[48]) { x q[21]; }
h q[22];
c[49] = measure q[22];
if (c[49]) { cz q[3], q[13]; }
if (c[49]) { x q[22]; }
h q[21];
t q[21];
cx q[3], q[21];
cx q[13], q[21];
cx q[21], q[3];
cx q[21], q[13];
tdg q[3];
tdg q[13];
t q[21];
cx q[21], q[3];
cx q[21], q[13];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[14], q[20];
cx q[20], q[21];
cx q[20], q[14];
tdg q[21];
tdg q[14];
t q[20];
cx q[20], q[21];
cx q[20], q[14];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[15], q[28];
cx q[28], q[20];
cx q[28], q[15];
tdg q[20];
tdg q[15];
t q[28];
cx q[28], q[20];
cx q[28], q[15];
h q[28];
s q[28];
cx q[28], q[16];
h q[28];
c[50] = measure q[28];
if (c[50]) { cz q[20], q[15]; }
if (c[50]) { x q[28]; }
h q[20];
c[51] = measure q[20];
if (c[51]) { cz q[21], q[14]; }
if (c[51]) { x q[20]; }
h q[21];
c[52] = measure q[21];
if (c[52]) { cz q[3], q[13]; }
if (c[52]) { x q[21]; }
h q[20];
t q[20];
cx q[3], q[20];
cx q[13], q[20];
cx q[20], q[3];
cx q[20], q[13];
tdg q[3];
tdg q[13];
t q[20];
cx q[20], q[3];
cx q[20], q[13];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[14], q[28];
cx q[28], q[20];
cx q[28], q[14];
tdg q[20];
tdg q[14];
t q[28];
cx q[28], q[20];
cx q[28], q[14];
h q[28];
s q[28];
cx q[28], q[15];
h q[28];
c[53] = measure q[28];
if (c[53]) { cz q[20], q[14]; }
if (c[53]) { x q[28]; }
h q[20];
c[54] = measure q[20];
if (c[54]) { cz q[3], q[13]; }
if (c[54]) { x q[20]; }
h q[28];
t q[28];
cx q[3], q[28];
cx q[13], q[28];
cx q[28], q[3];
cx q[28], q[13];
tdg q[3];
tdg q[13];
t q[28];
cx q[28], q[3];
cx q[28], q[13];
h q[28];
s q[28];
cx q[28], q[14];
h q[28];
c[55] = measure q[28];
if (c[55]) { cz q[3], q[13]; }
if (c[55]) { x q[28]; }
cx q[3], q[13];
h q[25];
t q[25];
cx q[2], q[25];
cx q[12], q[25];
cx q[25], q[2];
cx q[25], q[12];
tdg q[2];
tdg q[12];
t q[25];
cx q[25], q[2];
cx q[25], q[12];
h q[25];
s q[25];
h q[24];
t q[24];
cx q[25], q[24];
cx q[13], q[24];
cx q[24], q[25];
cx q[24], q[13];
tdg q[25];
tdg q[13];
t q[24];
cx q[24], q[25];
cx q[24], q[13];
h q[24];
s q[24];
h q[23];
t q[23];
cx q[24], q[23];
cx q[14], q[23];
cx q[23], q[24];
cx q[23], q[14];
tdg q[24];
tdg q[14];
t q[23];
cx q[23], q[24];
cx q[23], q[14];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[15], q[22];
cx q[22], q[23];
cx q[22], q[15];
tdg q[23];
tdg q[15];
t q[22];
cx q[22], q[23];
cx q[22], q[15];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[16], q[21];
cx q[21], q[22];
cx q[21], q[16];
tdg q[22];
tdg q[16];
t q[21];
cx q[21], q[22];
cx q[21], q[16];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[17], q[20];
cx q[20], q[21];
cx q[20], q[17];
tdg q[21];
tdg q[17];
t q[20];
cx q[20], q[21];
cx q[20], q[17];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[18], q[28];
cx q[28], q[20];
cx q[28], q[18];
tdg q[20];
tdg q[18];
t q[28];
cx q[28], q[20];
cx q[28], q[18];
h q[28];
s q[28];
cx q[28], q[19];
h q[28];
c[56] = measure q[28];
if (c[56]) { cz q[20], q[18]; }
if (c[56]) { x q[28]; }
h q[20];
c[57] = measure q[20];
if (c[57]) { cz q[21], q[17]; }
if (c[57]) { x q[20]; }
h q[21];
c[58] = measure q[21];
if (c[58]) { cz q[22], q[16]; }
if (c[58]) { x q[21]; }
h q[22];
c[59] = measure q[22];
if (c[59]) { cz q[23], q[15]; }
if (c[59]) { x q[22]; }
h q[23];
c[60] = measure q[23];
if (c[60]) { cz q[24], q[14]; }
if (c[60]) { x q[23]; }
h q[24];
c[61] = measure q[24];
if (c[61]) { cz q[25], q[13]; }
if (c[61]) { x q[24]; }
h q[25];
c[62] = measure q[25];
if (c[62]) { cz q[2], q[12]; }
if (c[62]) { x q[25]; }
h q[24];
t q[24];
cx q[2], q[24];
cx q[12], q[24];
cx q[24], q[2];
cx q[24], q[12];
tdg q[2];
tdg q[12];
t q[24];
cx q[24], q[2];
cx q[24], q[12];
h q[24];
s q[24];
h q[23];
t q[23];
cx q[24], q[23];
cx q[13], q[23];
cx q[23], q[24];
cx q[23], q[13];
tdg q[24];
tdg q[13];
t q[23];
cx q[23], q[24];
cx q[23], q[13];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[14], q[22];
cx q[22], q[23];
cx q[22], q[14];
tdg q[23];
tdg q[14];
t q[22];
cx q[22], q[23];
cx q[22], q[14];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[15], q[21];
cx q[21], q[22];
cx q[21], q[15];
tdg q[22];
tdg q[15];
t q[21];
cx q[21], q[22];
cx q[21], q[15];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[16], q[20];
cx q[20], q[21];
cx q[20], q[16];
tdg q[21];
tdg q[16];
t q[20];
cx q[20], q[21];
cx q[20], q[16];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[17], q[28];
cx q[28], q[20];
cx q[28], q[17];
tdg q[20];
tdg q[17];
t q[28];
cx q[28], q[20];
cx q[28], q[17];
h q[28];
s q[28];
cx q[28], q[18];
h q[28];
c[63] = measure q[28];
if (c[63]) { cz q[20], q[17]; }
if (c[63]) { x q[28]; }
h q[20];
c[64] = measure q[20];
if (c[64]) { cz q[21], q[16]; }
if (c[64]) { x q[20]; }
h q[21];
c[65] = measure q[21];
if (c[65]) { cz q[22], q[15]; }
if (c[65]) { x q[21]; }
h q[22];
c[66] = measure q[22];
if (c[66]) { cz q[23], q[14]; }
if (c[66]) { x q[22]; }
h q[23];
c[67] = measure q[23];
if (c[67]) { cz q[24], q[13]; }
if (c[67]) { x q[23]; }
h q[24];
c[68] = measure q[24];
if (c[68]) { cz q[2], q[12]; }
if (c[68]) { x q[24]; }
h q[23];
t q[23];
cx q[2], q[23];
cx q[12], q[23];
cx q[23], q[2];
cx q[23], q[12];
tdg q[2];
tdg q[12];
t q[23];
cx q[23], q[2];
cx q[23], q[12];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[13], q[22];
cx q[22], q[23];
cx q[22], q[13];
tdg q[23];
tdg q[13];
t q[22];
cx q[22], q[23];
cx q[22], q[13];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[14], q[21];
cx q[21], q[22];
cx q[21], q[14];
tdg q[22];
tdg q[14];
t q[21];
cx q[21], q[22];
cx q[21], q[14];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[15], q[20];
cx q[20], q[21];
cx q[20], q[15];
tdg q[21];
tdg q[15];
t q[20];
cx q[20], q[21];
cx q[20], q[15];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[16], q[28];
cx q[28], q[20];
cx q[28], q[16];
tdg q[20];
tdg q[16];
t q[28];
cx q[28], q[20];
cx q[28], q[16];
h q[28];
s q[28];
cx q[28], q[17];
h q[28];
c[69] = measure q[28];
if (c[69]) { cz q[20], q[16]; }
if (c[69]) { x q[28]; }
h q[20];
c[70] = measure q[20];
if (c[70]) { cz q[21], q[15]; }
if (c[70]) { x q[20]; }
h q[21];
c[71] = measure q[21];
if (c[71]) { cz q[22], q[14]; }
if (c[71]) { x q[21]; }
h q[22];
c[72] = measure q[22];
if (c[72]) { cz q[23], q[13]; }
if (c[72]) { x q[22]; }
h q[23];
c[73] = measure q[23];
if (c[73]) { cz q[2], q[12]; }
if (c[73]) { x q[23]; }
h q[22];
t q[22];
cx q[2], q[22];
cx q[12], q[22];
cx q[22], q[2];
cx q[22], q[12];
tdg q[2];
tdg q[12];
t q[22];
cx q[22], q[2];
cx q[22], q[12];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[13], q[21];
cx q[21], q[22];
cx q[21], q[13];
tdg q[22];
tdg q[13];
t q[21];
cx q[21], q[22];
cx q[21], q[13];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[14], q[20];
cx q[20], q[21];
cx q[20], q[14];
tdg q[21];
tdg q[14];
t q[20];
cx q[20], q[21];
cx q[20], q[14];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[15], q[28];
cx q[28], q[20];
cx q[28], q[15];
tdg q[20];
tdg q[15];
t q[28];
cx q[28], q[20];
cx q[28], q[15];
h q[28];
s q[28];
cx q[28], q[16];
h q[28];
c[74] = measure q[28];
if (c[74]) { cz q[20], q[15]; }
if (c[74]) { x q[28]; }
h q[20];
c[75] = measure q[20];
if (c[75]) { cz q[21], q[14]; }
if (c[75]) { x q[20]; }
h q[21];
c[76] = measure q[21];
if (c[76]) { cz q[22], q[13]; }
if (c[76]) { x q[21]; }
h q[22];
c[77] = measure q[22];
if (c[77]) { cz q[2], q[12]; }
if (c[77]) { x q[22]; }
h q[21];
t q[21];
cx q[2], q[21];
cx q[12], q[21];
cx q[21], q[2];
cx q[21], q[12];
tdg q[2];
tdg q[12];
t q[21];
cx q[21], q[2];
cx q[21], q[12];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[13], q[20];
cx q[20], q[21];
cx q[20], q[13];
tdg q[21];
tdg q[13];
t q[20];
cx q[20], q[21];
cx q[20], q[13];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[14], q[28];
cx q[28], q[20];
cx q[28], q[14];
tdg q[20];
tdg q[14];
t q[28];
cx q[28], q[20];
cx q[28], q[14];
h q[28];
s q[28];
cx q[28], q[15];
h q[28];
c[78] = measure q[28];
if (c[78]) { cz q[20], q[14]; }
if (c[78]) { x q[28]; }
h q[20];
c[79] = measure q[20];
if (c[79]) { cz q[21], q[13]; }
if (c[79]) { x q[20]; }
h q[21];
c[80] = measure q[21];
if (c[80]) { cz q[2], q[12]; }
if (c[80]) { x q[21]; }
h q[20];
t q[20];
cx q[2], q[20];
cx q[12], q[20];
cx q[20], q[2];
cx q[20], q[12];
tdg q[2];
tdg q[12];
t q[20];
cx q[20], q[2];
cx q[20], q[12];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[13], q[28];
cx q[28], q[20];
cx q[28], q[13];
tdg q[20];
tdg q[13];
t q[28];
cx q[28], q[20];
cx q[28], q[13];
h q[28];
s q[28];
cx q[28], q[14];
h q[28];
c[81] = measure q[28];
if (c[81]) { cz q[20], q[13]; }
if (c[81]) { x q[28]; }
h q[20];
c[82] = measure q[20];
if (c[82]) { cz q[2], q[12]; }
if (c[82]) { x q[20]; }
h q[28];
t q[28];
cx q[2], q[28];
cx q[12], q[28];
cx q[28], q[2];
cx q[28], q[12];
tdg q[2];
tdg q[12];
t q[28];
cx q[28], q[2];
cx q[28], q[12];
h q[28];
s q[28];
cx q[28], q[13];
h q[28];
c[83] = measure q[28];
if (c[83]) { cz q[2], q[12]; }
if (c[83]) { x q[28]; }
cx q[2], q[12];
h q[26];
t q[26];
cx q[1], q[26];
cx q[11], q[26];
cx q[26], q[1];
cx q[26], q[11];
tdg q[1];
tdg q[11];
t q[26];
cx q[26], q[1];
cx q[26], q[11];
h q[26];
s q[26];
h q[25];
t q[25];
cx q[26], q[25];
cx q[12], q[25];
cx q[25], q[26];
cx q[25], q[12];
tdg q[26];
tdg q[12];
t q[25];
cx q[25], q[26];
cx q[25], q[12];
h q[25];
s q[25];
h q[24];
t q[24];
cx q[25], q[24];
cx q[13], q[24];
cx q[24], q[25];
cx q[24], q[13];
tdg q[25];
tdg q[13];
t q[24];
cx q[24], q[25];
cx q[24], q[13];
h q[24];
s q[24];
h q[23];
t q[23];
cx q[24], q[23];
cx q[14], q[23];
cx q[23], q[24];
cx q[23], q[14];
tdg q[24];
tdg q[14];
t q[23];
cx q[23], q[24];
cx q[23], q[14];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[15], q[22];
cx q[22], q[23];
cx q[22], q[15];
tdg q[23];
tdg q[15];
t q[22];
cx q[22], q[23];
cx q[22], q[15];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[16], q[21];
cx q[21], q[22];
cx q[21], q[16];
tdg q[22];
tdg q[16];
t q[21];
cx q[21], q[22];
cx q[21], q[16];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[17], q[20];
cx q[20], q[21];
cx q[20], q[17];
tdg q[21];
tdg q[17];
t q[20];
cx q[20], q[21];
cx q[20], q[17];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[18], q[28];
cx q[28], q[20];
cx q[28], q[18];
tdg q[20];
tdg q[18];
t q[28];
cx q[28], q[20];
cx q[28], q[18];
h q[28];
s q[28];
cx q[28], q[19];
h q[28];
c[84] = measure q[28];
if (c[84]) { cz q[20], q[18]; }
if (c[84]) { x q[28]; }
h q[20];
c[85] = measure q[20];
if (c[85]) { cz q[21], q[17]; }
if (c[85]) { x q[20]; }
h q[21];
c[86] = measure q[21];
if (c[86]) { cz q[22], q[16]; }
if (c[86]) { x q[21]; }
h q[22];
c[87] = measure q[22];
if (c[87]) { cz q[23], q[15]; }
if (c[87]) { x q[22]; }
h q[23];
c[88] = measure q[23];
if (c[88]) { cz q[24], q[14]; }
if (c[88]) { x q[23]; }
h q[24];
c[89] = measure q[24];
if (c[89]) { cz q[25], q[13]; }
if (c[89]) { x q[24]; }
h q[25];
c[90] = measure q[25];
if (c[90]) { cz q[26], q[12]; }
if (c[90]) { x q[25]; }
h q[26];
c[91] = measure q[26];
if (c[91]) { cz q[1], q[11]; }
if (c[91]) { x q[26]; }
h q[25];
t q[25];
cx q[1], q[25];
cx q[11], q[25];
cx q[25], q[1];
cx q[25], q[11];
tdg q[1];
tdg q[11];
t q[25];
cx q[25], q[1];
cx q[25], q[11];
h q[25];
s q[25];
h q[24];
t q[24];
cx q[25], q[24];
cx q[12], q[24];
cx q[24], q[25];
cx q[24], q[12];
tdg q[25];
tdg q[12];
t q[24];
cx q[24], q[25];
cx q[24], q[12];
h q[24];
s q[24];
h q[23];
t q[23];
cx q[24], q[23];
cx q[13], q[23];
cx q[23], q[24];
cx q[23], q[13];
tdg q[24];
tdg q[13];
t q[23];
cx q[23], q[24];
cx q[23], q[13];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[14], q[22];
cx q[22], q[23];
cx q[22], q[14];
tdg q[23];
tdg q[14];
t q[22];
cx q[22], q[23];
cx q[22], q[14];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[15], q[21];
cx q[21], q[22];
cx q[21], q[15];
tdg q[22];
tdg q[15];
t q[21];
cx q[21], q[22];
cx q[21], q[15];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[16], q[20];
cx q[20], q[21];
cx q[20], q[16];
tdg q[21];
tdg q[16];
t q[20];
cx q[20], q[21];
cx q[20], q[16];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[17], q[28];
cx q[28], q[20];
cx q[28], q[17];
tdg q[20];
tdg q[17];
t q[28];
cx q[28], q[20];
cx q[28], q[17];
h q[28];
s q[28];
cx q[28], q[18];
h q[28];
c[92] = measure q[28];
if (c[92]) { cz q[20], q[17]; }
if (c[92]) { x q[28]; }
h q[20];
c[93] = measure q[20];
if (c[93]) { cz q[21], q[16]; }
if (c[93]) { x q[20]; }
h q[21];
c[94] = measure q[21];
if (c[94]) { cz q[22], q[15]; }
if (c[94]) { x q[21]; }
h q[22];
c[95] = measure q[22];
if (c[95]) { cz q[23], q[14]; }
if (c[95]) { x q[22]; }
h q[23];
c[96] = measure q[23];
if (c[96]) { cz q[24], q[13]; }
if (c[96]) { x q[23]; }
h q[24];
c[97] = measure q[24];
if (c[97]) { cz q[25], q[12]; }
if (c[97]) { x q[24]; }
h q[25];
c[98] = measure q[25];
if (c[98]) { cz q[1], q[11]; }
if (c[98]) { x q[25]; }
h q[24];
t q[24];
cx q[1], q[24];
cx q[11], q[24];
cx q[24], q[1];
cx q[24], q[11];
tdg q[1];
tdg q[11];
t q[24];
cx q[24], q[1];
cx q[24], q[11];
h q[24];
s q[24];
h q[23];
t q[23];
cx q[24], q[23];
cx q[12], q[23];
cx q[23], q[24];
cx q[23], q[12];
tdg q[24];
tdg q[12];
t q[23];
cx q[23], q[24];
cx q[23], q[12];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[13], q[22];
cx q[22], q[23];
cx q[22], q[13];
tdg q[23];
tdg q[13];
t q[22];
cx q[22], q[23];
cx q[22], q[13];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[14], q[21];
cx q[21], q[22];
cx q[21], q[14];
tdg q[22];
tdg q[14];
t q[21];
cx q[21], q[22];
cx q[21], q[14];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[15], q[20];
cx q[20], q[21];
cx q[20], q[15];
tdg q[21];
tdg q[15];
t q[20];
cx q[20], q[21];
cx q[20], q[15];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[16], q[28];
cx q[28], q[20];
cx q[28], q[16];
tdg q[20];
tdg q[16];
t q[28];
cx q[28], q[20];
cx q[28], q[16];
h q[28];
s q[28];
cx q[28], q[17];
h q[28];
c[99] = measure q[28];
if (c[99]) { cz q[20], q[16]; }
if (c[99]) { x q[28]; }
h q[20];
c[100] = measure q[20];
if (c[100]) { cz q[21], q[15]; }
if (c[100]) { x q[20]; }
h q[21];
c[101] = measure q[21];
if (c[101]) { cz q[22], q[14]; }
if (c[101]) { x q[21]; }
h q[22];
c[102] = measure q[22];
if (c[102]) { cz q[23], q[13]; }
if (c[102]) { x q[22]; }
h q[23];
c[103] = measure q[23];
if (c[103]) { cz q[24], q[12]; }
if (c[103]) { x q[23]; }
h q[24];
c[104] = measure q[24];
if (c[104]) { cz q[1], q[11]; }
if (c[104]) { x q[24]; }
h q[23];
t q[23];
cx q[1], q[23];
cx q[11], q[23];
cx q[23], q[1];
cx q[23], q[11];
tdg q[1];
tdg q[11];
t q[23];
cx q[23], q[1];
cx q[23], q[11];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[12], q[22];
cx q[22], q[23];
cx q[22], q[12];
tdg q[23];
tdg q[12];
t q[22];
cx q[22], q[23];
cx q[22], q[12];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[13], q[21];
cx q[21], q[22];
cx q[21], q[13];
tdg q[22];
tdg q[13];
t q[21];
cx q[21], q[22];
cx q[21], q[13];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[14], q[20];
cx q[20], q[21];
cx q[20], q[14];
tdg q[21];
tdg q[14];
t q[20];
cx q[20], q[21];
cx q[20], q[14];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[15], q[28];
cx q[28], q[20];
cx q[28], q[15];
tdg q[20];
tdg q[15];
t q[28];
cx q[28], q[20];
cx q[28], q[15];
h q[28];
s q[28];
cx q[28], q[16];
h q[28];
c[105] = measure q[28];
if (c[105]) { cz q[20], q[15]; }
if (c[105]) { x q[28]; }
h q[20];
c[106] = measure q[20];
if (c[106]) { cz q[21], q[14]; }
if (c[106]) { x q[20]; }
h q[21];
c[107] = measure q[21];
if (c[107]) { cz q[22], q[13]; }
if (c[107]) { x q[21]; }
h q[22];
c[108] = measure q[22];
if (c[108]) { cz q[23], q[12]; }
if (c[108]) { x q[22]; }
h q[23];
c[109] = measure q[23];
if (c[109]) { cz q[1], q[11]; }
if (c[109]) { x q[23]; }
h q[22];
t q[22];
cx q[1], q[22];
cx q[11], q[22];
cx q[22], q[1];
cx q[22], q[11];
tdg q[1];
tdg q[11];
t q[22];
cx q[22], q[1];
cx q[22], q[11];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[12], q[21];
cx q[21], q[22];
cx q[21], q[12];
tdg q[22];
tdg q[12];
t q[21];
cx q[21], q[22];
cx q[21], q[12];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[13], q[20];
cx q[20], q[21];
cx q[20], q[13];
tdg q[21];
tdg q[13];
t q[20];
cx q[20], q[21];
cx q[20], q[13];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[14], q[28];
cx q[28], q[20];
cx q[28], q[14];
tdg q[20];
tdg q[14];
t q[28];
cx q[28], q[20];
cx q[28], q[14];
h q[28];
s q[28];
cx q[28], q[15];
h q[28];
c[110] = measure q[28];
if (c[110]) { cz q[20], q[14]; }
if (c[110]) { x q[28]; }
h q[20];
c[111] = measure q[20];
if (c[111]) { cz q[21], q[13]; }
if (c[111]) { x q[20]; }
h q[21];
c[112] = measure q[21];
if (c[112]) { cz q[22], q[12]; }
if (c[112]) { x q[21]; }
h q[22];
c[113] = measure q[22];
if (c[113]) { cz q[1], q[11]; }
if (c[113]) { x q[22]; }
h q[21];
t q[21];
cx q[1], q[21];
cx q[11], q[21];
cx q[21], q[1];
cx q[21], q[11];
tdg q[1];
tdg q[11];
t q[21];
cx q[21], q[1];
cx q[21], q[11];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[12], q[20];
cx q[20], q[21];
cx q[20], q[12];
tdg q[21];
tdg q[12];
t q[20];
cx q[20], q[21];
cx q[20], q[12];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[13], q[28];
cx q[28], q[20];
cx q[28], q[13];
tdg q[20];
tdg q[13];
t q[28];
cx q[28], q[20];
cx q[28], q[13];
h q[28];
s q[28];
cx q[28], q[14];
h q[28];
c[114] = measure q[28];
if (c[114]) { cz q[20], q[13]; }
if (c[114]) { x q[28]; }
h q[20];
c[115] = measure q[20];
if (c[115]) { cz q[21], q[12]; }
if (c[115]) { x q[20]; }
h q[21];
c[116] = measure q[21];
if (c[116]) { cz q[1], q[11]; }
if (c[116]) { x q[21]; }
h q[20];
t q[20];
cx q[1], q[20];
cx q[11], q[20];
cx q[20], q[1];
cx q[20], q[11];
tdg q[1];
tdg q[11];
t q[20];
cx q[20], q[1];
cx q[20], q[11];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[12], q[28];
cx q[28], q[20];
cx q[28], q[12];
tdg q[20];
tdg q[12];
t q[28];
cx q[28], q[20];
cx q[28], q[12];
h q[28];
s q[28];
cx q[28], q[13];
h q[28];
c[117] = measure q[28];
if (c[117]) { cz q[20], q[12]; }
if (c[117]) { x q[28]; }
h q[20];
c[118] = measure q[20];
if (c[118]) { cz q[1], q[11]; }
if (c[118]) { x q[20]; }
h q[28];
t q[28];
cx q[1], q[28];
cx q[11], q[28];
cx q[28], q[1];
cx q[28], q[11];
tdg q[1];
tdg q[11];
t q[28];
cx q[28], q[1];
cx q[28], q[11];
h q[28];
s q[28];
cx q[28], q[12];
h q[28];
c[119] = measure q[28];
if (c[119]) { cz q[1], q[11]; }
if (c[119]) { x q[28]; }
cx q[1], q[11];
h q[27];
t q[27];
cx q[0], q[27];
cx q[10], q[27];
cx q[27], q[0];
cx q[27], q[10];
tdg q[0];
tdg q[10];
t q[27];
cx q[27], q[0];
cx q[27], q[10];
h q[27];
s q[27];
h q[26];
t q[26];
cx q[27], q[26];
cx q[11], q[26];
cx q[26], q[27];
cx q[26], q[11];
tdg q[27];
tdg q[11];
t q[26];
cx q[26], q[27];
cx q[26], q[11];
h q[26];
s q[26];
h q[25];
t q[25];
cx q[26], q[25];
cx q[12], q[25];
cx q[25], q[26];
cx q[25], q[12];
tdg q[26];
tdg q[12];
t q[25];
cx q[25], q[26];
cx q[25], q[12];
h q[25];
s q[25];
h q[24];
t q[24];
cx q[25], q[24];
cx q[13], q[24];
cx q[24], q[25];
cx q[24], q[13];
tdg q[25];
tdg q[13];
t q[24];
cx q[24], q[25];
cx q[24], q[13];
h q[24];
s q[24];
h q[23];
t q[23];
cx q[24], q[23];
cx q[14], q[23];
cx q[23], q[24];
cx q[23], q[14];
tdg q[24];
tdg q[14];
t q[23];
cx q[23], q[24];
cx q[23], q[14];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[15], q[22];
cx q[22], q[23];
cx q[22], q[15];
tdg q[23];
tdg q[15];
t q[22];
cx q[22], q[23];
cx q[22], q[15];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[16], q[21];
cx q[21], q[22];
cx q[21], q[16];
tdg q[22];
tdg q[16];
t q[21];
cx q[21], q[22];
cx q[21], q[16];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[17], q[20];
cx q[20], q[21];
cx q[20], q[17];
tdg q[21];
tdg q[17];
t q[20];
cx q[20], q[21];
cx q[20], q[17];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[18], q[28];
cx q[28], q[20];
cx q[28], q[18];
tdg q[20];
tdg q[18];
t q[28];
cx q[28], q[20];
cx q[28], q[18];
h q[28];
s q[28];
cx q[28], q[19];
h q[28];
c[120] = measure q[28];
if (c[120]) { cz q[20], q[18]; }
if (c[120]) { x q[28]; }
h q[20];
c[121] = measure q[20];
if (c[121]) { cz q[21], q[17]; }
if (c[121]) { x q[20]; }
h q[21];
c[122] = measure q[21];
if (c[122]) { cz q[22], q[16]; }
if (c[122]) { x q[21]; }
h q[22];
c[123] = measure q[22];
if (c[123]) { cz q[23], q[15]; }
if (c[123]) { x q[22]; }
h q[23];
c[124] = measure q[23];
if (c[124]) { cz q[24], q[14]; }
if (c[124]) { x q[23]; }
h q[24];
c[125] = measure q[24];
if (c[125]) { cz q[25], q[13]; }
if (c[125]) { x q[24]; }
h q[25];
c[126] = measure q[25];
if (c[126]) { cz q[26], q[12]; }
if (c[126]) { x q[25]; }
h q[26];
c[127] = measure q[26];
if (c[127]) { cz q[27], q[11]; }
if (c[127]) { x q[26]; }
h q[27];
c[128] = measure q[27];
if (c[128]) { cz q[0], q[10]; }
if (c[128]) { x q[27]; }
h q[26];
t q[26];
cx q[0], q[26];
cx q[10], q[26];
cx q[26], q[0];
cx q[26], q[10];
tdg q[0];
tdg q[10];
t q[26];
cx q[26], q[0];
cx q[26], q[10];
h q[26];
s q[26];
h q[25];
t q[25];
cx q[26], q[25];
cx q[11], q[25];
cx q[25], q[26];
cx q[25], q[11];
tdg q[26];
tdg q[11];
t q[25];
cx q[25], q[26];
cx q[25], q[11];
h q[25];
s q[25];
h q[24];
t q[24];
cx q[25], q[24];
cx q[12], q[24];
cx q[24], q[25];
cx q[24], q[12];
tdg q[25];
tdg q[12];
t q[24];
cx q[24], q[25];
cx q[24], q[12];
h q[24];
s q[24];
h q[23];
t q[23];
cx q[24], q[23];
cx q[13], q[23];
cx q[23], q[24];
cx q[23], q[13];
tdg q[24];
tdg q[13];
t q[23];
cx q[23], q[24];
cx q[23], q[13];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[14], q[22];
cx q[22], q[23];
cx q[22], q[14];
tdg q[23];
tdg q[14];
t q[22];
cx q[22], q[23];
cx q[22], q[14];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[15], q[21];
cx q[21], q[22];
cx q[21], q[15];
tdg q[22];
tdg q[15];
t q[21];
cx q[21], q[22];
cx q[21], q[15];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[16], q[20];
cx q[20], q[21];
cx q[20], q[16];
tdg q[21];
tdg q[16];
t q[20];
cx q[20], q[21];
cx q[20], q[16];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[17], q[28];
cx q[28], q[20];
cx q[28], q[17];
tdg q[20];
tdg q[17];
t q[28];
cx q[28], q[20];
cx q[28], q[17];
h q[28];
s q[28];
cx q[28], q[18];
h q[28];
c[129] = measure q[28];
if (c[129]) { cz q[20], q[17]; }
if (c[129]) { x q[28]; }
h q[20];
c[130] = measure q[20];
if (c[130]) { cz q[21], q[16]; }
if (c[130]) { x q[20]; }
h q[21];
c[131] = measure q[21];
if (c[131]) { cz q[22], q[15]; }
if (c[131]) { x q[21]; }
h q[22];
c[132] = measure q[22];
if (c[132]) { cz q[23], q[14]; }
if (c[132]) { x q[22]; }
h q[23];
c[133] = measure q[23];
if (c[133]) { cz q[24], q[13]; }
if (c[133]) { x q[23]; }
h q[24];
c[134] = measure q[24];
if (c[134]) { cz q[25], q[12]; }
if (c[134]) { x q[24]; }
h q[25];
c[135] = measure q[25];
if (c[135]) { cz q[26], q[11]; }
if (c[135]) { x q[25]; }
h q[26];
c[136] = measure q[26];
if (c[136]) { cz q[0], q[10]; }
if (c[136]) { x q[26]; }
h q[25];
t q[25];
cx q[0], q[25];
cx q[10], q[25];
cx q[25], q[0];
cx q[25], q[10];
tdg q[0];
tdg q[10];
t q[25];
cx q[25], q[0];
cx q[25], q[10];
h q[25];
s q[25];
h q[24];
t q[24];
cx q[25], q[24];
cx q[11], q[24];
cx q[24], q[25];
cx q[24], q[11];
tdg q[25];
tdg q[11];
t q[24];
cx q[24], q[25];
cx q[24], q[11];
h q[24];
s q[24];
h q[23];
t q[23];
cx q[24], q[23];
cx q[12], q[23];
cx q[23], q[24];
cx q[23], q[12];
tdg q[24];
tdg q[12];
t q[23];
cx q[23], q[24];
cx q[23], q[12];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[13], q[22];
cx q[22], q[23];
cx q[22], q[13];
tdg q[23];
tdg q[13];
t q[22];
cx q[22], q[23];
cx q[22], q[13];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[14], q[21];
cx q[21], q[22];
cx q[21], q[14];
tdg q[22];
tdg q[14];
t q[21];
cx q[21], q[22];
cx q[21], q[14];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[15], q[20];
cx q[20], q[21];
cx q[20], q[15];
tdg q[21];
tdg q[15];
t q[20];
cx q[20], q[21];
cx q[20], q[15];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[16], q[28];
cx q[28], q[20];
cx q[28], q[16];
tdg q[20];
tdg q[16];
t q[28];
cx q[28], q[20];
cx q[28], q[16];
h q[28];
s q[28];
cx q[28], q[17];
h q[28];
c[137] = measure q[28];
if (c[137]) { cz q[20], q[16]; }
if (c[137]) { x q[28]; }
h q[20];
c[138] = measure q[20];
if (c[138]) { cz q[21], q[15]; }
if (c[138]) { x q[20]; }
h q[21];
c[139] = measure q[21];
if (c[139]) { cz q[22], q[14]; }
if (c[139]) { x q[21]; }
h q[22];
c[140] = measure q[22];
if (c[140]) { cz q[23], q[13]; }
if (c[140]) { x q[22]; }
h q[23];
c[141] = measure q[23];
if (c[141]) { cz q[24], q[12]; }
if (c[141]) { x q[23]; }
h q[24];
c[142] = measure q[24];
if (c[142]) { cz q[25], q[11]; }
if (c[142]) { x q[24]; }
h q[25];
c[143] = measure q[25];
if (c[143]) { cz q[0], q[10]; }
if (c[143]) { x q[25]; }
h q[24];
t q[24];
cx q[0], q[24];
cx q[10], q[24];
cx q[24], q[0];
cx q[24], q[10];
tdg q[0];
tdg q[10];
t q[24];
cx q[24], q[0];
cx q[24], q[10];
h q[24];
s q[24];
h q[23];
t q[23];
cx q[24], q[23];
cx q[11], q[23];
cx q[23], q[24];
cx q[23], q[11];
tdg q[24];
tdg q[11];
t q[23];
cx q[23], q[24];
cx q[23], q[11];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[12], q[22];
cx q[22], q[23];
cx q[22], q[12];
tdg q[23];
tdg q[12];
t q[22];
cx q[22], q[23];
cx q[22], q[12];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[13], q[21];
cx q[21], q[22];
cx q[21], q[13];
tdg q[22];
tdg q[13];
t q[21];
cx q[21], q[22];
cx q[21], q[13];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[14], q[20];
cx q[20], q[21];
cx q[20], q[14];
tdg q[21];
tdg q[14];
t q[20];
cx q[20], q[21];
cx q[20], q[14];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[15], q[28];
cx q[28], q[20];
cx q[28], q[15];
tdg q[20];
tdg q[15];
t q[28];
cx q[28], q[20];
cx q[28], q[15];
h q[28];
s q[28];
cx q[28], q[16];
h q[28];
c[144] = measure q[28];
if (c[144]) { cz q[20], q[15]; }
if (c[144]) { x q[28]; }
h q[20];
c[145] = measure q[20];
if (c[145]) { cz q[21], q[14]; }
if (c[145]) { x q[20]; }
h q[21];
c[146] = measure q[21];
if (c[146]) { cz q[22], q[13]; }
if (c[146]) { x q[21]; }
h q[22];
c[147] = measure q[22];
if (c[147]) { cz q[23], q[12]; }
if (c[147]) { x q[22]; }
h q[23];
c[148] = measure q[23];
if (c[148]) { cz q[24], q[11]; }
if (c[148]) { x q[23]; }
h q[24];
c[149] = measure q[24];
if (c[149]) { cz q[0], q[10]; }
if (c[149]) { x q[24]; }
h q[23];
t q[23];
cx q[0], q[23];
cx q[10], q[23];
cx q[23], q[0];
cx q[23], q[10];
tdg q[0];
tdg q[10];
t q[23];
cx q[23], q[0];
cx q[23], q[10];
h q[23];
s q[23];
h q[22];
t q[22];
cx q[23], q[22];
cx q[11], q[22];
cx q[22], q[23];
cx q[22], q[11];
tdg q[23];
tdg q[11];
t q[22];
cx q[22], q[23];
cx q[22], q[11];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[12], q[21];
cx q[21], q[22];
cx q[21], q[12];
tdg q[22];
tdg q[12];
t q[21];
cx q[21], q[22];
cx q[21], q[12];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[13], q[20];
cx q[20], q[21];
cx q[20], q[13];
tdg q[21];
tdg q[13];
t q[20];
cx q[20], q[21];
cx q[20], q[13];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[14], q[28];
cx q[28], q[20];
cx q[28], q[14];
tdg q[20];
tdg q[14];
t q[28];
cx q[28], q[20];
cx q[28], q[14];
h q[28];
s q[28];
cx q[28], q[15];
h q[28];
c[150] = measure q[28];
if (c[150]) { cz q[20], q[14]; }
if (c[150]) { x q[28]; }
h q[20];
c[151] = measure q[20];
if (c[151]) { cz q[21], q[13]; }
if (c[151]) { x q[20]; }
h q[21];
c[152] = measure q[21];
if (c[152]) { cz q[22], q[12]; }
if (c[152]) { x q[21]; }
h q[22];
c[153] = measure q[22];
if (c[153]) { cz q[23], q[11]; }
if (c[153]) { x q[22]; }
h q[23];
c[154] = measure q[23];
if (c[154]) { cz q[0], q[10]; }
if (c[154]) { x q[23]; }
h q[22];
t q[22];
cx q[0], q[22];
cx q[10], q[22];
cx q[22], q[0];
cx q[22], q[10];
tdg q[0];
tdg q[10];
t q[22];
cx q[22], q[0];
cx q[22], q[10];
h q[22];
s q[22];
h q[21];
t q[21];
cx q[22], q[21];
cx q[11], q[21];
cx q[21], q[22];
cx q[21], q[11];
tdg q[22];
tdg q[11];
t q[21];
cx q[21], q[22];
cx q[21], q[11];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[12], q[20];
cx q[20], q[21];
cx q[20], q[12];
tdg q[21];
tdg q[12];
t q[20];
cx q[20], q[21];
cx q[20], q[12];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[13], q[28];
cx q[28], q[20];
cx q[28], q[13];
tdg q[20];
tdg q[13];
t q[28];
cx q[28], q[20];
cx q[28], q[13];
h q[28];
s q[28];
cx q[28], q[14];
h q[28];
c[155] = measure q[28];
if (c[155]) { cz q[20], q[13]; }
if (c[155]) { x q[28]; }
h q[20];
c[156] = measure q[20];
if (c[156]) { cz q[21], q[12]; }
if (c[156]) { x q[20]; }
h q[21];
c[157] = measure q[21];
if (c[157]) { cz q[22], q[11]; }
if (c[157]) { x q[21]; }
h q[22];
c[158] = measure q[22];
if (c[158]) { cz q[0], q[10]; }
if (c[158]) { x q[22]; }
h q[21];
t q[21];
cx q[0], q[21];
cx q[10], q[21];
cx q[21], q[0];
cx q[21], q[10];
tdg q[0];
tdg q[10];
t q[21];
cx q[21], q[0];
cx q[21], q[10];
h q[21];
s q[21];
h q[20];
t q[20];
cx q[21], q[20];
cx q[11], q[20];
cx q[20], q[21];
cx q[20], q[11];
tdg q[21];
tdg q[11];
t q[20];
cx q[20], q[21];
cx q[20], q[11];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[12], q[28];
cx q[28], q[20];
cx q[28], q[12];
tdg q[20];
tdg q[12];
t q[28];
cx q[28], q[20];
cx q[28], q[12];
h q[28];
s q[28];
cx q[28], q[13];
h q[28];
c[159] = measure q[28];
if (c[159]) { cz q[20], q[12]; }
if (c[159]) { x q[28]; }
h q[20];
c[160] = measure q[20];
if (c[160]) { cz q[21], q[11]; }
if (c[160]) { x q[20]; }
h q[21];
c[161] = measure q[21];
if (c[161]) { cz q[0], q[10]; }
if (c[161]) { x q[21]; }
h q[20];
t q[20];
cx q[0], q[20];
cx q[10], q[20];
cx q[20], q[0];
cx q[20], q[10];
tdg q[0];
tdg q[10];
t q[20];
cx q[20], q[0];
cx q[20], q[10];
h q[20];
s q[20];
h q[28];
t q[28];
cx q[20], q[28];
cx q[11], q[28];
cx q[28], q[20];
cx q[28], q[11];
tdg q[20];
tdg q[11];
t q[28];
cx q[28], q[20];
cx q[28], q[11];
h q[28];
s q[28];
cx q[28], q[12];
h q[28];
c[162] = measure q[28];
if (c[162]) { cz q[20], q[11]; }
if (c[162]) { x q[28]; }
h q[20];
c[163] = measure q[20];
if (c[163]) { cz q[0], q[10]; }
if (c[163]) { x q[20]; }
h q[28];
t q[28];
cx q[0], q[28];
cx q[10], q[28];
cx q[28], q[0];
cx q[28], q[10];
tdg q[0];
tdg q[10];
t q[28];
cx q[28], q[0];
cx q[28], q[10];
h q[28];
s q[28];
cx q[28], q[11];
h q[28];
c[164] = measure q[28];
if (c[164]) { cz q[0], q[10]; }
if (c[164]) { x q[28]; }
cx q[0], q[10];
