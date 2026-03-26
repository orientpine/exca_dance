from __future__ import annotations

from unittest.mock import MagicMock

import pygame

from exca_dance.core.game_loop import GameState as LoopState
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


def test_pause_selected_default_zero() -> None:
    renderer = MagicMock()
    text_renderer = MagicMock()
    game_loop = MagicMock()
    hud = MagicMock()
    visual_cues = MagicMock()
    viewport_layout = MagicMock()

    screen = GameplayScreen(renderer, text_renderer, game_loop, hud, visual_cues, viewport_layout)

    assert screen._pause_selected == 0


def test_pause_selected_changes_on_up_and_down_when_paused() -> None:
    renderer = MagicMock()
    text_renderer = MagicMock()
    game_loop = MagicMock()
    hud = MagicMock()
    visual_cues = MagicMock()
    viewport_layout = MagicMock()

    game_loop.state = LoopState.PAUSED
    screen = GameplayScreen(renderer, text_renderer, game_loop, hud, visual_cues, viewport_layout)

    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
    assert screen._pause_selected == 0

    screen.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
    assert screen._pause_selected == 1
