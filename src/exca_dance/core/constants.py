"""Game constants for Exca Dance."""

from __future__ import annotations
import pygame
from .models import JointName, Judgment

# Joint angle limits (degrees): (min, max)
JOINT_LIMITS: dict[JointName, tuple[float, float]] = {
    JointName.SWING: (-180.0, 180.0),
    JointName.BOOM: (-30.0, 60.0),
    JointName.ARM: (-50.0, 90.0),
    JointName.BUCKET: (0.0, 200.0),
}

# Timing judgment windows (ms — half-window, symmetric)
JUDGMENT_WINDOWS: dict[Judgment, float] = {
    Judgment.PERFECT: 35.0,
    Judgment.GREAT: 70.0,
    Judgment.GOOD: 120.0,
}

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

# Default key bindings: (positive_key, negative_key) per joint
DEFAULT_KEY_BINDINGS: dict[JointName, tuple[int, int]] = {
    JointName.SWING: (pygame.K_a, pygame.K_d),
    JointName.BOOM: (pygame.K_w, pygame.K_s),
    JointName.ARM: (pygame.K_UP, pygame.K_DOWN),
    JointName.BUCKET: (pygame.K_LEFT, pygame.K_RIGHT),
}

# Excavator link lengths (meters)
BOOM_LENGTH: float = 2.5
ARM_LENGTH: float = 2.0
BUCKET_LENGTH: float = 0.8
