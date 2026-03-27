from __future__ import annotations

import json
from typing import Any

import pytest

from exca_dance.core.beatmap import load_beatmap, save_beatmap, validate_beatmap
from exca_dance.core.models import BeatEvent, BeatMap, JointName


def _valid_payload() -> dict[str, Any]:
    return {
        "title": "Test Song",
        "artist": "Test Artist",
        "bpm": 120,
        "offset_ms": 10,
        "audio_file": "song.ogg",
        "events": [
            {
                "time_ms": 1000,
                "target_angles": {"boom": 10.0, "arm": 5.0},
                "duration_ms": 250,
            }
        ],
    }


def test_load_valid_json_returns_beatmap_with_expected_fields(tmp_path) -> None:
    data = _valid_payload()
    path = tmp_path / "valid.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    beatmap = load_beatmap(str(path))

    assert beatmap.title == "Test Song"
    assert beatmap.artist == "Test Artist"
    assert beatmap.bpm == 120.0
    assert beatmap.offset_ms == 10
    assert beatmap.audio_file == "song.ogg"
    assert len(beatmap.events) == 1
    assert beatmap.events[0].time_ms == 1000
    assert beatmap.events[0].target_angles[JointName.BOOM] == 10.0


def test_validate_missing_title_returns_title_error() -> None:
    data = _valid_payload()
    data.pop("title")

    errors = validate_beatmap(data)

    assert any("title" in error for error in errors)


def test_validate_invalid_angle_outside_joint_limits_returns_error() -> None:
    data = _valid_payload()
    data["events"][0]["target_angles"]["boom"] = 999.0

    errors = validate_beatmap(data)

    assert any("out of range" in error for error in errors)


def test_events_are_sorted_by_time_after_load(tmp_path) -> None:
    data = _valid_payload()
    data["events"] = [
        {"time_ms": 800, "target_angles": {"arm": 5.0}, "duration_ms": 300},
        {"time_ms": 100, "target_angles": {"boom": 10.0}, "duration_ms": 200},
        {"time_ms": 400, "target_angles": {"bucket": 50.0}, "duration_ms": 250},
    ]
    path = tmp_path / "unsorted.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    beatmap = load_beatmap(str(path))

    assert [event.time_ms for event in beatmap.events] == [100, 400, 800]


def test_save_then_load_roundtrip_preserves_data(tmp_path) -> None:
    original = BeatMap(
        title="Roundtrip",
        artist="Artist",
        bpm=128.0,
        offset_ms=-20,
        audio_file="roundtrip.ogg",
        events=[
            BeatEvent(
                time_ms=500,
                target_angles={JointName.BOOM: 10.0, JointName.ARM: 20.0},
                duration_ms=300,
            ),
            BeatEvent(
                time_ms=100,
                target_angles={JointName.SWING: -45.0},
                duration_ms=200,
            ),
        ],
    )

    path = tmp_path / "nested" / "roundtrip.json"
    save_beatmap(original, str(path))
    loaded = load_beatmap(str(path))

    assert loaded.title == original.title
    assert loaded.artist == original.artist
    assert loaded.bpm == original.bpm
    assert loaded.offset_ms == original.offset_ms
    assert loaded.audio_file == original.audio_file
    assert [event.time_ms for event in loaded.events] == [100, 500]
    assert loaded.events[0].target_angles[JointName.SWING] == -45.0
    assert loaded.events[1].target_angles[JointName.BOOM] == 10.0
    assert loaded.events[1].target_angles[JointName.ARM] == 20.0


def test_validate_empty_events_list_is_valid() -> None:
    data = _valid_payload()
    data["events"] = []

    errors = validate_beatmap(data)

    assert errors == []


def test_load_malformed_json_raises_value_error(tmp_path) -> None:
    path = tmp_path / "broken.json"
    path.write_text('{"title": "X", ', encoding="utf-8")

    with pytest.raises(ValueError):
        load_beatmap(str(path))


def test_validate_unknown_joint_name_returns_joint_error() -> None:
    data = _valid_payload()
    data["events"][0]["target_angles"] = {"not_a_joint": 10.0}

    errors = validate_beatmap(data)

    assert any("not_a_joint" in error for error in errors)
