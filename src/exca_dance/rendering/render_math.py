"""Rendering mathematics utilities for oriented 3D geometry."""

from __future__ import annotations

import math
from typing import cast

import numpy as np
import numpy.typing as npt


def direction_vector(p1: np.ndarray, p2: np.ndarray) -> np.ndarray:
    """Return unit direction vector from p1 to p2. Returns [1,0,0] if zero-length."""
    start: npt.NDArray[np.float32] = np.asarray(p1, dtype="f4")
    end: npt.NDArray[np.float32] = np.asarray(p2, dtype="f4")
    delta = end - start
    length = float(np.linalg.norm(delta))
    if length < 1e-6 or not math.isfinite(length):
        return np.array([1.0, 0.0, 0.0], dtype="f4")
    return delta / length


def rotation_matrix_from_direction(
    direction: np.ndarray,
    up: np.ndarray | None = None,
) -> np.ndarray:
    """Return 4x4 rotation matrix aligning X-axis with `direction`.

    up defaults to [0, 0, 1] (Z-up), falls back to [0, 1, 0] if parallel.
    Returns identity if direction is zero-length.
    """
    raw_dir: npt.NDArray[np.float32] = np.asarray(direction, dtype="f4")
    dir_len = float(np.linalg.norm(raw_dir))
    if dir_len < 1e-6 or not math.isfinite(dir_len):
        return np.eye(4, dtype="f4")

    x_axis = raw_dir / dir_len
    if up is None:
        ref_up: npt.NDArray[np.float32] = np.array([0.0, 0.0, 1.0], dtype="f4")
    else:
        ref_up = np.asarray(up, dtype="f4")

    alignment = cast(float, np.dot(x_axis, ref_up))
    if abs(alignment) > 0.95:
        ref_up = np.array([0.0, 1.0, 0.0], dtype="f4")

    y_axis = np.cross(ref_up, x_axis)
    y_len = float(np.linalg.norm(y_axis))
    if y_len < 1e-6 or not math.isfinite(y_len):
        return np.eye(4, dtype="f4")
    y_axis = y_axis / y_len

    z_axis = np.cross(x_axis, y_axis)
    z_len = float(np.linalg.norm(z_axis))
    if z_len < 1e-6 or not math.isfinite(z_len):
        return np.eye(4, dtype="f4")
    z_axis = z_axis / z_len

    mat = np.eye(4, dtype="f4")
    mat[:3, :3] = np.column_stack([x_axis, y_axis, z_axis]).astype("f4")
    return mat


def make_oriented_box(
    p1: np.ndarray,
    p2: np.ndarray,
    width: float,
    height: float,
) -> np.ndarray:
    """Generate 36 vertices for a box oriented along p1→p2, shape (36, 3)."""
    start: npt.NDArray[np.float32] = np.asarray(p1, dtype="f4")
    end: npt.NDArray[np.float32] = np.asarray(p2, dtype="f4")
    direction = end - start
    length = float(np.linalg.norm(direction))
    if length < 1e-6 or not math.isfinite(length):
        return np.empty((0, 3), dtype="f4")

    rot = rotation_matrix_from_direction(direction)[:3, :3]
    mid = (start + end) * 0.5

    hx = length / 2.0
    hy = width / 2.0
    hz = height / 2.0

    faces = [
        ((-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)),
        (
            (-hx, -hy, -hz),
            (-hx, hy, -hz),
            (hx, hy, -hz),
            (-hx, -hy, -hz),
            (hx, hy, -hz),
            (hx, -hy, -hz),
        ),
        ((hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, -hz), (hx, hy, hz), (hx, -hy, hz)),
        (
            (-hx, -hy, -hz),
            (-hx, -hy, hz),
            (-hx, hy, hz),
            (-hx, -hy, -hz),
            (-hx, hy, hz),
            (-hx, hy, -hz),
        ),
        ((-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz), (-hx, hy, -hz), (hx, hy, hz), (hx, hy, -hz)),
        (
            (-hx, -hy, -hz),
            (hx, -hy, -hz),
            (hx, -hy, hz),
            (-hx, -hy, -hz),
            (hx, -hy, hz),
            (-hx, -hy, hz),
        ),
    ]

    verts = np.empty((36, 3), dtype="f4")
    i = 0
    for face in faces:
        for lx, ly, lz in face:
            local = np.array([lx, ly, lz], dtype="f4")
            verts[i] = rot @ local + mid
            i += 1

    return verts


def validate_gl_matrix(mat: np.ndarray) -> bool:
    """Validate a 4x4 matrix is suitable for GL (f4, finite values)."""
    arr = np.asarray(mat)
    return bool(arr.shape == (4, 4) and arr.dtype == np.dtype("f4") and np.all(np.isfinite(arr)))
