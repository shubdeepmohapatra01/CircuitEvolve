"""Partition a Clifford+Rz circuit into blocks and group blocks by STRUCTURE.

1. BQSKit QuickPartitioner(block_size) (3 default, 2 optional) over the op list.
2. QuickPartitioner bounds qubits, not gates, so every block is cut into consecutive WINDOWS of at most
   `max_gates` ops (default 40). Each window is a Block on the qubits it actually touches.
3. A block's structure signature is its gate list with local qubits (index in the sorted global
   qubit tuple) and every synthesised rz angle abstracted to a0, a1, ... (in order of appearance);
   the instance angles are recorded. Clifford/T gates are part of the structure.
Concatenating blocks in order reproduces the input circuit exactly (tested).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .circuit_io import ops_to_bqskit


@dataclass
class Block:
    index: int
    qubits: tuple            # global qubits, sorted; local qubit i = qubits[i]
    ops: list                # local ops with numeric angles
    angles: list             # instance angles a0..ak (the rz angles in order)
    structure: str           # text signature (angles abstracted)
    sig: str                 # short hash of structure
    part: int = 0            # QuickPartitioner block index
    window: int = 0
    meta: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.qubits)


def structure_text(local_ops, n: int) -> str:
    lines, k = [f"qubits {n}"], 0
    for g, qs, _ in local_ops:
        q = " ".join(f"q{x}" for x in qs)
        if g == "rz":
            lines.append(f"rz(a{k}) {q}")
            k += 1
        else:
            lines.append(f"{g} {q}")
    return "\n".join(lines)


def sig_of(structure: str) -> str:
    return hashlib.sha1(structure.encode()).hexdigest()[:12]


def make_block(index, global_ops, part=0, window=0) -> Block:
    qubits = tuple(sorted({q for _, qs, _ in global_ops for q in qs}))
    loc = {q: i for i, q in enumerate(qubits)}
    local = [(g, tuple(loc[q] for q in qs), a) for g, qs, a in global_ops]
    st = structure_text(local, len(qubits))
    return Block(index=index, qubits=qubits, ops=local,
                 angles=[float(a) for g, _, a in local if g == "rz"], structure=st, sig=sig_of(st),
                 part=part, window=window)


def to_global(block: Block, local_ops) -> list:
    return [(g, tuple(block.qubits[q] for q in qs), a) for g, qs, a in local_ops]


def quick_partition(ops, n: int, block_size: int = 3) -> list[list]:
    """Return the QuickPartitioner blocks as lists of GLOBAL ops, in circuit order."""
    from bqskit.ir.gates import CircuitGate
    from bqskit.passes import QuickPartitioner
    from .circuit_io import bqskit_to_ops
    from .runtime import run_passes
    c = ops_to_bqskit(ops, n)
    run_passes(c, [QuickPartitioner(block_size)])
    parts = []
    for op in c:
        assert isinstance(op.gate, CircuitGate)
        parts.append(bqskit_to_ops(op.gate._circuit, location=list(op.location)))
    return parts


def partition(ops, n: int, block_size: int = 3, max_gates: int = 40) -> list[Block]:
    blocks = []
    for p, gops in enumerate(quick_partition(ops, n, block_size)):
        for w, s in enumerate(range(0, len(gops), max_gates)):
            blocks.append(make_block(len(blocks), gops[s:s + max_gates], part=p, window=w))
    return blocks


def reassemble(blocks, local_ops_per_block=None) -> list:
    out = []
    for i, b in enumerate(blocks):
        out.extend(to_global(b, b.ops if local_ops_per_block is None else local_ops_per_block[i]))
    return out


def group(blocks) -> dict:
    """sig -> list of blocks (circuit order)."""
    g: dict[str, list] = {}
    for b in blocks:
        g.setdefault(b.sig, []).append(b)
    return g
