// 2-bit Cuccaro ripple-carry adder (Cuccaro et al. 2004), same MAJ/UMA gates as QASMBench adder_n10 (4-bit).
// Small ancilla-arm test circuit: 6 qubits, 4 Toffolis. b <- a + b, cout ^= carry.
OPENQASM 2.0;
include "qelib1.inc";
gate majority a,b,c { cx c,b; cx c,a; ccx a,b,c; }
gate unmaj a,b,c { ccx a,b,c; cx c,a; cx a,b; }
qreg cin[1];
qreg a[2];
qreg b[2];
qreg cout[1];
majority cin[0],b[0],a[0];
majority a[0],b[1],a[1];
cx a[1],cout[0];
unmaj a[0],b[1],a[1];
unmaj cin[0],b[0],a[0];
