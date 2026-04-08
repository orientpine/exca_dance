from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pygame

from exca_dance.core.constants import DEFAULT_JOINT_ANGLES, JOINT_LIMITS
from exca_dance.core.game_loop import GameLoop
from exca_dance.core.models import JointName


def _make_game_loop() -> tuple[GameLoop, MagicMock, MagicMock]:
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
        renderer, audio, fk, scoring, keybinding, bridge, viewport_layout, excavator_model
    )
    return loop, keybinding, bridge


def _make_game_loop_virtual() -> tuple[GameLoop, MagicMock, MagicMock]:
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
        mode="virtual",
    )
    return loop, keybinding, bridge


def _make_game_loop_real() -> tuple[GameLoop, MagicMock, MagicMock]:
    from exca_dance.core.joint_limits import JointLimitsConfig

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
        mode="real",
        joint_limits=JointLimitsConfig(filepath="nonexistent/path.json"),
    )
    return loop, keybinding, bridge


def _start_song(loop: GameLoop) -> None:
    beatmap = MagicMock()
    beatmap.events = []
    beatmap.audio_file = "dummy.wav"
    loop.start_song(beatmap)


def test_real_mode_reads_bridge_angles() -> None:
    loop, _, bridge = _make_game_loop_real()
    bridge.get_raw_angles.return_value = {
        JointName.SWING: 45.0,
        JointName.BOOM: -30.0,
        JointName.ARM: 55.0,
        JointName.BUCKET: 10.0,
    }
    bridge.get_sensor_timestamps.return_value = {}
    _start_song(loop)

    loop.update_bridge()

    angles = cast(Any, loop.joint_angles)
    assert angles[JointName.SWING] == 45.0


def test_real_mode_ignores_keyboard() -> None:
    loop, keybinding, bridge = _make_game_loop_real()
    keybinding.get_joint_for_key.return_value = (JointName.BOOM, 1)
    bridge.get_raw_angles.return_value = {
        JointName.SWING: 0.0,
        JointName.BOOM: -10.0,
        JointName.ARM: 21.0,
        JointName.BUCKET: 0.0,
    }
    bridge.get_sensor_timestamps.return_value = {}
    _start_song(loop)
    loop._held_keys.add(pygame.K_w)

    loop.update_bridge()

    angles = cast(Any, loop.joint_angles)
    assert angles[JointName.BOOM] == -10.0


def test_real_mode_skips_send_command() -> None:
    loop, _, bridge = _make_game_loop_real()
    bridge.get_raw_angles.return_value = dict(DEFAULT_JOINT_ANGLES)
    bridge.get_sensor_timestamps.return_value = {}
    _start_song(loop)
    bridge.send_command.reset_mock()

    loop.tick(0.016)

    bridge.send_command.assert_not_called()


def test_real_mode_clamps_to_joint_limits() -> None:
    loop, _, bridge = _make_game_loop_real()
    bridge.get_raw_angles.return_value = {
        JointName.SWING: 0.0,
        JointName.BOOM: 999.0,
        JointName.ARM: 21.0,
        JointName.BUCKET: 0.0,
    }
    bridge.get_sensor_timestamps.return_value = {}
    _start_song(loop)

    loop.update_bridge()

    angles = cast(Any, loop.joint_angles)
    assert angles[JointName.BOOM] == cast(Any, JOINT_LIMITS)[JointName.BOOM][1]


def test_real_mode_handles_empty_angles() -> None:
    loop, _, bridge = _make_game_loop_real()
    bridge.get_raw_angles.return_value = {}
    bridge.get_sensor_timestamps.return_value = {}
    _start_song(loop)

    loop.update_bridge()

    angles = cast(Any, loop.joint_angles)
    assert angles == DEFAULT_JOINT_ANGLES


def test_virtual_mode_unchanged() -> None:
    loop, keybinding, bridge = _make_game_loop_virtual()
    keybinding.get_joint_for_key.return_value = (JointName.BOOM, 1)
    bridge.get_current_angles.return_value = dict(DEFAULT_JOINT_ANGLES)
    _start_song(loop)
    loop._held_keys.add(pygame.K_w)

    loop.tick(0.1)

    bridge.send_command.assert_called()
    angles = cast(Any, loop.joint_angles)
    assert angles[JointName.BOOM] > cast(Any, DEFAULT_JOINT_ANGLES)[JointName.BOOM]
