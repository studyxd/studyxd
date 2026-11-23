from __future__ import annotations

import struct
import zlib
from pathlib import Path


def write_png(path: Path, width: int, height: int, rgb: tuple[int, int, int], band: tuple[int, int, int] | None = None) -> None:
    """Write a solid PNG small enough to keep in the vault as a sample cover."""
    band_rows = int(height * 0.22) if band else 0
    rows = []
    for y in range(height):
        color = band if band and y < band_rows else rgb
        rows.append(b"\x00" + bytes(color) * width)
    raw = b"".join(rows)
    png = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(raw, 9))
    png += _chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
