# Aura – High-Cardinality Real-Time Analytics Engine

A high-speed system that monitors live data streams (website clicks, server logs, IoT sensors) to provide **real-time statistics** such as unique user counts and "trending" items **without storing raw data**.

**Requirements:** Python 3.10+. Run all commands from the **repository root** (the `Aura` folder).

## Tech Stack

| Component        | Choice |
|-----------------|--------|
| Language        | Python (asyncio for high-speed ingestion) |
| Cardinality     | **HyperLogLog** (from scratch) |
| Top-K / Heavy Hitters | **Misra-Gries** |
| Transport       | UDP via `asyncio.DatagramProtocol` |
| Optimization    | `mmap` (zero-copy file read), `struct` (binary packing), `hashlib.blake2b` (hashing) |

## Why These Choices?

- **UDP** – Faster than TCP for log-style traffic; no handshake. Bursts handled with a 2MB socket buffer and a producer-consumer queue.
- **HyperLogLog** – Count millions of uniques in ~1.5KB with ~0.81% standard error instead of ~800MB for exact counting.
- **Misra-Gries** – Identify heavy hitters (e.g. top 100 IPs) in one pass without a full histogram.
- **BLAKE2b** – Used for 64-bit hashing: faster than SHA-256 in Python with excellent distribution for HLL/MG.

## Project Structure

```
Aura/
├── src/
│   ├── __init__.py
│   ├── engine.py           # Core processing engine (HLL + MG, mmap replay)
│   ├── algorithms/
│   │   ├── hll.py          # HyperLogLog (p=14, bias correction)
│   │   └── misra_gries.py  # Heavy hitters (k=100)
│   ├── ingestion/
│   │   └── udp_server.py   # Asyncio UDP + Queue producer-consumer
│   └── utils/
│       └── hasher.py       # 64-bit BLAKE2b hashing
├── tests/
│   ├── test_hll.py
│   └── test_mg.py
├── scripts/
│   └── simulator.py       # Generate 10M-event binary file
├── requirements.txt
├── README.md
└── main.py                 # Entry: file replay or UDP server
```

## Verify after clone

From the repo root, run these to confirm everything works:

```bash
# Run all tests (9 unit tests)
python -m pytest tests/ -v

# Or run test scripts directly:
python tests/test_hll.py
python tests/test_mg.py

# Generate sample data and run the engine
mkdir data
python scripts/simulator.py -n 50000 -o data/events.bin
python main.py file data/events.bin
```

You should see tests pass and a stats block (events processed, throughput, unique estimate, etc.). No errors = ready to use.

## Quick Start

### 1. Generate test data (10M events)

```bash
python scripts/simulator.py -n 10000000 -o data/events_10M.bin
```

### 2. Run engine on file (mmap, no full load into RAM)

```bash
python main.py file data/events_10M.bin
```

### 3. Run UDP live server

```bash
python main.py udp --host 0.0.0.0 --port 9999
# Optional: run for 60 seconds then print stats
python main.py udp --duration 60
```

### 4. Run tests

```bash
python -m pytest tests/ -v
# or
python tests/test_hll.py && python tests/test_mg.py
```

## Performance (Reference)

| Metric | Target / Typical |
|--------|-------------------|
| **Throughput** | 50,000+ events/sec (file replay; depends on disk and p=14/k=100) |
| **Memory (exact count for 100M uniques)** | ~800 MB |
| **Memory (HLL, p=14)** | &lt;5 KB (~16,384 bytes) for million-scale cardinality |
| **HLL standard error** | ~0.81% (p=14) |
| **P99 latency** | Sub-millisecond per-packet processing (struct + hash + HLL/MG update) |
| **UDP buffer** | 2 MB to handle bursts |

## Configuration

- **HLL registers** – `p=14` → 2^14 = 16,384 registers, ~0.81% standard error.
- **Top-K** – `k=100` for heavy hitters.
- **Binary format** – Each event: 4-byte length (big-endian) + UTF-8 payload.

## Resume Bullets (as specified)

- **Engineered** a real-time telemetry analyzer in Python capable of processing **50,000+ events/sec** by leveraging asyncio and non-blocking I/O.
- **Implemented HyperLogLog from scratch** to estimate unique user cardinality, reducing memory overhead from ~1GB to **&lt;5KB** for million-scale datasets.
- **Designed** a Top-K frequency tracker using the **Misra-Gries** algorithm, enabling real-time detection of "Heavy Hitter" IP addresses during DDoS simulation.
- **Optimized** data serialization using Python's `struct` module and bitwise operations to achieve **sub-millisecond** per-packet processing latency.

## License

MIT.
