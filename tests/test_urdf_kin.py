from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from exca_dance.core.models import JointName
from exca_dance.rendering.excavator_model import build_model_matrix
from exca_dance.rendering.stl_loader import load_binary_stl
from exca_dance.rendering.urdf_kin import (
    JOINTS,
    _PARENT_RELATIVE,
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
        "boom_link": (0.028356, 0.807231, 1.835171),
        "stick_link": (0.028356, 2.817397, 1.835171),
        "bucket_link": (0.026002, 3.086246, 2.090338),
    },
    "swing30": {
        "center_link": (0.0, -0.251134, 0.549174),
        "body_link": (0.0, -0.251134, 0.549174),
        "boom_link": (-0.504625, 0.679615, 1.835171),
        "stick_link": (-1.509708, 2.42047, 1.835171),
        "bucket_link": (-1.646172, 2.652123, 2.090338),
    },
    "boom30": {
        "center_link": (0.0, -0.251134, 0.549174),
        "body_link": (0.0, -0.251134, 0.549174),
        "boom_link": (0.028356, 0.807231, 1.835171),
        "stick_link": (0.028356, 2.548086, 2.840254),
        "bucket_link": (0.026002, 2.653332, 3.19566),
    },
    "arm-20": {
        "center_link": (0.0, -0.251134, 0.549174),
        "body_link": (0.0, -0.251134, 0.549174),
        "boom_link": (0.028356, 0.807231, 1.835171),
        "stick_link": (0.028356, 2.817397, 1.835171),
        "bucket_link": (0.026002, 3.157305, 1.982998),
    },
    "bucket45": {
        "center_link": (0.0, -0.251134, 0.549174),
        "body_link": (0.0, -0.251134, 0.549174),
        "boom_link": (0.028356, 0.807231, 1.835171),
        "stick_link": (0.028356, 2.817397, 1.835171),
        "bucket_link": (0.026002, 3.086246, 2.090338),
    },
    "combo": {
        "center_link": (0.0, -0.251134, 0.549174),
        "body_link": (0.0, -0.251134, 0.549174),
        "boom_link": (-0.504625, 0.679615, 1.835171),
        "stick_link": (-1.449095, 2.315483, 2.522688),
        "bucket_link": (-1.561361, 2.505226, 2.820664),
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
        expected = (parent_T @ np.array([*_PARENT_RELATIVE[joint.name], 1.0], dtype=np.float64))[:3]
        np.testing.assert_allclose(child_T[:3, 3], expected, atol=1e-10)


def test_bucket_rotation_changes_orientation_without_moving_bucket_origin() -> None:
    zero = compute_link_transforms(_angles())
    bent = compute_link_transforms(_angles(bucket=45.0))
    np.testing.assert_allclose(_pos(zero, "bucket_link"), _pos(bent, "bucket_link"), atol=1e-9)
    assert not np.allclose(zero["bucket_link"][:3, :3], bent["bucket_link"][:3, :3], atol=1e-9)


def test_collision_mesh_model_matrix_applies_correction() -> None:
    from exca_dance.rendering.urdf_kin import compute_mesh_corrections
    zero = compute_zero_angle_transforms()
    corr = compute_mesh_corrections()
    identity = np.eye(4, dtype=np.float64)
    model = build_model_matrix(zero["boom_link"], corr.get("boom_link", identity))
    assert not np.allclose(model, zero["boom_link"], atol=1e-6)


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
        from exca_dance.rendering.urdf_kin import compute_mesh_corrections
        corr = compute_mesh_corrections()
        identity = np.eye(4, dtype=np.float64)
        model = build_model_matrix(zero[link_names[stem]], corr.get(link_names[stem], identity))
        world_centroid = (model @ np.array([*centroid, 1.0], dtype=np.float64))[:3]
        np.testing.assert_allclose(world_centroid, expected_centroid, atol=1e-6)


def test_boom_pitch_moves_stick_in_sagittal_plane() -> None:
    t0 = compute_link_transforms(_angles())
    t30 = compute_link_transforms(_angles(boom=30.0))
    s0 = _pos(t0, "stick_link")
    s30 = _pos(t30, "stick_link")
    dx, dy, dz = s30 - s0
    assert abs(dx) < 0.1, f"boom pitch should not move stick laterally: dX={dx:.4f}"
    assert abs(dy) > 0.2, f"boom pitch must change forward reach: dY={dy:.4f}"
    assert abs(dz) > 0.3, f"boom pitch must change height: dZ={dz:.4f}"


def test_arm_pitch_moves_bucket_in_sagittal_plane() -> None:
    t0 = compute_link_transforms(_angles())
    t30 = compute_link_transforms(_angles(arm=-20.0))
    b0 = _pos(t0, "bucket_link")
    b30 = _pos(t30, "bucket_link")
    dx, dy, dz = b30 - b0
    assert abs(dx) < 0.1, f"arm pitch should not move bucket laterally: dX={dx:.4f}"
    assert abs(dy) + abs(dz) > 0.15, f"arm pitch must change forward reach or height"
