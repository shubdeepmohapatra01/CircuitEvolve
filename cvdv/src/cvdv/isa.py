"""Instruction sets (L0 membership check).

PS_BS   phase-space ISA of Liu et al. (2407.10381) extended with beam splitters, the target ISA:
        qubit rotations + R, D, BS, CR, CP, CD.
GENESIS Genesis Table 2 (adds CBS and RB).
"""
QUBIT = {"h", "x", "y", "z", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "r"}
ARITY = {  # name -> (n_qubits, n_qumodes)
    **{g: (1, 0) for g in QUBIT},
    "R": (0, 1), "D": (0, 1), "BS": (0, 2), "CR": (1, 1), "CP": (1, 1), "CD": (1, 1),
    "CBS": (1, 2), "RB": (1, 1),
}
NPARAMS = {"h": 0, "x": 0, "y": 0, "z": 0, "s": 0, "sdg": 0, "t": 0, "tdg": 0, "rx": 1, "ry": 1,
           "rz": 1, "r": 2, "R": 1, "D": 1, "BS": 2, "CR": 1, "CP": 0, "CD": 1, "CBS": 2, "RB": 1}
PS_BS = QUBIT | {"R", "D", "BS", "CR", "CP", "CD"}
GENESIS = PS_BS | {"CBS", "RB"}


def check(ops, isa=PS_BS):
    """Return a list of violations (empty = OK)."""
    bad = []
    for i, o in enumerate(ops):
        if o.name not in isa:
            bad.append((i, f"gate {o.name} not in ISA"))
            continue
        nq, nm = ARITY[o.name]
        if len(o.qubits) != nq or len(o.qumodes) != nm or len(o.wires) != nq + nm:
            bad.append((i, f"{o.name}: wrong operands {o.wires}"))
        if len(set(o.wires)) != len(o.wires):
            bad.append((i, f"{o.name}: repeated operand"))
        if len(o.params) != NPARAMS[o.name]:
            bad.append((i, f"{o.name}: expected {NPARAMS[o.name]} params, got {len(o.params)}"))
        for p in o.params:
            z = complex(p)
            if z != z or abs(z) == float("inf"):
                bad.append((i, f"{o.name}: non-finite parameter"))
        if o.name not in ("D", "CD") and any(abs(complex(p).imag) > 1e-12 for p in o.params):
            bad.append((i, f"{o.name}: complex parameter"))
    return bad
