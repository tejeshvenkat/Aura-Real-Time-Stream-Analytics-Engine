"""
Unit tests for Misra-Gries: heavy hitters and pruning.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.algorithms import MisraGries


def test_mg_heavy_hitter() -> None:
    """One item with > n/(k+1) frequency must appear in top-k."""
    mg = MisraGries(k=10)
    for _ in range(500):
        mg.add("heavy")
    for i in range(100):
        mg.add(f"light_{i}")
    top = mg.top(5)
    keys = [t[0] for t in top]
    assert "heavy" in keys, f"Heavy hitter missing: {top}"


def test_mg_top_order() -> None:
    """Top list should be sorted by count descending."""
    mg = MisraGries(k=100)
    mg.add("a")
    mg.add("a")
    mg.add("a")
    mg.add("b")
    mg.add("b")
    mg.add("c")
    top = mg.top(10)
    assert top[0][0] == "a" and top[0][1] == 3
    assert top[1][0] == "b" and top[1][1] == 2
    assert top[2][0] == "c" and top[2][1] == 1


def test_mg_pruning() -> None:
    """With k=2, only 2 candidates; pruning on full table."""
    mg = MisraGries(k=2)
    for i in range(20):
        mg.add(f"x_{i % 3}")  # x_0, x_1, x_2 repeated
    top = mg.top(5)
    assert len(top) <= 2


def test_mg_top_n() -> None:
    """top(n) returns at most n entries."""
    mg = MisraGries(k=50)
    for i in range(100):
        mg.add(f"item_{i}")
    assert len(mg.top(5)) <= 5
    assert len(mg.top(10)) <= 10


if __name__ == "__main__":
    test_mg_heavy_hitter()
    test_mg_top_order()
    test_mg_pruning()
    test_mg_top_n()
    print("All Misra-Gries tests passed.")
