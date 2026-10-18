OPENQASM 3.0;
include "stdgates.inc";
qubit[49] q;
bit[241] c;
h q[32];
t q[32];
cx q[15], q[32];
cx q[17], q[32];
cx q[32], q[15];
cx q[32], q[17];
tdg q[15];
tdg q[17];
t q[32];
cx q[32], q[15];
cx q[32], q[17];
h q[32];
s q[32];
h q[48];
t q[48];
cx q[14], q[48];
cx q[18], q[48];
cx q[48], q[14];
cx q[48], q[18];
tdg q[14];
tdg q[18];
t q[48];
cx q[48], q[14];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[0] = measure q[48];
if (c[0]) { cz q[14], q[18]; }
if (c[0]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[19], q[48];
cx q[48], q[13];
cx q[48], q[19];
tdg q[13];
tdg q[19];
t q[48];
cx q[48], q[13];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[1] = measure q[48];
if (c[1]) { cz q[13], q[19]; }
if (c[1]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[20], q[48];
cx q[48], q[12];
cx q[48], q[20];
tdg q[12];
tdg q[20];
t q[48];
cx q[48], q[12];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[2] = measure q[48];
if (c[2]) { cz q[12], q[20]; }
if (c[2]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[21], q[48];
cx q[48], q[11];
cx q[48], q[21];
tdg q[11];
tdg q[21];
t q[48];
cx q[48], q[11];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[3] = measure q[48];
if (c[3]) { cz q[11], q[21]; }
if (c[3]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[22], q[48];
cx q[48], q[10];
cx q[48], q[22];
tdg q[10];
tdg q[22];
t q[48];
cx q[48], q[10];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[4] = measure q[48];
if (c[4]) { cz q[10], q[22]; }
if (c[4]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[23], q[48];
cx q[48], q[9];
cx q[48], q[23];
tdg q[9];
tdg q[23];
t q[48];
cx q[48], q[9];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[5] = measure q[48];
if (c[5]) { cz q[9], q[23]; }
if (c[5]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[24], q[48];
cx q[48], q[8];
cx q[48], q[24];
tdg q[8];
tdg q[24];
t q[48];
cx q[48], q[8];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[6] = measure q[48];
if (c[6]) { cz q[8], q[24]; }
if (c[6]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[25], q[48];
cx q[48], q[7];
cx q[48], q[25];
tdg q[7];
tdg q[25];
t q[48];
cx q[48], q[7];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[7] = measure q[48];
if (c[7]) { cz q[7], q[25]; }
if (c[7]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[26], q[48];
cx q[48], q[6];
cx q[48], q[26];
tdg q[6];
tdg q[26];
t q[48];
cx q[48], q[6];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[8] = measure q[48];
if (c[8]) { cz q[6], q[26]; }
if (c[8]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[27], q[48];
cx q[48], q[5];
cx q[48], q[27];
tdg q[5];
tdg q[27];
t q[48];
cx q[48], q[5];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[9] = measure q[48];
if (c[9]) { cz q[5], q[27]; }
if (c[9]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[28], q[48];
cx q[48], q[4];
cx q[48], q[28];
tdg q[4];
tdg q[28];
t q[48];
cx q[48], q[4];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[10] = measure q[48];
if (c[10]) { cz q[4], q[28]; }
if (c[10]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[29], q[48];
cx q[48], q[3];
cx q[48], q[29];
tdg q[3];
tdg q[29];
t q[48];
cx q[48], q[3];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[11] = measure q[48];
if (c[11]) { cz q[3], q[29]; }
if (c[11]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[30], q[48];
cx q[48], q[2];
cx q[48], q[30];
tdg q[2];
tdg q[30];
t q[48];
cx q[48], q[2];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[12] = measure q[48];
if (c[12]) { cz q[2], q[30]; }
if (c[12]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[31], q[48];
cx q[48], q[1];
cx q[48], q[31];
tdg q[1];
tdg q[31];
t q[48];
cx q[48], q[1];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[13] = measure q[48];
if (c[13]) { cz q[1], q[31]; }
if (c[13]) { x q[48]; }
h q[33];
t q[33];
cx q[15], q[33];
cx q[18], q[33];
cx q[33], q[15];
cx q[33], q[18];
tdg q[15];
tdg q[18];
t q[33];
cx q[33], q[15];
cx q[33], q[18];
h q[33];
s q[33];
h q[48];
t q[48];
cx q[14], q[48];
cx q[19], q[48];
cx q[48], q[14];
cx q[48], q[19];
tdg q[14];
tdg q[19];
t q[48];
cx q[48], q[14];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[14] = measure q[48];
if (c[14]) { cz q[14], q[19]; }
if (c[14]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[20], q[48];
cx q[48], q[13];
cx q[48], q[20];
tdg q[13];
tdg q[20];
t q[48];
cx q[48], q[13];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[15] = measure q[48];
if (c[15]) { cz q[13], q[20]; }
if (c[15]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[21], q[48];
cx q[48], q[12];
cx q[48], q[21];
tdg q[12];
tdg q[21];
t q[48];
cx q[48], q[12];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[16] = measure q[48];
if (c[16]) { cz q[12], q[21]; }
if (c[16]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[22], q[48];
cx q[48], q[11];
cx q[48], q[22];
tdg q[11];
tdg q[22];
t q[48];
cx q[48], q[11];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[17] = measure q[48];
if (c[17]) { cz q[11], q[22]; }
if (c[17]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[23], q[48];
cx q[48], q[10];
cx q[48], q[23];
tdg q[10];
tdg q[23];
t q[48];
cx q[48], q[10];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[18] = measure q[48];
if (c[18]) { cz q[10], q[23]; }
if (c[18]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[24], q[48];
cx q[48], q[9];
cx q[48], q[24];
tdg q[9];
tdg q[24];
t q[48];
cx q[48], q[9];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[19] = measure q[48];
if (c[19]) { cz q[9], q[24]; }
if (c[19]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[25], q[48];
cx q[48], q[8];
cx q[48], q[25];
tdg q[8];
tdg q[25];
t q[48];
cx q[48], q[8];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[20] = measure q[48];
if (c[20]) { cz q[8], q[25]; }
if (c[20]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[26], q[48];
cx q[48], q[7];
cx q[48], q[26];
tdg q[7];
tdg q[26];
t q[48];
cx q[48], q[7];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[21] = measure q[48];
if (c[21]) { cz q[7], q[26]; }
if (c[21]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[27], q[48];
cx q[48], q[6];
cx q[48], q[27];
tdg q[6];
tdg q[27];
t q[48];
cx q[48], q[6];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[22] = measure q[48];
if (c[22]) { cz q[6], q[27]; }
if (c[22]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[28], q[48];
cx q[48], q[5];
cx q[48], q[28];
tdg q[5];
tdg q[28];
t q[48];
cx q[48], q[5];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[23] = measure q[48];
if (c[23]) { cz q[5], q[28]; }
if (c[23]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[29], q[48];
cx q[48], q[4];
cx q[48], q[29];
tdg q[4];
tdg q[29];
t q[48];
cx q[48], q[4];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[24] = measure q[48];
if (c[24]) { cz q[4], q[29]; }
if (c[24]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[30], q[48];
cx q[48], q[3];
cx q[48], q[30];
tdg q[3];
tdg q[30];
t q[48];
cx q[48], q[3];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[25] = measure q[48];
if (c[25]) { cz q[3], q[30]; }
if (c[25]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[31], q[48];
cx q[48], q[2];
cx q[48], q[31];
tdg q[2];
tdg q[31];
t q[48];
cx q[48], q[2];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[26] = measure q[48];
if (c[26]) { cz q[2], q[31]; }
if (c[26]) { x q[48]; }
h q[34];
t q[34];
cx q[15], q[34];
cx q[19], q[34];
cx q[34], q[15];
cx q[34], q[19];
tdg q[15];
tdg q[19];
t q[34];
cx q[34], q[15];
cx q[34], q[19];
h q[34];
s q[34];
h q[48];
t q[48];
cx q[14], q[48];
cx q[20], q[48];
cx q[48], q[14];
cx q[48], q[20];
tdg q[14];
tdg q[20];
t q[48];
cx q[48], q[14];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[27] = measure q[48];
if (c[27]) { cz q[14], q[20]; }
if (c[27]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[21], q[48];
cx q[48], q[13];
cx q[48], q[21];
tdg q[13];
tdg q[21];
t q[48];
cx q[48], q[13];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[28] = measure q[48];
if (c[28]) { cz q[13], q[21]; }
if (c[28]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[22], q[48];
cx q[48], q[12];
cx q[48], q[22];
tdg q[12];
tdg q[22];
t q[48];
cx q[48], q[12];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[29] = measure q[48];
if (c[29]) { cz q[12], q[22]; }
if (c[29]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[23], q[48];
cx q[48], q[11];
cx q[48], q[23];
tdg q[11];
tdg q[23];
t q[48];
cx q[48], q[11];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[30] = measure q[48];
if (c[30]) { cz q[11], q[23]; }
if (c[30]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[24], q[48];
cx q[48], q[10];
cx q[48], q[24];
tdg q[10];
tdg q[24];
t q[48];
cx q[48], q[10];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[31] = measure q[48];
if (c[31]) { cz q[10], q[24]; }
if (c[31]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[25], q[48];
cx q[48], q[9];
cx q[48], q[25];
tdg q[9];
tdg q[25];
t q[48];
cx q[48], q[9];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[32] = measure q[48];
if (c[32]) { cz q[9], q[25]; }
if (c[32]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[26], q[48];
cx q[48], q[8];
cx q[48], q[26];
tdg q[8];
tdg q[26];
t q[48];
cx q[48], q[8];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[33] = measure q[48];
if (c[33]) { cz q[8], q[26]; }
if (c[33]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[27], q[48];
cx q[48], q[7];
cx q[48], q[27];
tdg q[7];
tdg q[27];
t q[48];
cx q[48], q[7];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[34] = measure q[48];
if (c[34]) { cz q[7], q[27]; }
if (c[34]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[28], q[48];
cx q[48], q[6];
cx q[48], q[28];
tdg q[6];
tdg q[28];
t q[48];
cx q[48], q[6];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[35] = measure q[48];
if (c[35]) { cz q[6], q[28]; }
if (c[35]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[29], q[48];
cx q[48], q[5];
cx q[48], q[29];
tdg q[5];
tdg q[29];
t q[48];
cx q[48], q[5];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[36] = measure q[48];
if (c[36]) { cz q[5], q[29]; }
if (c[36]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[30], q[48];
cx q[48], q[4];
cx q[48], q[30];
tdg q[4];
tdg q[30];
t q[48];
cx q[48], q[4];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[37] = measure q[48];
if (c[37]) { cz q[4], q[30]; }
if (c[37]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[31], q[48];
cx q[48], q[3];
cx q[48], q[31];
tdg q[3];
tdg q[31];
t q[48];
cx q[48], q[3];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[38] = measure q[48];
if (c[38]) { cz q[3], q[31]; }
if (c[38]) { x q[48]; }
h q[35];
t q[35];
cx q[15], q[35];
cx q[20], q[35];
cx q[35], q[15];
cx q[35], q[20];
tdg q[15];
tdg q[20];
t q[35];
cx q[35], q[15];
cx q[35], q[20];
h q[35];
s q[35];
h q[48];
t q[48];
cx q[14], q[48];
cx q[21], q[48];
cx q[48], q[14];
cx q[48], q[21];
tdg q[14];
tdg q[21];
t q[48];
cx q[48], q[14];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[39] = measure q[48];
if (c[39]) { cz q[14], q[21]; }
if (c[39]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[22], q[48];
cx q[48], q[13];
cx q[48], q[22];
tdg q[13];
tdg q[22];
t q[48];
cx q[48], q[13];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[40] = measure q[48];
if (c[40]) { cz q[13], q[22]; }
if (c[40]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[23], q[48];
cx q[48], q[12];
cx q[48], q[23];
tdg q[12];
tdg q[23];
t q[48];
cx q[48], q[12];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[41] = measure q[48];
if (c[41]) { cz q[12], q[23]; }
if (c[41]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[24], q[48];
cx q[48], q[11];
cx q[48], q[24];
tdg q[11];
tdg q[24];
t q[48];
cx q[48], q[11];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[42] = measure q[48];
if (c[42]) { cz q[11], q[24]; }
if (c[42]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[25], q[48];
cx q[48], q[10];
cx q[48], q[25];
tdg q[10];
tdg q[25];
t q[48];
cx q[48], q[10];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[43] = measure q[48];
if (c[43]) { cz q[10], q[25]; }
if (c[43]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[26], q[48];
cx q[48], q[9];
cx q[48], q[26];
tdg q[9];
tdg q[26];
t q[48];
cx q[48], q[9];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[44] = measure q[48];
if (c[44]) { cz q[9], q[26]; }
if (c[44]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[27], q[48];
cx q[48], q[8];
cx q[48], q[27];
tdg q[8];
tdg q[27];
t q[48];
cx q[48], q[8];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[45] = measure q[48];
if (c[45]) { cz q[8], q[27]; }
if (c[45]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[28], q[48];
cx q[48], q[7];
cx q[48], q[28];
tdg q[7];
tdg q[28];
t q[48];
cx q[48], q[7];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[46] = measure q[48];
if (c[46]) { cz q[7], q[28]; }
if (c[46]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[29], q[48];
cx q[48], q[6];
cx q[48], q[29];
tdg q[6];
tdg q[29];
t q[48];
cx q[48], q[6];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[47] = measure q[48];
if (c[47]) { cz q[6], q[29]; }
if (c[47]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[30], q[48];
cx q[48], q[5];
cx q[48], q[30];
tdg q[5];
tdg q[30];
t q[48];
cx q[48], q[5];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[48] = measure q[48];
if (c[48]) { cz q[5], q[30]; }
if (c[48]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[31], q[48];
cx q[48], q[4];
cx q[48], q[31];
tdg q[4];
tdg q[31];
t q[48];
cx q[48], q[4];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[49] = measure q[48];
if (c[49]) { cz q[4], q[31]; }
if (c[49]) { x q[48]; }
h q[36];
t q[36];
cx q[15], q[36];
cx q[21], q[36];
cx q[36], q[15];
cx q[36], q[21];
tdg q[15];
tdg q[21];
t q[36];
cx q[36], q[15];
cx q[36], q[21];
h q[36];
s q[36];
h q[48];
t q[48];
cx q[14], q[48];
cx q[22], q[48];
cx q[48], q[14];
cx q[48], q[22];
tdg q[14];
tdg q[22];
t q[48];
cx q[48], q[14];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[50] = measure q[48];
if (c[50]) { cz q[14], q[22]; }
if (c[50]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[23], q[48];
cx q[48], q[13];
cx q[48], q[23];
tdg q[13];
tdg q[23];
t q[48];
cx q[48], q[13];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[51] = measure q[48];
if (c[51]) { cz q[13], q[23]; }
if (c[51]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[24], q[48];
cx q[48], q[12];
cx q[48], q[24];
tdg q[12];
tdg q[24];
t q[48];
cx q[48], q[12];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[52] = measure q[48];
if (c[52]) { cz q[12], q[24]; }
if (c[52]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[25], q[48];
cx q[48], q[11];
cx q[48], q[25];
tdg q[11];
tdg q[25];
t q[48];
cx q[48], q[11];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[53] = measure q[48];
if (c[53]) { cz q[11], q[25]; }
if (c[53]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[26], q[48];
cx q[48], q[10];
cx q[48], q[26];
tdg q[10];
tdg q[26];
t q[48];
cx q[48], q[10];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[54] = measure q[48];
if (c[54]) { cz q[10], q[26]; }
if (c[54]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[27], q[48];
cx q[48], q[9];
cx q[48], q[27];
tdg q[9];
tdg q[27];
t q[48];
cx q[48], q[9];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[55] = measure q[48];
if (c[55]) { cz q[9], q[27]; }
if (c[55]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[28], q[48];
cx q[48], q[8];
cx q[48], q[28];
tdg q[8];
tdg q[28];
t q[48];
cx q[48], q[8];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[56] = measure q[48];
if (c[56]) { cz q[8], q[28]; }
if (c[56]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[29], q[48];
cx q[48], q[7];
cx q[48], q[29];
tdg q[7];
tdg q[29];
t q[48];
cx q[48], q[7];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[57] = measure q[48];
if (c[57]) { cz q[7], q[29]; }
if (c[57]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[30], q[48];
cx q[48], q[6];
cx q[48], q[30];
tdg q[6];
tdg q[30];
t q[48];
cx q[48], q[6];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[58] = measure q[48];
if (c[58]) { cz q[6], q[30]; }
if (c[58]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[31], q[48];
cx q[48], q[5];
cx q[48], q[31];
tdg q[5];
tdg q[31];
t q[48];
cx q[48], q[5];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[59] = measure q[48];
if (c[59]) { cz q[5], q[31]; }
if (c[59]) { x q[48]; }
h q[37];
t q[37];
cx q[15], q[37];
cx q[22], q[37];
cx q[37], q[15];
cx q[37], q[22];
tdg q[15];
tdg q[22];
t q[37];
cx q[37], q[15];
cx q[37], q[22];
h q[37];
s q[37];
h q[48];
t q[48];
cx q[14], q[48];
cx q[23], q[48];
cx q[48], q[14];
cx q[48], q[23];
tdg q[14];
tdg q[23];
t q[48];
cx q[48], q[14];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[60] = measure q[48];
if (c[60]) { cz q[14], q[23]; }
if (c[60]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[24], q[48];
cx q[48], q[13];
cx q[48], q[24];
tdg q[13];
tdg q[24];
t q[48];
cx q[48], q[13];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[61] = measure q[48];
if (c[61]) { cz q[13], q[24]; }
if (c[61]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[25], q[48];
cx q[48], q[12];
cx q[48], q[25];
tdg q[12];
tdg q[25];
t q[48];
cx q[48], q[12];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[62] = measure q[48];
if (c[62]) { cz q[12], q[25]; }
if (c[62]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[26], q[48];
cx q[48], q[11];
cx q[48], q[26];
tdg q[11];
tdg q[26];
t q[48];
cx q[48], q[11];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[63] = measure q[48];
if (c[63]) { cz q[11], q[26]; }
if (c[63]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[27], q[48];
cx q[48], q[10];
cx q[48], q[27];
tdg q[10];
tdg q[27];
t q[48];
cx q[48], q[10];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[64] = measure q[48];
if (c[64]) { cz q[10], q[27]; }
if (c[64]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[28], q[48];
cx q[48], q[9];
cx q[48], q[28];
tdg q[9];
tdg q[28];
t q[48];
cx q[48], q[9];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[65] = measure q[48];
if (c[65]) { cz q[9], q[28]; }
if (c[65]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[29], q[48];
cx q[48], q[8];
cx q[48], q[29];
tdg q[8];
tdg q[29];
t q[48];
cx q[48], q[8];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[66] = measure q[48];
if (c[66]) { cz q[8], q[29]; }
if (c[66]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[30], q[48];
cx q[48], q[7];
cx q[48], q[30];
tdg q[7];
tdg q[30];
t q[48];
cx q[48], q[7];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[67] = measure q[48];
if (c[67]) { cz q[7], q[30]; }
if (c[67]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[31], q[48];
cx q[48], q[6];
cx q[48], q[31];
tdg q[6];
tdg q[31];
t q[48];
cx q[48], q[6];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[68] = measure q[48];
if (c[68]) { cz q[6], q[31]; }
if (c[68]) { x q[48]; }
h q[38];
t q[38];
cx q[15], q[38];
cx q[23], q[38];
cx q[38], q[15];
cx q[38], q[23];
tdg q[15];
tdg q[23];
t q[38];
cx q[38], q[15];
cx q[38], q[23];
h q[38];
s q[38];
h q[48];
t q[48];
cx q[14], q[48];
cx q[24], q[48];
cx q[48], q[14];
cx q[48], q[24];
tdg q[14];
tdg q[24];
t q[48];
cx q[48], q[14];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[69] = measure q[48];
if (c[69]) { cz q[14], q[24]; }
if (c[69]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[25], q[48];
cx q[48], q[13];
cx q[48], q[25];
tdg q[13];
tdg q[25];
t q[48];
cx q[48], q[13];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[70] = measure q[48];
if (c[70]) { cz q[13], q[25]; }
if (c[70]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[26], q[48];
cx q[48], q[12];
cx q[48], q[26];
tdg q[12];
tdg q[26];
t q[48];
cx q[48], q[12];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[71] = measure q[48];
if (c[71]) { cz q[12], q[26]; }
if (c[71]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[27], q[48];
cx q[48], q[11];
cx q[48], q[27];
tdg q[11];
tdg q[27];
t q[48];
cx q[48], q[11];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[72] = measure q[48];
if (c[72]) { cz q[11], q[27]; }
if (c[72]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[28], q[48];
cx q[48], q[10];
cx q[48], q[28];
tdg q[10];
tdg q[28];
t q[48];
cx q[48], q[10];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[73] = measure q[48];
if (c[73]) { cz q[10], q[28]; }
if (c[73]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[29], q[48];
cx q[48], q[9];
cx q[48], q[29];
tdg q[9];
tdg q[29];
t q[48];
cx q[48], q[9];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[74] = measure q[48];
if (c[74]) { cz q[9], q[29]; }
if (c[74]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[30], q[48];
cx q[48], q[8];
cx q[48], q[30];
tdg q[8];
tdg q[30];
t q[48];
cx q[48], q[8];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[75] = measure q[48];
if (c[75]) { cz q[8], q[30]; }
if (c[75]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[31], q[48];
cx q[48], q[7];
cx q[48], q[31];
tdg q[7];
tdg q[31];
t q[48];
cx q[48], q[7];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[76] = measure q[48];
if (c[76]) { cz q[7], q[31]; }
if (c[76]) { x q[48]; }
h q[39];
t q[39];
cx q[15], q[39];
cx q[24], q[39];
cx q[39], q[15];
cx q[39], q[24];
tdg q[15];
tdg q[24];
t q[39];
cx q[39], q[15];
cx q[39], q[24];
h q[39];
s q[39];
h q[48];
t q[48];
cx q[14], q[48];
cx q[25], q[48];
cx q[48], q[14];
cx q[48], q[25];
tdg q[14];
tdg q[25];
t q[48];
cx q[48], q[14];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[77] = measure q[48];
if (c[77]) { cz q[14], q[25]; }
if (c[77]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[26], q[48];
cx q[48], q[13];
cx q[48], q[26];
tdg q[13];
tdg q[26];
t q[48];
cx q[48], q[13];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[78] = measure q[48];
if (c[78]) { cz q[13], q[26]; }
if (c[78]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[27], q[48];
cx q[48], q[12];
cx q[48], q[27];
tdg q[12];
tdg q[27];
t q[48];
cx q[48], q[12];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[79] = measure q[48];
if (c[79]) { cz q[12], q[27]; }
if (c[79]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[28], q[48];
cx q[48], q[11];
cx q[48], q[28];
tdg q[11];
tdg q[28];
t q[48];
cx q[48], q[11];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[80] = measure q[48];
if (c[80]) { cz q[11], q[28]; }
if (c[80]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[29], q[48];
cx q[48], q[10];
cx q[48], q[29];
tdg q[10];
tdg q[29];
t q[48];
cx q[48], q[10];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[81] = measure q[48];
if (c[81]) { cz q[10], q[29]; }
if (c[81]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[30], q[48];
cx q[48], q[9];
cx q[48], q[30];
tdg q[9];
tdg q[30];
t q[48];
cx q[48], q[9];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[82] = measure q[48];
if (c[82]) { cz q[9], q[30]; }
if (c[82]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[31], q[48];
cx q[48], q[8];
cx q[48], q[31];
tdg q[8];
tdg q[31];
t q[48];
cx q[48], q[8];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[83] = measure q[48];
if (c[83]) { cz q[8], q[31]; }
if (c[83]) { x q[48]; }
h q[40];
t q[40];
cx q[15], q[40];
cx q[25], q[40];
cx q[40], q[15];
cx q[40], q[25];
tdg q[15];
tdg q[25];
t q[40];
cx q[40], q[15];
cx q[40], q[25];
h q[40];
s q[40];
h q[48];
t q[48];
cx q[14], q[48];
cx q[26], q[48];
cx q[48], q[14];
cx q[48], q[26];
tdg q[14];
tdg q[26];
t q[48];
cx q[48], q[14];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[84] = measure q[48];
if (c[84]) { cz q[14], q[26]; }
if (c[84]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[27], q[48];
cx q[48], q[13];
cx q[48], q[27];
tdg q[13];
tdg q[27];
t q[48];
cx q[48], q[13];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[85] = measure q[48];
if (c[85]) { cz q[13], q[27]; }
if (c[85]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[28], q[48];
cx q[48], q[12];
cx q[48], q[28];
tdg q[12];
tdg q[28];
t q[48];
cx q[48], q[12];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[86] = measure q[48];
if (c[86]) { cz q[12], q[28]; }
if (c[86]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[29], q[48];
cx q[48], q[11];
cx q[48], q[29];
tdg q[11];
tdg q[29];
t q[48];
cx q[48], q[11];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[87] = measure q[48];
if (c[87]) { cz q[11], q[29]; }
if (c[87]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[30], q[48];
cx q[48], q[10];
cx q[48], q[30];
tdg q[10];
tdg q[30];
t q[48];
cx q[48], q[10];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[88] = measure q[48];
if (c[88]) { cz q[10], q[30]; }
if (c[88]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[31], q[48];
cx q[48], q[9];
cx q[48], q[31];
tdg q[9];
tdg q[31];
t q[48];
cx q[48], q[9];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[89] = measure q[48];
if (c[89]) { cz q[9], q[31]; }
if (c[89]) { x q[48]; }
h q[41];
t q[41];
cx q[15], q[41];
cx q[26], q[41];
cx q[41], q[15];
cx q[41], q[26];
tdg q[15];
tdg q[26];
t q[41];
cx q[41], q[15];
cx q[41], q[26];
h q[41];
s q[41];
h q[48];
t q[48];
cx q[14], q[48];
cx q[27], q[48];
cx q[48], q[14];
cx q[48], q[27];
tdg q[14];
tdg q[27];
t q[48];
cx q[48], q[14];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[90] = measure q[48];
if (c[90]) { cz q[14], q[27]; }
if (c[90]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[28], q[48];
cx q[48], q[13];
cx q[48], q[28];
tdg q[13];
tdg q[28];
t q[48];
cx q[48], q[13];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[91] = measure q[48];
if (c[91]) { cz q[13], q[28]; }
if (c[91]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[29], q[48];
cx q[48], q[12];
cx q[48], q[29];
tdg q[12];
tdg q[29];
t q[48];
cx q[48], q[12];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[92] = measure q[48];
if (c[92]) { cz q[12], q[29]; }
if (c[92]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[30], q[48];
cx q[48], q[11];
cx q[48], q[30];
tdg q[11];
tdg q[30];
t q[48];
cx q[48], q[11];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[93] = measure q[48];
if (c[93]) { cz q[11], q[30]; }
if (c[93]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[31], q[48];
cx q[48], q[10];
cx q[48], q[31];
tdg q[10];
tdg q[31];
t q[48];
cx q[48], q[10];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[94] = measure q[48];
if (c[94]) { cz q[10], q[31]; }
if (c[94]) { x q[48]; }
h q[42];
t q[42];
cx q[15], q[42];
cx q[27], q[42];
cx q[42], q[15];
cx q[42], q[27];
tdg q[15];
tdg q[27];
t q[42];
cx q[42], q[15];
cx q[42], q[27];
h q[42];
s q[42];
h q[48];
t q[48];
cx q[14], q[48];
cx q[28], q[48];
cx q[48], q[14];
cx q[48], q[28];
tdg q[14];
tdg q[28];
t q[48];
cx q[48], q[14];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[95] = measure q[48];
if (c[95]) { cz q[14], q[28]; }
if (c[95]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[29], q[48];
cx q[48], q[13];
cx q[48], q[29];
tdg q[13];
tdg q[29];
t q[48];
cx q[48], q[13];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[96] = measure q[48];
if (c[96]) { cz q[13], q[29]; }
if (c[96]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[30], q[48];
cx q[48], q[12];
cx q[48], q[30];
tdg q[12];
tdg q[30];
t q[48];
cx q[48], q[12];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[97] = measure q[48];
if (c[97]) { cz q[12], q[30]; }
if (c[97]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[31], q[48];
cx q[48], q[11];
cx q[48], q[31];
tdg q[11];
tdg q[31];
t q[48];
cx q[48], q[11];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[98] = measure q[48];
if (c[98]) { cz q[11], q[31]; }
if (c[98]) { x q[48]; }
h q[43];
t q[43];
cx q[15], q[43];
cx q[28], q[43];
cx q[43], q[15];
cx q[43], q[28];
tdg q[15];
tdg q[28];
t q[43];
cx q[43], q[15];
cx q[43], q[28];
h q[43];
s q[43];
h q[48];
t q[48];
cx q[14], q[48];
cx q[29], q[48];
cx q[48], q[14];
cx q[48], q[29];
tdg q[14];
tdg q[29];
t q[48];
cx q[48], q[14];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[99] = measure q[48];
if (c[99]) { cz q[14], q[29]; }
if (c[99]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[30], q[48];
cx q[48], q[13];
cx q[48], q[30];
tdg q[13];
tdg q[30];
t q[48];
cx q[48], q[13];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[100] = measure q[48];
if (c[100]) { cz q[13], q[30]; }
if (c[100]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[31], q[48];
cx q[48], q[12];
cx q[48], q[31];
tdg q[12];
tdg q[31];
t q[48];
cx q[48], q[12];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[101] = measure q[48];
if (c[101]) { cz q[12], q[31]; }
if (c[101]) { x q[48]; }
h q[44];
t q[44];
cx q[15], q[44];
cx q[29], q[44];
cx q[44], q[15];
cx q[44], q[29];
tdg q[15];
tdg q[29];
t q[44];
cx q[44], q[15];
cx q[44], q[29];
h q[44];
s q[44];
h q[48];
t q[48];
cx q[14], q[48];
cx q[30], q[48];
cx q[48], q[14];
cx q[48], q[30];
tdg q[14];
tdg q[30];
t q[48];
cx q[48], q[14];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[102] = measure q[48];
if (c[102]) { cz q[14], q[30]; }
if (c[102]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[31], q[48];
cx q[48], q[13];
cx q[48], q[31];
tdg q[13];
tdg q[31];
t q[48];
cx q[48], q[13];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[103] = measure q[48];
if (c[103]) { cz q[13], q[31]; }
if (c[103]) { x q[48]; }
h q[45];
t q[45];
cx q[15], q[45];
cx q[30], q[45];
cx q[45], q[15];
cx q[45], q[30];
tdg q[15];
tdg q[30];
t q[45];
cx q[45], q[15];
cx q[45], q[30];
h q[45];
s q[45];
h q[48];
t q[48];
cx q[14], q[48];
cx q[31], q[48];
cx q[48], q[14];
cx q[48], q[31];
tdg q[14];
tdg q[31];
t q[48];
cx q[48], q[14];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[104] = measure q[48];
if (c[104]) { cz q[14], q[31]; }
if (c[104]) { x q[48]; }
h q[46];
t q[46];
cx q[15], q[46];
cx q[31], q[46];
cx q[46], q[15];
cx q[46], q[31];
tdg q[15];
tdg q[31];
t q[46];
cx q[46], q[15];
cx q[46], q[31];
h q[46];
s q[46];
cx q[46], q[35];
cx q[46], q[33];
cx q[46], q[32];
cx q[45], q[34];
cx q[45], q[32];
cx q[45], q[47];
cx q[44], q[33];
cx q[44], q[47];
cx q[44], q[46];
cx q[43], q[32];
cx q[43], q[46];
cx q[43], q[45];
cx q[42], q[47];
cx q[42], q[45];
cx q[42], q[44];
cx q[41], q[46];
cx q[41], q[44];
cx q[41], q[43];
cx q[40], q[45];
cx q[40], q[43];
cx q[40], q[42];
cx q[39], q[44];
cx q[39], q[42];
cx q[39], q[41];
cx q[38], q[43];
cx q[38], q[41];
cx q[38], q[40];
cx q[37], q[42];
cx q[37], q[40];
cx q[37], q[39];
cx q[36], q[41];
cx q[36], q[39];
cx q[36], q[38];
cx q[35], q[40];
cx q[35], q[38];
cx q[35], q[37];
cx q[34], q[39];
cx q[34], q[37];
cx q[34], q[36];
cx q[33], q[38];
cx q[33], q[36];
cx q[33], q[35];
cx q[32], q[37];
cx q[32], q[35];
cx q[32], q[34];
h q[48];
t q[48];
cx q[15], q[48];
cx q[16], q[48];
cx q[48], q[15];
cx q[48], q[16];
tdg q[15];
tdg q[16];
t q[48];
cx q[48], q[15];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[105] = measure q[48];
if (c[105]) { cz q[15], q[16]; }
if (c[105]) { x q[48]; }
h q[48];
t q[48];
cx q[14], q[48];
cx q[17], q[48];
cx q[48], q[14];
cx q[48], q[17];
tdg q[14];
tdg q[17];
t q[48];
cx q[48], q[14];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[106] = measure q[48];
if (c[106]) { cz q[14], q[17]; }
if (c[106]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[18], q[48];
cx q[48], q[13];
cx q[48], q[18];
tdg q[13];
tdg q[18];
t q[48];
cx q[48], q[13];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[107] = measure q[48];
if (c[107]) { cz q[13], q[18]; }
if (c[107]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[19], q[48];
cx q[48], q[12];
cx q[48], q[19];
tdg q[12];
tdg q[19];
t q[48];
cx q[48], q[12];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[108] = measure q[48];
if (c[108]) { cz q[12], q[19]; }
if (c[108]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[20], q[48];
cx q[48], q[11];
cx q[48], q[20];
tdg q[11];
tdg q[20];
t q[48];
cx q[48], q[11];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[109] = measure q[48];
if (c[109]) { cz q[11], q[20]; }
if (c[109]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[21], q[48];
cx q[48], q[10];
cx q[48], q[21];
tdg q[10];
tdg q[21];
t q[48];
cx q[48], q[10];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[110] = measure q[48];
if (c[110]) { cz q[10], q[21]; }
if (c[110]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[22], q[48];
cx q[48], q[9];
cx q[48], q[22];
tdg q[9];
tdg q[22];
t q[48];
cx q[48], q[9];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[111] = measure q[48];
if (c[111]) { cz q[9], q[22]; }
if (c[111]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[23], q[48];
cx q[48], q[8];
cx q[48], q[23];
tdg q[8];
tdg q[23];
t q[48];
cx q[48], q[8];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[112] = measure q[48];
if (c[112]) { cz q[8], q[23]; }
if (c[112]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[24], q[48];
cx q[48], q[7];
cx q[48], q[24];
tdg q[7];
tdg q[24];
t q[48];
cx q[48], q[7];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[113] = measure q[48];
if (c[113]) { cz q[7], q[24]; }
if (c[113]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[25], q[48];
cx q[48], q[6];
cx q[48], q[25];
tdg q[6];
tdg q[25];
t q[48];
cx q[48], q[6];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[114] = measure q[48];
if (c[114]) { cz q[6], q[25]; }
if (c[114]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[26], q[48];
cx q[48], q[5];
cx q[48], q[26];
tdg q[5];
tdg q[26];
t q[48];
cx q[48], q[5];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[115] = measure q[48];
if (c[115]) { cz q[5], q[26]; }
if (c[115]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[27], q[48];
cx q[48], q[4];
cx q[48], q[27];
tdg q[4];
tdg q[27];
t q[48];
cx q[48], q[4];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[116] = measure q[48];
if (c[116]) { cz q[4], q[27]; }
if (c[116]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[28], q[48];
cx q[48], q[3];
cx q[48], q[28];
tdg q[3];
tdg q[28];
t q[48];
cx q[48], q[3];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[117] = measure q[48];
if (c[117]) { cz q[3], q[28]; }
if (c[117]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[29], q[48];
cx q[48], q[2];
cx q[48], q[29];
tdg q[2];
tdg q[29];
t q[48];
cx q[48], q[2];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[118] = measure q[48];
if (c[118]) { cz q[2], q[29]; }
if (c[118]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[30], q[48];
cx q[48], q[1];
cx q[48], q[30];
tdg q[1];
tdg q[30];
t q[48];
cx q[48], q[1];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[119] = measure q[48];
if (c[119]) { cz q[1], q[30]; }
if (c[119]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[31], q[48];
cx q[48], q[0];
cx q[48], q[31];
tdg q[0];
tdg q[31];
t q[48];
cx q[48], q[0];
cx q[48], q[31];
h q[48];
s q[48];
cx q[48], q[47];
h q[48];
c[120] = measure q[48];
if (c[120]) { cz q[0], q[31]; }
if (c[120]) { x q[48]; }
h q[48];
t q[48];
cx q[14], q[48];
cx q[16], q[48];
cx q[48], q[14];
cx q[48], q[16];
tdg q[14];
tdg q[16];
t q[48];
cx q[48], q[14];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[121] = measure q[48];
if (c[121]) { cz q[14], q[16]; }
if (c[121]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[17], q[48];
cx q[48], q[13];
cx q[48], q[17];
tdg q[13];
tdg q[17];
t q[48];
cx q[48], q[13];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[122] = measure q[48];
if (c[122]) { cz q[13], q[17]; }
if (c[122]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[18], q[48];
cx q[48], q[12];
cx q[48], q[18];
tdg q[12];
tdg q[18];
t q[48];
cx q[48], q[12];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[123] = measure q[48];
if (c[123]) { cz q[12], q[18]; }
if (c[123]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[19], q[48];
cx q[48], q[11];
cx q[48], q[19];
tdg q[11];
tdg q[19];
t q[48];
cx q[48], q[11];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[124] = measure q[48];
if (c[124]) { cz q[11], q[19]; }
if (c[124]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[20], q[48];
cx q[48], q[10];
cx q[48], q[20];
tdg q[10];
tdg q[20];
t q[48];
cx q[48], q[10];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[125] = measure q[48];
if (c[125]) { cz q[10], q[20]; }
if (c[125]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[21], q[48];
cx q[48], q[9];
cx q[48], q[21];
tdg q[9];
tdg q[21];
t q[48];
cx q[48], q[9];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[126] = measure q[48];
if (c[126]) { cz q[9], q[21]; }
if (c[126]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[22], q[48];
cx q[48], q[8];
cx q[48], q[22];
tdg q[8];
tdg q[22];
t q[48];
cx q[48], q[8];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[127] = measure q[48];
if (c[127]) { cz q[8], q[22]; }
if (c[127]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[23], q[48];
cx q[48], q[7];
cx q[48], q[23];
tdg q[7];
tdg q[23];
t q[48];
cx q[48], q[7];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[128] = measure q[48];
if (c[128]) { cz q[7], q[23]; }
if (c[128]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[24], q[48];
cx q[48], q[6];
cx q[48], q[24];
tdg q[6];
tdg q[24];
t q[48];
cx q[48], q[6];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[129] = measure q[48];
if (c[129]) { cz q[6], q[24]; }
if (c[129]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[25], q[48];
cx q[48], q[5];
cx q[48], q[25];
tdg q[5];
tdg q[25];
t q[48];
cx q[48], q[5];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[130] = measure q[48];
if (c[130]) { cz q[5], q[25]; }
if (c[130]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[26], q[48];
cx q[48], q[4];
cx q[48], q[26];
tdg q[4];
tdg q[26];
t q[48];
cx q[48], q[4];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[131] = measure q[48];
if (c[131]) { cz q[4], q[26]; }
if (c[131]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[27], q[48];
cx q[48], q[3];
cx q[48], q[27];
tdg q[3];
tdg q[27];
t q[48];
cx q[48], q[3];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[132] = measure q[48];
if (c[132]) { cz q[3], q[27]; }
if (c[132]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[28], q[48];
cx q[48], q[2];
cx q[48], q[28];
tdg q[2];
tdg q[28];
t q[48];
cx q[48], q[2];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[133] = measure q[48];
if (c[133]) { cz q[2], q[28]; }
if (c[133]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[29], q[48];
cx q[48], q[1];
cx q[48], q[29];
tdg q[1];
tdg q[29];
t q[48];
cx q[48], q[1];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[134] = measure q[48];
if (c[134]) { cz q[1], q[29]; }
if (c[134]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[30], q[48];
cx q[48], q[0];
cx q[48], q[30];
tdg q[0];
tdg q[30];
t q[48];
cx q[48], q[0];
cx q[48], q[30];
h q[48];
s q[48];
cx q[48], q[46];
h q[48];
c[135] = measure q[48];
if (c[135]) { cz q[0], q[30]; }
if (c[135]) { x q[48]; }
h q[48];
t q[48];
cx q[13], q[48];
cx q[16], q[48];
cx q[48], q[13];
cx q[48], q[16];
tdg q[13];
tdg q[16];
t q[48];
cx q[48], q[13];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[136] = measure q[48];
if (c[136]) { cz q[13], q[16]; }
if (c[136]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[17], q[48];
cx q[48], q[12];
cx q[48], q[17];
tdg q[12];
tdg q[17];
t q[48];
cx q[48], q[12];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[137] = measure q[48];
if (c[137]) { cz q[12], q[17]; }
if (c[137]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[18], q[48];
cx q[48], q[11];
cx q[48], q[18];
tdg q[11];
tdg q[18];
t q[48];
cx q[48], q[11];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[138] = measure q[48];
if (c[138]) { cz q[11], q[18]; }
if (c[138]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[19], q[48];
cx q[48], q[10];
cx q[48], q[19];
tdg q[10];
tdg q[19];
t q[48];
cx q[48], q[10];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[139] = measure q[48];
if (c[139]) { cz q[10], q[19]; }
if (c[139]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[20], q[48];
cx q[48], q[9];
cx q[48], q[20];
tdg q[9];
tdg q[20];
t q[48];
cx q[48], q[9];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[140] = measure q[48];
if (c[140]) { cz q[9], q[20]; }
if (c[140]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[21], q[48];
cx q[48], q[8];
cx q[48], q[21];
tdg q[8];
tdg q[21];
t q[48];
cx q[48], q[8];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[141] = measure q[48];
if (c[141]) { cz q[8], q[21]; }
if (c[141]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[22], q[48];
cx q[48], q[7];
cx q[48], q[22];
tdg q[7];
tdg q[22];
t q[48];
cx q[48], q[7];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[142] = measure q[48];
if (c[142]) { cz q[7], q[22]; }
if (c[142]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[23], q[48];
cx q[48], q[6];
cx q[48], q[23];
tdg q[6];
tdg q[23];
t q[48];
cx q[48], q[6];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[143] = measure q[48];
if (c[143]) { cz q[6], q[23]; }
if (c[143]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[24], q[48];
cx q[48], q[5];
cx q[48], q[24];
tdg q[5];
tdg q[24];
t q[48];
cx q[48], q[5];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[144] = measure q[48];
if (c[144]) { cz q[5], q[24]; }
if (c[144]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[25], q[48];
cx q[48], q[4];
cx q[48], q[25];
tdg q[4];
tdg q[25];
t q[48];
cx q[48], q[4];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[145] = measure q[48];
if (c[145]) { cz q[4], q[25]; }
if (c[145]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[26], q[48];
cx q[48], q[3];
cx q[48], q[26];
tdg q[3];
tdg q[26];
t q[48];
cx q[48], q[3];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[146] = measure q[48];
if (c[146]) { cz q[3], q[26]; }
if (c[146]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[27], q[48];
cx q[48], q[2];
cx q[48], q[27];
tdg q[2];
tdg q[27];
t q[48];
cx q[48], q[2];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[147] = measure q[48];
if (c[147]) { cz q[2], q[27]; }
if (c[147]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[28], q[48];
cx q[48], q[1];
cx q[48], q[28];
tdg q[1];
tdg q[28];
t q[48];
cx q[48], q[1];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[148] = measure q[48];
if (c[148]) { cz q[1], q[28]; }
if (c[148]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[29], q[48];
cx q[48], q[0];
cx q[48], q[29];
tdg q[0];
tdg q[29];
t q[48];
cx q[48], q[0];
cx q[48], q[29];
h q[48];
s q[48];
cx q[48], q[45];
h q[48];
c[149] = measure q[48];
if (c[149]) { cz q[0], q[29]; }
if (c[149]) { x q[48]; }
h q[48];
t q[48];
cx q[12], q[48];
cx q[16], q[48];
cx q[48], q[12];
cx q[48], q[16];
tdg q[12];
tdg q[16];
t q[48];
cx q[48], q[12];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[150] = measure q[48];
if (c[150]) { cz q[12], q[16]; }
if (c[150]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[17], q[48];
cx q[48], q[11];
cx q[48], q[17];
tdg q[11];
tdg q[17];
t q[48];
cx q[48], q[11];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[151] = measure q[48];
if (c[151]) { cz q[11], q[17]; }
if (c[151]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[18], q[48];
cx q[48], q[10];
cx q[48], q[18];
tdg q[10];
tdg q[18];
t q[48];
cx q[48], q[10];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[152] = measure q[48];
if (c[152]) { cz q[10], q[18]; }
if (c[152]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[19], q[48];
cx q[48], q[9];
cx q[48], q[19];
tdg q[9];
tdg q[19];
t q[48];
cx q[48], q[9];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[153] = measure q[48];
if (c[153]) { cz q[9], q[19]; }
if (c[153]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[20], q[48];
cx q[48], q[8];
cx q[48], q[20];
tdg q[8];
tdg q[20];
t q[48];
cx q[48], q[8];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[154] = measure q[48];
if (c[154]) { cz q[8], q[20]; }
if (c[154]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[21], q[48];
cx q[48], q[7];
cx q[48], q[21];
tdg q[7];
tdg q[21];
t q[48];
cx q[48], q[7];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[155] = measure q[48];
if (c[155]) { cz q[7], q[21]; }
if (c[155]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[22], q[48];
cx q[48], q[6];
cx q[48], q[22];
tdg q[6];
tdg q[22];
t q[48];
cx q[48], q[6];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[156] = measure q[48];
if (c[156]) { cz q[6], q[22]; }
if (c[156]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[23], q[48];
cx q[48], q[5];
cx q[48], q[23];
tdg q[5];
tdg q[23];
t q[48];
cx q[48], q[5];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[157] = measure q[48];
if (c[157]) { cz q[5], q[23]; }
if (c[157]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[24], q[48];
cx q[48], q[4];
cx q[48], q[24];
tdg q[4];
tdg q[24];
t q[48];
cx q[48], q[4];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[158] = measure q[48];
if (c[158]) { cz q[4], q[24]; }
if (c[158]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[25], q[48];
cx q[48], q[3];
cx q[48], q[25];
tdg q[3];
tdg q[25];
t q[48];
cx q[48], q[3];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[159] = measure q[48];
if (c[159]) { cz q[3], q[25]; }
if (c[159]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[26], q[48];
cx q[48], q[2];
cx q[48], q[26];
tdg q[2];
tdg q[26];
t q[48];
cx q[48], q[2];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[160] = measure q[48];
if (c[160]) { cz q[2], q[26]; }
if (c[160]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[27], q[48];
cx q[48], q[1];
cx q[48], q[27];
tdg q[1];
tdg q[27];
t q[48];
cx q[48], q[1];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[161] = measure q[48];
if (c[161]) { cz q[1], q[27]; }
if (c[161]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[28], q[48];
cx q[48], q[0];
cx q[48], q[28];
tdg q[0];
tdg q[28];
t q[48];
cx q[48], q[0];
cx q[48], q[28];
h q[48];
s q[48];
cx q[48], q[44];
h q[48];
c[162] = measure q[48];
if (c[162]) { cz q[0], q[28]; }
if (c[162]) { x q[48]; }
h q[48];
t q[48];
cx q[11], q[48];
cx q[16], q[48];
cx q[48], q[11];
cx q[48], q[16];
tdg q[11];
tdg q[16];
t q[48];
cx q[48], q[11];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[163] = measure q[48];
if (c[163]) { cz q[11], q[16]; }
if (c[163]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[17], q[48];
cx q[48], q[10];
cx q[48], q[17];
tdg q[10];
tdg q[17];
t q[48];
cx q[48], q[10];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[164] = measure q[48];
if (c[164]) { cz q[10], q[17]; }
if (c[164]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[18], q[48];
cx q[48], q[9];
cx q[48], q[18];
tdg q[9];
tdg q[18];
t q[48];
cx q[48], q[9];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[165] = measure q[48];
if (c[165]) { cz q[9], q[18]; }
if (c[165]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[19], q[48];
cx q[48], q[8];
cx q[48], q[19];
tdg q[8];
tdg q[19];
t q[48];
cx q[48], q[8];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[166] = measure q[48];
if (c[166]) { cz q[8], q[19]; }
if (c[166]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[20], q[48];
cx q[48], q[7];
cx q[48], q[20];
tdg q[7];
tdg q[20];
t q[48];
cx q[48], q[7];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[167] = measure q[48];
if (c[167]) { cz q[7], q[20]; }
if (c[167]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[21], q[48];
cx q[48], q[6];
cx q[48], q[21];
tdg q[6];
tdg q[21];
t q[48];
cx q[48], q[6];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[168] = measure q[48];
if (c[168]) { cz q[6], q[21]; }
if (c[168]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[22], q[48];
cx q[48], q[5];
cx q[48], q[22];
tdg q[5];
tdg q[22];
t q[48];
cx q[48], q[5];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[169] = measure q[48];
if (c[169]) { cz q[5], q[22]; }
if (c[169]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[23], q[48];
cx q[48], q[4];
cx q[48], q[23];
tdg q[4];
tdg q[23];
t q[48];
cx q[48], q[4];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[170] = measure q[48];
if (c[170]) { cz q[4], q[23]; }
if (c[170]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[24], q[48];
cx q[48], q[3];
cx q[48], q[24];
tdg q[3];
tdg q[24];
t q[48];
cx q[48], q[3];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[171] = measure q[48];
if (c[171]) { cz q[3], q[24]; }
if (c[171]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[25], q[48];
cx q[48], q[2];
cx q[48], q[25];
tdg q[2];
tdg q[25];
t q[48];
cx q[48], q[2];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[172] = measure q[48];
if (c[172]) { cz q[2], q[25]; }
if (c[172]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[26], q[48];
cx q[48], q[1];
cx q[48], q[26];
tdg q[1];
tdg q[26];
t q[48];
cx q[48], q[1];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[173] = measure q[48];
if (c[173]) { cz q[1], q[26]; }
if (c[173]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[27], q[48];
cx q[48], q[0];
cx q[48], q[27];
tdg q[0];
tdg q[27];
t q[48];
cx q[48], q[0];
cx q[48], q[27];
h q[48];
s q[48];
cx q[48], q[43];
h q[48];
c[174] = measure q[48];
if (c[174]) { cz q[0], q[27]; }
if (c[174]) { x q[48]; }
h q[48];
t q[48];
cx q[10], q[48];
cx q[16], q[48];
cx q[48], q[10];
cx q[48], q[16];
tdg q[10];
tdg q[16];
t q[48];
cx q[48], q[10];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[175] = measure q[48];
if (c[175]) { cz q[10], q[16]; }
if (c[175]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[17], q[48];
cx q[48], q[9];
cx q[48], q[17];
tdg q[9];
tdg q[17];
t q[48];
cx q[48], q[9];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[176] = measure q[48];
if (c[176]) { cz q[9], q[17]; }
if (c[176]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[18], q[48];
cx q[48], q[8];
cx q[48], q[18];
tdg q[8];
tdg q[18];
t q[48];
cx q[48], q[8];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[177] = measure q[48];
if (c[177]) { cz q[8], q[18]; }
if (c[177]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[19], q[48];
cx q[48], q[7];
cx q[48], q[19];
tdg q[7];
tdg q[19];
t q[48];
cx q[48], q[7];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[178] = measure q[48];
if (c[178]) { cz q[7], q[19]; }
if (c[178]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[20], q[48];
cx q[48], q[6];
cx q[48], q[20];
tdg q[6];
tdg q[20];
t q[48];
cx q[48], q[6];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[179] = measure q[48];
if (c[179]) { cz q[6], q[20]; }
if (c[179]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[21], q[48];
cx q[48], q[5];
cx q[48], q[21];
tdg q[5];
tdg q[21];
t q[48];
cx q[48], q[5];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[180] = measure q[48];
if (c[180]) { cz q[5], q[21]; }
if (c[180]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[22], q[48];
cx q[48], q[4];
cx q[48], q[22];
tdg q[4];
tdg q[22];
t q[48];
cx q[48], q[4];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[181] = measure q[48];
if (c[181]) { cz q[4], q[22]; }
if (c[181]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[23], q[48];
cx q[48], q[3];
cx q[48], q[23];
tdg q[3];
tdg q[23];
t q[48];
cx q[48], q[3];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[182] = measure q[48];
if (c[182]) { cz q[3], q[23]; }
if (c[182]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[24], q[48];
cx q[48], q[2];
cx q[48], q[24];
tdg q[2];
tdg q[24];
t q[48];
cx q[48], q[2];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[183] = measure q[48];
if (c[183]) { cz q[2], q[24]; }
if (c[183]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[25], q[48];
cx q[48], q[1];
cx q[48], q[25];
tdg q[1];
tdg q[25];
t q[48];
cx q[48], q[1];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[184] = measure q[48];
if (c[184]) { cz q[1], q[25]; }
if (c[184]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[26], q[48];
cx q[48], q[0];
cx q[48], q[26];
tdg q[0];
tdg q[26];
t q[48];
cx q[48], q[0];
cx q[48], q[26];
h q[48];
s q[48];
cx q[48], q[42];
h q[48];
c[185] = measure q[48];
if (c[185]) { cz q[0], q[26]; }
if (c[185]) { x q[48]; }
h q[48];
t q[48];
cx q[9], q[48];
cx q[16], q[48];
cx q[48], q[9];
cx q[48], q[16];
tdg q[9];
tdg q[16];
t q[48];
cx q[48], q[9];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[186] = measure q[48];
if (c[186]) { cz q[9], q[16]; }
if (c[186]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[17], q[48];
cx q[48], q[8];
cx q[48], q[17];
tdg q[8];
tdg q[17];
t q[48];
cx q[48], q[8];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[187] = measure q[48];
if (c[187]) { cz q[8], q[17]; }
if (c[187]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[18], q[48];
cx q[48], q[7];
cx q[48], q[18];
tdg q[7];
tdg q[18];
t q[48];
cx q[48], q[7];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[188] = measure q[48];
if (c[188]) { cz q[7], q[18]; }
if (c[188]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[19], q[48];
cx q[48], q[6];
cx q[48], q[19];
tdg q[6];
tdg q[19];
t q[48];
cx q[48], q[6];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[189] = measure q[48];
if (c[189]) { cz q[6], q[19]; }
if (c[189]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[20], q[48];
cx q[48], q[5];
cx q[48], q[20];
tdg q[5];
tdg q[20];
t q[48];
cx q[48], q[5];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[190] = measure q[48];
if (c[190]) { cz q[5], q[20]; }
if (c[190]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[21], q[48];
cx q[48], q[4];
cx q[48], q[21];
tdg q[4];
tdg q[21];
t q[48];
cx q[48], q[4];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[191] = measure q[48];
if (c[191]) { cz q[4], q[21]; }
if (c[191]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[22], q[48];
cx q[48], q[3];
cx q[48], q[22];
tdg q[3];
tdg q[22];
t q[48];
cx q[48], q[3];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[192] = measure q[48];
if (c[192]) { cz q[3], q[22]; }
if (c[192]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[23], q[48];
cx q[48], q[2];
cx q[48], q[23];
tdg q[2];
tdg q[23];
t q[48];
cx q[48], q[2];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[193] = measure q[48];
if (c[193]) { cz q[2], q[23]; }
if (c[193]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[24], q[48];
cx q[48], q[1];
cx q[48], q[24];
tdg q[1];
tdg q[24];
t q[48];
cx q[48], q[1];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[194] = measure q[48];
if (c[194]) { cz q[1], q[24]; }
if (c[194]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[25], q[48];
cx q[48], q[0];
cx q[48], q[25];
tdg q[0];
tdg q[25];
t q[48];
cx q[48], q[0];
cx q[48], q[25];
h q[48];
s q[48];
cx q[48], q[41];
h q[48];
c[195] = measure q[48];
if (c[195]) { cz q[0], q[25]; }
if (c[195]) { x q[48]; }
h q[48];
t q[48];
cx q[8], q[48];
cx q[16], q[48];
cx q[48], q[8];
cx q[48], q[16];
tdg q[8];
tdg q[16];
t q[48];
cx q[48], q[8];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[196] = measure q[48];
if (c[196]) { cz q[8], q[16]; }
if (c[196]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[17], q[48];
cx q[48], q[7];
cx q[48], q[17];
tdg q[7];
tdg q[17];
t q[48];
cx q[48], q[7];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[197] = measure q[48];
if (c[197]) { cz q[7], q[17]; }
if (c[197]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[18], q[48];
cx q[48], q[6];
cx q[48], q[18];
tdg q[6];
tdg q[18];
t q[48];
cx q[48], q[6];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[198] = measure q[48];
if (c[198]) { cz q[6], q[18]; }
if (c[198]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[19], q[48];
cx q[48], q[5];
cx q[48], q[19];
tdg q[5];
tdg q[19];
t q[48];
cx q[48], q[5];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[199] = measure q[48];
if (c[199]) { cz q[5], q[19]; }
if (c[199]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[20], q[48];
cx q[48], q[4];
cx q[48], q[20];
tdg q[4];
tdg q[20];
t q[48];
cx q[48], q[4];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[200] = measure q[48];
if (c[200]) { cz q[4], q[20]; }
if (c[200]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[21], q[48];
cx q[48], q[3];
cx q[48], q[21];
tdg q[3];
tdg q[21];
t q[48];
cx q[48], q[3];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[201] = measure q[48];
if (c[201]) { cz q[3], q[21]; }
if (c[201]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[22], q[48];
cx q[48], q[2];
cx q[48], q[22];
tdg q[2];
tdg q[22];
t q[48];
cx q[48], q[2];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[202] = measure q[48];
if (c[202]) { cz q[2], q[22]; }
if (c[202]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[23], q[48];
cx q[48], q[1];
cx q[48], q[23];
tdg q[1];
tdg q[23];
t q[48];
cx q[48], q[1];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[203] = measure q[48];
if (c[203]) { cz q[1], q[23]; }
if (c[203]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[24], q[48];
cx q[48], q[0];
cx q[48], q[24];
tdg q[0];
tdg q[24];
t q[48];
cx q[48], q[0];
cx q[48], q[24];
h q[48];
s q[48];
cx q[48], q[40];
h q[48];
c[204] = measure q[48];
if (c[204]) { cz q[0], q[24]; }
if (c[204]) { x q[48]; }
h q[48];
t q[48];
cx q[7], q[48];
cx q[16], q[48];
cx q[48], q[7];
cx q[48], q[16];
tdg q[7];
tdg q[16];
t q[48];
cx q[48], q[7];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[205] = measure q[48];
if (c[205]) { cz q[7], q[16]; }
if (c[205]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[17], q[48];
cx q[48], q[6];
cx q[48], q[17];
tdg q[6];
tdg q[17];
t q[48];
cx q[48], q[6];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[206] = measure q[48];
if (c[206]) { cz q[6], q[17]; }
if (c[206]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[18], q[48];
cx q[48], q[5];
cx q[48], q[18];
tdg q[5];
tdg q[18];
t q[48];
cx q[48], q[5];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[207] = measure q[48];
if (c[207]) { cz q[5], q[18]; }
if (c[207]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[19], q[48];
cx q[48], q[4];
cx q[48], q[19];
tdg q[4];
tdg q[19];
t q[48];
cx q[48], q[4];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[208] = measure q[48];
if (c[208]) { cz q[4], q[19]; }
if (c[208]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[20], q[48];
cx q[48], q[3];
cx q[48], q[20];
tdg q[3];
tdg q[20];
t q[48];
cx q[48], q[3];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[209] = measure q[48];
if (c[209]) { cz q[3], q[20]; }
if (c[209]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[21], q[48];
cx q[48], q[2];
cx q[48], q[21];
tdg q[2];
tdg q[21];
t q[48];
cx q[48], q[2];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[210] = measure q[48];
if (c[210]) { cz q[2], q[21]; }
if (c[210]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[22], q[48];
cx q[48], q[1];
cx q[48], q[22];
tdg q[1];
tdg q[22];
t q[48];
cx q[48], q[1];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[211] = measure q[48];
if (c[211]) { cz q[1], q[22]; }
if (c[211]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[23], q[48];
cx q[48], q[0];
cx q[48], q[23];
tdg q[0];
tdg q[23];
t q[48];
cx q[48], q[0];
cx q[48], q[23];
h q[48];
s q[48];
cx q[48], q[39];
h q[48];
c[212] = measure q[48];
if (c[212]) { cz q[0], q[23]; }
if (c[212]) { x q[48]; }
h q[48];
t q[48];
cx q[6], q[48];
cx q[16], q[48];
cx q[48], q[6];
cx q[48], q[16];
tdg q[6];
tdg q[16];
t q[48];
cx q[48], q[6];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[213] = measure q[48];
if (c[213]) { cz q[6], q[16]; }
if (c[213]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[17], q[48];
cx q[48], q[5];
cx q[48], q[17];
tdg q[5];
tdg q[17];
t q[48];
cx q[48], q[5];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[214] = measure q[48];
if (c[214]) { cz q[5], q[17]; }
if (c[214]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[18], q[48];
cx q[48], q[4];
cx q[48], q[18];
tdg q[4];
tdg q[18];
t q[48];
cx q[48], q[4];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[215] = measure q[48];
if (c[215]) { cz q[4], q[18]; }
if (c[215]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[19], q[48];
cx q[48], q[3];
cx q[48], q[19];
tdg q[3];
tdg q[19];
t q[48];
cx q[48], q[3];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[216] = measure q[48];
if (c[216]) { cz q[3], q[19]; }
if (c[216]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[20], q[48];
cx q[48], q[2];
cx q[48], q[20];
tdg q[2];
tdg q[20];
t q[48];
cx q[48], q[2];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[217] = measure q[48];
if (c[217]) { cz q[2], q[20]; }
if (c[217]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[21], q[48];
cx q[48], q[1];
cx q[48], q[21];
tdg q[1];
tdg q[21];
t q[48];
cx q[48], q[1];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[218] = measure q[48];
if (c[218]) { cz q[1], q[21]; }
if (c[218]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[22], q[48];
cx q[48], q[0];
cx q[48], q[22];
tdg q[0];
tdg q[22];
t q[48];
cx q[48], q[0];
cx q[48], q[22];
h q[48];
s q[48];
cx q[48], q[38];
h q[48];
c[219] = measure q[48];
if (c[219]) { cz q[0], q[22]; }
if (c[219]) { x q[48]; }
h q[48];
t q[48];
cx q[5], q[48];
cx q[16], q[48];
cx q[48], q[5];
cx q[48], q[16];
tdg q[5];
tdg q[16];
t q[48];
cx q[48], q[5];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[220] = measure q[48];
if (c[220]) { cz q[5], q[16]; }
if (c[220]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[17], q[48];
cx q[48], q[4];
cx q[48], q[17];
tdg q[4];
tdg q[17];
t q[48];
cx q[48], q[4];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[221] = measure q[48];
if (c[221]) { cz q[4], q[17]; }
if (c[221]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[18], q[48];
cx q[48], q[3];
cx q[48], q[18];
tdg q[3];
tdg q[18];
t q[48];
cx q[48], q[3];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[222] = measure q[48];
if (c[222]) { cz q[3], q[18]; }
if (c[222]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[19], q[48];
cx q[48], q[2];
cx q[48], q[19];
tdg q[2];
tdg q[19];
t q[48];
cx q[48], q[2];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[223] = measure q[48];
if (c[223]) { cz q[2], q[19]; }
if (c[223]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[20], q[48];
cx q[48], q[1];
cx q[48], q[20];
tdg q[1];
tdg q[20];
t q[48];
cx q[48], q[1];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[224] = measure q[48];
if (c[224]) { cz q[1], q[20]; }
if (c[224]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[21], q[48];
cx q[48], q[0];
cx q[48], q[21];
tdg q[0];
tdg q[21];
t q[48];
cx q[48], q[0];
cx q[48], q[21];
h q[48];
s q[48];
cx q[48], q[37];
h q[48];
c[225] = measure q[48];
if (c[225]) { cz q[0], q[21]; }
if (c[225]) { x q[48]; }
h q[48];
t q[48];
cx q[4], q[48];
cx q[16], q[48];
cx q[48], q[4];
cx q[48], q[16];
tdg q[4];
tdg q[16];
t q[48];
cx q[48], q[4];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[226] = measure q[48];
if (c[226]) { cz q[4], q[16]; }
if (c[226]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[17], q[48];
cx q[48], q[3];
cx q[48], q[17];
tdg q[3];
tdg q[17];
t q[48];
cx q[48], q[3];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[227] = measure q[48];
if (c[227]) { cz q[3], q[17]; }
if (c[227]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[18], q[48];
cx q[48], q[2];
cx q[48], q[18];
tdg q[2];
tdg q[18];
t q[48];
cx q[48], q[2];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[228] = measure q[48];
if (c[228]) { cz q[2], q[18]; }
if (c[228]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[19], q[48];
cx q[48], q[1];
cx q[48], q[19];
tdg q[1];
tdg q[19];
t q[48];
cx q[48], q[1];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[229] = measure q[48];
if (c[229]) { cz q[1], q[19]; }
if (c[229]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[20], q[48];
cx q[48], q[0];
cx q[48], q[20];
tdg q[0];
tdg q[20];
t q[48];
cx q[48], q[0];
cx q[48], q[20];
h q[48];
s q[48];
cx q[48], q[36];
h q[48];
c[230] = measure q[48];
if (c[230]) { cz q[0], q[20]; }
if (c[230]) { x q[48]; }
h q[48];
t q[48];
cx q[3], q[48];
cx q[16], q[48];
cx q[48], q[3];
cx q[48], q[16];
tdg q[3];
tdg q[16];
t q[48];
cx q[48], q[3];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[231] = measure q[48];
if (c[231]) { cz q[3], q[16]; }
if (c[231]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[17], q[48];
cx q[48], q[2];
cx q[48], q[17];
tdg q[2];
tdg q[17];
t q[48];
cx q[48], q[2];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[232] = measure q[48];
if (c[232]) { cz q[2], q[17]; }
if (c[232]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[18], q[48];
cx q[48], q[1];
cx q[48], q[18];
tdg q[1];
tdg q[18];
t q[48];
cx q[48], q[1];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[233] = measure q[48];
if (c[233]) { cz q[1], q[18]; }
if (c[233]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[19], q[48];
cx q[48], q[0];
cx q[48], q[19];
tdg q[0];
tdg q[19];
t q[48];
cx q[48], q[0];
cx q[48], q[19];
h q[48];
s q[48];
cx q[48], q[35];
h q[48];
c[234] = measure q[48];
if (c[234]) { cz q[0], q[19]; }
if (c[234]) { x q[48]; }
h q[48];
t q[48];
cx q[2], q[48];
cx q[16], q[48];
cx q[48], q[2];
cx q[48], q[16];
tdg q[2];
tdg q[16];
t q[48];
cx q[48], q[2];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[235] = measure q[48];
if (c[235]) { cz q[2], q[16]; }
if (c[235]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[17], q[48];
cx q[48], q[1];
cx q[48], q[17];
tdg q[1];
tdg q[17];
t q[48];
cx q[48], q[1];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[236] = measure q[48];
if (c[236]) { cz q[1], q[17]; }
if (c[236]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[18], q[48];
cx q[48], q[0];
cx q[48], q[18];
tdg q[0];
tdg q[18];
t q[48];
cx q[48], q[0];
cx q[48], q[18];
h q[48];
s q[48];
cx q[48], q[34];
h q[48];
c[237] = measure q[48];
if (c[237]) { cz q[0], q[18]; }
if (c[237]) { x q[48]; }
h q[48];
t q[48];
cx q[1], q[48];
cx q[16], q[48];
cx q[48], q[1];
cx q[48], q[16];
tdg q[1];
tdg q[16];
t q[48];
cx q[48], q[1];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[238] = measure q[48];
if (c[238]) { cz q[1], q[16]; }
if (c[238]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[17], q[48];
cx q[48], q[0];
cx q[48], q[17];
tdg q[0];
tdg q[17];
t q[48];
cx q[48], q[0];
cx q[48], q[17];
h q[48];
s q[48];
cx q[48], q[33];
h q[48];
c[239] = measure q[48];
if (c[239]) { cz q[0], q[17]; }
if (c[239]) { x q[48]; }
h q[48];
t q[48];
cx q[0], q[48];
cx q[16], q[48];
cx q[48], q[0];
cx q[48], q[16];
tdg q[0];
tdg q[16];
t q[48];
cx q[48], q[0];
cx q[48], q[16];
h q[48];
s q[48];
cx q[48], q[32];
h q[48];
c[240] = measure q[48];
if (c[240]) { cz q[0], q[16]; }
if (c[240]) { x q[48]; }
