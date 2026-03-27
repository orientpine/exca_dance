"""URDF-based forward kinematics for the ix35e excavator mesh model.

Encodes the kinematic chain from the HR35 URDF so that STL meshes
(stored in link-local coordinates) can be placed in world space at
runtime given the four game joint angles.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from exca_dance.core.models import JointName


# ---------------------------------------------------------------------------
# Joint / link data straight from the URDF
#
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class URDFJoint:
    """One joint in the kinematic chain."""

    name: str
    parent_link: str
    child_link: str
    joint_type: str  # "fixed", "revolute", "continuous"
    origin_xyz: tuple[float, float, float]
    axis: tuple[float, float, float]  # rotation axis (unit vector)


# Complete kinematic chain extracted from ix35e.urdf.
# Order matters: parents before children so we can compute world transforms
# in a single pass.
JOINTS: list[URDFJoint] = [
    # --- base children (fixed / continuous - wheels & tracks) ---
    URDFJoint(
        "lower_frame_shadow_joint",
        "base_link",
        "lower_frame_shadow_link",
        "fixed",
        (0.0, -0.251134, 0.307028),
        (0, 0, 0),
    ),
    URDFJoint(
        "left_track_joint",
        "base_link",
        "left_track_link",
        "fixed",
        (-0.722768, -0.028878, 0.218181),
        (0, 0, 0),
    ),
    URDFJoint(
        "right_track_joint",
        "base_link",
        "right_track_link",
        "fixed",
        (0.722768, -0.028878, 0.218181),
        (0, 0, 0),
    ),
    URDFJoint(
        "wheel1_l_joint",
        "base_link",
        "wheel1_l_link",
        "continuous",
        (-0.616227, -0.002767, 0.217807),
        (0, 1, 0),
    ),
    URDFJoint(
        "wheel1_r_joint",
        "base_link",
        "wheel1_r_link",
        "continuous",
        (0.616226, -0.002767, 0.217807),
        (0, 1, 0),
    ),
    URDFJoint(
        "wheel2_l_joint",
        "base_link",
        "wheel2_l_link",
        "continuous",
        (-0.616227, -0.002603, 0.217807),
        (0, 1, 0),
    ),
    URDFJoint(
        "wheel2_r_joint",
        "base_link",
        "wheel2_r_link",
        "continuous",
        (0.616226, -0.002603, 0.217807),
        (0, 1, 0),
    ),
    URDFJoint(
        "blade_joint", "base_link", "blade_link", "revolute", (0.0, 0.700199, 0.362182), (0, 1, 0)
    ),
    URDFJoint(
        "blade_shadow_joint", "blade_link", "blade_shadow_link", "fixed", (0.0, 0.0, 0.0), (0, 0, 0)
    ),
    # --- swing → upper body ---
    URDFJoint(
        "swing_joint",
        "base_link",
        "center_link",
        "continuous",
        (0.0, -0.251134, 0.549174),
        (0, 0, 1),
    ),
    URDFJoint("body_joint", "center_link", "body_link", "fixed", (0.0, 0.0, 0.0), (0, 0, 0)),
    URDFJoint(
        "inner_features_l_joint",
        "body_link",
        "inner_features_l_link",
        "fixed",
        (0.004091, 0.503557, 1.306274),
        (0, 0, 0),
    ),
    URDFJoint(
        "inner_features_r_joint",
        "body_link",
        "inner_features_r_link",
        "fixed",
        (-0.105456, 0.503655, 1.305971),
        (0, 0, 0),
    ),
    # --- boom ---
    URDFJoint(
        "boom_joint",
        "body_link",
        "boom_link",
        "revolute",
        (0.028356, 0.807231, 1.835171),
        (1, 0, 0),
    ),
    URDFJoint(
        "boom_stick_joint",
        "boom_link",
        "boom_stick_link",
        "fixed",
        (0.341806, 0.632914, 0.611229),
        (0, 0, 0),
    ),
    URDFJoint(
        "boom_cylinder_joint",
        "boom_link",
        "boom_cylinder_link",
        "fixed",
        (0.013234, 1.252810, 1.190373),
        (0, 0, 0),
    ),
    URDFJoint(
        "boom_piston_joint",
        "boom_link",
        "boom_piston_link",
        "fixed",
        (0.029507, 1.416225, 1.545614),
        (0, 0, 0),
    ),
    # --- stick (= game "arm") ---
    URDFJoint(
        "stick_joint",
        "boom_link",
        "stick_link",
        "revolute",
        (0.028356, 2.817397, 1.835171),
        (1, 0, 0),
    ),
    URDFJoint(
        "stick_cylinder_joint",
        "stick_link",
        "stick_cylinder_link",
        "fixed",
        (0.029916, 1.887204, 2.579915),
        (0, 0, 0),
    ),
    URDFJoint(
        "stick_piston_joint",
        "stick_link",
        "stick_piston_link",
        "fixed",
        (0.029506, 2.498188, 2.719850),
        (0, 0, 0),
    ),
    # --- bucket ---
    URDFJoint(
        "bucket_joint",
        "stick_link",
        "bucket_link",
        "revolute",
        (0.026002, 3.086246, 2.090338),
        (1, 0, 0),
    ),
    URDFJoint(
        "bucket_cylinder_joint",
        "bucket_link",
        "bucket_cylinder_link",
        "fixed",
        (0.026002, 2.907623, 1.998876),
        (0, 0, 0),
    ),
    URDFJoint(
        "bucket_piston_joint",
        "bucket_link",
        "bucket_piston_link",
        "fixed",
        (0.025784, 2.850467, 1.776733),
        (0, 0, 0),
    ),
    URDFJoint(
        "bucket_link1_joint",
        "bucket_link",
        "bucket_link1_link",
        "fixed",
        (0.026002, 2.602376, 1.442937),
        (0, 0, 0),
    ),
    URDFJoint(
        "bucket_link2_joint",
        "bucket_link",
        "bucket_link2_link",
        "fixed",
        (0.028439, 2.661966, 1.304928),
        (0, 0, 0),
    ),
]

# Mapping: URDF visual mesh filename stem → link name
# (extracted from URDF <visual><mesh filename> attributes)
MESH_TO_LINK: dict[str, str] = {
    "lower_frame_shadow_volume": "lower_frame_shadow_link",
    "left_track": "left_track_link",
    "right_track": "right_track_link",
    "wheel1_l": "wheel1_l_link",
    "wheel1_r": "wheel1_r_link",
    "wheel2_l": "wheel2_l_link",
    "wheel2_r": "wheel2_r_link",
    "blade": "blade_link",
    "blade_shadow_volume": "blade_shadow_link",
    "center": "center_link",
    "main_body": "body_link",
    "inner_features_l": "inner_features_l_link",
    "inner_features_r": "inner_features_r_link",
    "boom": "boom_link",
    "boom_stick": "boom_stick_link",
    "boom_cylinder": "boom_cylinder_link",
    "boom_piston": "boom_piston_link",
    "stick": "stick_link",
    "stick_cylinder": "stick_cylinder_link",
    "stick_piston": "stick_piston_link",
    "bucket": "bucket_link",
    "bucket_cylinder": "bucket_cylinder_link",
    "bucket_piston": "bucket_piston_link",
    "bucket_link_1": "bucket_link1_link",
    "bucket_link_2": "bucket_link2_link",
}

# Game JointName → URDF joint name
# Colour groups: which links belong to which visual group.
# The key is used to look up colors in the joint_colors dict.
LINK_COLOR_GROUPS: dict[str, list[str]] = {
    "base": [
        "base_link",
        "lower_frame_shadow_link",
        "left_track_link",
        "right_track_link",
        "wheel1_l_link",
        "wheel1_r_link",
        "wheel2_l_link",
        "wheel2_r_link",
        "blade_link",
        "blade_shadow_link",
    ],
    "turret": [
        "center_link",
        "body_link",
        "inner_features_l_link",
        "inner_features_r_link",
    ],
    JointName.BOOM: [
        "boom_link",
        "boom_stick_link",
        "boom_cylinder_link",
        "boom_piston_link",
    ],
    JointName.ARM: [
        "stick_link",
        "stick_cylinder_link",
        "stick_piston_link",
    ],
    JointName.BUCKET: [
        "bucket_link",
        "bucket_cylinder_link",
        "bucket_piston_link",
        "bucket_link1_link",
        "bucket_link2_link",
    ],
}


# ---------------------------------------------------------------------------
# Transform helpers
# ---------------------------------------------------------------------------


def _rotation_matrix(axis: tuple[float, float, float], angle_rad: float) -> np.ndarray:
    """Rodrigues rotation → 4×4 homogeneous matrix.

    Parameters
    ----------
    axis : (x, y, z) — unit rotation axis
    angle_rad : rotation angle in radians
    """
    ax, ay, az = axis
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    t = 1.0 - c
    m = np.array(
        [
            [t * ax * ax + c, t * ax * ay - s * az, t * ax * az + s * ay, 0],
            [t * ax * ay + s * az, t * ay * ay + c, t * ay * az - s * ax, 0],
            [t * ax * az - s * ay, t * ay * az + s * ax, t * az * az + c, 0],
            [0, 0, 0, 1],
        ],
        dtype=np.float64,
    )
    return m


def _translation_matrix(xyz: tuple[float, float, float]) -> np.ndarray:
    """4×4 homogeneous translation matrix."""
    m = np.eye(4, dtype=np.float64)
    m[0, 3], m[1, 3], m[2, 3] = xyz
    return m


MEASURED_PIVOTS: dict[str, tuple[float, float, float]] = {
    "swing_joint": (0.033333, -0.01235, 0.497222),
    "boom_joint": (0.030949, 0.892745, 1.072785),
    "stick_joint": (0.02915, 2.768744, 2.618858),
    "bucket_joint": (0.032427, 2.358864, 1.335591),
}


def _build_parent_relative_origins() -> dict[str, tuple[float, float, float]]:
    world_pos: dict[str, tuple[float, float, float]] = {"base_link": (0.0, 0.0, 0.0)}
    result: dict[str, tuple[float, float, float]] = {}
    for joint in JOINTS:
        px, py, pz = world_pos.get(joint.parent_link, (0.0, 0.0, 0.0))
        origin = MEASURED_PIVOTS.get(joint.name, joint.origin_xyz)
        ox, oy, oz = origin
        if joint.parent_link == "base_link" or (ox, oy, oz) == (0.0, 0.0, 0.0):
            rel = origin
        else:
            rel = (ox - px, oy - py, oz - pz)
        result[joint.name] = rel
        world_pos[joint.child_link] = (px + rel[0], py + rel[1], pz + rel[2])
    return result


_PARENT_RELATIVE: dict[str, tuple[float, float, float]] = _build_parent_relative_origins()


def _compute_raw_origin_fk() -> dict[str, np.ndarray]:
    transforms: dict[str, np.ndarray] = {"base_link": np.eye(4, dtype=np.float64)}
    for joint in JOINTS:
        parent_T = transforms.get(joint.parent_link)
        if parent_T is None:
            continue
        transforms[joint.child_link] = parent_T @ _translation_matrix(joint.origin_xyz)
    return transforms


def compute_mesh_corrections() -> dict[str, np.ndarray]:
    corrected = compute_zero_angle_transforms()
    raw = _compute_raw_origin_fk()
    return {
        link: np.linalg.inv(corrected[link]) @ raw[link]
        for link in corrected
        if link in raw
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_link_transforms(
    joint_angles: dict[JointName, float],
) -> dict[str, np.ndarray]:
    """Compute 4×4 world transform for every link in the kinematic chain.

    Parameters
    ----------
    joint_angles : dict mapping ``JointName`` → angle in **degrees**.
        Only the four game joints are expected (SWING, BOOM, ARM, BUCKET).
        Fixed / wheel / blade joints default to angle 0.

    Returns
    -------
    dict[str, ndarray] — link_name → 4×4 float64 world transform matrix.
    """
    # Build URDF joint name → angle (radians) lookup
    joint_angles_by_name = {joint.value: angle for joint, angle in joint_angles.items()}
    urdf_angles: dict[str, float] = {}
    urdf_angles["swing_joint"] = math.radians(joint_angles_by_name.get("swing", 0.0))
    urdf_angles["boom_joint"] = math.radians(joint_angles_by_name.get("boom", 0.0))
    urdf_angles["stick_joint"] = math.radians(joint_angles_by_name.get("arm", 0.0))
    urdf_angles["bucket_joint"] = math.radians(joint_angles_by_name.get("bucket", 0.0))

    # base_link is at world origin
    transforms: dict[str, np.ndarray] = {"base_link": np.eye(4, dtype=np.float64)}

    for joint in JOINTS:
        parent_T = transforms.get(joint.parent_link)
        if parent_T is None:
            # Parent not yet computed — skip (shouldn't happen with correct ordering)
            continue

        T_joint = _translation_matrix(_PARENT_RELATIVE[joint.name])

        if joint.joint_type in ("revolute", "continuous"):
            angle = urdf_angles.get(joint.name, 0.0)
            if abs(angle) > 1e-12:
                T_joint = T_joint @ _rotation_matrix(joint.axis, angle)

        transforms[joint.child_link] = parent_T @ T_joint

    return transforms


def build_link_to_color_key() -> dict[str, str | JointName]:
    """Return a mapping from link_name → color group key.

    The key is either a plain string ("base", "turret") or a JointName enum.
    """
    result: dict[str, str | JointName] = {}
    for key, links in LINK_COLOR_GROUPS.items():
        for link in links:
            result[link] = key
    return result


def compute_zero_angle_transforms() -> dict[str, np.ndarray]:
    """Compute link transforms at all-zero joint angles.

    Returns a dict mapping link_name → 4×4 float64 world transform matrix
    with all game joints set to 0°.  Used to convert assembly-frame meshes
    into per-link local coordinates via ``inv(T_zero)``.
    """
    zero_angles: dict[JointName, float] = {j: 0.0 for j in JointName}
    return compute_link_transforms(zero_angles)


def compute_inv_zero_transforms() -> dict[str, np.ndarray]:
    """Precompute ``inv(link_T_zero)`` for every link.

    These matrices convert assembly-frame mesh vertices to link-local
    coordinates.  Caching them avoids per-frame matrix inversions.
    """
    zero_T = compute_zero_angle_transforms()
    return {name: np.linalg.inv(T) for name, T in zero_T.items()}
