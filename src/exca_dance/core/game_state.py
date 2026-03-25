"""Game state machine for Exca Dance."""

from __future__ import annotations
import pygame
from exca_dance.core.game_loop import GameLoop, GameState as LoopState


class ScreenName:
    MAIN_MENU = "main_menu"
    SONG_SELECT = "song_select"
    GAMEPLAY = "gameplay"
    PAUSED = "paused"
    RESULTS = "results"
    LEADERBOARD = "leaderboard"
    SETTINGS = "settings"
    EDITOR = "editor"


class GameStateManager:
    """
    Manages screen transitions and delegates events/updates/renders
    to the currently active screen.
    """

    def __init__(self) -> None:
        self._screens: dict[str, object] = {}
        self._current: str = ScreenName.MAIN_MENU
        self._transition_data: dict = {}

    def register(self, name: str, screen) -> None:
        self._screens[name] = screen

    def transition_to(self, name: str, **kwargs) -> None:
        self._current = name
        self._transition_data = kwargs
        screen = self._screens.get(name)
        if screen and hasattr(screen, "on_enter"):
            screen.on_enter(**kwargs)

    def get_current_state(self) -> str:
        return self._current

    def handle_event(self, event: pygame.event.Event) -> None:
        screen = self._screens.get(self._current)
        if screen and hasattr(screen, "handle_event"):
            result = screen.handle_event(event)
            if result:
                self._handle_transition(result)

    def update(self, dt: float) -> None:
        screen = self._screens.get(self._current)
        if screen and hasattr(screen, "update"):
            result = screen.update(dt)
            if result:
                self._handle_transition(result)

    def render(self, renderer, text_renderer) -> None:
        screen = self._screens.get(self._current)
        if screen and hasattr(screen, "render"):
            screen.render(renderer, text_renderer)

    def _handle_transition(self, result) -> None:
        if isinstance(result, str):
            self.transition_to(result)
        elif isinstance(result, tuple) and len(result) == 2:
            name, kwargs = result
            if isinstance(kwargs, dict):
                self.transition_to(name, **kwargs)
            else:
                self.transition_to(name)
