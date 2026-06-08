"""
Unit tests for HyperLogLog: accuracy and bias correction.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.algorithms import HyperLogLog


def test_hll_cardinality_small() -> None:
    """Small set: estimate should be close to actual."""
    hll = HyperLogLog(p=14)
    for i in range(1000):
        hll.add(f"user_{i}")
    est = hll.cardinality()
    assert 900 <= est <= 1100, f"Expected ~1000, got {est}"


def test_hll_cardinality_large() -> None:
    """Larger set: relative error should be < ~2% with p=14."""
    n = 100_000
    hll = HyperLogLog(p=14)
    for i in range(n):
        hll.add(f"id_{i}")
    est = hll.cardinality()
    err_pct = abs(est - n) / n * 100
    assert err_pct < 3.0, f"Relative error {err_pct}% too high for n={n}"


def test_hll_duplicates() -> None:
    """Adding same item many times should not increase cardinality."""
    hll = HyperLogLog(p=14)
    for _ in range(5000):
        hll.add("same_user")
    assert 0.5 <= hll.cardinality() <= 2.0  # ~1 unique


def test_hll_merge() -> None:
    """Merge two sketches; cardinality of union ~ sum of distinct."""
    hll_a = HyperLogLog(p=14)
    hll_b = HyperLogLog(p=14)
    for i in range(1000):
        hll_a.add(f"a_{i}")
    for i in range(1000):
        hll_b.add(f"b_{i}")
    hll_a.merge(hll_b)
    est = hll_a.cardinality()
    # Union has 2000 distinct
    assert 1800 <= est <= 2200, f"Expected ~2000, got {est}"


def test_hll_memory() -> None:
    """p=14 -> 16384 bytes of registers."""
    hll = HyperLogLog(p=14)
    assert hll.memory_bytes() == 16384


if __name__ == "__main__":
    test_hll_cardinality_small()
    test_hll_cardinality_large()
    test_hll_duplicates()
    test_hll_merge()
    test_hll_memory()
    print("All HLL tests passed.")
