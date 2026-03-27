"""GameplayScreen tests — verify screen orchestration and data isolation.

Includes integration tests verifying that visual_cues receives player angles
and upcoming events on separate data paths, confirming that operating the
excavator does NOT move the target ghost.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pygame

from exca_dance.core.game_loop import GameState as LoopState
from exca_dance.core.models import BeatEvent, JointName, Judgment
from exca_dance.ui.screens.gameplay_screen import GameplayScreen


def _make_gameplay_screen(
    **overrides: object,
) -> tuple[GameplayScreen, MagicMock, MagicMock, MagicMock]:
    """Create a GameplayScreen with all mocked dependencies.

    Returns (screen, game_loop, visual_cues, hud).
    """
    renderer = MagicMock()
    text_renderer = MagicMock()
    game_loop = MagicMock()
    hud = MagicMock()
    visual_cues = MagicMock()
    viewport_layout = MagicMock()
    hit_sounds: dict[Judgment, pygame.mixer.Sound] = {}

    game_loop.state = overrides.get("state", "playing")
    game_loop.tick.return_value = overrides.get("tick_return", [])
    game_loop.get_upcoming_events.return_value = overrides.get("upcoming", [])
    game_loop._scoring._combo = 0
    game_loop.current_time_ms = overrides.get("current_time_ms", 0.0)
    game_loop.joint_angles = overrides.get("joint_angles", {j: 0.0 for j in JointName})

    screen = GameplayScreen(
        renderer,
        text_renderer,
        game_loop,
        hud,
        visual_cues,
        viewport_layout,
        hit_sounds,
    )
    return screen, game_loop, visual_cues, hud


# ── Pre-existing tests (fixed: now pass hit_sounds) ─────────────────


def test_update_does_not_raise_when_upcoming_events_are_empty() -> None:
    screen, game_loop, _, _ = _make_gameplay_screen(
        tick_return=[MagicMock()],
    )
    screen._beatmap = MagicMock()

    screen.update(0.016)

    game_loop.get_upcoming_events.assert_any_call(500)
    game_loop.get_upcoming_events.assert_any_call(6000.0)
    assert game_loop.get_upcoming_events.call_count == 2


def test_pause_selected_default_zero() -> None:
    screen, _, _, _ = _make_gameplay_screen()
    assert screen._pause_selected == 0


def test_pause_selected_changes_on_up_and_down_when_paused() -> None:
    screen, _, _, _ = _make_gameplay_screen(state=LoopState.PAUSED)

    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
    assert screen._pause_selected == 0

    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
    assert screen._pause_selected == 1


# ── Integration: visual_cues receives correct data paths ────────────


def test_visual_cues_update_receives_player_angles_not_target() -> None:
    """GameplayScreen.update() must pass player joint_angles to visual_cues.update().

    The visual_cues.update() call must receive the player's current angles
    as current_angles, NOT the target angles from beat events.
    """
    player_angles = {
        JointName.SWING: 45.0,
        JointName.BOOM: 10.0,
        JointName.ARM: -15.0,
        JointName.BUCKET: 30.0,
    }

    upcoming_events = [
        BeatEvent(time_ms=2000, target_angles={JointName.BOOM: 60.0}),
    ]

    screen, game_loop, visual_cues, _ = _make_gameplay_screen()

    game_loop.tick.return_value = []
    game_loop._scoring._combo = 0
    game_loop.current_time_ms = 1000.0
    game_loop.joint_angles = player_angles
    game_loop.state = "playing"
    # tick() returns no results → only the 3000ms get_upcoming_events call fires
    game_loop.get_upcoming_events.return_value = upcoming_events
    screen._beatmap = MagicMock()

    screen.update(0.016)

    # visual_cues.update must have been called
    visual_cues.update.assert_called_once()
    vc_args = visual_cues.update.call_args

    # Second argument (current_angles) must be the player's angles
    vc_current_angles = vc_args[0][1]
    assert vc_current_angles == player_angles

    # Third argument (upcoming_events) must be the beat events
    vc_upcoming = vc_args[0][2]
    assert vc_upcoming == upcoming_events

    # Verify: the player angles passed to visual_cues are NOT the target angles
    assert vc_current_angles[JointName.BOOM] == 10.0  # player's value
    assert vc_current_angles[JointName.BOOM] != 60.0  # NOT the target


def test_visual_cues_receives_separate_data_across_frames() -> None:
    """Over multiple frames, visual_cues.update() must always receive player angles.

    Simulates the player moving joints while a target event exists.
    """
    screen, game_loop, visual_cues, _ = _make_gameplay_screen()
    screen._beatmap = MagicMock()

    target_event = BeatEvent(
        time_ms=3000,
        target_angles={JointName.BOOM: 45.0, JointName.ARM: -20.0},
    )

    # Simulate 3 frames with changing player angles
    frame_angles = [
        {JointName.SWING: 0.0, JointName.BOOM: 0.0, JointName.ARM: 0.0, JointName.BUCKET: 0.0},
        {JointName.SWING: 30.0, JointName.BOOM: 5.0, JointName.ARM: 0.0, JointName.BUCKET: 0.0},
        {JointName.SWING: 60.0, JointName.BOOM: 10.0, JointName.ARM: 5.0, JointName.BUCKET: 0.0},
    ]

    for i, angles in enumerate(frame_angles):
        visual_cues.reset_mock()
        game_loop.joint_angles = angles
        game_loop.get_upcoming_events.side_effect = [
            [],  # 500ms call
            [target_event],  # 3000ms call
        ]

        screen.update(0.016)

        visual_cues.update.assert_called_once()
        vc_angles = visual_cues.update.call_args[0][1]

        # Must always be the player's angles for this frame
        assert vc_angles == angles, (
            f"Frame {i}: visual_cues received {vc_angles}, expected {angles}"
        )

        # Must never be the target angles
        assert vc_angles.get(JointName.BOOM) != 45.0 or i == 0, (
            f"Frame {i}: visual_cues received target BOOM=45.0 instead of player"
        )


def test_game_loop_tick_called_before_visual_cues_update() -> None:
    """tick() must be called before visual_cues.update() in each frame.

    This ensures joint angles are updated from input before being passed
    to the visual cue system.
    """
    screen, game_loop, visual_cues, _ = _make_gameplay_screen()
    screen._beatmap = MagicMock()

    call_order: list[str] = []
    game_loop.tick.side_effect = lambda dt: (call_order.append("tick"), [])[1]
    visual_cues.update.side_effect = lambda *a: call_order.append("visual_cues.update")
    game_loop.get_upcoming_events.return_value = []

    screen.update(0.016)

    assert call_order == ["tick", "visual_cues.update"]
