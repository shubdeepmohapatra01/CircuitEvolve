"""Partition a circuit into dependency-contiguous blocks of at most `width` qubits.

v3's `rotation_count_minimal_block_refit` (retired) and `pauli_subalgebra_dimension_recompression` both
re-derived this. The frozen `circuitevolve/blocks/partition.py` does it with BQSKit's QuickPartitioner,
which a rule may not import, so here it is in pure Python.

A block is a CONTIGUOUS range [lo, hi) of the op list whose ops touch at most `width` qubits. Contiguity
is what makes a block replaceable: splicing new local ops back in at [lo, hi) is a valid rewrite of the
whole circuit whatever the rest of the circuit does, and the judge's window check sees exactly that span.

    partition(circuit_or_ops, width=4, max_gates=40)  -> [Block]
    Block.local_ops / .qubits / .lo / .hi / .k
    Block.to_global(new_local_ops)                    -> ops for the whole circuit
    splice(ops, block, new_local_ops)                 -> new global op list
    DPF's partition: width 4, which is what arXiv:2606.05397 uses.
"""
from __future__ import annotations

from dataclasses import dataclass

WIDTH = 4
MAX_GATES = 40


@dataclass(frozen=True)
class Block:
    index: int
    lo: int
    hi: int
    qubits: tuple               # global qubit indices, sorted; local index = position in this tuple
    local_ops: tuple            # the block's ops re-indexed to 0..k-1

    @property
    def k(self) -> int:
        return len(self.qubits)

    @property
    def n_ops(self) -> int:
        return len(self.local_ops)

    def to_local(self, global_ops) -> list:
        loc = {q: i for i, q in enumerate(self.qubits)}
        return [(g, tuple(loc[q] for q in qs), a) for g, qs, a in global_ops]

    def to_global(self, local_ops) -> list:
        return [(g, tuple(self.qubits[i] for i in qs), a) for g, qs, a in local_ops]

    def rotations(self) -> list:
        """[(local position, angle)] of the block's t / tdg / rz ops."""
        from . import dv
        return [(i, dv.rotation(op)) for i, op in enumerate(self.local_ops) if dv.rotation(op) is not None]


def _ops_of(c):
    from . import dv
    if dv.is_angle_circuit(c):
        return list(c.ops)
    if isinstance(c, (list, tuple)):
        return list(c)
    raise TypeError("partition takes a dv_angle Circuit or an op list")


def partition(c, width: int = WIDTH, max_gates: int = MAX_GATES) -> list:
    """Greedy left-to-right partition into contiguous blocks of <= `width` qubits and <= `max_gates` ops.

    An op that would take the current block over the width (or the gate limit) closes it and starts a
    new one, so concatenating the blocks reproduces the circuit exactly."""
    ops = _ops_of(c)
    out, lo, qs = [], 0, set()
    for i, op in enumerate(ops):
        want = qs | set(op[1])
        if qs and (len(want) > width or i - lo >= max_gates):
            out.append(_make(len(out), lo, i, qs, ops))
            lo, qs = i, set(op[1])
        else:
            qs = want
    if lo < len(ops):
        out.append(_make(len(out), lo, len(ops), qs, ops))
    return out


def _make(index, lo, hi, qs, ops) -> Block:
    qubits = tuple(sorted(qs))
    loc = {q: i for i, q in enumerate(qubits)}
    local = tuple((g, tuple(loc[q] for q in qq), a) for g, qq, a in ops[lo:hi])
    return Block(index, lo, hi, qubits, local)


def splice(ops, block: Block, new_local_ops) -> list:
    """`ops` with the block's span replaced by `new_local_ops` (given in LOCAL indices)."""
    ops = list(ops)
    return ops[:block.lo] + block.to_global(list(new_local_ops)) + ops[block.hi:]


def reassemble(ops, blocks, new_local_per_block: dict) -> list:
    """`ops` with several blocks replaced at once (`{block index: new local ops}`), right to left."""
    out = list(ops)
    for b in sorted(blocks, key=lambda b: -b.lo):
        if b.index in new_local_per_block:
            out = splice(out, b, new_local_per_block[b.index])
    return out


def blocks_with_rotations(c, width: int = WIDTH, max_gates: int = MAX_GATES, minimum: int = 2) -> list:
    """Blocks holding at least `minimum` non-Clifford rotations - the ones worth refitting."""
    from . import dv
    out = []
    for b in partition(c, width, max_gates):
        n = sum(1 for op in b.local_ops if dv.rotation(op) is not None and not dv.on_grid(dv.rotation(op)))
        if n >= minimum:
            out.append(b)
    return out
