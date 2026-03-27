"""Binary STL file parser — zero external dependencies, vectorized."""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np


def load_binary_stl(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Parse a binary STL file using vectorized numpy operations.

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

    if tri_count == 0:
        return (
            np.empty((0, 3), dtype=np.float32),
            np.empty((0, 3), dtype=np.float32),
        )

    # Structured dtype: 12 floats (normal + 3 vertices) + 1 uint16 attribute = 50 bytes
    tri_dtype = np.dtype(
        [
            ("normal", "<3f"),
            ("v1", "<3f"),
            ("v2", "<3f"),
            ("v3", "<3f"),
            ("attr", "<u2"),
        ]
    )
    tris = np.frombuffer(data, dtype=tri_dtype, offset=84, count=tri_count)

    # Stack vertices: (N, 3) each → interleave to (N*3, 3)
    v1 = tris["v1"]  # (N, 3)
    v2 = tris["v2"]  # (N, 3)
    v3 = tris["v3"]  # (N, 3)
    vertices = np.empty((tri_count * 3, 3), dtype=np.float32)
    vertices[0::3] = v1
    vertices[1::3] = v2
    vertices[2::3] = v3

    # Expand face normals to per-vertex (same normal for all 3 vertices of a tri)
    face_normals = tris["normal"]  # (N, 3)
    normals = np.empty((tri_count * 3, 3), dtype=np.float32)
    normals[0::3] = face_normals
    normals[1::3] = face_normals
    normals[2::3] = face_normals

    return vertices, normals
