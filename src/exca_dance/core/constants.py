"""Game constants for Exca Dance."""

from __future__ import annotations
import pygame
from .models import JointName, Judgment

# Joint angle limits (degrees): (min, max)
# Derived from real excavator sensor data (action_space_finder workspace analysis).
# Sensor data uses absolute inclinometer angles; game uses cumulative/relative angles:
#   game_boom = boom_latitude  (absolute)
#   game_arm  = arm_latitude - boom_latitude  (relative to boom)
#   game_bucket = bucket_latitude - arm_latitude  (relative to arm)
JOINT_LIMITS: dict[JointName, tuple[float, float]] = {
    JointName.SWING: (-180.0, 180.0),
    JointName.BOOM: (-52.0, 13.0),
    JointName.ARM: (21.0, 153.0),
    JointName.BUCKET: (-132.0, 47.0),
}

# Default starting angles (degrees) — clamped to JOINT_LIMITS.
# 0.0 for all joints except ARM which has a positive minimum.
DEFAULT_JOINT_ANGLES: dict[JointName, float] = {
    JointName.SWING: 0.0,
    JointName.BOOM: 0.0,
    JointName.ARM: 21.0,
    JointName.BUCKET: 0.0,
}

# Timing judgment windows (ms — half-window, symmetric)
JUDGMENT_WINDOWS: dict[Judgment, float] = {
    Judgment.PERFECT: 35.0,
    Judgment.GREAT: 70.0,
    Judgment.GOOD: 120.0,
}

# Grace period (ms) after duration_ms before auto-MISS
MISS_GRACE_MS: float = 500.0

# Base score per judgment
SCORE_VALUES: dict[Judgment, int] = {
    Judgment.PERFECT: 300,
    Judgment.GREAT: 200,
    Judgment.GOOD: 100,
    Judgment.MISS: 0,
}

# Combo count → multiplier
COMBO_THRESHOLDS: dict[int, int] = {
    0: 1,
    10: 2,
    25: 3,
    50: 4,
}

# Display
TARGET_FPS: int = 60
SCREEN_WIDTH: int = 1920
SCREEN_HEIGHT: int = 1080

# Joint angular velocity (degrees per second when key held)
JOINT_ANGULAR_VELOCITY: float = 60.0

# ── Real-mode safety gate ────────────────────────────────────────────
# Applies only in real ROS2 mode; virtual mode is unaffected.

# Velocity magnitudes below this threshold are treated as "no input"
# and never count as pushing a joint further out of range.
SAFETY_VELOCITY_DEADBAND: float = 0.01

# Sensor-freshness cutoff (seconds). If no new sensor sample arrived for
# a given joint within this window, the joint is considered stale and its
# outgoing velocity is zeroed (fail-close).
SAFETY_SENSOR_STALE_SEC: float = 0.5

# Grace window after (re)connecting the real-mode bridge during which
# fail-close on missing sensors is suppressed. Prevents a spurious
# "no sensor" block at startup before the first ROS2 state snapshot lands.
SAFETY_SENSOR_GRACE_SEC: float = 2.0

# Default key bindings: (positive_key, negative_key) per joint
# Left stick (WASD): swing + arm  |  Right stick (UHJK): boom + bucket
DEFAULT_KEY_BINDINGS: dict[JointName, tuple[int, int]] = {
    JointName.SWING: (pygame.K_a, pygame.K_d),  # left stick: A=left(+), D=right(-)
    JointName.ARM: (pygame.K_w, pygame.K_s),  # left stick: W=extend(+), S=retract(-)
    JointName.BOOM: (pygame.K_j, pygame.K_u),  # right stick: J=ascend(+), U=descend(-)
    JointName.BUCKET: (pygame.K_k, pygame.K_h),  # right stick: K=open(+), H=curl(-)
}

# Excavator link lengths (meters)
BOOM_LENGTH: float = 2.5
ARM_LENGTH: float = 2.0
BUCKET_LENGTH: float = 0.8

# ── Gamepad (Xbox controller) ────────────────────────────────────────
GAMEPAD_AXIS_DEADZONE: float = 0.15

# axis_index → (SDL axis, invert)
# Left stick:  axis 0 = X (left/right), axis 1 = Y (up/down, SDL up = -1)
# Right stick: axis 3 = X, axis 4 = Y
# invert=True flips sign so positive output matches keyboard positive key.
#   Swing  positive = A (left)  → left stick X negative → invert
#   Arm    positive = W (up)    → left stick Y negative → invert
#   Boom   positive = J (down)  → right stick Y positive → no invert
#   Bucket positive = K (right) → right stick X positive → no invert
GAMEPAD_AXIS_MAP: dict[JointName, tuple[int, bool]] = {
    JointName.SWING: (0, True),
    JointName.ARM: (1, True),
    JointName.BOOM: (4, False),
    JointName.BUCKET: (3, False),
}

GAMEPAD_BUTTON_A: int = 0
GAMEPAD_BUTTON_B: int = 1
GAMEPAD_BUTTON_START: int = 7
