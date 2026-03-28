"""GameLoop tests — verify player input only affects the player excavator model.

Regression tests for the bug where operating the excavator also moved the
target ghost pose.  These tests verify the data isolation between the player's
joint_angles (modified by key presses) and any external model/ghost state.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pygame

from exca_dance.core.constants import DEFAULT_JOINT_ANGLES, JOINT_ANGULAR_VELOCITY, JOINT_LIMITS
from exca_dance.core.game_loop import GameLoop
from exca_dance.core.models import BeatEvent, JointName


def _make_game_loop() -> tuple[GameLoop, MagicMock, MagicMock, MagicMock]:
    """Create a GameLoop with mocked dependencies.

    Returns (game_loop, keybinding_mock, excavator_model_mock, bridge_mock).
    """
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

    loop = GameLoop(
        renderer, audio, fk, scoring, keybinding, bridge, viewport_layout, excavator_model
    )
    return loop, keybinding, excavator_model, bridge


def _start_song_with_events(
    loop: GameLoop,
    events: list[BeatEvent] | None = None,
) -> None:
    """Start a song on the game loop with the given beat events."""
    beatmap = MagicMock()
    beatmap.events = events or []
    beatmap.audio_file = "dummy.wav"
    loop.start_song(beatmap)


# ── Player joint angle isolation ─────────────────────────────────────


def test_update_joints_only_modifies_player_joint_angles() -> None:
    """_update_joints must ONLY modify the player's internal _joint_angles.

    The excavator_model is updated separately in tick(), not in _update_joints.
    """
    loop, keybinding, excavator_model, _ = _make_game_loop()

    # Simulate holding BOOM positive key
    keybinding.get_joint_for_key.return_value = (JointName.BOOM, 1)
    _start_song_with_events(loop)

    # Record initial angles
    initial_angles = dict(loop._joint_angles)

    # Simulate key held
    loop._held_keys.add(pygame.K_w)

    # Call _update_joints directly
    dt = 0.1  # 100ms
    loop._update_joints(dt)

    # BOOM must have changed
    expected_delta = 1 * JOINT_ANGULAR_VELOCITY * dt
    assert loop._joint_angles[JointName.BOOM] == initial_angles[JointName.BOOM] + expected_delta

    # Other joints must NOT have changed
    assert loop._joint_angles[JointName.SWING] == initial_angles[JointName.SWING]
    assert loop._joint_angles[JointName.ARM] == initial_angles[JointName.ARM]
    assert loop._joint_angles[JointName.BUCKET] == initial_angles[JointName.BUCKET]

    # excavator_model.update must NOT have been called by _update_joints
    # (it was called once by start_song → tick is not called yet)
    excavator_model.update.reset_mock()
    loop._update_joints(dt)
    excavator_model.update.assert_not_called()


def test_tick_passes_player_angles_to_excavator_model() -> None:
    """tick() must call excavator_model.update() with the player's current angles."""
    loop, keybinding, excavator_model, _ = _make_game_loop()

    keybinding.get_joint_for_key.return_value = (JointName.SWING, 1)
    _start_song_with_events(loop)
    excavator_model.update.reset_mock()

    # Hold SWING positive key
    loop._held_keys.add(pygame.K_a)

    loop.tick(0.05)

    # excavator_model.update must have been called with the player's angles
    excavator_model.update.assert_called_once()
    passed_angles = excavator_model.update.call_args[0][0]
    assert passed_angles[JointName.SWING] == 1 * JOINT_ANGULAR_VELOCITY * 0.05


def test_tick_does_not_modify_beat_event_target_angles() -> None:
    """tick() must never mutate BeatEvent.target_angles.

    BeatEvent is frozen, but target_angles is a mutable dict.  Verify that
    the game loop does NOT write into it.
    """
    loop, keybinding, _, _ = _make_game_loop()

    target = {JointName.BOOM: 45.0, JointName.ARM: -20.0}
    original_target = dict(target)
    event = BeatEvent(time_ms=500, target_angles=target)

    keybinding.get_joint_for_key.return_value = (JointName.BOOM, 1)
    _start_song_with_events(loop, [event])

    # Hold a key and tick several frames
    loop._held_keys.add(pygame.K_w)
    for _ in range(10):
        loop.tick(0.016)

    # target_angles dict must be untouched
    assert event.target_angles == original_target


def test_joint_angles_property_returns_copy() -> None:
    """joint_angles property must return a copy, not the internal dict.

    Mutating the returned dict must NOT affect the GameLoop's internal state.
    """
    loop, _, _, _ = _make_game_loop()
    _start_song_with_events(loop)

    angles = loop.joint_angles
    angles[JointName.BOOM] = 999.0  # mutate the returned copy

    # Internal state must be unaffected
    assert loop._joint_angles[JointName.BOOM] == DEFAULT_JOINT_ANGLES[JointName.BOOM]
    assert loop.joint_angles[JointName.BOOM] == DEFAULT_JOINT_ANGLES[JointName.BOOM]


def test_multiple_keys_held_only_affect_respective_joints() -> None:
    """Holding multiple keys must only affect their mapped joints."""
    loop, keybinding, _, _ = _make_game_loop()

    # Map two keys to different joints
    def mock_get_joint(key: int) -> tuple[JointName, int] | None:
        if key == pygame.K_w:
            return (JointName.BOOM, 1)
        if key == pygame.K_UP:
            return (JointName.ARM, 1)
        return None

    keybinding.get_joint_for_key.side_effect = mock_get_joint
    _start_song_with_events(loop)

    loop._held_keys.add(pygame.K_w)
    loop._held_keys.add(pygame.K_UP)

    dt = 0.1
    loop._update_joints(dt)

    expected = JOINT_ANGULAR_VELOCITY * dt
    assert loop._joint_angles[JointName.BOOM] == DEFAULT_JOINT_ANGLES[JointName.BOOM] + expected
    assert loop._joint_angles[JointName.ARM] == DEFAULT_JOINT_ANGLES[JointName.ARM] + expected
    # Untouched joints stay at defaults
    assert loop._joint_angles[JointName.SWING] == DEFAULT_JOINT_ANGLES[JointName.SWING]
    assert loop._joint_angles[JointName.BUCKET] == DEFAULT_JOINT_ANGLES[JointName.BUCKET]


def test_joint_angles_clamped_to_limits() -> None:
    """_update_joints must clamp angles to JOINT_LIMITS."""
    loop, keybinding, _, _ = _make_game_loop()

    keybinding.get_joint_for_key.return_value = (JointName.BOOM, 1)
    _start_song_with_events(loop)

    loop._held_keys.add(pygame.K_w)

    # Tick for a very long time to exceed BOOM upper limit (60°)
    for _ in range(100):
        loop._update_joints(0.1)

    lo, hi = JOINT_LIMITS[JointName.BOOM]
    assert loop._joint_angles[JointName.BOOM] == hi


def test_no_keys_held_no_angle_change() -> None:
    """When no keys are held, joint angles must not change."""
    loop, keybinding, _, _ = _make_game_loop()
    _start_song_with_events(loop)

    initial = dict(loop._joint_angles)
    loop._update_joints(0.016)

    for joint in JointName:
        assert loop._joint_angles[joint] == initial[joint]


# ── Ghost / target model isolation ───────────────────────────────────


def test_excavator_model_update_receives_only_player_state() -> None:
    """The excavator model must receive player angles, never ghost/target angles.

    Simulates a full gameplay frame: key press → tick → verify model update.
    """
    loop, keybinding, excavator_model, _ = _make_game_loop()

    target = {JointName.BOOM: 45.0}
    event = BeatEvent(time_ms=5000, target_angles=target)

    keybinding.get_joint_for_key.return_value = (JointName.SWING, 1)
    _start_song_with_events(loop, [event])
    excavator_model.update.reset_mock()

    loop._held_keys.add(pygame.K_a)
    loop.tick(0.1)

    passed_angles = excavator_model.update.call_args[0][0]

    # Model receives player's SWING angle (modified by input)
    assert passed_angles[JointName.SWING] == 1 * JOINT_ANGULAR_VELOCITY * 0.1
    # Model receives player's BOOM at 0.0 (player hasn't touched it)
    assert passed_angles[JointName.BOOM] == DEFAULT_JOINT_ANGLES[JointName.BOOM]
    # NOT the target's BOOM=45.0
    assert passed_angles[JointName.BOOM] != target[JointName.BOOM]


def test_bridge_receives_only_player_angles() -> None:
    """The ROS2 bridge must receive player angles, not target angles."""
    loop, keybinding, _, bridge = _make_game_loop()

    target = {JointName.ARM: -30.0}
    event = BeatEvent(time_ms=5000, target_angles=target)

    keybinding.get_joint_for_key.return_value = (JointName.BOOM, 1)
    _start_song_with_events(loop, [event])
    bridge.send_command.reset_mock()

    loop._held_keys.add(pygame.K_w)
    loop.tick(0.05)

    passed_angles = bridge.send_command.call_args[0][0]
    # Bridge receives player's ARM at default (not target's -30.0)
    assert passed_angles[JointName.ARM] == DEFAULT_JOINT_ANGLES[JointName.ARM]


def test_player_input_across_multiple_frames_does_not_leak() -> None:
    """Over multiple frames, player input must accumulate only in player angles.

    Verifies no cross-contamination between frames.
    """
    loop, keybinding, excavator_model, _ = _make_game_loop()

    keybinding.get_joint_for_key.return_value = (JointName.BOOM, 1)
    _start_song_with_events(loop)
    excavator_model.update.reset_mock()

    loop._held_keys.add(pygame.K_w)

    dt = 0.016
    for frame in range(5):
        loop.tick(dt)

        passed = excavator_model.update.call_args[0][0]
        expected_boom = min(
            JOINT_LIMITS[JointName.BOOM][1],
            JOINT_ANGULAR_VELOCITY * dt * (frame + 1),
        )
        assert abs(passed[JointName.BOOM] - expected_boom) < 0.001, (
            f"Frame {frame}: expected BOOM={expected_boom:.3f}, got {passed[JointName.BOOM]:.3f}"
        )
        # Non-operated joints stay at defaults
        assert passed[JointName.SWING] == DEFAULT_JOINT_ANGLES[JointName.SWING]
        assert passed[JointName.ARM] == DEFAULT_JOINT_ANGLES[JointName.ARM]
        assert passed[JointName.BUCKET] == DEFAULT_JOINT_ANGLES[JointName.BUCKET]


def test_handle_event_keydown_only_adds_to_held_keys() -> None:
    """handle_event KEYDOWN must only add keys to _held_keys set.

    It must NOT directly modify joint_angles or the excavator model.
    """
    loop, _, excavator_model, _ = _make_game_loop()
    _start_song_with_events(loop)
    excavator_model.update.reset_mock()

    initial_angles = dict(loop._joint_angles)

    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w)
    loop.handle_event(event)

    # Key added to held set
    assert pygame.K_w in loop._held_keys
    # Angles NOT modified yet (happens in tick → _update_joints)
    for joint in JointName:
        assert loop._joint_angles[joint] == initial_angles[joint]
    # Model NOT updated by handle_event
    excavator_model.update.assert_not_called()


def test_handle_event_keyup_removes_from_held_keys() -> None:
    """handle_event KEYUP must remove keys from _held_keys set."""
    loop, _, _, _ = _make_game_loop()
    _start_song_with_events(loop)

    loop._held_keys.add(pygame.K_w)
    event = pygame.event.Event(pygame.KEYUP, key=pygame.K_w)
    loop.handle_event(event)

    assert pygame.K_w not in loop._held_keys
