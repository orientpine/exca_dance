"""Calibration settings for mapping between ROS2 and game coordinate systems.

Two calibration domains:
  1. Velocity output: game input → UpperControlCmd velocity direction
  2. Angle input:     ROS2 joint topics → game display angles

Formula:  game_angle = sign * ros2_value * scale + offset
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path

from exca_dance.core.models import JointName

logger = logging.getLogger(__name__)


@dataclass
class JointCalibration:
    """Per-joint calibration coefficients."""

    # Velocity output: multiplied to game input before sending to UpperControlCmd
    velocity_sign: float = 1.0

    # Angle input: game_angle = angle_sign * ros2_value * angle_scale + angle_offset
    angle_sign: float = 1.0
    angle_scale: float = 1.0
    angle_offset: float = 0.0

    def transform_angle(self, ros2_value: float) -> float:
        """Convert a raw ROS2 joint angle to game coordinate."""
        return self.angle_sign * ros2_value * self.angle_scale + self.angle_offset

    def transform_velocity(self, game_velocity: float) -> float:
        """Apply sign correction to game velocity for ROS2 output."""
        return self.velocity_sign * game_velocity


# Defaults: identity transform — user adjusts via calibration UI
_DEFAULT_CALIBRATIONS = {
    JointName.SWING: JointCalibration(velocity_sign=1.0),
    JointName.BOOM: JointCalibration(velocity_sign=1.0),
    JointName.ARM: JointCalibration(velocity_sign=1.0),
    JointName.BUCKET: JointCalibration(velocity_sign=1.0),
}


class CalibrationSettings:
    """Manages per-joint calibration with JSON persistence."""

    def __init__(self, filepath: str = "data/calibration.json") -> None:
        self._filepath: Path = Path(filepath)
        self._joints: dict[JointName, JointCalibration] = {
            j: JointCalibration(
                velocity_sign=d.velocity_sign,
                angle_sign=d.angle_sign,
                angle_scale=d.angle_scale,
                angle_offset=d.angle_offset,
            )
            for j, d in _DEFAULT_CALIBRATIONS.items()
        }
        self.load()

    def get(self, joint: JointName) -> JointCalibration:
        """Return calibration for a joint (never None)."""
        return self._joints[joint]

    def transform_angle(self, joint: JointName, ros2_value: float) -> float:
        """Convenience: transform a single ROS2 angle to game angle."""
        return self._joints[joint].transform_angle(ros2_value)

    def transform_velocity(self, joint: JointName, game_velocity: float) -> float:
        """Convenience: transform a single game velocity to ROS2 velocity."""
        return self._joints[joint].transform_velocity(game_velocity)

    # ── Persistence ──────────────────────────────────────────────────

    def save(self) -> None:
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, object] = {}
        for joint, cal in self._joints.items():
            data[joint.value] = asdict(cal)
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        if not self._filepath.exists():
            return
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                return
            for jname_str, coeffs in raw.items():
                if not isinstance(coeffs, dict):
                    continue
                try:
                    jname = JointName(jname_str)
                except ValueError:
                    continue
                cal = self._joints[jname]
                cal.velocity_sign = float(coeffs.get("velocity_sign", cal.velocity_sign))
                cal.angle_sign = float(coeffs.get("angle_sign", cal.angle_sign))
                cal.angle_scale = float(coeffs.get("angle_scale", cal.angle_scale))
                cal.angle_offset = float(coeffs.get("angle_offset", cal.angle_offset))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("Calibration file unreadable, using defaults: %s", exc)

    def reset_to_defaults(self) -> None:
        for joint in JointName:
            default = _DEFAULT_CALIBRATIONS[joint]
            cal = self._joints[joint]
            cal.velocity_sign = default.velocity_sign
            cal.angle_sign = default.angle_sign
            cal.angle_scale = default.angle_scale
            cal.angle_offset = default.angle_offset
