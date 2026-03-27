from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from exca_dance.core.models import JointName
from exca_dance.rendering.excavator_model import build_model_matrix
from exca_dance.rendering.stl_loader import load_binary_stl
from exca_dance.rendering.urdf_kin import (
    JOINTS,
    compute_link_transforms,
    compute_zero_angle_transforms,
)


def _angles(
    swing: float = 0.0,
    boom: float = 0.0,
    arm: float = 0.0,
    bucket: float = 0.0,
) -> dict[JointName, float]:
    values = (swing, boom, arm, bucket)
    return {joint: value for joint, value in zip(JointName, values)}


def _pos(transforms: dict[str, np.ndarray], link: str) -> np.ndarray:
    return transforms[link][:3, 3].copy()


_REFERENCE_POSITIONS: dict[str, dict[str, tuple[float, float, float]]] = {
    "zero": {
        "center_link": (0.0, -0.251134, 0.549174),
        "body_link": (0.0, -0.251134, 0.549174),
        "boom_link": (0.028356, 0.556097, 2.384345),
        "stick_link": (0.056712, 3.373494, 4.219516),
        "bucket_link": (0.082714, 6.45974, 6.309854),
    },
    "swing30": {
        "center_link": (0.0, -0.251134, 0.549174),
        "body_link": (0.0, -0.251134, 0.549174),
        "boom_link": (-0.379058, 0.462127, 2.384345),
        "stick_link": (-1.7632, 2.916242, 4.219516),
        "bucket_link": (-3.283805, 5.60201, 6.309854),
    },
    "boom30": {
        "center_link": (0.0, -0.251134, 0.549174),
        "body_link": (0.0, -0.251134, 0.549174),
        "boom_link": (0.028356, 0.556097, 2.384345),
        "stick_link": (0.970499, 3.373494, 3.959472),
        "bucket_link": (2.038186, 6.45974, 5.756757),
    },
    "arm-20": {
        "center_link": (0.0, -0.251134, 0.549174),
        "body_link": (0.0, -0.251134, 0.549174),
        "boom_link": (0.028356, 0.556097, 2.384345),
        "stick_link": (0.056712, 3.373494, 4.219516),
        "bucket_link": (-0.633792, 6.45974, 6.192684),
    },
    "bucket45": {
        "center_link": (0.0, -0.251134, 0.549174),
        "body_link": (0.0, -0.251134, 0.549174),
        "boom_link": (0.028356, 0.556097, 2.384345),
        "stick_link": (0.056712, 3.373494, 4.219516),
        "bucket_link": (0.082714, 6.45974, 6.309854),
    },
    "combo": {
        "center_link": (0.0, -0.251134, 0.549174),
        "body_link": (0.0, -0.251134, 0.549174),
        "boom_link": (-0.379058, 0.462127, 2.384345),
        "stick_link": (-1.221107, 3.22922, 4.099143),
        "bucket_link": (-2.427701, 6.096282, 6.153209),
    },
}

_REFERENCE_ANGLES: dict[str, dict[JointName, float]] = {
    "zero": _angles(),
    "swing30": _angles(swing=30.0),
    "boom30": _angles(boom=30.0),
    "arm-20": _angles(arm=-20.0),
    "bucket45": _angles(bucket=45.0),
    "combo": _angles(swing=30.0, boom=20.0, arm=-10.0, bucket=45.0),
}


@pytest.mark.parametrize(
    ("case_name", "angles"),
    list(_REFERENCE_ANGLES.items()),
    ids=list(_REFERENCE_ANGLES.keys()),
)
def test_main_chain_positions_match_reference_urdf(
    case_name: str,
    angles: dict[JointName, float],
) -> None:
    transforms = compute_link_transforms(angles)
    for link_name, expected in _REFERENCE_POSITIONS[case_name].items():
        np.testing.assert_allclose(_pos(transforms, link_name), expected, atol=1e-6)


def test_child_origin_equals_joint_position() -> None:
    transforms = compute_link_transforms(_angles(swing=30.0, boom=20.0, arm=-10.0, bucket=45.0))
    for joint in JOINTS:
        parent_T = transforms[joint.parent_link]
        child_T = transforms[joint.child_link]
        expected = (parent_T @ np.array([*joint.origin_xyz, 1.0], dtype=np.float64))[:3]
        np.testing.assert_allclose(child_T[:3, 3], expected, atol=1e-10)


def test_bucket_rotation_changes_orientation_without_moving_bucket_origin() -> None:
    zero = compute_link_transforms(_angles())
    bent = compute_link_transforms(_angles(bucket=45.0))
    np.testing.assert_allclose(_pos(zero, "bucket_link"), _pos(bent, "bucket_link"), atol=1e-9)
    assert not np.allclose(zero["bucket_link"][:3, :3], bent["bucket_link"][:3, :3], atol=1e-9)


def test_collision_mesh_model_matrix_uses_link_transform_directly() -> None:
    zero = compute_zero_angle_transforms()
    np.testing.assert_allclose(
        build_model_matrix(zero["stick_link"]),
        zero["stick_link"],
        atol=1e-12,
    )


def test_zero_pose_collision_mesh_centroids_match_reference_assembly() -> None:
    mesh_dir = Path(__file__).resolve().parent.parent / "assets" / "meshes" / "collision"
    zero = compute_zero_angle_transforms()
    expected = {
        "boom": (0.028596, 1.683646, 2.136119),
        "stick": (0.02682, 2.86093, 2.439465),
        "bucket": (0.026824, 2.41481, 1.028476),
    }
    link_names = {
        "boom": "boom_link",
        "stick": "stick_link",
        "bucket": "bucket_link",
    }

    for stem, expected_centroid in expected.items():
        verts, _ = load_binary_stl(mesh_dir / f"{stem}.stl")
        centroid = verts.mean(axis=0)
        model = build_model_matrix(zero[link_names[stem]])
        world_centroid = (model @ np.array([*centroid, 1.0], dtype=np.float64))[:3]
        np.testing.assert_allclose(world_centroid, expected_centroid, atol=1e-6)
