from __future__ import annotations

from unittest.mock import MagicMock

from exca_dance.core.models import JointName


def test_overlay_target_pose_uses_defaults_not_player_angles() -> None:
    """2D overlay target FK must use 0.0 for unspecified joints, not player angles.

    Regression test: previously, full_target started from dict(current_angles),
    so non-targeted joints in the 2D ghost tracked the player's movements.
    """
    from exca_dance.rendering.overlay_2d import Overlay2DRenderer

    renderer = MagicMock()
    renderer.ctx = MagicMock()
    renderer.prog_solid = MagicMock()

    fk = MagicMock()
    fk.get_joint_positions_2d_top.return_value = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
    fk.get_joint_positions_2d_side.return_value = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]

    overlay = Overlay2DRenderer(renderer, fk)

    # Player has moved SWING=90, BUCKET=150
    player_angles = {
        JointName.SWING: 90.0,
        JointName.BOOM: 20.0,
        JointName.ARM: -15.0,
        JointName.BUCKET: 150.0,
    }

    # Target only specifies BOOM=45.0
    target_angles = {JointName.BOOM: 45.0}

    mvp = MagicMock()

    overlay.render(
        viewport_name="top_2d",
        mvp=mvp,
        current_angles=player_angles,
        target_angles=target_angles,
        text_renderer=None,
        match_pct=None,
    )

    # FK was called twice: once for current, once for target
    assert fk.get_joint_positions_2d_top.call_count == 2

    # Second call is for the target pose
    target_call_angles = fk.get_joint_positions_2d_top.call_args_list[1][0][0]

    # Target BOOM must be 45.0 (from target_angles)
    assert target_call_angles[JointName.BOOM] == 45.0
    # Non-targeted joints must be 0.0 (default), NOT the player's angles
    assert target_call_angles[JointName.SWING] == 0.0, (
        f"Expected SWING=0.0, got {target_call_angles[JointName.SWING]}"
    )
    assert target_call_angles[JointName.ARM] == 0.0, (
        f"Expected ARM=0.0, got {target_call_angles[JointName.ARM]}"
    )
    assert target_call_angles[JointName.BUCKET] == 0.0, (
        f"Expected BUCKET=0.0, got {target_call_angles[JointName.BUCKET]}"
    )


def test_overlay_target_pose_side_view_uses_defaults() -> None:
    """Same verification for the side_2d viewport."""
    from exca_dance.rendering.overlay_2d import Overlay2DRenderer

    renderer = MagicMock()
    renderer.ctx = MagicMock()
    renderer.prog_solid = MagicMock()

    fk = MagicMock()
    fk.get_joint_positions_2d_top.return_value = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
    fk.get_joint_positions_2d_side.return_value = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]

    overlay = Overlay2DRenderer(renderer, fk)

    player_angles = {
        JointName.SWING: -45.0,
        JointName.BOOM: 30.0,
        JointName.ARM: 60.0,
        JointName.BUCKET: 100.0,
    }

    target_angles = {JointName.ARM: -20.0, JointName.BUCKET: 80.0}

    mvp = MagicMock()

    overlay.render(
        viewport_name="side_2d",
        mvp=mvp,
        current_angles=player_angles,
        target_angles=target_angles,
        text_renderer=None,
        match_pct=None,
    )

    assert fk.get_joint_positions_2d_side.call_count == 2

    target_call_angles = fk.get_joint_positions_2d_side.call_args_list[1][0][0]

    # Targeted joints use target values
    assert target_call_angles[JointName.ARM] == -20.0
    assert target_call_angles[JointName.BUCKET] == 80.0
    # Non-targeted joints use 0.0 defaults
    assert target_call_angles[JointName.SWING] == 0.0
    assert target_call_angles[JointName.BOOM] == 0.0
