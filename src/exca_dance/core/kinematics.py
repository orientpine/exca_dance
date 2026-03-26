from __future__ import annotations

import math

from exca_dance.core.constants import (
    ARM_LENGTH,
    BOOM_LENGTH,
    BUCKET_LENGTH,
    JOINT_LIMITS,
)
from exca_dance.core.models import JointName


class ExcavatorFK:
    def __init__(
        self,
        boom_length: float = BOOM_LENGTH,
        arm_length: float = ARM_LENGTH,
        bucket_length: float = BUCKET_LENGTH,
    ) -> None:
        self.boom_length: float = boom_length
        self.arm_length: float = arm_length
        self.bucket_length: float = bucket_length

    def clamp_angles(self, joints: dict[JointName, float]) -> dict[JointName, float]:
        result: dict[JointName, float] = {}
        for jname, angle in joints.items():
            lo, hi = JOINT_LIMITS[jname]
            result[jname] = max(lo, min(hi, angle))
        return result

    def forward_kinematics(
        self,
        joints: dict[JointName, float],
    ) -> dict[str, tuple[float, float, float]]:
        j = self.clamp_angles(joints)
        swing_rad = math.radians(j.get(JointName.SWING, 0.0))
        boom_rad = math.radians(j.get(JointName.BOOM, 0.0))
        arm_rad = math.radians(j.get(JointName.ARM, 0.0))
        buck_rad = math.radians(j.get(JointName.BUCKET, 0.0))

        base = (0.0, 0.0, 0.0)
        swing_pivot = (0.0, 0.0, 0.5)

        cs, ss = math.cos(swing_rad), math.sin(swing_rad)
        boom_h = self.boom_length * math.cos(boom_rad)
        boom_v = self.boom_length * math.sin(boom_rad)
        bx = swing_pivot[0] + boom_h * cs
        by = swing_pivot[1] + boom_h * ss
        bz = swing_pivot[2] + boom_v
        boom_pivot = (bx, by, bz)

        arm_angle = boom_rad + arm_rad
        ax = bx + self.arm_length * math.cos(arm_angle) * cs
        ay = by + self.arm_length * math.cos(arm_angle) * ss
        az = bz + self.arm_length * math.sin(arm_angle)
        arm_pivot = (ax, ay, az)

        buck_angle = arm_angle + buck_rad
        tx = ax + self.bucket_length * math.cos(buck_angle) * cs
        ty = ay + self.bucket_length * math.cos(buck_angle) * ss
        tz = az + self.bucket_length * math.sin(buck_angle)
        bucket_tip = (tx, ty, tz)

        return {
            "base": base,
            "swing_pivot": swing_pivot,
            "boom_pivot": boom_pivot,
            "arm_pivot": arm_pivot,
            "bucket_tip": bucket_tip,
        }

    def get_joint_positions_2d_side(
        self,
        joints: dict[JointName, float],
    ) -> list[tuple[float, float]]:
        """Side-view projection: always swing=0 so the arm profile is shown
        regardless of swing rotation.  Horizontal = radial distance from base,
        vertical = height."""
        side_joints = dict(joints)
        side_joints[JointName.SWING] = 0.0
        pos = self.forward_kinematics(side_joints)
        keys = ["base", "swing_pivot", "boom_pivot", "arm_pivot", "bucket_tip"]
        return [(pos[k][0], pos[k][2]) for k in keys]

    def get_joint_positions_2d_top(
        self,
        joints: dict[JointName, float],
    ) -> list[tuple[float, float]]:
        pos = self.forward_kinematics(joints)
        keys = ["base", "swing_pivot", "boom_pivot", "arm_pivot", "bucket_tip"]
        return [(pos[k][0], pos[k][1]) for k in keys]
