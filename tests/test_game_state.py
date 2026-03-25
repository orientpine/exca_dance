from __future__ import annotations

from typing import Protocol

import pygame

from exca_dance.core.game_state import GameStateManager


class _Renderer(Protocol):
    width: int
    height: int


class _TextRenderer(Protocol):
    def render(self, *args: object, **kwargs: object) -> None: ...


class _MockScreen:
    def on_enter(self, **kwargs: object) -> None:
        _ = kwargs

    def handle_event(self, event: pygame.event.Event) -> None:
        _ = event
        return None

    def update(self, dt: float) -> None:
        _ = dt
        return None

    def render(self, renderer: _Renderer, text_renderer: _TextRenderer) -> None:
        _ = renderer
        _ = text_renderer


def _mock_screen() -> _MockScreen:
    return _MockScreen()


def test_transition_is_transitioning() -> None:
    mgr = GameStateManager()
    mgr.register("screen_a", _mock_screen())
    mgr.register("screen_b", _mock_screen())

    mgr.transition_to("screen_a")
    for _ in range(100):
        _ = mgr.update(0.01)

    mgr.transition_to("screen_b")
    assert mgr.is_transitioning


def test_transition_completes_after_06s() -> None:
    mgr = GameStateManager()
    mgr.register("screen_a", _mock_screen())
    mgr.register("screen_b", _mock_screen())

    mgr.transition_to("screen_a")
    for _ in range(100):
        _ = mgr.update(0.01)

    mgr.transition_to("screen_b")
    for _ in range(100):
        _ = mgr.update(0.01)

    assert not mgr.is_transitioning
