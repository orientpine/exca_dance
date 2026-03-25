"""Data models for Exca Dance rhythm game."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class JointName(str, Enum):
    SWING = "swing"
    BOOM = "boom"
    ARM = "arm"
    BUCKET = "bucket"


class Judgment(str, Enum):
    PERFECT = "perfect"
    GREAT = "great"
    GOOD = "good"
    MISS = "miss"


@dataclass(frozen=True)
class JointState:
    name: JointName
    angle: float
    velocity: float = 0.0


@dataclass
class ExcavatorState:
    joints: dict[JointName, JointState] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass(frozen=True)
class BeatEvent:
    time_ms: int
    target_angles: dict[JointName, float]
    duration_ms: int = 500


@dataclass
class BeatMap:
    title: str
    artist: str
    bpm: float
    offset_ms: int
    audio_file: str
    difficulty: str = "NORMAL"
    events: list[BeatEvent] = field(default_factory=list)


@dataclass(frozen=True)
class HitResult:
    judgment: Judgment
    score: int
    angle_error: float
    timing_error_ms: float


@dataclass
class LeaderboardEntry:
    initials: str
    score: int
    song_title: str
    timestamp: str


@dataclass
class KeyBinding:
    joint: JointName
    positive_key: int
    negative_key: int
