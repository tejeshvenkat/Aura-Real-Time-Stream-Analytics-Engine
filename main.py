"""
Aura – High-Cardinality Real-Time Analytics Engine.

Entry point: run UDP live server or process a binary event file (mmap).
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.engine import ProcessingEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_file(path: str) -> None:
    """Process binary event file with mmap and print stats."""
    engine = ProcessingEngine(hll_p=14, mg_k=100)
    stats = engine.run_mmap_file(path)
    print("--- Aura run_mmap_file results ---")
    print(f"Events processed:     {stats['events']:,}")
    print(f"Elapsed (sec):        {stats['elapsed_sec']:.2f}")
    print(f"Throughput (events/s): {stats['throughput_per_sec']:,.0f}")
    print(f"Unique (HLL estimate): {stats['unique_estimate']:,.0f}")
    print(f"HLL memory (bytes):   {stats['hll_memory_bytes']:,}")
    print(f"P99 latency (ms):     {stats['p99_latency_ms']:.4f}")
    print("Top 5 heavy hitters:", stats["heavy_hitters_top5"])


async def run_udp(host: str, port: int, duration_sec: float | None) -> None:
    """Run UDP ingestion server; optionally run for duration_sec then exit."""
    engine = ProcessingEngine(hll_p=14, mg_k=100, udp_host=host, udp_port=port)
    try:
        if duration_sec is not None:
            await engine.run_udp_live(duration_sec=duration_sec)
            print("--- Aura UDP run stats ---")
            print(engine.stats())
        else:
            await engine.run_udp_live()
    except (KeyboardInterrupt, asyncio.CancelledError):
        await engine.udp_server.stop()
        print("--- Aura UDP run stats ---")
        print(engine.stats())


def main() -> int:
    parser = argparse.ArgumentParser(description="Aura Real-Time Analytics Engine")
    sub = parser.add_subparsers(dest="command", required=True)
    file_p = sub.add_parser("file", help="Process binary event file (mmap)")
    file_p.add_argument("path", help="Path to events .bin file")
    udp_p = sub.add_parser("udp", help="Run UDP ingestion server")
    udp_p.add_argument("--host", default="0.0.0.0", help="Bind host")
    udp_p.add_argument("--port", type=int, default=9999, help="Bind port")
    udp_p.add_argument("--duration", type=float, default=None, help="Run for N seconds then exit")
    args = parser.parse_args()
    if args.command == "file":
        run_file(args.path)
    elif args.command == "udp":
        asyncio.run(run_udp(args.host, args.port, args.duration))
    return 0


if __name__ == "__main__":
    sys.exit(main())
