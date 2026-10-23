"""Exact arithmetic in D[ω] = Z[ω, 1/√2], ω = e^{iπ/4}.

An element is (a + bω + cω² + dω³) / √2^k with integers a..d and k ≥ 0, kept in canonical form
(k minimal), so equality is structural. Every Clifford+T amplitude lives in this ring, which lets
the verifier ACCEPT on exact equality rather than a floating-point tolerance.
"""
from __future__ import annotations

import cmath
import math


def _mul_coeffs(x, y):
    # (Σ x_i ω^i)(Σ y_j ω^j) with ω^4 = -1
    out = [0, 0, 0, 0]
    for i, xi in enumerate(x):
        if xi == 0:
            continue
        for j, yj in enumerate(y):
            if yj == 0:
                continue
            p = i + j
            if p >= 4:
                out[p - 4] -= xi * yj
            else:
                out[p] += xi * yj
    return tuple(out)


_SQRT2 = (0, 1, 0, -1)  # √2 = ω - ω³


class D:
    """Element of Z[ω, 1/√2]. Immutable."""

    __slots__ = ("c", "k")

    def __init__(self, c=(0, 0, 0, 0), k=0):
        c = tuple(int(v) for v in c)
        if c == (0, 0, 0, 0):
            k = 0
        else:
            # reduce k while numerator is divisible by √2: x/√2 = x·√2/2
            while k > 0:
                y = _mul_coeffs(c, _SQRT2)
                if all(v % 2 == 0 for v in y):
                    c = tuple(v // 2 for v in y)
                    k -= 1
                else:
                    break
        self.c = c
        self.k = k

    # construction helpers -------------------------------------------------------------
    @staticmethod
    def omega_pow(j: int) -> "D":
        j %= 8
        sign = -1 if j >= 4 else 1
        c = [0, 0, 0, 0]
        c[j % 4] = sign
        return D(c, 0)

    # arithmetic -----------------------------------------------------------------------
    def _lift(self, k):
        c = self.c
        for _ in range(k - self.k):
            c = _mul_coeffs(c, _SQRT2)
        return c

    def __add__(self, other: "D") -> "D":
        k = max(self.k, other.k)
        a, b = self._lift(k), other._lift(k)
        return D(tuple(x + y for x, y in zip(a, b)), k)

    def __neg__(self) -> "D":
        return D(tuple(-v for v in self.c), self.k)

    def __sub__(self, other: "D") -> "D":
        return self + (-other)

    def __mul__(self, other: "D") -> "D":
        return D(_mul_coeffs(self.c, other.c), self.k + other.k)

    def times_omega(self, j: int) -> "D":
        return self * D.omega_pow(j)

    def conj(self) -> "D":
        a, b, c, d = self.c
        return D((a, -d, -c, -b), self.k)

    def norm2(self) -> "D":
        return self * self.conj()

    def is_zero(self) -> bool:
        return self.c == (0, 0, 0, 0)

    def __eq__(self, other) -> bool:
        return isinstance(other, D) and self.c == other.c and self.k == other.k

    def __hash__(self):
        return hash((self.c, self.k))

    def __complex__(self) -> complex:
        w = cmath.exp(1j * math.pi / 4)
        return sum(v * w**i for i, v in enumerate(self.c)) / math.sqrt(2) ** self.k

    def __repr__(self) -> str:
        return f"D({self.c}, k={self.k})"


ZERO = D()
ONE = D((1, 0, 0, 0))
INV_SQRT2 = D((1, 0, 0, 0), 1)
