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
    BG: Color = Color(0.04, 0.04, 0.10)  # near-black navy
    BG_PANEL: Color = Color(0.06, 0.06, 0.14)  # slightly lighter panel bg

    # Primary neons
    NEON_BLUE: Color = Color(0.0, 0.83, 1.0)  # electric blue  #00D4FF
    NEON_PINK: Color = Color(1.0, 0.0, 0.40)  # hot pink       #FF0066
    NEON_GREEN: Color = Color(0.0, 1.0, 0.53)  # neon green     #00FF88
    NEON_ORANGE: Color = Color(1.0, 0.53, 0.0)  # neon orange    #FF8800
    NEON_PURPLE: Color = Color(0.67, 0.0, 1.0)  # neon purple    #AA00FF

    # Text
    TEXT_WHITE: Color = Color(1.0, 1.0, 1.0)
    TEXT_DIM: Color = Color(0.6, 0.6, 0.7)

    # Judgment colors
    PERFECT: Color = Color(1.0, 0.84, 0.0)  # gold   #FFD700
    GREAT: Color = Color(0.0, 0.80, 1.0)  # cyan   #00CCFF
    GOOD: Color = Color(0.0, 1.0, 0.53)  # green  #00FF88
    MISS: Color = Color(1.0, 0.0, 0.27)  # red    #FF0044

    PERFECT_GLOW: Color = Color(1.0, 0.95, 0.4, 0.6)
    GREAT_GLOW: Color = Color(0.3, 0.9, 1.0, 0.5)
    GOOD_GLOW: Color = Color(0.3, 1.0, 0.7, 0.4)
    MISS_GLOW: Color = Color(1.0, 0.3, 0.3, 0.3)

    PARTICLE_GOLD: Color = Color(1.0, 0.9, 0.3)
    PARTICLE_CYAN: Color = Color(0.4, 0.9, 1.0)
    PARTICLE_WHITE: Color = Color(1.0, 1.0, 1.0, 0.8)

    # Panel borders (electric blue, semi-transparent)
    BORDER: Color = Color(0.0, 0.83, 1.0, 0.6)

    # Joint colors (match excavator_model.py)
    JOINT_SWING: Color = Color(0.5, 0.5, 0.6)
    JOINT_BOOM: Color = Color(1.0, 0.4, 0.0)
    JOINT_ARM: Color = Color(1.0, 0.8, 0.0)
    JOINT_BUCKET: Color = Color(0.0, 0.8, 1.0)

    # Ghost (target pose) colors — blue palette for visibility against dark BG
    GHOST_ALPHA: float = 0.65
    GHOST_SWING: Color = Color(0.0, 0.4, 0.9)
    GHOST_BOOM: Color = Color(0.0, 0.6, 1.0)
    GHOST_ARM: Color = Color(0.0, 0.75, 1.0)
    GHOST_BUCKET: Color = Color(0.0, 0.9, 1.0)
    GHOST_OUTLINE: Color = Color(0.0, 0.83, 1.0, 1.0)
    GHOST_OUTLINE_PULSE_MIN: float = 0.4
    GHOST_OUTLINE_PULSE_SPEED: float = 4.0

    # 2D overlay — match quality indicators
    MATCH_GOOD: Color = Color(0.0, 1.0, 0.4)  # green  — >80% match
    MATCH_MEDIUM: Color = Color(1.0, 0.9, 0.0)  # yellow — 50-80%
    MATCH_BAD: Color = Color(1.0, 0.2, 0.1)  # red    — <50%

    # Kinematic diagram
    DIAGRAM_GROUND: Color = Color(0.0, 0.55, 0.40, 0.6)  # teal ground line
    DIAGRAM_GRID: Color = Color(0.10, 0.10, 0.20, 0.25)  # subtle reference lines
    DIAGRAM_ARC_FILL: Color = Color(0.25, 0.25, 0.45, 0.35)  # angle arc fill
    DIAGRAM_REF_LINE: Color = Color(0.35, 0.35, 0.50, 0.5)  # reference direction line

    # Timeline
    TIMELINE_BG: Color = Color(0.025, 0.025, 0.065)  # deep dark background
    TIMELINE_LANE: Color = Color(0.07, 0.07, 0.15, 0.4)  # lane divider lines
    TIMELINE_HIT: Color = Color(0.0, 0.9, 1.0)  # hit line color

    # Panel label backgrounds
    PANEL_LABEL_BG: Color = Color(0.05, 0.05, 0.12, 0.7)  # translucent header

    @classmethod
    def judgment_color(cls, judgment: Judgment) -> Color:
        return {
            Judgment.PERFECT: cls.PERFECT,
            Judgment.GREAT: cls.GREAT,
            Judgment.GOOD: cls.GOOD,
            Judgment.MISS: cls.MISS,
        }[judgment]

    @classmethod
    def judgment_glow_color(cls, judgment: Judgment) -> Color:
        return {
            Judgment.PERFECT: cls.PERFECT_GLOW,
            Judgment.GREAT: cls.GREAT_GLOW,
            Judgment.GOOD: cls.GOOD_GLOW,
            Judgment.MISS: cls.MISS_GLOW,
        }[judgment]
