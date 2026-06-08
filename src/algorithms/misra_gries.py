"""
Misra-Gries (heavy hitters) algorithm for Top-K frequency estimation.

Maintains at most k candidates. On overflow, decrement all counts and remove zeros.
Enables real-time "trending" items without storing the full stream.
"""

from __future__ import annotations

from typing import Callable, Union

from src.utils.hasher import hash_to_64bit


class MisraGries:
    """
    Misra-Gries summary for finding heavy hitters in a stream.

    Tracks at most k candidates. Items with frequency > n/(k+1) are guaranteed
    to appear in the summary (with possible undercount). k=100 is typical.
    """

    __slots__ = ("_k", "_counts", "_hasher")

    def __init__(
        self,
        k: int = 100,
        hasher: Callable[[Union[str, bytes]], int] | None = None,
    ) -> None:
        if k < 1:
            raise ValueError("k must be >= 1")
        self._k = k
        self._counts: dict[str, int] = {}
        self._hasher = hasher or hash_to_64bit

    def add(self, item: Union[str, bytes]) -> None:
        """Process one item (we use item identity, not hash, for key)."""
        key = item.decode("utf-8") if isinstance(item, bytes) else item
        if key in self._counts:
            self._counts[key] += 1
            return
        if len(self._counts) < self._k:
            self._counts[key] = 1
            return
        # Prune: decrement all, remove zeros
        to_del = []
        for ckey in self._counts:
            self._counts[ckey] -= 1
            if self._counts[ckey] <= 0:
                to_del.append(ckey)
        for ckey in to_del:
            del self._counts[ckey]
        # If we freed a slot, add the new item
        if len(self._counts) < self._k:
            self._counts[key] = 1

    def top(self, n: int | None = None) -> list[tuple[str, int]]:
        """Return heavy hitters as (item, count) sorted by count descending."""
        out = sorted(self._counts.items(), key=lambda x: -x[1])
        if n is not None:
            out = out[:n]
        return out

    def __len__(self) -> int:
        return len(self._counts)
