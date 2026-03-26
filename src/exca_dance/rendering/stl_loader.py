"""Binary STL file parser — zero external dependencies."""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np


def load_binary_stl(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Parse a binary STL file.

    Returns
    -------
    vertices : ndarray, shape (N*3, 3), dtype float32
        Triangle vertex positions (3 vertices per triangle, N triangles).
    normals : ndarray, shape (N*3, 3), dtype float32
        Per-vertex face normals (same normal repeated for each vertex of a triangle).
    """
    data = Path(path).read_bytes()

    # Binary STL layout:
    #   80 bytes  — header (ignored)
    #    4 bytes  — uint32 triangle count
    #   50 bytes  — per triangle: normal(3f) + v1(3f) + v2(3f) + v3(3f) + attr(H)
    if len(data) < 84:
        raise ValueError(f"STL file too small: {path}")

    tri_count = struct.unpack_from("<I", data, 80)[0]
    expected = 84 + tri_count * 50
    if len(data) < expected:
        raise ValueError(f"STL file truncated: expected {expected} bytes, got {len(data)} — {path}")

    # Pre-allocate output arrays
    vertices = np.empty((tri_count * 3, 3), dtype=np.float32)
    normals = np.empty((tri_count * 3, 3), dtype=np.float32)

    offset = 84
    for i in range(tri_count):
        # 12 floats: normal(3) + v1(3) + v2(3) + v3(3)
        floats = struct.unpack_from("<12f", data, offset)
        nx, ny, nz = floats[0], floats[1], floats[2]
        normals[i * 3] = (nx, ny, nz)
        normals[i * 3 + 1] = (nx, ny, nz)
        normals[i * 3 + 2] = (nx, ny, nz)
        vertices[i * 3] = floats[3:6]
        vertices[i * 3 + 1] = floats[6:9]
        vertices[i * 3 + 2] = floats[9:12]
        offset += 50  # 12 floats (48 bytes) + 2 bytes attribute

    return vertices, normals
