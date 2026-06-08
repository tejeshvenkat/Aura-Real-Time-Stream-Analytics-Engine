"""
HyperLogLog cardinality estimator.

Estimates the number of unique items in a stream using ~1.5KB for 2^14 registers
with ~0.81% standard error. Replaces exact counting (~800MB for 100M uniques).
"""

from __future__ import annotations

import math
from typing import Callable, Union

from src.utils.hasher import hash_to_64bit


def _compute_alpha(m: int) -> float:
    """Bias correction factor alpha for m registers (m >= 128)."""
    if m < 128:
        raise ValueError("m must be >= 128 for HyperLogLog")
    return 0.7213 / (1.0 + 1.079 / m)


def _count_leading_zeros(w: int, max_bits: int = 50) -> int:
    """Count leading zeros in w (LSB part of hash), capped at max_bits."""
    if w == 0:
        return max_bits
    n = 0
    while (w & 1) == 0 and n < max_bits:
        n += 1
        w >>= 1
    return n


class HyperLogLog:
    """
    HyperLogLog with configurable precision p (number of register index bits).

    p=14 gives 2^14 = 16,384 registers, ~0.81% standard error, ~1.5KB memory.
    """

    __slots__ = ("_p", "_m", "_registers", "_alpha", "_hasher")

    def __init__(
        self,
        p: int = 14,
        hasher: Callable[[Union[str, bytes]], int] | None = None,
    ) -> None:
        if not 4 <= p <= 16:
            raise ValueError("p must be in [4, 16]")
        self._p = p
        self._m = 1 << p  # 2^p registers
        self._registers = bytearray(self._m)  # each register 0..50
        self._alpha = _compute_alpha(self._m)
        self._hasher = hasher or hash_to_64bit

    def add(self, item: Union[str, bytes]) -> None:
        """Add an item to the sketch (update one register)."""
        h = self._hasher(item)
        # First p bits -> bucket index
        idx = h & ((1 << self._p) - 1)
        # Remaining bits (64 - p) for leading-zero count; use 64-p bits
        w = h >> self._p
        max_bits = 64 - self._p
        rho = _count_leading_zeros(w, max_bits) + 1  # 1-based rank
        if rho > self._registers[idx]:
            self._registers[idx] = rho

    def cardinality(self) -> float:
        """Return estimated cardinality (number of distinct items)."""
        m = self._m
        zeros = sum(1 for j in range(m) if self._registers[j] == 0)
        inv_sum = sum(2.0 ** (-x) for x in self._registers)
        raw = self._alpha * (m * m) / inv_sum

        # Small range correction (linear counting)
        if raw <= 2.5 * m and zeros > 0:
            return m * math.log(m / zeros)
        # Intermediate range: use raw
        if raw <= (1 / 30) * (1 << 32):
            return raw
        # Large range correction
        return -(1 << 32) * math.log1p(-raw / (1 << 32))

    def merge(self, other: HyperLogLog) -> None:
        """Merge another HLL into this one (in-place). Same p required."""
        if self._p != other._p:
            raise ValueError("Precision p must match for merge")
        for j in range(self._m):
            if other._registers[j] > self._registers[j]:
                self._registers[j] = other._registers[j]

    def __len__(self) -> int:
        return int(round(self.cardinality()))

    def memory_bytes(self) -> int:
        """Approximate memory usage of the register array."""
        return len(self._registers)
