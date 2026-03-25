from __future__ import annotations

from unittest.mock import MagicMock

from exca_dance.ui.screens.gameplay_screen import GameplayScreen


def test_update_does_not_raise_when_upcoming_events_are_empty() -> None:
    renderer = MagicMock()
    text_renderer = MagicMock()
    game_loop = MagicMock()
    hud = MagicMock()
    visual_cues = MagicMock()
    viewport_layout = MagicMock()

    game_loop.tick.return_value = [MagicMock()]
    game_loop.get_upcoming_events.return_value = []
    game_loop._scoring._combo = 0
    game_loop.current_time_ms = 0.0
    game_loop.joint_angles = {}
    game_loop.state = "playing"

    screen = GameplayScreen(renderer, text_renderer, game_loop, hud, visual_cues, viewport_layout)
    screen._beatmap = MagicMock()

    screen.update(0.016)

    game_loop.get_upcoming_events.assert_any_call(500)
    game_loop.get_upcoming_events.assert_any_call(3000.0)
    assert game_loop.get_upcoming_events.call_count == 2
