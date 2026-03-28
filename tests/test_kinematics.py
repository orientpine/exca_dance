from __future__ import annotations

import math

from exca_dance.core.constants import ARM_LENGTH, BOOM_LENGTH, BUCKET_LENGTH, JOINT_LIMITS
from exca_dance.core.kinematics import ExcavatorFK
from exca_dance.core.models import JointName


def test_zero_angles_positions() -> None:
    fk = ExcavatorFK()
    pos = fk.forward_kinematics({})

    assert pos["boom_pivot"] == (BOOM_LENGTH, 0.0, 0.5)
    assert pos["bucket_tip"] == (BOOM_LENGTH + ARM_LENGTH + BUCKET_LENGTH, 0.0, 0.5)


def test_boom_beyond_max_clamps_and_goes_up() -> None:
    fk = ExcavatorFK()
    boom_max = JOINT_LIMITS[JointName.BOOM][1]
    pos = fk.forward_kinematics({JointName.BOOM: 90.0})

    swing_pivot = pos["swing_pivot"]
    boom_pivot = pos["boom_pivot"]

    assert boom_pivot[2] > swing_pivot[2]
    assert math.isclose(
        boom_pivot[2], 0.5 + BOOM_LENGTH * math.sin(math.radians(boom_max)), abs_tol=1e-9
    )


def test_swing_ninety_rotates_reach_into_positive_y() -> None:
    fk = ExcavatorFK()
    pos = fk.forward_kinematics({JointName.SWING: 64.0, JointName.ARM: 45.0})

    for key in ("boom_pivot", "arm_pivot", "bucket_tip"):
        assert pos[key][1] > 0.0
        assert pos[key][1] > 0.0


def test_clamp_angles_caps_boom_to_max() -> None:
    fk = ExcavatorFK()
    boom_max = JOINT_LIMITS[JointName.BOOM][1]
    clamped = fk.clamp_angles({JointName.BOOM: 999.0})

    assert clamped[JointName.BOOM] == boom_max


def test_side_view_returns_five_points() -> None:
    fk = ExcavatorFK()
    points = fk.get_joint_positions_2d_side({})

    assert len(points) == 5
    assert points[0] == (0.0, 0.0)
    assert points[1] == (0.0, 0.5)


def test_top_view_shows_swing_effect() -> None:
    fk = ExcavatorFK()
    top_zero = fk.get_joint_positions_2d_top({JointName.SWING: 0.0})
    top_sixty_four = fk.get_joint_positions_2d_top({JointName.SWING: 64.0})

    assert top_zero[2][1] == 0.0
    assert top_sixty_four[2][1] > 0.0
