OPENQASM 3.0;
include "stdgates.inc";
qubit[31] q;
bit[91] c;
h q[20];
t q[20];
cx q[9], q[20];
cx q[11], q[20];
cx q[20], q[9];
cx q[20], q[11];
tdg q[9];
tdg q[11];
t q[20];
cx q[20], q[9];
cx q[20], q[11];
h q[20];
s q[20];
h q[30];
t q[30];
cx q[8], q[30];
cx q[12], q[30];
cx q[30], q[8];
cx q[30], q[12];
tdg q[8];
tdg q[12];
t q[30];
cx q[30], q[8];
cx q[30], q[12];
h q[30];
s q[30];
cx q[30], q[20];
h q[30];
c[0] = measure q[30];
if (c[0]) { cz q[8], q[12]; }
if (c[0]) { x q[30]; }
h q[30];
t q[30];
cx q[7], q[30];
cx q[13], q[30];
cx q[30], q[7];
cx q[30], q[13];
tdg q[7];
tdg q[13];
t q[30];
cx q[30], q[7];
cx q[30], q[13];
h q[30];
s q[30];
cx q[30], q[20];
h q[30];
c[1] = measure q[30];
if (c[1]) { cz q[7], q[13]; }
if (c[1]) { x q[30]; }
h q[30];
t q[30];
cx q[6], q[30];
cx q[14], q[30];
cx q[30], q[6];
cx q[30], q[14];
tdg q[6];
tdg q[14];
t q[30];
cx q[30], q[6];
cx q[30], q[14];
h q[30];
s q[30];
cx q[30], q[20];
h q[30];
c[2] = measure q[30];
if (c[2]) { cz q[6], q[14]; }
if (c[2]) { x q[30]; }
h q[30];
t q[30];
cx q[5], q[30];
cx q[15], q[30];
cx q[30], q[5];
cx q[30], q[15];
tdg q[5];
tdg q[15];
t q[30];
cx q[30], q[5];
cx q[30], q[15];
h q[30];
s q[30];
cx q[30], q[20];
h q[30];
c[3] = measure q[30];
if (c[3]) { cz q[5], q[15]; }
if (c[3]) { x q[30]; }
h q[30];
t q[30];
cx q[4], q[30];
cx q[16], q[30];
cx q[30], q[4];
cx q[30], q[16];
tdg q[4];
tdg q[16];
t q[30];
cx q[30], q[4];
cx q[30], q[16];
h q[30];
s q[30];
cx q[30], q[20];
h q[30];
c[4] = measure q[30];
if (c[4]) { cz q[4], q[16]; }
if (c[4]) { x q[30]; }
h q[30];
t q[30];
cx q[3], q[30];
cx q[17], q[30];
cx q[30], q[3];
cx q[30], q[17];
tdg q[3];
tdg q[17];
t q[30];
cx q[30], q[3];
cx q[30], q[17];
h q[30];
s q[30];
cx q[30], q[20];
h q[30];
c[5] = measure q[30];
if (c[5]) { cz q[3], q[17]; }
if (c[5]) { x q[30]; }
h q[30];
t q[30];
cx q[2], q[30];
cx q[18], q[30];
cx q[30], q[2];
cx q[30], q[18];
tdg q[2];
tdg q[18];
t q[30];
cx q[30], q[2];
cx q[30], q[18];
h q[30];
s q[30];
cx q[30], q[20];
h q[30];
c[6] = measure q[30];
if (c[6]) { cz q[2], q[18]; }
if (c[6]) { x q[30]; }
h q[30];
t q[30];
cx q[1], q[30];
cx q[19], q[30];
cx q[30], q[1];
cx q[30], q[19];
tdg q[1];
tdg q[19];
t q[30];
cx q[30], q[1];
cx q[30], q[19];
h q[30];
s q[30];
cx q[30], q[20];
h q[30];
c[7] = measure q[30];
if (c[7]) { cz q[1], q[19]; }
if (c[7]) { x q[30]; }
h q[21];
t q[21];
cx q[9], q[21];
cx q[12], q[21];
cx q[21], q[9];
cx q[21], q[12];
tdg q[9];
tdg q[12];
t q[21];
cx q[21], q[9];
cx q[21], q[12];
h q[21];
s q[21];
h q[30];
t q[30];
cx q[8], q[30];
cx q[13], q[30];
cx q[30], q[8];
cx q[30], q[13];
tdg q[8];
tdg q[13];
t q[30];
cx q[30], q[8];
cx q[30], q[13];
h q[30];
s q[30];
cx q[30], q[21];
h q[30];
c[8] = measure q[30];
if (c[8]) { cz q[8], q[13]; }
if (c[8]) { x q[30]; }
h q[30];
t q[30];
cx q[7], q[30];
cx q[14], q[30];
cx q[30], q[7];
cx q[30], q[14];
tdg q[7];
tdg q[14];
t q[30];
cx q[30], q[7];
cx q[30], q[14];
h q[30];
s q[30];
cx q[30], q[21];
h q[30];
c[9] = measure q[30];
if (c[9]) { cz q[7], q[14]; }
if (c[9]) { x q[30]; }
h q[30];
t q[30];
cx q[6], q[30];
cx q[15], q[30];
cx q[30], q[6];
cx q[30], q[15];
tdg q[6];
tdg q[15];
t q[30];
cx q[30], q[6];
cx q[30], q[15];
h q[30];
s q[30];
cx q[30], q[21];
h q[30];
c[10] = measure q[30];
if (c[10]) { cz q[6], q[15]; }
if (c[10]) { x q[30]; }
h q[30];
t q[30];
cx q[5], q[30];
cx q[16], q[30];
cx q[30], q[5];
cx q[30], q[16];
tdg q[5];
tdg q[16];
t q[30];
cx q[30], q[5];
cx q[30], q[16];
h q[30];
s q[30];
cx q[30], q[21];
h q[30];
c[11] = measure q[30];
if (c[11]) { cz q[5], q[16]; }
if (c[11]) { x q[30]; }
h q[30];
t q[30];
cx q[4], q[30];
cx q[17], q[30];
cx q[30], q[4];
cx q[30], q[17];
tdg q[4];
tdg q[17];
t q[30];
cx q[30], q[4];
cx q[30], q[17];
h q[30];
s q[30];
cx q[30], q[21];
h q[30];
c[12] = measure q[30];
if (c[12]) { cz q[4], q[17]; }
if (c[12]) { x q[30]; }
h q[30];
t q[30];
cx q[3], q[30];
cx q[18], q[30];
cx q[30], q[3];
cx q[30], q[18];
tdg q[3];
tdg q[18];
t q[30];
cx q[30], q[3];
cx q[30], q[18];
h q[30];
s q[30];
cx q[30], q[21];
h q[30];
c[13] = measure q[30];
if (c[13]) { cz q[3], q[18]; }
if (c[13]) { x q[30]; }
h q[30];
t q[30];
cx q[2], q[30];
cx q[19], q[30];
cx q[30], q[2];
cx q[30], q[19];
tdg q[2];
tdg q[19];
t q[30];
cx q[30], q[2];
cx q[30], q[19];
h q[30];
s q[30];
cx q[30], q[21];
h q[30];
c[14] = measure q[30];
if (c[14]) { cz q[2], q[19]; }
if (c[14]) { x q[30]; }
h q[22];
t q[22];
cx q[9], q[22];
cx q[13], q[22];
cx q[22], q[9];
cx q[22], q[13];
tdg q[9];
tdg q[13];
t q[22];
cx q[22], q[9];
cx q[22], q[13];
h q[22];
s q[22];
h q[30];
t q[30];
cx q[8], q[30];
cx q[14], q[30];
cx q[30], q[8];
cx q[30], q[14];
tdg q[8];
tdg q[14];
t q[30];
cx q[30], q[8];
cx q[30], q[14];
h q[30];
s q[30];
cx q[30], q[22];
h q[30];
c[15] = measure q[30];
if (c[15]) { cz q[8], q[14]; }
if (c[15]) { x q[30]; }
h q[30];
t q[30];
cx q[7], q[30];
cx q[15], q[30];
cx q[30], q[7];
cx q[30], q[15];
tdg q[7];
tdg q[15];
t q[30];
cx q[30], q[7];
cx q[30], q[15];
h q[30];
s q[30];
cx q[30], q[22];
h q[30];
c[16] = measure q[30];
if (c[16]) { cz q[7], q[15]; }
if (c[16]) { x q[30]; }
h q[30];
t q[30];
cx q[6], q[30];
cx q[16], q[30];
cx q[30], q[6];
cx q[30], q[16];
tdg q[6];
tdg q[16];
t q[30];
cx q[30], q[6];
cx q[30], q[16];
h q[30];
s q[30];
cx q[30], q[22];
h q[30];
c[17] = measure q[30];
if (c[17]) { cz q[6], q[16]; }
if (c[17]) { x q[30]; }
h q[30];
t q[30];
cx q[5], q[30];
cx q[17], q[30];
cx q[30], q[5];
cx q[30], q[17];
tdg q[5];
tdg q[17];
t q[30];
cx q[30], q[5];
cx q[30], q[17];
h q[30];
s q[30];
cx q[30], q[22];
h q[30];
c[18] = measure q[30];
if (c[18]) { cz q[5], q[17]; }
if (c[18]) { x q[30]; }
h q[30];
t q[30];
cx q[4], q[30];
cx q[18], q[30];
cx q[30], q[4];
cx q[30], q[18];
tdg q[4];
tdg q[18];
t q[30];
cx q[30], q[4];
cx q[30], q[18];
h q[30];
s q[30];
cx q[30], q[22];
h q[30];
c[19] = measure q[30];
if (c[19]) { cz q[4], q[18]; }
if (c[19]) { x q[30]; }
h q[30];
t q[30];
cx q[3], q[30];
cx q[19], q[30];
cx q[30], q[3];
cx q[30], q[19];
tdg q[3];
tdg q[19];
t q[30];
cx q[30], q[3];
cx q[30], q[19];
h q[30];
s q[30];
cx q[30], q[22];
h q[30];
c[20] = measure q[30];
if (c[20]) { cz q[3], q[19]; }
if (c[20]) { x q[30]; }
h q[23];
t q[23];
cx q[9], q[23];
cx q[14], q[23];
cx q[23], q[9];
cx q[23], q[14];
tdg q[9];
tdg q[14];
t q[23];
cx q[23], q[9];
cx q[23], q[14];
h q[23];
s q[23];
h q[30];
t q[30];
cx q[8], q[30];
cx q[15], q[30];
cx q[30], q[8];
cx q[30], q[15];
tdg q[8];
tdg q[15];
t q[30];
cx q[30], q[8];
cx q[30], q[15];
h q[30];
s q[30];
cx q[30], q[23];
h q[30];
c[21] = measure q[30];
if (c[21]) { cz q[8], q[15]; }
if (c[21]) { x q[30]; }
h q[30];
t q[30];
cx q[7], q[30];
cx q[16], q[30];
cx q[30], q[7];
cx q[30], q[16];
tdg q[7];
tdg q[16];
t q[30];
cx q[30], q[7];
cx q[30], q[16];
h q[30];
s q[30];
cx q[30], q[23];
h q[30];
c[22] = measure q[30];
if (c[22]) { cz q[7], q[16]; }
if (c[22]) { x q[30]; }
h q[30];
t q[30];
cx q[6], q[30];
cx q[17], q[30];
cx q[30], q[6];
cx q[30], q[17];
tdg q[6];
tdg q[17];
t q[30];
cx q[30], q[6];
cx q[30], q[17];
h q[30];
s q[30];
cx q[30], q[23];
h q[30];
c[23] = measure q[30];
if (c[23]) { cz q[6], q[17]; }
if (c[23]) { x q[30]; }
h q[30];
t q[30];
cx q[5], q[30];
cx q[18], q[30];
cx q[30], q[5];
cx q[30], q[18];
tdg q[5];
tdg q[18];
t q[30];
cx q[30], q[5];
cx q[30], q[18];
h q[30];
s q[30];
cx q[30], q[23];
h q[30];
c[24] = measure q[30];
if (c[24]) { cz q[5], q[18]; }
if (c[24]) { x q[30]; }
h q[30];
t q[30];
cx q[4], q[30];
cx q[19], q[30];
cx q[30], q[4];
cx q[30], q[19];
tdg q[4];
tdg q[19];
t q[30];
cx q[30], q[4];
cx q[30], q[19];
h q[30];
s q[30];
cx q[30], q[23];
h q[30];
c[25] = measure q[30];
if (c[25]) { cz q[4], q[19]; }
if (c[25]) { x q[30]; }
h q[24];
t q[24];
cx q[9], q[24];
cx q[15], q[24];
cx q[24], q[9];
cx q[24], q[15];
tdg q[9];
tdg q[15];
t q[24];
cx q[24], q[9];
cx q[24], q[15];
h q[24];
s q[24];
h q[30];
t q[30];
cx q[8], q[30];
cx q[16], q[30];
cx q[30], q[8];
cx q[30], q[16];
tdg q[8];
tdg q[16];
t q[30];
cx q[30], q[8];
cx q[30], q[16];
h q[30];
s q[30];
cx q[30], q[24];
h q[30];
c[26] = measure q[30];
if (c[26]) { cz q[8], q[16]; }
if (c[26]) { x q[30]; }
h q[30];
t q[30];
cx q[7], q[30];
cx q[17], q[30];
cx q[30], q[7];
cx q[30], q[17];
tdg q[7];
tdg q[17];
t q[30];
cx q[30], q[7];
cx q[30], q[17];
h q[30];
s q[30];
cx q[30], q[24];
h q[30];
c[27] = measure q[30];
if (c[27]) { cz q[7], q[17]; }
if (c[27]) { x q[30]; }
h q[30];
t q[30];
cx q[6], q[30];
cx q[18], q[30];
cx q[30], q[6];
cx q[30], q[18];
tdg q[6];
tdg q[18];
t q[30];
cx q[30], q[6];
cx q[30], q[18];
h q[30];
s q[30];
cx q[30], q[24];
h q[30];
c[28] = measure q[30];
if (c[28]) { cz q[6], q[18]; }
if (c[28]) { x q[30]; }
h q[30];
t q[30];
cx q[5], q[30];
cx q[19], q[30];
cx q[30], q[5];
cx q[30], q[19];
tdg q[5];
tdg q[19];
t q[30];
cx q[30], q[5];
cx q[30], q[19];
h q[30];
s q[30];
cx q[30], q[24];
h q[30];
c[29] = measure q[30];
if (c[29]) { cz q[5], q[19]; }
if (c[29]) { x q[30]; }
h q[25];
t q[25];
cx q[9], q[25];
cx q[16], q[25];
cx q[25], q[9];
cx q[25], q[16];
tdg q[9];
tdg q[16];
t q[25];
cx q[25], q[9];
cx q[25], q[16];
h q[25];
s q[25];
h q[30];
t q[30];
cx q[8], q[30];
cx q[17], q[30];
cx q[30], q[8];
cx q[30], q[17];
tdg q[8];
tdg q[17];
t q[30];
cx q[30], q[8];
cx q[30], q[17];
h q[30];
s q[30];
cx q[30], q[25];
h q[30];
c[30] = measure q[30];
if (c[30]) { cz q[8], q[17]; }
if (c[30]) { x q[30]; }
h q[30];
t q[30];
cx q[7], q[30];
cx q[18], q[30];
cx q[30], q[7];
cx q[30], q[18];
tdg q[7];
tdg q[18];
t q[30];
cx q[30], q[7];
cx q[30], q[18];
h q[30];
s q[30];
cx q[30], q[25];
h q[30];
c[31] = measure q[30];
if (c[31]) { cz q[7], q[18]; }
if (c[31]) { x q[30]; }
h q[30];
t q[30];
cx q[6], q[30];
cx q[19], q[30];
cx q[30], q[6];
cx q[30], q[19];
tdg q[6];
tdg q[19];
t q[30];
cx q[30], q[6];
cx q[30], q[19];
h q[30];
s q[30];
cx q[30], q[25];
h q[30];
c[32] = measure q[30];
if (c[32]) { cz q[6], q[19]; }
if (c[32]) { x q[30]; }
h q[26];
t q[26];
cx q[9], q[26];
cx q[17], q[26];
cx q[26], q[9];
cx q[26], q[17];
tdg q[9];
tdg q[17];
t q[26];
cx q[26], q[9];
cx q[26], q[17];
h q[26];
s q[26];
h q[30];
t q[30];
cx q[8], q[30];
cx q[18], q[30];
cx q[30], q[8];
cx q[30], q[18];
tdg q[8];
tdg q[18];
t q[30];
cx q[30], q[8];
cx q[30], q[18];
h q[30];
s q[30];
cx q[30], q[26];
h q[30];
c[33] = measure q[30];
if (c[33]) { cz q[8], q[18]; }
if (c[33]) { x q[30]; }
h q[30];
t q[30];
cx q[7], q[30];
cx q[19], q[30];
cx q[30], q[7];
cx q[30], q[19];
tdg q[7];
tdg q[19];
t q[30];
cx q[30], q[7];
cx q[30], q[19];
h q[30];
s q[30];
cx q[30], q[26];
h q[30];
c[34] = measure q[30];
if (c[34]) { cz q[7], q[19]; }
if (c[34]) { x q[30]; }
h q[27];
t q[27];
cx q[9], q[27];
cx q[18], q[27];
cx q[27], q[9];
cx q[27], q[18];
tdg q[9];
tdg q[18];
t q[27];
cx q[27], q[9];
cx q[27], q[18];
h q[27];
s q[27];
h q[30];
t q[30];
cx q[8], q[30];
cx q[19], q[30];
cx q[30], q[8];
cx q[30], q[19];
tdg q[8];
tdg q[19];
t q[30];
cx q[30], q[8];
cx q[30], q[19];
h q[30];
s q[30];
cx q[30], q[27];
h q[30];
c[35] = measure q[30];
if (c[35]) { cz q[8], q[19]; }
if (c[35]) { x q[30]; }
h q[28];
t q[28];
cx q[9], q[28];
cx q[19], q[28];
cx q[28], q[9];
cx q[28], q[19];
tdg q[9];
tdg q[19];
t q[28];
cx q[28], q[9];
cx q[28], q[19];
h q[28];
s q[28];
cx q[28], q[21];
cx q[27], q[20];
cx q[26], q[29];
cx q[25], q[28];
cx q[24], q[27];
cx q[23], q[26];
cx q[22], q[25];
cx q[21], q[24];
cx q[20], q[23];
h q[30];
t q[30];
cx q[9], q[30];
cx q[10], q[30];
cx q[30], q[9];
cx q[30], q[10];
tdg q[9];
tdg q[10];
t q[30];
cx q[30], q[9];
cx q[30], q[10];
h q[30];
s q[30];
cx q[30], q[29];
h q[30];
c[36] = measure q[30];
if (c[36]) { cz q[9], q[10]; }
if (c[36]) { x q[30]; }
h q[30];
t q[30];
cx q[8], q[30];
cx q[11], q[30];
cx q[30], q[8];
cx q[30], q[11];
tdg q[8];
tdg q[11];
t q[30];
cx q[30], q[8];
cx q[30], q[11];
h q[30];
s q[30];
cx q[30], q[29];
h q[30];
c[37] = measure q[30];
if (c[37]) { cz q[8], q[11]; }
if (c[37]) { x q[30]; }
h q[30];
t q[30];
cx q[7], q[30];
cx q[12], q[30];
cx q[30], q[7];
cx q[30], q[12];
tdg q[7];
tdg q[12];
t q[30];
cx q[30], q[7];
cx q[30], q[12];
h q[30];
s q[30];
cx q[30], q[29];
h q[30];
c[38] = measure q[30];
if (c[38]) { cz q[7], q[12]; }
if (c[38]) { x q[30]; }
h q[30];
t q[30];
cx q[6], q[30];
cx q[13], q[30];
cx q[30], q[6];
cx q[30], q[13];
tdg q[6];
tdg q[13];
t q[30];
cx q[30], q[6];
cx q[30], q[13];
h q[30];
s q[30];
cx q[30], q[29];
h q[30];
c[39] = measure q[30];
if (c[39]) { cz q[6], q[13]; }
if (c[39]) { x q[30]; }
h q[30];
t q[30];
cx q[5], q[30];
cx q[14], q[30];
cx q[30], q[5];
cx q[30], q[14];
tdg q[5];
tdg q[14];
t q[30];
cx q[30], q[5];
cx q[30], q[14];
h q[30];
s q[30];
cx q[30], q[29];
h q[30];
c[40] = measure q[30];
if (c[40]) { cz q[5], q[14]; }
if (c[40]) { x q[30]; }
h q[30];
t q[30];
cx q[4], q[30];
cx q[15], q[30];
cx q[30], q[4];
cx q[30], q[15];
tdg q[4];
tdg q[15];
t q[30];
cx q[30], q[4];
cx q[30], q[15];
h q[30];
s q[30];
cx q[30], q[29];
h q[30];
c[41] = measure q[30];
if (c[41]) { cz q[4], q[15]; }
if (c[41]) { x q[30]; }
h q[30];
t q[30];
cx q[3], q[30];
cx q[16], q[30];
cx q[30], q[3];
cx q[30], q[16];
tdg q[3];
tdg q[16];
t q[30];
cx q[30], q[3];
cx q[30], q[16];
h q[30];
s q[30];
cx q[30], q[29];
h q[30];
c[42] = measure q[30];
if (c[42]) { cz q[3], q[16]; }
if (c[42]) { x q[30]; }
h q[30];
t q[30];
cx q[2], q[30];
cx q[17], q[30];
cx q[30], q[2];
cx q[30], q[17];
tdg q[2];
tdg q[17];
t q[30];
cx q[30], q[2];
cx q[30], q[17];
h q[30];
s q[30];
cx q[30], q[29];
h q[30];
c[43] = measure q[30];
if (c[43]) { cz q[2], q[17]; }
if (c[43]) { x q[30]; }
h q[30];
t q[30];
cx q[1], q[30];
cx q[18], q[30];
cx q[30], q[1];
cx q[30], q[18];
tdg q[1];
tdg q[18];
t q[30];
cx q[30], q[1];
cx q[30], q[18];
h q[30];
s q[30];
cx q[30], q[29];
h q[30];
c[44] = measure q[30];
if (c[44]) { cz q[1], q[18]; }
if (c[44]) { x q[30]; }
h q[30];
t q[30];
cx q[0], q[30];
cx q[19], q[30];
cx q[30], q[0];
cx q[30], q[19];
tdg q[0];
tdg q[19];
t q[30];
cx q[30], q[0];
cx q[30], q[19];
h q[30];
s q[30];
cx q[30], q[29];
h q[30];
c[45] = measure q[30];
if (c[45]) { cz q[0], q[19]; }
if (c[45]) { x q[30]; }
h q[30];
t q[30];
cx q[8], q[30];
cx q[10], q[30];
cx q[30], q[8];
cx q[30], q[10];
tdg q[8];
tdg q[10];
t q[30];
cx q[30], q[8];
cx q[30], q[10];
h q[30];
s q[30];
cx q[30], q[28];
h q[30];
c[46] = measure q[30];
if (c[46]) { cz q[8], q[10]; }
if (c[46]) { x q[30]; }
h q[30];
t q[30];
cx q[7], q[30];
cx q[11], q[30];
cx q[30], q[7];
cx q[30], q[11];
tdg q[7];
tdg q[11];
t q[30];
cx q[30], q[7];
cx q[30], q[11];
h q[30];
s q[30];
cx q[30], q[28];
h q[30];
c[47] = measure q[30];
if (c[47]) { cz q[7], q[11]; }
if (c[47]) { x q[30]; }
h q[30];
t q[30];
cx q[6], q[30];
cx q[12], q[30];
cx q[30], q[6];
cx q[30], q[12];
tdg q[6];
tdg q[12];
t q[30];
cx q[30], q[6];
cx q[30], q[12];
h q[30];
s q[30];
cx q[30], q[28];
h q[30];
c[48] = measure q[30];
if (c[48]) { cz q[6], q[12]; }
if (c[48]) { x q[30]; }
h q[30];
t q[30];
cx q[5], q[30];
cx q[13], q[30];
cx q[30], q[5];
cx q[30], q[13];
tdg q[5];
tdg q[13];
t q[30];
cx q[30], q[5];
cx q[30], q[13];
h q[30];
s q[30];
cx q[30], q[28];
h q[30];
c[49] = measure q[30];
if (c[49]) { cz q[5], q[13]; }
if (c[49]) { x q[30]; }
h q[30];
t q[30];
cx q[4], q[30];
cx q[14], q[30];
cx q[30], q[4];
cx q[30], q[14];
tdg q[4];
tdg q[14];
t q[30];
cx q[30], q[4];
cx q[30], q[14];
h q[30];
s q[30];
cx q[30], q[28];
h q[30];
c[50] = measure q[30];
if (c[50]) { cz q[4], q[14]; }
if (c[50]) { x q[30]; }
h q[30];
t q[30];
cx q[3], q[30];
cx q[15], q[30];
cx q[30], q[3];
cx q[30], q[15];
tdg q[3];
tdg q[15];
t q[30];
cx q[30], q[3];
cx q[30], q[15];
h q[30];
s q[30];
cx q[30], q[28];
h q[30];
c[51] = measure q[30];
if (c[51]) { cz q[3], q[15]; }
if (c[51]) { x q[30]; }
h q[30];
t q[30];
cx q[2], q[30];
cx q[16], q[30];
cx q[30], q[2];
cx q[30], q[16];
tdg q[2];
tdg q[16];
t q[30];
cx q[30], q[2];
cx q[30], q[16];
h q[30];
s q[30];
cx q[30], q[28];
h q[30];
c[52] = measure q[30];
if (c[52]) { cz q[2], q[16]; }
if (c[52]) { x q[30]; }
h q[30];
t q[30];
cx q[1], q[30];
cx q[17], q[30];
cx q[30], q[1];
cx q[30], q[17];
tdg q[1];
tdg q[17];
t q[30];
cx q[30], q[1];
cx q[30], q[17];
h q[30];
s q[30];
cx q[30], q[28];
h q[30];
c[53] = measure q[30];
if (c[53]) { cz q[1], q[17]; }
if (c[53]) { x q[30]; }
h q[30];
t q[30];
cx q[0], q[30];
cx q[18], q[30];
cx q[30], q[0];
cx q[30], q[18];
tdg q[0];
tdg q[18];
t q[30];
cx q[30], q[0];
cx q[30], q[18];
h q[30];
s q[30];
cx q[30], q[28];
h q[30];
c[54] = measure q[30];
if (c[54]) { cz q[0], q[18]; }
if (c[54]) { x q[30]; }
h q[30];
t q[30];
cx q[7], q[30];
cx q[10], q[30];
cx q[30], q[7];
cx q[30], q[10];
tdg q[7];
tdg q[10];
t q[30];
cx q[30], q[7];
cx q[30], q[10];
h q[30];
s q[30];
cx q[30], q[27];
h q[30];
c[55] = measure q[30];
if (c[55]) { cz q[7], q[10]; }
if (c[55]) { x q[30]; }
h q[30];
t q[30];
cx q[6], q[30];
cx q[11], q[30];
cx q[30], q[6];
cx q[30], q[11];
tdg q[6];
tdg q[11];
t q[30];
cx q[30], q[6];
cx q[30], q[11];
h q[30];
s q[30];
cx q[30], q[27];
h q[30];
c[56] = measure q[30];
if (c[56]) { cz q[6], q[11]; }
if (c[56]) { x q[30]; }
h q[30];
t q[30];
cx q[5], q[30];
cx q[12], q[30];
cx q[30], q[5];
cx q[30], q[12];
tdg q[5];
tdg q[12];
t q[30];
cx q[30], q[5];
cx q[30], q[12];
h q[30];
s q[30];
cx q[30], q[27];
h q[30];
c[57] = measure q[30];
if (c[57]) { cz q[5], q[12]; }
if (c[57]) { x q[30]; }
h q[30];
t q[30];
cx q[4], q[30];
cx q[13], q[30];
cx q[30], q[4];
cx q[30], q[13];
tdg q[4];
tdg q[13];
t q[30];
cx q[30], q[4];
cx q[30], q[13];
h q[30];
s q[30];
cx q[30], q[27];
h q[30];
c[58] = measure q[30];
if (c[58]) { cz q[4], q[13]; }
if (c[58]) { x q[30]; }
h q[30];
t q[30];
cx q[3], q[30];
cx q[14], q[30];
cx q[30], q[3];
cx q[30], q[14];
tdg q[3];
tdg q[14];
t q[30];
cx q[30], q[3];
cx q[30], q[14];
h q[30];
s q[30];
cx q[30], q[27];
h q[30];
c[59] = measure q[30];
if (c[59]) { cz q[3], q[14]; }
if (c[59]) { x q[30]; }
h q[30];
t q[30];
cx q[2], q[30];
cx q[15], q[30];
cx q[30], q[2];
cx q[30], q[15];
tdg q[2];
tdg q[15];
t q[30];
cx q[30], q[2];
cx q[30], q[15];
h q[30];
s q[30];
cx q[30], q[27];
h q[30];
c[60] = measure q[30];
if (c[60]) { cz q[2], q[15]; }
if (c[60]) { x q[30]; }
h q[30];
t q[30];
cx q[1], q[30];
cx q[16], q[30];
cx q[30], q[1];
cx q[30], q[16];
tdg q[1];
tdg q[16];
t q[30];
cx q[30], q[1];
cx q[30], q[16];
h q[30];
s q[30];
cx q[30], q[27];
h q[30];
c[61] = measure q[30];
if (c[61]) { cz q[1], q[16]; }
if (c[61]) { x q[30]; }
h q[30];
t q[30];
cx q[0], q[30];
cx q[17], q[30];
cx q[30], q[0];
cx q[30], q[17];
tdg q[0];
tdg q[17];
t q[30];
cx q[30], q[0];
cx q[30], q[17];
h q[30];
s q[30];
cx q[30], q[27];
h q[30];
c[62] = measure q[30];
if (c[62]) { cz q[0], q[17]; }
if (c[62]) { x q[30]; }
h q[30];
t q[30];
cx q[6], q[30];
cx q[10], q[30];
cx q[30], q[6];
cx q[30], q[10];
tdg q[6];
tdg q[10];
t q[30];
cx q[30], q[6];
cx q[30], q[10];
h q[30];
s q[30];
cx q[30], q[26];
h q[30];
c[63] = measure q[30];
if (c[63]) { cz q[6], q[10]; }
if (c[63]) { x q[30]; }
h q[30];
t q[30];
cx q[5], q[30];
cx q[11], q[30];
cx q[30], q[5];
cx q[30], q[11];
tdg q[5];
tdg q[11];
t q[30];
cx q[30], q[5];
cx q[30], q[11];
h q[30];
s q[30];
cx q[30], q[26];
h q[30];
c[64] = measure q[30];
if (c[64]) { cz q[5], q[11]; }
if (c[64]) { x q[30]; }
h q[30];
t q[30];
cx q[4], q[30];
cx q[12], q[30];
cx q[30], q[4];
cx q[30], q[12];
tdg q[4];
tdg q[12];
t q[30];
cx q[30], q[4];
cx q[30], q[12];
h q[30];
s q[30];
cx q[30], q[26];
h q[30];
c[65] = measure q[30];
if (c[65]) { cz q[4], q[12]; }
if (c[65]) { x q[30]; }
h q[30];
t q[30];
cx q[3], q[30];
cx q[13], q[30];
cx q[30], q[3];
cx q[30], q[13];
tdg q[3];
tdg q[13];
t q[30];
cx q[30], q[3];
cx q[30], q[13];
h q[30];
s q[30];
cx q[30], q[26];
h q[30];
c[66] = measure q[30];
if (c[66]) { cz q[3], q[13]; }
if (c[66]) { x q[30]; }
h q[30];
t q[30];
cx q[2], q[30];
cx q[14], q[30];
cx q[30], q[2];
cx q[30], q[14];
tdg q[2];
tdg q[14];
t q[30];
cx q[30], q[2];
cx q[30], q[14];
h q[30];
s q[30];
cx q[30], q[26];
h q[30];
c[67] = measure q[30];
if (c[67]) { cz q[2], q[14]; }
if (c[67]) { x q[30]; }
h q[30];
t q[30];
cx q[1], q[30];
cx q[15], q[30];
cx q[30], q[1];
cx q[30], q[15];
tdg q[1];
tdg q[15];
t q[30];
cx q[30], q[1];
cx q[30], q[15];
h q[30];
s q[30];
cx q[30], q[26];
h q[30];
c[68] = measure q[30];
if (c[68]) { cz q[1], q[15]; }
if (c[68]) { x q[30]; }
h q[30];
t q[30];
cx q[0], q[30];
cx q[16], q[30];
cx q[30], q[0];
cx q[30], q[16];
tdg q[0];
tdg q[16];
t q[30];
cx q[30], q[0];
cx q[30], q[16];
h q[30];
s q[30];
cx q[30], q[26];
h q[30];
c[69] = measure q[30];
if (c[69]) { cz q[0], q[16]; }
if (c[69]) { x q[30]; }
h q[30];
t q[30];
cx q[5], q[30];
cx q[10], q[30];
cx q[30], q[5];
cx q[30], q[10];
tdg q[5];
tdg q[10];
t q[30];
cx q[30], q[5];
cx q[30], q[10];
h q[30];
s q[30];
cx q[30], q[25];
h q[30];
c[70] = measure q[30];
if (c[70]) { cz q[5], q[10]; }
if (c[70]) { x q[30]; }
h q[30];
t q[30];
cx q[4], q[30];
cx q[11], q[30];
cx q[30], q[4];
cx q[30], q[11];
tdg q[4];
tdg q[11];
t q[30];
cx q[30], q[4];
cx q[30], q[11];
h q[30];
s q[30];
cx q[30], q[25];
h q[30];
c[71] = measure q[30];
if (c[71]) { cz q[4], q[11]; }
if (c[71]) { x q[30]; }
h q[30];
t q[30];
cx q[3], q[30];
cx q[12], q[30];
cx q[30], q[3];
cx q[30], q[12];
tdg q[3];
tdg q[12];
t q[30];
cx q[30], q[3];
cx q[30], q[12];
h q[30];
s q[30];
cx q[30], q[25];
h q[30];
c[72] = measure q[30];
if (c[72]) { cz q[3], q[12]; }
if (c[72]) { x q[30]; }
h q[30];
t q[30];
cx q[2], q[30];
cx q[13], q[30];
cx q[30], q[2];
cx q[30], q[13];
tdg q[2];
tdg q[13];
t q[30];
cx q[30], q[2];
cx q[30], q[13];
h q[30];
s q[30];
cx q[30], q[25];
h q[30];
c[73] = measure q[30];
if (c[73]) { cz q[2], q[13]; }
if (c[73]) { x q[30]; }
h q[30];
t q[30];
cx q[1], q[30];
cx q[14], q[30];
cx q[30], q[1];
cx q[30], q[14];
tdg q[1];
tdg q[14];
t q[30];
cx q[30], q[1];
cx q[30], q[14];
h q[30];
s q[30];
cx q[30], q[25];
h q[30];
c[74] = measure q[30];
if (c[74]) { cz q[1], q[14]; }
if (c[74]) { x q[30]; }
h q[30];
t q[30];
cx q[0], q[30];
cx q[15], q[30];
cx q[30], q[0];
cx q[30], q[15];
tdg q[0];
tdg q[15];
t q[30];
cx q[30], q[0];
cx q[30], q[15];
h q[30];
s q[30];
cx q[30], q[25];
h q[30];
c[75] = measure q[30];
if (c[75]) { cz q[0], q[15]; }
if (c[75]) { x q[30]; }
h q[30];
t q[30];
cx q[4], q[30];
cx q[10], q[30];
cx q[30], q[4];
cx q[30], q[10];
tdg q[4];
tdg q[10];
t q[30];
cx q[30], q[4];
cx q[30], q[10];
h q[30];
s q[30];
cx q[30], q[24];
h q[30];
c[76] = measure q[30];
if (c[76]) { cz q[4], q[10]; }
if (c[76]) { x q[30]; }
h q[30];
t q[30];
cx q[3], q[30];
cx q[11], q[30];
cx q[30], q[3];
cx q[30], q[11];
tdg q[3];
tdg q[11];
t q[30];
cx q[30], q[3];
cx q[30], q[11];
h q[30];
s q[30];
cx q[30], q[24];
h q[30];
c[77] = measure q[30];
if (c[77]) { cz q[3], q[11]; }
if (c[77]) { x q[30]; }
h q[30];
t q[30];
cx q[2], q[30];
cx q[12], q[30];
cx q[30], q[2];
cx q[30], q[12];
tdg q[2];
tdg q[12];
t q[30];
cx q[30], q[2];
cx q[30], q[12];
h q[30];
s q[30];
cx q[30], q[24];
h q[30];
c[78] = measure q[30];
if (c[78]) { cz q[2], q[12]; }
if (c[78]) { x q[30]; }
h q[30];
t q[30];
cx q[1], q[30];
cx q[13], q[30];
cx q[30], q[1];
cx q[30], q[13];
tdg q[1];
tdg q[13];
t q[30];
cx q[30], q[1];
cx q[30], q[13];
h q[30];
s q[30];
cx q[30], q[24];
h q[30];
c[79] = measure q[30];
if (c[79]) { cz q[1], q[13]; }
if (c[79]) { x q[30]; }
h q[30];
t q[30];
cx q[0], q[30];
cx q[14], q[30];
cx q[30], q[0];
cx q[30], q[14];
tdg q[0];
tdg q[14];
t q[30];
cx q[30], q[0];
cx q[30], q[14];
h q[30];
s q[30];
cx q[30], q[24];
h q[30];
c[80] = measure q[30];
if (c[80]) { cz q[0], q[14]; }
if (c[80]) { x q[30]; }
h q[30];
t q[30];
cx q[3], q[30];
cx q[10], q[30];
cx q[30], q[3];
cx q[30], q[10];
tdg q[3];
tdg q[10];
t q[30];
cx q[30], q[3];
cx q[30], q[10];
h q[30];
s q[30];
cx q[30], q[23];
h q[30];
c[81] = measure q[30];
if (c[81]) { cz q[3], q[10]; }
if (c[81]) { x q[30]; }
h q[30];
t q[30];
cx q[2], q[30];
cx q[11], q[30];
cx q[30], q[2];
cx q[30], q[11];
tdg q[2];
tdg q[11];
t q[30];
cx q[30], q[2];
cx q[30], q[11];
h q[30];
s q[30];
cx q[30], q[23];
h q[30];
c[82] = measure q[30];
if (c[82]) { cz q[2], q[11]; }
if (c[82]) { x q[30]; }
h q[30];
t q[30];
cx q[1], q[30];
cx q[12], q[30];
cx q[30], q[1];
cx q[30], q[12];
tdg q[1];
tdg q[12];
t q[30];
cx q[30], q[1];
cx q[30], q[12];
h q[30];
s q[30];
cx q[30], q[23];
h q[30];
c[83] = measure q[30];
if (c[83]) { cz q[1], q[12]; }
if (c[83]) { x q[30]; }
h q[30];
t q[30];
cx q[0], q[30];
cx q[13], q[30];
cx q[30], q[0];
cx q[30], q[13];
tdg q[0];
tdg q[13];
t q[30];
cx q[30], q[0];
cx q[30], q[13];
h q[30];
s q[30];
cx q[30], q[23];
h q[30];
c[84] = measure q[30];
if (c[84]) { cz q[0], q[13]; }
if (c[84]) { x q[30]; }
h q[30];
t q[30];
cx q[2], q[30];
cx q[10], q[30];
cx q[30], q[2];
cx q[30], q[10];
tdg q[2];
tdg q[10];
t q[30];
cx q[30], q[2];
cx q[30], q[10];
h q[30];
s q[30];
cx q[30], q[22];
h q[30];
c[85] = measure q[30];
if (c[85]) { cz q[2], q[10]; }
if (c[85]) { x q[30]; }
h q[30];
t q[30];
cx q[1], q[30];
cx q[11], q[30];
cx q[30], q[1];
cx q[30], q[11];
tdg q[1];
tdg q[11];
t q[30];
cx q[30], q[1];
cx q[30], q[11];
h q[30];
s q[30];
cx q[30], q[22];
h q[30];
c[86] = measure q[30];
if (c[86]) { cz q[1], q[11]; }
if (c[86]) { x q[30]; }
h q[30];
t q[30];
cx q[0], q[30];
cx q[12], q[30];
cx q[30], q[0];
cx q[30], q[12];
tdg q[0];
tdg q[12];
t q[30];
cx q[30], q[0];
cx q[30], q[12];
h q[30];
s q[30];
cx q[30], q[22];
h q[30];
c[87] = measure q[30];
if (c[87]) { cz q[0], q[12]; }
if (c[87]) { x q[30]; }
h q[30];
t q[30];
cx q[1], q[30];
cx q[10], q[30];
cx q[30], q[1];
cx q[30], q[10];
tdg q[1];
tdg q[10];
t q[30];
cx q[30], q[1];
cx q[30], q[10];
h q[30];
s q[30];
cx q[30], q[21];
h q[30];
c[88] = measure q[30];
if (c[88]) { cz q[1], q[10]; }
if (c[88]) { x q[30]; }
h q[30];
t q[30];
cx q[0], q[30];
cx q[11], q[30];
cx q[30], q[0];
cx q[30], q[11];
tdg q[0];
tdg q[11];
t q[30];
cx q[30], q[0];
cx q[30], q[11];
h q[30];
s q[30];
cx q[30], q[21];
h q[30];
c[89] = measure q[30];
if (c[89]) { cz q[0], q[11]; }
if (c[89]) { x q[30]; }
h q[30];
t q[30];
cx q[0], q[30];
cx q[10], q[30];
cx q[30], q[0];
cx q[30], q[10];
tdg q[0];
tdg q[10];
t q[30];
cx q[30], q[0];
cx q[30], q[10];
h q[30];
s q[30];
cx q[30], q[20];
h q[30];
c[90] = measure q[30];
if (c[90]) { cz q[0], q[10]; }
if (c[90]) { x q[30]; }
