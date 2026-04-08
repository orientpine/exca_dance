from __future__ import annotations

import json
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from exca_dance.core.game_settings import GameSettings
from exca_dance.core.game_loop import GameLoop
from exca_dance.core.models import JointName
from exca_dance.core.constants import DEFAULT_JOINT_ANGLES


def test_default_mode_is_virtual() -> None:
    gs = GameSettings(filepath="nonexistent/path.json")
    assert gs.mode == "virtual"


def test_set_mode_real() -> None:
    gs = GameSettings(filepath="nonexistent/path.json")
    gs.mode = "real"
    assert gs.mode == "real"


def test_set_invalid_mode_raises() -> None:
    gs = GameSettings(filepath="nonexistent/path.json")
    with pytest.raises(ValueError, match="Invalid mode"):
        gs.mode = "invalid"


def test_save_and_load_roundtrip(tmp_path) -> None:
    path = str(tmp_path / "settings.json")
    gs = GameSettings(filepath=path)
    gs.mode = "real"
    gs.save()

    gs2 = GameSettings(filepath=path)
    assert gs2.mode == "real"


def test_load_missing_file_uses_defaults() -> None:
    gs = GameSettings(filepath="nonexistent/does_not_exist.json")
    assert gs.mode == "virtual"


def test_load_corrupt_json_uses_defaults(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not valid json {{{")
    gs = GameSettings(filepath=str(path))
    assert gs.mode == "virtual"


def test_load_invalid_mode_in_file_uses_default(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"mode": "bogus"}))
    gs = GameSettings(filepath=str(path))
    assert gs.mode == "virtual"


def test_default_playback_speed_is_1() -> None:
    gs = GameSettings(filepath="nonexistent/path.json")
    assert gs.playback_speed == 1.0


def test_set_playback_speed() -> None:
    gs = GameSettings(filepath="nonexistent/path.json")
    gs.playback_speed = 1.5
    assert gs.playback_speed == 1.5
    gs.playback_speed = 0.75
    assert gs.playback_speed == 0.75


def test_set_playback_speed_out_of_range_raises() -> None:
    gs = GameSettings(filepath="nonexistent/path.json")
    with pytest.raises(ValueError, match="Playback speed"):
        gs.playback_speed = 0.1
    with pytest.raises(ValueError, match="Playback speed"):
        gs.playback_speed = 5.0


def test_playback_speed_save_load_roundtrip(tmp_path) -> None:
    path = str(tmp_path / "settings.json")
    gs = GameSettings(filepath=path)
    gs.mode = "real"
    gs.playback_speed = 1.25
    gs.save()

    gs2 = GameSettings(filepath=path)
    assert gs2.mode == "real"
    assert gs2.playback_speed == 1.25


def test_load_invalid_speed_uses_default(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"mode": "virtual", "playback_speed": 99.0}))
    gs = GameSettings(filepath=str(path))
    assert gs.playback_speed == 1.0


def test_load_missing_speed_uses_default(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"mode": "virtual"}))
    gs = GameSettings(filepath=str(path))
    assert gs.playback_speed == 1.0


# ── GameLoop reads mode from GameSettings ────────────────────────────


def _make_loop_with_settings(
    game_settings: GameSettings,
) -> tuple[GameLoop, MagicMock, MagicMock]:
    renderer = MagicMock()
    audio = MagicMock()
    audio.get_position_ms.return_value = 0.0
    audio.is_playing.return_value = True
    fk = MagicMock()
    scoring = MagicMock()
    keybinding = MagicMock()
    bridge = MagicMock()
    viewport_layout = MagicMock()
    excavator_model = MagicMock()

    loop = cast(Any, GameLoop)(
        renderer,
        audio,
        fk,
        scoring,
        keybinding,
        bridge,
        viewport_layout,
        excavator_model,
        game_settings=game_settings,
    )
    return loop, keybinding, bridge


def test_game_loop_reads_mode_from_settings() -> None:
    gs = GameSettings(filepath="nonexistent/path.json")
    gs.mode = "real"
    loop, _, bridge = _make_loop_with_settings(gs)

    bridge.get_raw_angles.return_value = {
        JointName.SWING: 30.0,
        JointName.BOOM: -10.0,
        JointName.ARM: 50.0,
        JointName.BUCKET: 5.0,
    }
    bridge.get_sensor_timestamps.return_value = {}

    beatmap = MagicMock()
    beatmap.events = []
    beatmap.audio_file = "dummy.wav"
    loop.start_song(beatmap)
    loop.update_bridge()

    angles = cast(Any, loop.joint_angles)
    assert angles[JointName.SWING] == 30.0


def test_game_loop_responds_to_settings_change_at_start_song() -> None:
    gs = GameSettings(filepath="nonexistent/path.json")
    loop, keybinding, bridge = _make_loop_with_settings(gs)

    keybinding.get_joint_for_key.return_value = None
    bridge.get_raw_angles.return_value = {
        JointName.SWING: 99.0,
        JointName.BOOM: -10.0,
        JointName.ARM: 50.0,
        JointName.BUCKET: 5.0,
    }
    bridge.get_sensor_timestamps.return_value = {}

    beatmap = MagicMock()
    beatmap.events = []
    beatmap.audio_file = "dummy.wav"

    loop.start_song(beatmap)
    loop.tick(0.016)
    assert cast(Any, loop.joint_angles)[JointName.SWING] == DEFAULT_JOINT_ANGLES[JointName.SWING]

    gs.mode = "real"
    loop.start_song(beatmap)
    loop.update_bridge()
    assert cast(Any, loop.joint_angles)[JointName.SWING] == 99.0


def test_bridge_recreated_on_mode_change() -> None:
    gs = GameSettings(filepath="nonexistent/path.json")
    original_bridge = MagicMock()
    new_bridge = MagicMock()
    new_bridge.get_raw_angles.return_value = dict(DEFAULT_JOINT_ANGLES)
    factory = MagicMock(return_value=new_bridge)

    renderer = MagicMock()
    audio = MagicMock()
    audio.get_position_ms.return_value = 0.0
    audio.is_playing.return_value = True

    loop = cast(Any, GameLoop)(
        renderer,
        audio,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        original_bridge,
        MagicMock(),
        MagicMock(),
        game_settings=gs,
        bridge_factory=factory,
    )

    beatmap = MagicMock()
    beatmap.events = []
    beatmap.audio_file = "dummy.wav"

    loop.start_song(beatmap)
    factory.assert_not_called()

    gs.mode = "real"
    loop.start_song(beatmap)

    original_bridge.disconnect.assert_called_once()
    factory.assert_called_once_with("real")
