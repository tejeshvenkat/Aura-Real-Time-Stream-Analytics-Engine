"""
Core processing engine: wires ingestion to HyperLogLog and Misra-Gries.

Supports live UDP stream and mmap-based file replay for "big data" simulation.
"""

from __future__ import annotations

import asyncio
import mmap
import struct
import time
from pathlib import Path
from typing import Optional

from src.algorithms import HyperLogLog, MisraGries
from src.ingestion import UDPServer


# Binary format: 4-byte length + payload (user_id string)
_PACK_FMT = "!I"  # big-endian unsigned int length
_PACK_HEADER_LEN = 4


def unpack_event(data: bytes) -> Optional[bytes]:
    """Decode one event from binary: 4-byte length + UTF-8 payload. Returns payload or None."""
    if len(data) < _PACK_HEADER_LEN:
        return None
    (length,) = struct.unpack(_PACK_FMT, data[:_PACK_HEADER_LEN])
    if length <= 0 or len(data) < _PACK_HEADER_LEN + length:
        return None
    return data[_PACK_HEADER_LEN : _PACK_HEADER_LEN + length]


def pack_event(user_id: bytes) -> bytes:
    """Encode one event for UDP or file: 4-byte length + payload."""
    return struct.pack(_PACK_FMT, len(user_id)) + user_id


class ProcessingEngine:
    """
    Runs HyperLogLog (cardinality) and Misra-Gries (heavy hitters) on a stream.

    Configuration: p=14 (HLL), k=100 (MG), optional sliding window for live mode.
    """

    __slots__ = (
        "hll",
        "mg",
        "udp_server",
        "events_processed",
        "start_time",
        "_latencies",
        "_window_maxlen",
    )

    def __init__(
        self,
        hll_p: int = 14,
        mg_k: int = 100,
        sliding_window_seconds: Optional[int] = None,
        udp_host: str = "0.0.0.0",
        udp_port: int = 9999,
    ) -> None:
        self.hll = HyperLogLog(p=hll_p)
        self.mg = MisraGries(k=mg_k)
        self.events_processed = 0
        self.start_time: Optional[float] = None
        self._latencies: list[float] = []  # for P99
        # Approximate window: assume ~50k events/sec, 60s -> 3M events (cap with maxlen)
        self._window_maxlen = (sliding_window_seconds or 60) * 50_000 if sliding_window_seconds else None
        self.udp_server = UDPServer(
            host=udp_host,
            port=udp_port,
            process_fn=self._on_packet,
            queue_maxsize=200_000,
            sliding_window_maxlen=min(self._window_maxlen, 500_000) if self._window_maxlen else None,
        )

    def _on_packet(self, data: bytes) -> None:
        """Process one UDP packet (can contain one or more packed events)."""
        t0 = time.perf_counter()
        pos = 0
        while pos < len(data):
            if len(data) - pos < _PACK_HEADER_LEN:
                break
            (length,) = struct.unpack(_PACK_FMT, data[pos : pos + _PACK_HEADER_LEN])
            pos += _PACK_HEADER_LEN
            if length <= 0 or pos + length > len(data):
                break
            payload = data[pos : pos + length]
            pos += length
            try:
                uid = payload.decode("utf-8")
            except UnicodeDecodeError:
                uid = payload  # keep bytes for HLL
            self.hll.add(uid)
            self.mg.add(uid)
            self.events_processed += 1
        self._latencies.append(time.perf_counter() - t0)
        # Keep last 100k latencies for P99
        if len(self._latencies) > 100_000:
            self._latencies = self._latencies[-50_000:]

    def process_event(self, user_id: str | bytes) -> None:
        """Process a single event (for file/mmap replay)."""
        t0 = time.perf_counter()
        if isinstance(user_id, str):
            user_id = user_id.encode("utf-8")
        self.hll.add(user_id)
        self.mg.add(user_id)
        self.events_processed += 1
        self._latencies.append(time.perf_counter() - t0)
        if len(self._latencies) > 100_000:
            self._latencies = self._latencies[-50_000:]

    def run_mmap_file(self, path: str | Path, batch_size: int = 64 * 1024) -> dict:
        """
        Read events from a binary file via mmap (zero-copy) and process.

        File format: repeated [4-byte length][payload]. Returns stats dict.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        self.start_time = time.perf_counter()
        self.events_processed = 0
        self._latencies = []
        with open(path, "rb") as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                pos = 0
                while pos < len(mm):
                    if len(mm) - pos < _PACK_HEADER_LEN:
                        break
                    (length,) = struct.unpack_from(_PACK_FMT, mm, pos)
                    pos += _PACK_HEADER_LEN
                    if length <= 0 or pos + length > len(mm):
                        break
                    # Copy slice (bytes on Windows; memoryview on Unix - bytes() works for both)
                    payload = bytes(mm[pos : pos + length])
                    pos += length
                    self.process_event(payload)
        elapsed = time.perf_counter() - self.start_time
        throughput = self.events_processed / elapsed if elapsed > 0 else 0
        self._latencies.sort()
        p99_idx = int(len(self._latencies) * 0.99) - 1
        p99_ms = (self._latencies[p99_idx] * 1000) if self._latencies and p99_idx >= 0 else 0
        return {
            "events": self.events_processed,
            "elapsed_sec": elapsed,
            "throughput_per_sec": throughput,
            "unique_estimate": self.hll.cardinality(),
            "heavy_hitters_top5": self.mg.top(5),
            "p99_latency_ms": p99_ms,
            "hll_memory_bytes": self.hll.memory_bytes(),
        }

    async def run_udp_live(self, duration_sec: Optional[float] = None) -> None:
        """Run UDP server for live ingestion. If duration_sec is set, stop after that."""
        self.start_time = time.perf_counter()
        await self.udp_server.start()
        if duration_sec is not None:
            await asyncio.sleep(duration_sec)
            await self.udp_server.stop()
        else:
            await asyncio.Future()  # run until cancelled (e.g. KeyboardInterrupt)

    def stats(self) -> dict:
        """Current stats (cardinality, top-k, throughput, P99)."""
        elapsed = (time.perf_counter() - self.start_time) if self.start_time else 0
        throughput = self.events_processed / elapsed if elapsed > 0 else 0
        self._latencies.sort()
        p99_idx = int(len(self._latencies) * 0.99) - 1
        p99_ms = (self._latencies[p99_idx] * 1000) if self._latencies and p99_idx >= 0 else 0
        return {
            "events_processed": self.events_processed,
            "elapsed_sec": elapsed,
            "throughput_per_sec": throughput,
            "unique_estimate": self.hll.cardinality(),
            "heavy_hitters_top10": self.mg.top(10),
            "p99_latency_ms": p99_ms,
        }
