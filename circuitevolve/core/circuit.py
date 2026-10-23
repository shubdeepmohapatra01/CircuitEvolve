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
import math
import re
from dataclasses import dataclass, field

from ..blocks import REPO
from ..blocks.circuit_io import classify_angle, emit_rz, ops_to_qasm

CORE_GATES = frozenset({"h", "s", "sdg", "x", "z", "t", "tdg", "cx", "cz", "rz"})
STAGE1 = ("qft_8", "qpe_8", "qae_13", "heisenberg_6", "tfim_6", "hubbard_8", "qml_13", "hhl_8")
STAGE1_INPUTS = REPO / "results" / "bqskit_baselines" / "stage1" / "inputs"
WINDOW_QUBITS = 4
WINDOW_GATES = 40


NUM = r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
ANGLE_RE = re.compile(rf"^([+-])?\s*(?:({NUM})\s*\*?\s*)?(pi)?\s*(?:/\s*({NUM}))?$")


class ParseError(ValueError):
    pass


def parse_angle(text: str) -> float:
    m = ANGLE_RE.match(text.strip().replace("\u03c0", "pi"))
    if not m or not (m.group(2) or m.group(3)):
        raise ParseError(f"bad angle {text!r}")
    sign, num, pi, den = m.groups()
    v = float(num) if num else 1.0
    if pi:
        v *= math.pi
    if den:
        d = float(den)
        if d == 0:
            raise ParseError("division by zero in angle")
        v /= d
    v = -v if sign == "-" else v
    if not math.isfinite(v):
        raise ParseError(f"non-finite angle {text!r}")
    return v


QREG_RE = re.compile(r"^qreg\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]\s*;$")
GATE_LINE_RE = re.compile(r"^([a-z]+)\s*(?:\(([^()]*)\))?\s+(.+?)\s*;$")
ARG_RE = re.compile(r"^([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]$")
SKIP = ("OPENQASM", "include", "creg", "measure", "barrier", "//")


def read_qasm(text: str) -> tuple[list, int]:
    """OpenQASM 2 -> (ops, n) over {h,s,sdg,x,z,t,tdg,cx,cz,rz}. Several qregs are concatenated in
    declaration order (the BQSKit / qiskit convention). rz angles may be decimals or pytket's `k*pi` form;
    they go through the literal parse_angle (no eval). Unknown gates raise ValueError."""
    offs, n, ops = {}, 0, []
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line or line.startswith(SKIP):
            continue
        m = QREG_RE.match(line)
        if m:
            offs[m.group(1)] = n
            n += int(m.group(2))
            continue
        m = GATE_LINE_RE.match(line)
        if not m:
            raise ValueError(f"cannot parse QASM line {raw!r}")
        g, arg, args = m.groups()
        if g not in CORE_GATES:
            raise ValueError(f"gate {g!r} is not in the Clifford+Rz core gate set")
        qs = []
        for a in args.split(","):
            am = ARG_RE.match(a.strip())
            if not am or am.group(1) not in offs:
                raise ValueError(f"bad qubit argument {a!r} in {raw!r}")
            qs.append(offs[am.group(1)] + int(am.group(2)))
        ops.append((g, tuple(qs), parse_angle(arg) if g == "rz" else None))
    return ops, n


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
        """OpenQASM 2 over the core gate set; see read_qasm."""
        ops, n = read_qasm(text)
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
    from bqskit.passes.partitioning import quick as _quick

    from ..blocks.partition import partition
    # QuickPartitioner keeps bins in hash sets keyed by a process-global counter (Bin.id), so the partition
    # of the same circuit depended on how many partitions ran before in the process (observed in tests:
    # one 3-qubit block vs two 2-qubit blocks). Ids only need to be unique within one call: reset it so
    # windows are a deterministic function of the circuit.
    _quick.Bin.id = 0
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
