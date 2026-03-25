from __future__ import annotations

from typing import cast

import numpy as np

import exca_dance.rendering.excavator_model as excavator_model
from exca_dance.rendering.render_math import (
    direction_vector,
    make_oriented_box,
    rotation_matrix_from_direction,
    validate_gl_matrix,
)


def test_direction_vector_unit_length() -> None:
    p1 = np.array([1.0, 2.0, 3.0], dtype="f4")
    p2 = np.array([4.0, 6.0, 3.0], dtype="f4")
    d = direction_vector(p1, p2)

    assert np.isclose(np.linalg.norm(d), 1.0)


def test_direction_vector_axis_aligned_x() -> None:
    d = direction_vector(
        np.array([0.0, 0.0, 0.0], dtype="f4"), np.array([1.0, 0.0, 0.0], dtype="f4")
    )

    assert np.allclose(d, np.array([1.0, 0.0, 0.0], dtype="f4"))


def test_rotation_matrix_is_4x4_f4() -> None:
    mat = rotation_matrix_from_direction(np.array([1.0, 2.0, 3.0], dtype="f4"))

    assert mat.shape == (4, 4)
    assert mat.dtype == np.dtype("f4")


def test_rotation_aligns_x_axis() -> None:
    direction = np.array([2.0, 1.0, 0.5], dtype="f4")
    unit_direction = direction / np.linalg.norm(direction)
    mat = rotation_matrix_from_direction(direction)

    assert np.allclose(mat[:3, 0], unit_direction, atol=1e-6)


def test_oriented_box_shape() -> None:
    verts = make_oriented_box(
        np.array([0.0, 0.0, 0.0], dtype="f4"),
        np.array([2.0, 0.0, 0.0], dtype="f4"),
        0.5,
        0.5,
    )

    assert verts.shape == (36, 3)
    assert verts.dtype == np.dtype("f4")


def test_oriented_box_endpoints_near_p1_p2() -> None:
    p1 = np.array([0.0, 0.0, 0.0], dtype="f4")
    p2 = np.array([2.0, 0.0, 0.0], dtype="f4")
    verts = make_oriented_box(p1, p2, 0.5, 0.5)
    min_x = cast(float, np.min(verts[:, 0]))
    max_x = cast(float, np.max(verts[:, 0]))

    assert np.isclose(min_x, 0.0, atol=1e-6)
    assert np.isclose(max_x, 2.0, atol=1e-6)


def test_degenerate_zero_length() -> None:
    p = np.array([1.0, 1.0, 1.0], dtype="f4")
    verts = make_oriented_box(p, p, 0.5, 0.5)

    assert verts.shape == (0, 3)
    assert not np.isnan(verts).any()


def test_validate_gl_matrix_valid() -> None:
    mat = np.eye(4, dtype="f4")

    assert validate_gl_matrix(mat)


def test_validate_gl_matrix_nan() -> None:
    mat = np.eye(4, dtype="f4")
    mat[0, 0] = np.nan

    assert not validate_gl_matrix(mat)


def test_make_octagonal_prism_verts_vertex_count() -> None:
    make_octagonal_prism_verts = getattr(excavator_model, "_make_octagonal_prism_verts")
    p1 = (0.0, 0.0, 0.0)
    p2 = (1.0, 0.0, 0.0)
    verts = make_octagonal_prism_verts(p1, p2, radius=0.1, color=(1.0, 0.5, 0.0), sides=8)

    assert len(verts) == 8 * 12 * 9


def test_octagonal_prism_vertex_count_greater_than_single_box() -> None:
    make_octagonal_prism_verts = getattr(excavator_model, "_make_octagonal_prism_verts")
    p1 = (0.0, 0.0, 0.0)
    p2 = (2.5, 0.0, 0.0)
    verts = make_octagonal_prism_verts(p1, p2, radius=0.12, color=(1.0, 0.4, 0.0), sides=8)

    assert len(verts) == 8 * 12 * 9
    assert len(verts) > 36 * 9
