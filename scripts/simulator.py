"""
High-speed data generator for testing: writes N events to a binary file.

Format: repeated [4-byte length (big-endian)][UTF-8 user_id].
Use with engine.run_mmap_file() for zero-copy replay.
"""

import argparse
import random
import struct
import sys
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.engine import pack_event

_PACK_FMT = "!I"


def generate_user_ids(
    total_events: int,
    unique_users: int | None = None,
    seed: int = 42,
) -> list[bytes]:
    """
    Generate total_events user IDs. If unique_users is set, that many distinct IDs
    are drawn (with repetition); else unique_users = min(total_events, 2M).
    """
    random.seed(seed)
    u = unique_users or min(total_events, 2_000_000)
    # IDs like "user_12345" or "ip_192.168.1.1" for variety
    pool = [f"user_{i}".encode("utf-8") for i in range(u)]
    return [random.choice(pool) for _ in range(total_events)]


def write_events_file(path: Path, events: list[bytes], batch_write: int = 100_000) -> None:
    """Write events in binary format to path. Batched for speed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        for i in range(0, len(events), batch_write):
            batch = events[i : i + batch_write]
            for uid in batch:
                f.write(pack_event(uid))
    print(f"Wrote {len(events)} events to {path} ({path.stat().st_size / (1024*1024):.2f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate event file for Aura engine")
    parser.add_argument("-n", "--events", type=int, default=10_000_000, help="Number of events")
    parser.add_argument("-u", "--unique", type=int, default=None, help="Unique user count (default: min(n, 2M))")
    parser.add_argument("-o", "--output", type=str, default="data/events_10M.bin", help="Output file path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()
    events = generate_user_ids(args.events, args.unique, args.seed)
    write_events_file(Path(args.output), events)


if __name__ == "__main__":
    main()
