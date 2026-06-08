"""
Optimized 64-bit hashing for probabilistic structures.

We use BLAKE2b for speed and good distribution. It is faster than SHA-256
in Python and provides excellent avalanche properties for HLL/Misra-Gries.
MurmurHash3 would be faster in C; in pure Python, blake2b is the best trade-off.
"""

import hashlib
import struct
from typing import Union


def hash_to_64bit(item: Union[str, bytes]) -> int:
    """
    Hash an item to a 64-bit integer suitable for HyperLogLog and Misra-Gries.

    Uses BLAKE2b (64-bit digest) for speed and good distribution. In benchmarks,
    blake2b is significantly faster than sha256 for short inputs and provides
    sufficient collision resistance for cardinality estimation.
    """
    if isinstance(item, str):
        data = item.encode("utf-8")
    else:
        data = item
    digest = hashlib.blake2b(data, digest_size=8).digest()
    return struct.unpack("<Q", digest)[0]
