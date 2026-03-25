from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

class JointName(str, Enum):
    SWING: str
    BOOM: str
    ARM: str
    BUCKET: str

class Judgment(str, Enum):
    PERFECT: str
    GREAT: str
    GOOD: str
    MISS: str

@dataclass(frozen=True)
class JointState:
    name: JointName
    angle: float
    velocity: float = 0.0

@dataclass
class ExcavatorState:
    joints: dict[JointName, JointState]
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
    events: list[BeatEvent]

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
