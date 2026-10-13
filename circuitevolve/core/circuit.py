"""Clifford+Rz circuit object, QASM in/out, stage-1 inputs and windows.

Op format (shared with circuitevolve/blocks): (name, qubits_tuple, angle) with name in CORE_GATES; angle is a
float for rz, else None. Qubit 0 is the most significant matrix index (verify_block convention).

Inputs. The comparison protocol (skill bqskit-ft-reference-baseline) starts every method from the TKET
FullPeepholeOptimise output of the qseed circuit. `load_input(name)` takes the Baselines track's file
results/bqskit_baselines/stage1/inputs/<name>*.qasm when it exists, else runs the same TKET pass here
(blocks/classical.tket_optimise: FullPeepholeOptimise -> replace_implicit_wire_swaps ->
AutoRebase{CX,H,Rz} -> RemoveRedundancies) and records which one was used in `meta["source"]`.

Windows. A window is a convex piece of the circuit on <= 4 qubits and <= 40 ops: BQSKit QuickPartitioner(4)
blocks cut into consecutive runs of <= 40 ops (blocks/partition.partition). Concatenating the windows in
order reproduces the circuit exactly, so replacing one window's ops and re-concatenating is a valid
rewrite of the whole circuit.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from ..blocks import REPO
from ..blocks.circuit_io import classify_angle, emit_rz, ops_to_qasm, qasm_to_ops

CORE_GATES = frozenset({"h", "s", "sdg", "x", "z", "t", "tdg", "cx", "cz", "rz"})
STAGE1 = ("qft_8", "qpe_8", "qae_13", "heisenberg_6", "tfim_6", "hubbard_8", "qml_13", "hhl_8")
STAGE1_INPUTS = REPO / "results" / "bqskit_baselines" / "stage1" / "inputs"
WINDOW_QUBITS = 4
WINDOW_GATES = 40


def normalize(ops) -> list:
    """rz at a multiple of pi/4 (within circuit_io.ANGLE_TOL) -> Clifford/T gates; everything else kept."""
    out: list = []
    for g, qs, a in ops:
        if g == "rz":
            emit_rz(out, qs[0], float(a))
        else:
            out.append((g, tuple(qs), None))
    return out


@dataclass
class Circuit:
    n: int
    ops: list
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        self.ops = [(g, tuple(int(q) for q in qs), (float(a) if g == "rz" else None)) for g, qs, a in self.ops]
        for g, qs, a in self.ops:
            if g not in CORE_GATES:
                raise ValueError(f"gate {g!r} is not in the Clifford+Rz core gate set")
            if len(qs) != (2 if g in ("cx", "cz") else 1) or len(set(qs)) != len(qs) or \
                    any(not 0 <= q < self.n for q in qs):
                raise ValueError(f"bad qubits {qs} for {g} on n={self.n}")

    # ------------------------------------------------------------------ I/O
    @classmethod
    def from_qasm(cls, text: str, **meta) -> "Circuit":
        ops, n = qasm_to_ops(text)
        return cls(n, normalize(ops), dict(meta))

    def to_qasm(self) -> str:
        return ops_to_qasm(self.ops, self.n)

    def copy(self) -> "Circuit":
        return Circuit(self.n, list(self.ops), dict(self.meta))

    def digest(self) -> str:
        return hashlib.sha1(self.to_qasm().encode()).hexdigest()[:16]

    def counts(self) -> dict:
        rz = [a for g, _, a in self.ops if g == "rz" and classify_angle(a) is None]
        return dict(ops=len(self.ops), rz=len(rz), t=sum(g in ("t", "tdg") for g, _, _ in self.ops),
                    cx=sum(g in ("cx", "cz") for g, _, _ in self.ops))


# ---------------------------------------------------------------------- stage-1 inputs
def original_ops(name: str) -> tuple[list, int]:
    """The qseed circuit itself (u3 + cx ops) - the reference for whole-circuit checks."""
    from ..blocks.circuit_io import bqskit_to_ops, load_u3cx
    c, _ = load_u3cx(name)
    return bqskit_to_ops(c), c.num_qudits


def load_input(name: str, prefer_baseline_file: bool = True) -> Circuit:
    """TKET-pre-optimized Clifford+Rz input for `name` (see module docstring)."""
    if prefer_baseline_file and STAGE1_INPUTS.is_dir():
        hits = sorted(p for p in STAGE1_INPUTS.glob(f"{name}*.qasm")
                      if p.stem == name or p.stem.startswith(name + "_"))
        if hits:
            return Circuit.from_qasm(hits[0].read_text(), name=name, source=str(hits[0].relative_to(REPO)))
    from ..blocks.circuit_io import load_u3cx
    from ..blocks.classical import tket_optimise
    u3cx, note = load_u3cx(name)
    return Circuit(u3cx.num_qudits, normalize(tket_optimise(u3cx)),
                   dict(name=name, source="tket FullPeepholeOptimise (circuitevolve.blocks.classical.tket_optimise)",
                        note=note))


# ---------------------------------------------------------------------- windows
@dataclass
class Window:
    index: int
    qubits: tuple            # global qubits, sorted; local qubit i = qubits[i]
    start: int               # position of the window's first op in the concatenated op list
    ops: list                # LOCAL ops (qubits 0..k-1)

    @property
    def k(self) -> int:
        return len(self.qubits)

    def to_global(self, local_ops) -> list:
        return [(g, tuple(self.qubits[q] for q in qs), a) for g, qs, a in local_ops]


def windows(circ: Circuit, block_size: int = WINDOW_QUBITS, max_gates: int = WINDOW_GATES) -> tuple[list, list]:
    """(windows, flat_ops). `flat_ops` is the concatenation of the windows (a topological re-ordering of
    circ.ops, the same circuit); window.start indexes into it."""
    from ..blocks.partition import partition
    blocks = partition(circ.ops, circ.n, block_size=block_size, max_gates=max_gates)
    out, flat = [], []
    for b in blocks:
        out.append(Window(index=len(out), qubits=tuple(b.qubits), start=len(flat), ops=list(b.ops)))
        flat.extend((g, tuple(b.qubits[q] for q in qs), a) for g, qs, a in b.ops)
    return out, flat


def splice(flat_ops: list, w: Window, new_local_ops: list) -> list:
    """Replace window `w` (positions w.start .. w.start+len(w.ops)) of `flat_ops` by new local ops."""
    return flat_ops[:w.start] + w.to_global(new_local_ops) + flat_ops[w.start + len(w.ops):]


def window_text(local_ops) -> str:
    """Literal text format used in prompts (and parsed back by mutator.parse_window)."""
    lines = []
    for g, qs, a in local_ops:
        q = " ".join(f"q{x}" for x in qs)
        lines.append(f"rz({float(a)!r}) {q}" if g == "rz" else f"{g} {q}")
    return "\n".join(lines)
