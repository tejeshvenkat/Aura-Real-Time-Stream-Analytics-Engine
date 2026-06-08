"""
High-throughput UDP ingestion with producer-consumer pattern.

UDP avoids TCP handshake overhead for log-style traffic. Packets are pushed
into an asyncio.Queue; a separate consumer task processes them to avoid
dropping packets during CPU-bound work.
"""

import asyncio
import logging
import socket
from asyncio import DatagramProtocol, DatagramTransport
from collections import deque
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# 2MB socket buffer to handle bursts (Linux: net.core.rmem_max may need tuning)
UDP_RECV_BUFFER_BYTES = 2 * 1024 * 1024


class UDPReceiverProtocol(DatagramProtocol):
    """Protocol that forwards every datagram into a queue."""

    def __init__(self, queue: asyncio.Queue) -> None:
        self._queue = queue
        self._transport: Optional[DatagramTransport] = None

    def connection_made(self, transport: DatagramTransport) -> None:
        self._transport = transport
        try:
            sock = transport.get_extra_info("socket")
            if sock is not None:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_RECV_BUFFER_BYTES)
        except Exception as e:
            logger.warning("Could not set UDP buffer size: %s", e)

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            self._queue.put_nowait((data, addr))
        except asyncio.QueueFull:
            logger.warning("Queue full, dropping packet from %s", addr)

    def error_received(self, exc: Exception) -> None:
        logger.error("UDP error: %s", exc)


class UDPServer:
    """
    Async UDP server with producer-consumer pattern.

    Producer: receives packets and puts (data, addr) into queue.
    Consumer: runs process_fn(data) for each packet (e.g. update HLL/MG).
    Sliding window: optional deque with maxlen to only analyze last N items or time window.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9999,
        process_fn: Optional[Callable[[bytes], None]] = None,
        queue_maxsize: int = 100_000,
        sliding_window_maxlen: Optional[int] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._process_fn = process_fn or (lambda _: None)
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_maxsize)
        self._sliding_window: Optional[deque] = (
            deque(maxlen=sliding_window_maxlen) if sliding_window_maxlen else None
        )
        self._consumer_task: Optional[asyncio.Task] = None
        self._running = False

    async def _consumer(self) -> None:
        """Pull from queue and process; maintains throughput during CPU spikes."""
        while self._running:
            try:
                data, _ = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                if self._sliding_window is not None:
                    self._sliding_window.append(data)
                    # Process only from window if you want windowed stats; here we process every packet
                self._process_fn(data)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Consumer error: %s", e)

    async def start(self) -> None:
        """Start UDP listener and consumer task."""
        self._running = True
        loop = asyncio.get_event_loop()
        self._consumer_task = loop.create_task(self._consumer())
        transport, _ = await loop.create_datagram_endpoint(
            lambda: UDPReceiverProtocol(self._queue),
            local_addr=(self._host, self._port),
        )
        self._transport = transport
        logger.info("UDP server listening on %s:%s", self._host, self._port)

    async def stop(self) -> None:
        """Stop consumer and close transport."""
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        if getattr(self, "_transport", None):
            self._transport.close()

    @property
    def sliding_window(self) -> Optional[deque]:
        """Expose sliding window for engine (e.g. last 60s of items)."""
        return self._sliding_window
