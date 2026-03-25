"""Neon/cyberpunk visual theme for Exca Dance."""

from __future__ import annotations
from dataclasses import dataclass
from exca_dance.core.models import Judgment


@dataclass(frozen=True)
class Color:
    r: float
    g: float
    b: float
    a: float = 1.0

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.r, self.g, self.b, self.a)

    def as_rgb(self) -> tuple[float, float, float]:
        return (self.r, self.g, self.b)

    def as_pygame_rgb(self) -> tuple[int, int, int]:
        return (int(self.r * 255), int(self.g * 255), int(self.b * 255))

    def with_alpha(self, a: float) -> "Color":
        return Color(self.r, self.g, self.b, a)


class NeonTheme:
    """Neon/cyberpunk color constants."""

    # Backgrounds
    BG = Color(0.04, 0.04, 0.10)  # near-black navy
    BG_PANEL = Color(0.06, 0.06, 0.14)  # slightly lighter panel bg

    # Primary neons
    NEON_BLUE = Color(0.0, 0.83, 1.0)  # electric blue  #00D4FF
    NEON_PINK = Color(1.0, 0.0, 0.40)  # hot pink       #FF0066
    NEON_GREEN = Color(0.0, 1.0, 0.53)  # neon green     #00FF88
    NEON_ORANGE = Color(1.0, 0.53, 0.0)  # neon orange    #FF8800
    NEON_PURPLE = Color(0.67, 0.0, 1.0)  # neon purple    #AA00FF

    # Text
    TEXT_WHITE = Color(1.0, 1.0, 1.0)
    TEXT_DIM = Color(0.6, 0.6, 0.7)

    # Judgment colors
    PERFECT = Color(1.0, 0.84, 0.0)  # gold   #FFD700
    GREAT = Color(0.0, 0.80, 1.0)  # cyan   #00CCFF
    GOOD = Color(0.0, 1.0, 0.53)  # green  #00FF88
    MISS = Color(1.0, 0.0, 0.27)  # red    #FF0044

    # Panel borders (electric blue, semi-transparent)
    BORDER = Color(0.0, 0.83, 1.0, 0.6)

    # Joint colors (match excavator_model.py)
    JOINT_SWING = Color(0.5, 0.5, 0.6)
    JOINT_BOOM = Color(1.0, 0.4, 0.0)
    JOINT_ARM = Color(1.0, 0.8, 0.0)
    JOINT_BUCKET = Color(0.0, 0.8, 1.0)

    @classmethod
    def judgment_color(cls, judgment: Judgment) -> Color:
        return {
            Judgment.PERFECT: cls.PERFECT,
            Judgment.GREAT: cls.GREAT,
            Judgment.GOOD: cls.GOOD,
            Judgment.MISS: cls.MISS,
        }[judgment]
