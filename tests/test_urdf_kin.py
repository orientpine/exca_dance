"""Tests for URDF-based forward kinematics — joint connectivity, rotation, plausibility.

These tests verify that the excavator kinematic chain in ``urdf_kin.py``
correctly assembles the excavator (all links connected) and that each game
joint (swing / boom / arm / bucket) produces physically correct motion.

Key invariants
--------------
1. All links present in the transform dict.
2. Zero-angle pose is physically plausible (no compounding errors).
3. Swing rotates turret + arm in the XY plane (Z unchanged).
4. Boom / arm / bucket pitch changes BOTH forward reach (Y) AND height (Z).
5. Boom / arm / bucket pitch does NOT move laterally (X stays ~constant).
6. Parent rotation moves all descendants; siblings stay fixed.
7. 360° rotation returns to start.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from exca_dance.core.models import JointName
from exca_dance.rendering.urdf_kin import (
    JOINTS,
    compute_link_transforms,
    compute_zero_angle_transforms,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _angles(
    swing: float = 0.0,
    boom: float = 0.0,
    arm: float = 0.0,
    bucket: float = 0.0,
) -> dict[JointName, float]:
    # zip over JointName enum to keep basedpyright happy (StrEnum quirk)
    values = (swing, boom, arm, bucket)  # order must match JointName members
    return {j: v for j, v in zip(JointName, values)}


def _pos(transforms: dict[str, np.ndarray], link: str) -> np.ndarray:
    """World-frame position (x, y, z) of a link's origin."""
    return transforms[link][:3, 3].copy()


# The four game joints + a combined pose for parametrised tests.
_ANGLE_COMBOS: list[dict[JointName, float]] = [
    _angles(),
    _angles(swing=45.0),
    _angles(boom=30.0),
    _angles(arm=-20.0),
    _angles(bucket=90.0),
    _angles(swing=30.0, boom=20.0, arm=-10.0, bucket=45.0),
    _angles(swing=-90.0, boom=60.0, arm=90.0, bucket=180.0),
]

# Links in the main arm chain (from base to bucket).
_ARM_CHAIN = ["base_link", "center_link", "body_link", "boom_link", "stick_link", "bucket_link"]


# ===================================================================
# 1. Completeness — every expected link must have a transform
# ===================================================================


def test_all_main_chain_links_present() -> None:
    """compute_link_transforms must return entries for all arm-chain links."""
    transforms = compute_zero_angle_transforms()
    for link in _ARM_CHAIN:
        assert link in transforms, f"Missing transform for '{link}'"


def test_all_urdf_child_links_present() -> None:
    """Every child link declared in JOINTS must appear in the output."""
    transforms = compute_zero_angle_transforms()
    for joint in JOINTS:
        assert joint.child_link in transforms, (
            f"child_link '{joint.child_link}' (from joint '{joint.name}') missing"
        )


# ===================================================================
# 2. Zero-angle physical plausibility
#
#    These catch *origin compounding* errors: if joint origin_xyz values
#    are world-frame coordinates but treated as parent-relative offsets,
#    the successive translations accumulate to unreasonable heights.
# ===================================================================


def test_zero_angle_boom_height_plausible() -> None:
    """Boom pivot should be 0.5 – 3.0 m above ground."""
    z = _pos(compute_zero_angle_transforms(), "boom_link")[2]
    assert 0.5 < z < 3.0, f"boom_link Z = {z:.3f} m — out of plausible range"


def test_zero_angle_stick_height_close_to_boom() -> None:
    """Horizontal boom at 0° → stick pivot Z ≈ boom pivot Z (±0.5 m)."""
    t = compute_zero_angle_transforms()
    boom_z = _pos(t, "boom_link")[2]
    stick_z = _pos(t, "stick_link")[2]
    delta = abs(stick_z - boom_z)
    assert delta < 0.5, (
        f"stick Z={stick_z:.3f} too far from boom Z={boom_z:.3f} "
        f"(Δ={delta:.3f} m) — boom should be roughly horizontal at 0°"
    )


def test_zero_angle_bucket_height_plausible() -> None:
    """Bucket pivot should be above −2 m (slight dig OK, not deep underground)."""
    z = _pos(compute_zero_angle_transforms(), "bucket_link")[2]
    assert z > -2.0, f"bucket_link Z = {z:.3f} m — implausibly underground"


def test_zero_angle_arm_chain_within_reach() -> None:
    """Every arm-chain link must be < 8 m from base (mini excavator envelope).

    If origins compound incorrectly the bucket ends up ~9 m away.
    """
    t = compute_zero_angle_transforms()
    for link in _ARM_CHAIN[1:]:
        d = float(np.linalg.norm(_pos(t, link)))
        assert d < 8.0, f"{link} at {d:.3f} m from base — likely origin compounding error"


def test_zero_angle_boom_extends_forward() -> None:
    """Stick pivot Y should be well ahead of boom pivot Y (boom extends forward)."""
    t = compute_zero_angle_transforms()
    boom_y = _pos(t, "boom_link")[1]
    stick_y = _pos(t, "stick_link")[1]
    assert stick_y > boom_y + 0.5, (
        f"stick Y={stick_y:.3f} not forward of boom Y={boom_y:.3f} — boom too short?"
    )


# ===================================================================
# 3. Link connectivity
#
#    For every joint: child_origin_world == parent_T @ [origin_xyz, 1].
#    This is guaranteed by construction in a correct FK engine, but
#    guards against accidental breakage during refactors.
# ===================================================================


def _joint_pos_from_parent(
    parent_T: np.ndarray,
    origin_xyz: tuple[float, float, float],
) -> np.ndarray:
    h = np.array([*origin_xyz, 1.0], dtype=np.float64)
    return (parent_T @ h)[:3]


@pytest.mark.parametrize(
    "angles",
    _ANGLE_COMBOS,
    ids=[
        "zero",
        "swing45",
        "boom30",
        "arm-20",
        "bucket90",
        "combo",
        "extreme",
    ],
)
def test_child_origin_equals_joint_position(angles: dict[JointName, float]) -> None:
    """Child link origin must match the joint position computed from parent.

    Uses the corrected parent-relative origins (not the raw world-frame values).
    """
    from exca_dance.rendering.urdf_kin import _PARENT_RELATIVE

    transforms = compute_link_transforms(angles)
    for joint in JOINTS:
        parent_T = transforms.get(joint.parent_link)
        child_T = transforms.get(joint.child_link)
        if parent_T is None or child_T is None:
            continue
        origin = _PARENT_RELATIVE[joint.name]
        expected = _joint_pos_from_parent(parent_T, origin)
        actual = child_T[:3, 3]
        np.testing.assert_allclose(
            actual,
            expected,
            atol=1e-10,
            err_msg=(
                f"Joint '{joint.name}': child '{joint.child_link}' disconnected "
                f"from parent '{joint.parent_link}'"
            ),
        )


# ===================================================================
# 4. Swing rotation
# ===================================================================


def test_swing_rotates_boom_in_xy_plane() -> None:
    """Swing = 90° should move boom in XY but not change Z."""
    t0 = compute_link_transforms(_angles())
    t90 = compute_link_transforms(_angles(swing=90.0))
    p0 = _pos(t0, "boom_link")
    p90 = _pos(t90, "boom_link")

    # Z must not change (rotation about Z axis)
    assert abs(p90[2] - p0[2]) < 1e-9, f"Swing changed boom Z: {p0[2]:.4f} → {p90[2]:.4f}"
    # XY must change
    xy_shift = float(np.linalg.norm(p90[:2] - p0[:2]))
    assert xy_shift > 0.1, "Swing=90° should move boom in XY"


def test_swing_preserves_base_children() -> None:
    """Tracks and wheels must NOT move when swing changes."""
    t0 = compute_link_transforms(_angles())
    t90 = compute_link_transforms(_angles(swing=90.0))
    for link in ("left_track_link", "right_track_link", "wheel1_l_link", "wheel1_r_link"):
        if link in t0 and link in t90:
            np.testing.assert_allclose(
                t0[link],
                t90[link],
                atol=1e-12,
                err_msg=f"{link} moved when swing rotated",
            )


def test_swing_moves_all_descendants() -> None:
    """Swing should move every descendant link (position or orientation).

    center_link and body_link sit AT the swing pivot (body_joint offset=0,0,0)
    so their *position* doesn't change, only their orientation.
    Links further out (boom, stick, bucket) must change position.
    """
    t0 = compute_link_transforms(_angles())
    t45 = compute_link_transforms(_angles(swing=45.0))

    # Pivot links: full transform (orientation) must change
    for link in ("center_link", "body_link"):
        assert not np.allclose(t0[link], t45[link], atol=1e-6), (
            f"Swing=45° should change {link} orientation"
        )

    # Downstream links: position must change
    for link in ("boom_link", "stick_link", "bucket_link"):
        assert not np.allclose(_pos(t0, link), _pos(t45, link), atol=1e-6), (
            f"Swing=45° should move {link}"
        )


# ===================================================================
# 5. Boom rotation — the most critical axis test
#
#    Physical excavator: pitching the boom changes forward reach (Y)
#    AND height (Z), while lateral position (X) stays ~constant.
#
#    Bug to catch: if boom axis is (0,1,0) instead of the correct
#    lateral axis, Y stays constant and X swings wildly.
# ===================================================================


def test_boom_pitch_changes_stick_height() -> None:
    """Boom = 30° should raise the stick pivot."""
    t0 = compute_link_transforms(_angles())
    t30 = compute_link_transforms(_angles(boom=30.0))
    z0 = _pos(t0, "stick_link")[2]
    z30 = _pos(t30, "stick_link")[2]
    assert z30 > z0 + 0.1, f"Boom=30° should raise stick: Z {z0:.4f} → {z30:.4f}"


def test_boom_pitch_changes_forward_reach() -> None:
    """Boom = 45° MUST change stick Y (forward reach).

    This catches wrong rotation axis: with axis=(0,1,0) the Y component
    is invariant under rotation, so forward reach never changes.
    """
    t0 = compute_link_transforms(_angles())
    t45 = compute_link_transforms(_angles(boom=45.0))
    y0 = _pos(t0, "stick_link")[1]
    y45 = _pos(t45, "stick_link")[1]
    delta = abs(y45 - y0)
    assert delta > 0.3, (
        f"Boom=45° must change stick forward reach (Y): "
        f"{y0:.4f} → {y45:.4f} (Δ={delta:.4f}) — axis may be wrong"
    )


def test_boom_pitch_preserves_lateral_position() -> None:
    """Boom pitch must NOT move the stick sideways (X stays ~constant).

    This catches wrong rotation axis: with axis=(0,1,0) the X component
    gets large rotational contribution, violating the sagittal-plane constraint.
    """
    t0 = compute_link_transforms(_angles())
    t45 = compute_link_transforms(_angles(boom=45.0))
    x0 = _pos(t0, "stick_link")[0]
    x45 = _pos(t45, "stick_link")[0]
    delta = abs(x45 - x0)
    assert delta < 0.3, (
        f"Boom pitch should not move stick laterally: "
        f"X {x0:.4f} → {x45:.4f} (Δ={delta:.4f}) — axis may be wrong"
    )


def test_boom_does_not_move_turret() -> None:
    """body_link must not move when boom rotates."""
    t0 = compute_link_transforms(_angles())
    t30 = compute_link_transforms(_angles(boom=30.0))
    np.testing.assert_allclose(
        t0["body_link"],
        t30["body_link"],
        atol=1e-12,
        err_msg="body_link moved when boom rotated",
    )


def test_boom_moves_stick_and_bucket() -> None:
    """Boom rotation must move both stick and bucket."""
    t0 = compute_link_transforms(_angles())
    t30 = compute_link_transforms(_angles(boom=30.0))
    for link in ("stick_link", "bucket_link"):
        assert not np.allclose(_pos(t0, link), _pos(t30, link), atol=1e-6), (
            f"Boom=30° should move {link}"
        )


# ===================================================================
# 6. Arm (stick) rotation
# ===================================================================


def test_arm_pitch_changes_bucket_height() -> None:
    """Arm = 30° should change bucket Z."""
    t0 = compute_link_transforms(_angles())
    t30 = compute_link_transforms(_angles(arm=30.0))
    z0 = _pos(t0, "bucket_link")[2]
    z30 = _pos(t30, "bucket_link")[2]
    assert abs(z30 - z0) > 0.1, f"Arm=30° should change bucket Z: {z0:.4f} → {z30:.4f}"


def test_arm_pitch_changes_bucket_forward_reach() -> None:
    """Arm = 30° MUST change bucket Y (forward reach).

    Same axis test as boom — catches axis=(0,1,0) bug on the stick joint.
    """
    t0 = compute_link_transforms(_angles())
    t30 = compute_link_transforms(_angles(arm=30.0))
    y0 = _pos(t0, "bucket_link")[1]
    y30 = _pos(t30, "bucket_link")[1]
    delta = abs(y30 - y0)
    assert delta > 0.1, f"Arm=30° must change bucket Y: {y0:.4f} → {y30:.4f} (Δ={delta:.4f})"


def test_arm_pitch_preserves_bucket_lateral() -> None:
    """Arm pitch must NOT swing the bucket sideways."""
    t0 = compute_link_transforms(_angles())
    t30 = compute_link_transforms(_angles(arm=30.0))
    x0 = _pos(t0, "bucket_link")[0]
    x30 = _pos(t30, "bucket_link")[0]
    delta = abs(x30 - x0)
    assert delta < 0.3, f"Arm pitch moved bucket laterally: X {x0:.4f} → {x30:.4f} (Δ={delta:.4f})"


def test_arm_does_not_move_boom() -> None:
    """boom_link must not move when arm rotates."""
    t0 = compute_link_transforms(_angles())
    t30 = compute_link_transforms(_angles(arm=30.0))
    np.testing.assert_allclose(
        t0["boom_link"],
        t30["boom_link"],
        atol=1e-12,
        err_msg="boom_link moved when arm rotated",
    )


# ===================================================================
# 7. Bucket rotation
# ===================================================================


def test_bucket_does_not_move_stick() -> None:
    """stick_link must not move when bucket rotates."""
    t0 = compute_link_transforms(_angles())
    t90 = compute_link_transforms(_angles(bucket=90.0))
    np.testing.assert_allclose(
        t0["stick_link"],
        t90["stick_link"],
        atol=1e-12,
        err_msg="stick_link moved when bucket rotated",
    )


def test_bucket_rotation_changes_bucket_subparts() -> None:
    """Bucket rotation must move bucket sub-parts (cylinder, piston, links)."""
    t0 = compute_link_transforms(_angles())
    t90 = compute_link_transforms(_angles(bucket=90.0))
    for link in ("bucket_cylinder_link", "bucket_piston_link", "bucket_link1_link"):
        if link in t0 and link in t90:
            assert not np.allclose(t0[link], t90[link], atol=1e-6), f"Bucket=90° should move {link}"


def test_bucket_pitch_changes_subpart_forward_reach() -> None:
    """Bucket rotation MUST change sub-part Y — same axis test as boom/arm."""
    t0 = compute_link_transforms(_angles())
    t90 = compute_link_transforms(_angles(bucket=90.0))
    sub = "bucket_cylinder_link"
    if sub not in t0 or sub not in t90:
        pytest.skip(f"{sub} not in transforms")
    y0 = _pos(t0, sub)[1]
    y90 = _pos(t90, sub)[1]
    delta = abs(y90 - y0)
    assert delta > 0.05, f"Bucket=90° should change {sub} Y: {y0:.4f} → {y90:.4f} (Δ={delta:.4f})"


# ===================================================================
# 8. Fixed sub-part joints — descendants follow parent
# ===================================================================


def test_fixed_boom_subparts_follow_boom() -> None:
    """boom_stick, boom_cylinder, boom_piston must move with boom_link."""
    t0 = compute_link_transforms(_angles())
    t30 = compute_link_transforms(_angles(boom=30.0))
    boom_delta = _pos(t30, "boom_link") - _pos(t0, "boom_link")
    for link in ("boom_stick_link", "boom_cylinder_link", "boom_piston_link"):
        if link not in t0 or link not in t30:
            continue
        sub_delta = _pos(t30, link) - _pos(t0, link)
        # Fixed children should have moved (not stayed in place)
        assert float(np.linalg.norm(sub_delta)) > 0.01, (
            f"{link} should move with boom when boom rotates"
        )


def test_fixed_stick_subparts_follow_arm() -> None:
    """stick_cylinder, stick_piston must move when arm rotates."""
    t0 = compute_link_transforms(_angles())
    t30 = compute_link_transforms(_angles(arm=30.0))
    for link in ("stick_cylinder_link", "stick_piston_link"):
        if link not in t0 or link not in t30:
            continue
        delta = float(np.linalg.norm(_pos(t30, link) - _pos(t0, link)))
        assert delta > 0.01, f"{link} should move with stick when arm rotates"


# ===================================================================
# 9. Rotation consistency: 360° → identity, ±angle symmetry
# ===================================================================


def test_swing_360_returns_to_start() -> None:
    """Full 360° swing must return all links to original positions."""
    t0 = compute_link_transforms(_angles())
    t360 = compute_link_transforms(_angles(swing=360.0))
    for link in _ARM_CHAIN:
        np.testing.assert_allclose(
            t0[link],
            t360[link],
            atol=1e-9,
            err_msg=f"{link} not restored after 360° swing",
        )


def test_boom_symmetry_positive_negative() -> None:
    """Boom +30° and −30° should produce symmetric Z movement around zero-angle Z."""
    t0 = compute_link_transforms(_angles())
    tp = compute_link_transforms(_angles(boom=30.0))
    tn = compute_link_transforms(_angles(boom=-30.0))
    z0 = _pos(t0, "stick_link")[2]
    zp = _pos(tp, "stick_link")[2]
    zn = _pos(tn, "stick_link")[2]
    # z0 should be roughly the midpoint of zp and zn
    midpoint = (zp + zn) / 2.0
    assert abs(midpoint - z0) < 0.15, (
        f"Boom ±30° should be symmetric around 0°: "
        f"Z(−30)={zn:.3f}, Z(0)={z0:.3f}, Z(+30)={zp:.3f}, mid={midpoint:.3f}"
    )


# ===================================================================
# 10. Combined motion — sanity checks
# ===================================================================


def test_combined_angles_no_nan_or_inf() -> None:
    """All transforms must be finite (no NaN / Inf) at extreme angles."""
    extreme = _angles(swing=-180.0, boom=60.0, arm=90.0, bucket=200.0)
    transforms = compute_link_transforms(extreme)
    for link, T in transforms.items():
        assert np.all(np.isfinite(T)), f"{link} has NaN/Inf at extreme angles"


def test_combined_angles_links_within_reach() -> None:
    """Even at extreme angles, arm-chain links should stay within reach envelope."""
    extreme = _angles(swing=45.0, boom=60.0, arm=90.0, bucket=200.0)
    transforms = compute_link_transforms(extreme)
    for link in _ARM_CHAIN[1:]:
        d = float(np.linalg.norm(_pos(transforms, link)))
        assert d < 15.0, f"{link} at {d:.3f} m from base at extreme angles — implausible"


# ===================================================================
# 11. inv_zero transforms — regression guard
# ===================================================================


def test_inv_zero_times_zero_is_identity() -> None:
    """link_T(zero) @ inv(link_T(zero)) must equal identity for every link."""
    from exca_dance.rendering.urdf_kin import compute_inv_zero_transforms

    zero_T = compute_zero_angle_transforms()
    inv_T = compute_inv_zero_transforms()

    for link in zero_T:
        if link not in inv_T:
            continue
        product = zero_T[link] @ inv_T[link]
        np.testing.assert_allclose(
            product,
            np.eye(4),
            atol=1e-10,
            err_msg=f"T(zero) @ inv(T(zero)) ≠ I for '{link}'",
        )
