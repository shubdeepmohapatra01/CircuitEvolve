"""Specifications: what a candidate must compute, independent of how.

A spec fixes named registers, the set of valid inputs (ancillas always start in |0>), and the
expected output basis state for each valid input. Qubits not in a register are ancillas and must
end in |0>.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .ir import Circuit


@dataclass(frozen=True)
class AdderSpec:
    """In-place n-bit addition: a -> a, b -> (a+b) mod 2^n, z (starts 0) -> carry out."""

    name: str = "adder"

    def register_sizes(self, n: int) -> dict:
        return {"a": n, "b": n, "z": 1}

    @staticmethod
    def _key(circ: Circuit, vals: dict) -> int:
        k = 0
        for reg, v in vals.items():
            for i, q in enumerate(circ.registers[reg]):
                if (v >> i) & 1:
                    k |= 1 << q
        return k

    def inputs(self, circ: Circuit, n: int, max_inputs: int | None = None, seed: int = 0) -> list:
        """List of (input_key, expected_output_key). Exhaustive if 4^n <= max_inputs."""
        total = 1 << (2 * n)
        if max_inputs is None or total <= max_inputs:
            pairs = [(A, B) for A in range(1 << n) for B in range(1 << n)]
        else:
            rng = random.Random(seed)
            edge = [(0, 0), ((1 << n) - 1, (1 << n) - 1), ((1 << n) - 1, 1), (1, (1 << n) - 1)]
            pairs = edge + [(rng.getrandbits(n), rng.getrandbits(n)) for _ in range(max_inputs - len(edge))]
        out = []
        for A, B in pairs:
            s = A + B
            x = self._key(circ, {"a": A, "b": B, "z": 0})
            y = self._key(circ, {"a": A, "b": s % (1 << n), "z": s >> n})
            out.append((x, y))
        return out


SPECS = {"adder": AdderSpec()}
