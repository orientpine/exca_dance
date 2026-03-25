"""Beat map JSON serialization and validation utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exca_dance.core.constants import JOINT_LIMITS
from exca_dance.core.models import BeatEvent, BeatMap, JointName


def validate_beatmap(data: dict[str, Any]) -> list[str]:
    """Return list of validation error strings. Empty = valid."""
    errors = []
    if "title" not in data or not data["title"]:
        errors.append("Missing required field: title")
    if "bpm" not in data:
        errors.append("Missing required field: bpm")
    elif not isinstance(data["bpm"], (int, float)) or data["bpm"] <= 0:
        errors.append("bpm must be a positive number")
    if "audio_file" not in data or not data["audio_file"]:
        errors.append("Missing required field: audio_file")
    for i, ev in enumerate(data.get("events", [])):
        if "time_ms" not in ev:
            errors.append(f"Event {i}: missing time_ms")
        elif ev["time_ms"] < 0:
            errors.append(f"Event {i}: time_ms must be >= 0")
        for jname_str, angle in ev.get("target_angles", {}).items():
            try:
                jname = JointName(jname_str)
                lo, hi = JOINT_LIMITS[jname]
                if not (lo <= angle <= hi):
                    errors.append(f"Event {i}: {jname_str} angle {angle} out of range [{lo}, {hi}]")
            except ValueError:
                errors.append(f"Event {i}: unknown joint '{jname_str}'")
    return errors


def load_beatmap(path: str) -> BeatMap:
    """Load and parse a beat map JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    errors = validate_beatmap(data)
    if errors:
        raise ValueError(f"Invalid beat map: {errors}")
    events = []
    for ev in data.get("events", []):
        target_angles = {JointName(k): float(v) for k, v in ev.get("target_angles", {}).items()}
        events.append(
            BeatEvent(
                time_ms=int(ev["time_ms"]),
                target_angles=target_angles,
                duration_ms=int(ev.get("duration_ms", 500)),
            )
        )
    events.sort(key=lambda e: e.time_ms)
    return BeatMap(
        title=data["title"],
        artist=data.get("artist", ""),
        bpm=float(data["bpm"]),
        offset_ms=int(data.get("offset_ms", 0)),
        audio_file=data["audio_file"],
        events=events,
    )


def save_beatmap(beatmap: BeatMap, path: str) -> None:
    """Serialize a BeatMap to JSON."""
    data = {
        "title": beatmap.title,
        "artist": beatmap.artist,
        "bpm": beatmap.bpm,
        "offset_ms": beatmap.offset_ms,
        "audio_file": beatmap.audio_file,
        "events": [
            {
                "time_ms": ev.time_ms,
                "target_angles": {k.value: v for k, v in ev.target_angles.items()},
                "duration_ms": ev.duration_ms,
            }
            for ev in beatmap.events
        ],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
