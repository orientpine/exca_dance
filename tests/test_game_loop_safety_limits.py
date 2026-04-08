"""Tests for the real-mode safety gate in GameLoop.

The gate lives in `GameLoop._apply_safety_limits()` and is exercised through
the runtime path `GameLoop.update_bridge()`. All tests drive the loop through
that public entry point because that is what `__main__.main()` calls every
frame; `tick(dt)` never reaches the gate in real mode.
"""

from __future__ import annotations

import time
from typing import Any, cast
from unittest.mock import MagicMock

import pygame

from exca_dance.core.constants import (
    JOINT_LIMITS,
    SAFETY_SENSOR_GRACE_SEC,
    SAFETY_SENSOR_STALE_SEC,
)
from exca_dance.core.game_loop import (
    GameLoop,
    GameState,
    SAFETY_REASON_MAX,
    SAFETY_REASON_MIN,
    SAFETY_REASON_NO_SENSOR,
    SAFETY_REASON_STALE,
)
from exca_dance.core.models import JointName


def _make_loop(mode: str = "real") -> tuple[GameLoop, MagicMock, MagicMock, MagicMock]:
    renderer = MagicMock()
    audio = MagicMock()
    audio.get_position_ms.return_value = 0.0
    audio.is_playing.return_value = True
    fk = MagicMock()
    scoring = MagicMock()
    keybinding = MagicMock()
    keybinding.get_joint_for_key.return_value = None
    bridge = MagicMock()
    bridge.get_raw_angles.return_value = {}
    bridge.get_sensor_timestamps.return_value = {}
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
        mode=mode,
    )
    return loop, bridge, keybinding, scoring


def _arm_safety(loop: GameLoop) -> None:
    """Pretend the grace window has already elapsed so fail-close is active."""
    loop._safety_armed_at = time.perf_counter() - SAFETY_SENSOR_GRACE_SEC - 1.0


def _fresh_timestamps(joints: list[JointName]) -> dict[JointName, float]:
    now = time.perf_counter()
    return {j: now for j in joints}


def _stale_timestamps(joints: list[JointName]) -> dict[JointName, float]:
    then = time.perf_counter() - SAFETY_SENSOR_STALE_SEC - 0.5
    return {j: then for j in joints}


def _start_playing(loop: GameLoop) -> None:
    loop._state = GameState.PLAYING


def _push_joystick(loop: GameLoop, joint: JointName, value: float) -> None:
    """Inject a velocity for `joint` by stubbing `_get_input_velocities`."""
    all_joints = {j: 0.0 for j in JointName}
    all_joints[joint] = value
    cast(Any, loop)._get_input_velocities = lambda: dict(all_joints)


def _push_joysticks(loop: GameLoop, velocities: dict[JointName, float]) -> None:
    merged = {j: 0.0 for j in JointName}
    merged.update(velocities)
    cast(Any, loop)._get_input_velocities = lambda: dict(merged)


def _sent_velocity(bridge: MagicMock) -> dict[JointName, float]:
    assert bridge.send_velocity.called, "send_velocity was never called"
    args, _ = bridge.send_velocity.call_args
    return args[0]


def _mid_angles() -> dict[JointName, float]:
    result: dict[JointName, float] = {}
    for joint, (lo, hi) in JOINT_LIMITS.items():
        result[joint] = (lo + hi) / 2.0
    return result



def test_within_limits_passes_velocity_unchanged() -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    bridge.get_raw_angles.return_value = _mid_angles()
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    _push_joystick(loop, JointName.BOOM, 0.5)

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert sent[JointName.BOOM] == 0.5
    assert loop.safety_blocked_joints == {}



def test_below_min_blocks_negative_velocity() -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    lo, hi = JOINT_LIMITS[JointName.BOOM]
    bridge.get_raw_angles.return_value = {**_mid_angles(), JointName.BOOM: lo - 5.0}
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    _push_joystick(loop, JointName.BOOM, -0.8)

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert sent[JointName.BOOM] == 0.0
    assert loop.safety_blocked_joints == {JointName.BOOM: SAFETY_REASON_MIN}


def test_below_min_allows_positive_recovery_velocity() -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    lo, hi = JOINT_LIMITS[JointName.BOOM]
    bridge.get_raw_angles.return_value = {**_mid_angles(), JointName.BOOM: lo - 5.0}
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    _push_joystick(loop, JointName.BOOM, 0.8)

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert sent[JointName.BOOM] == 0.8
    assert loop.safety_blocked_joints == {}



def test_above_max_blocks_positive_velocity() -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    lo, hi = JOINT_LIMITS[JointName.ARM]
    bridge.get_raw_angles.return_value = {**_mid_angles(), JointName.ARM: hi + 5.0}
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    _push_joystick(loop, JointName.ARM, 0.9)

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert sent[JointName.ARM] == 0.0
    assert loop.safety_blocked_joints == {JointName.ARM: SAFETY_REASON_MAX}


def test_above_max_allows_negative_recovery_velocity() -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    lo, hi = JOINT_LIMITS[JointName.ARM]
    bridge.get_raw_angles.return_value = {**_mid_angles(), JointName.ARM: hi + 5.0}
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    _push_joystick(loop, JointName.ARM, -0.9)

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert sent[JointName.ARM] == -0.9
    assert loop.safety_blocked_joints == {}



def test_at_max_exactly_blocks_further_positive() -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    lo, hi = JOINT_LIMITS[JointName.BUCKET]
    bridge.get_raw_angles.return_value = {**_mid_angles(), JointName.BUCKET: hi}
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    _push_joystick(loop, JointName.BUCKET, 0.5)

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert sent[JointName.BUCKET] == 0.0
    assert loop.safety_blocked_joints == {JointName.BUCKET: SAFETY_REASON_MAX}


def test_at_min_exactly_blocks_further_negative() -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    lo, hi = JOINT_LIMITS[JointName.BUCKET]
    bridge.get_raw_angles.return_value = {**_mid_angles(), JointName.BUCKET: lo}
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    _push_joystick(loop, JointName.BUCKET, -0.5)

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert sent[JointName.BUCKET] == 0.0
    assert loop.safety_blocked_joints == {JointName.BUCKET: SAFETY_REASON_MIN}



def test_deadband_velocity_does_not_trigger_block() -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    lo, hi = JOINT_LIMITS[JointName.BOOM]
    bridge.get_raw_angles.return_value = {**_mid_angles(), JointName.BOOM: lo - 5.0}
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    _push_joystick(loop, JointName.BOOM, -0.001)

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert sent[JointName.BOOM] == -0.001
    assert loop.safety_blocked_joints == {}



def test_missing_sensor_after_grace_blocks_active_velocity() -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    bridge.get_raw_angles.return_value = {}
    bridge.get_sensor_timestamps.return_value = {}
    _push_joystick(loop, JointName.SWING, 0.5)

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert sent[JointName.SWING] == 0.0
    assert loop.safety_blocked_joints == {JointName.SWING: SAFETY_REASON_NO_SENSOR}


def test_missing_sensor_inside_grace_allows_velocity() -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    bridge.get_raw_angles.return_value = {}
    bridge.get_sensor_timestamps.return_value = {}
    _push_joystick(loop, JointName.SWING, 0.5)

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert sent[JointName.SWING] == 0.5
    assert loop.safety_blocked_joints == {}



def test_stale_sensor_blocks_active_velocity() -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    bridge.get_raw_angles.return_value = _mid_angles()
    bridge.get_sensor_timestamps.return_value = _stale_timestamps(list(JointName))
    _push_joystick(loop, JointName.SWING, 0.4)

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert sent[JointName.SWING] == 0.0
    assert loop.safety_blocked_joints == {JointName.SWING: SAFETY_REASON_STALE}


def test_stale_sensor_with_zero_velocity_does_not_block() -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    bridge.get_raw_angles.return_value = _mid_angles()
    bridge.get_sensor_timestamps.return_value = _stale_timestamps(list(JointName))

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert all(v == 0.0 for v in sent.values())
    assert loop.safety_blocked_joints == {}



def test_multiple_joints_only_out_of_range_is_blocked() -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    lo_boom, hi_boom = JOINT_LIMITS[JointName.BOOM]
    bridge.get_raw_angles.return_value = {
        **_mid_angles(),
        JointName.BOOM: hi_boom + 3.0,
    }
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    _push_joysticks(
        loop,
        {
            JointName.SWING: 0.3,
            JointName.BOOM: 0.5,
            JointName.ARM: -0.2,
            JointName.BUCKET: 0.1,
        },
    )

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert sent[JointName.SWING] == 0.3
    assert sent[JointName.BOOM] == 0.0
    assert sent[JointName.ARM] == -0.2
    assert sent[JointName.BUCKET] == 0.1
    assert loop.safety_blocked_joints == {JointName.BOOM: SAFETY_REASON_MAX}



def test_menu_state_forces_zero_velocity_even_with_input() -> None:
    loop, bridge, _, _ = _make_loop()
    loop._state = GameState.MENU
    _arm_safety(loop)
    bridge.get_raw_angles.return_value = _mid_angles()
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    _push_joystick(loop, JointName.BOOM, 0.9)

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert all(v == 0.0 for v in sent.values())
    assert loop.safety_blocked_joints == {}


def test_paused_state_forces_zero_velocity_even_with_input() -> None:
    loop, bridge, _, _ = _make_loop()
    loop._state = GameState.PAUSED
    _arm_safety(loop)
    bridge.get_raw_angles.return_value = _mid_angles()
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    _push_joystick(loop, JointName.SWING, -0.9)

    loop.update_bridge()

    sent = _sent_velocity(bridge)
    assert all(v == 0.0 for v in sent.values())



def test_virtual_mode_does_not_invoke_safety_gate() -> None:
    loop, bridge, _, _ = _make_loop(mode="virtual")
    _start_playing(loop)

    loop.update_bridge()

    bridge.send_velocity.assert_not_called()
    assert loop.safety_blocked_joints == {}



def test_state_transition_log_fires_only_on_change(caplog: Any) -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    lo, hi = JOINT_LIMITS[JointName.ARM]
    bridge.get_raw_angles.return_value = {**_mid_angles(), JointName.ARM: hi + 5.0}
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    _push_joystick(loop, JointName.ARM, 0.7)

    with caplog.at_level("WARNING"):
        loop.update_bridge()
    first_warning_count = sum(1 for r in caplog.records if "SAFETY BLOCK" in r.message)
    assert first_warning_count == 1

    with caplog.at_level("WARNING"):
        loop.update_bridge()
    second_warning_count = sum(1 for r in caplog.records if "SAFETY BLOCK" in r.message)
    assert second_warning_count == 1, "should not log again while still blocked"


def test_recovery_log_fires_when_joint_re_enters_range(caplog: Any) -> None:
    loop, bridge, _, _ = _make_loop()
    _start_playing(loop)
    _arm_safety(loop)
    lo, hi = JOINT_LIMITS[JointName.BOOM]
    bridge.get_raw_angles.return_value = {**_mid_angles(), JointName.BOOM: hi + 5.0}
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    _push_joystick(loop, JointName.BOOM, 0.8)
    loop.update_bridge()
    assert JointName.BOOM in loop.safety_blocked_joints

    bridge.get_raw_angles.return_value = _mid_angles()
    bridge.get_sensor_timestamps.return_value = _fresh_timestamps(list(JointName))
    with caplog.at_level("INFO"):
        loop.update_bridge()

    assert loop.safety_blocked_joints == {}
    assert any("SAFETY CLEAR" in r.message for r in caplog.records)



def test_start_song_resets_safety_state() -> None:
    loop, bridge, _, _ = _make_loop()
    _arm_safety(loop)
    loop._safety_blocked = {JointName.BOOM: SAFETY_REASON_MAX}
    loop._unclamped_angles = {JointName.BOOM: 999.0}

    beatmap = MagicMock()
    beatmap.events = []
    beatmap.audio_file = "dummy.wav"
    loop.start_song(beatmap)

    assert loop.safety_blocked_joints == {}
    assert loop._unclamped_angles == {}


def test_stop_resets_safety_state_and_held_keys() -> None:
    loop, _, _, _ = _make_loop()
    loop._safety_blocked = {JointName.ARM: SAFETY_REASON_MIN}
    loop._unclamped_angles = {JointName.ARM: -50.0}
    loop._held_keys.add(pygame.K_w)

    loop.stop()

    assert loop.safety_blocked_joints == {}
    assert loop._unclamped_angles == {}
    assert loop._held_keys == set()
