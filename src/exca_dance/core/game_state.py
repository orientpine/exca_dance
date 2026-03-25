"""Game state machine for Exca Dance."""

from __future__ import annotations
from typing import Protocol, final
import pygame


TransitionResult = str | tuple[str, dict[str, object]]


class _Renderer(Protocol):
    width: int
    height: int


class _TextRenderer(Protocol):
    def render(self, *args: object, **kwargs: object) -> None: ...


class _Screen(Protocol):
    def on_enter(self, **kwargs: object) -> None: ...

    def handle_event(self, event: pygame.event.Event) -> TransitionResult | None: ...

    def update(self, dt: float) -> TransitionResult | None: ...

    def render(self, renderer: _Renderer, text_renderer: _TextRenderer) -> None: ...


@final
class ScreenName:
    MAIN_MENU = "main_menu"
    SONG_SELECT = "song_select"
    GAMEPLAY = "gameplay"
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
        self._screens: dict[str, _Screen] = {}
        self._current: str = ScreenName.MAIN_MENU
        self._transition_data: dict[str, object] = {}
        self._quit_requested: bool = False
        self._fade_state: str = "none"
        self._fade_alpha: float = 0.0
        self._pending_screen: str | None = None
        self._pending_kwargs: dict[str, object] = {}
        self._fade_duration: float = 0.3
        self._fade_elapsed: float = 0.0

    def register(self, name: str, screen: _Screen) -> None:
        self._screens[name] = screen

    def transition_to(self, name: str, **kwargs: object) -> None:
        self._pending_screen = name
        self._pending_kwargs = kwargs
        self._fade_state = "out"
        self._fade_elapsed = 0.0
        self._fade_alpha = 0.0

    @property
    def is_transitioning(self) -> bool:
        return self._fade_state != "none"

    @property
    def fade_alpha(self) -> float:
        return self._fade_alpha

    def get_current_state(self) -> str:
        return self._current

    def handle_event(self, event: pygame.event.Event) -> None:
        screen = self._screens.get(self._current)
        if screen and hasattr(screen, "handle_event"):
            result = screen.handle_event(event)
            if result:
                self._process_result(result)

    def update(self, dt: float) -> str | None:
        if self._quit_requested:
            return "quit"

        if self._fade_state == "out":
            self._fade_elapsed += dt
            self._fade_alpha = min(1.0, self._fade_elapsed / self._fade_duration)
            if self._fade_elapsed >= self._fade_duration:
                if self._pending_screen is not None:
                    self._current = self._pending_screen
                    self._transition_data = self._pending_kwargs
                    screen = self._screens.get(self._current)
                    if screen and hasattr(screen, "on_enter"):
                        screen.on_enter(**self._pending_kwargs)
                self._pending_screen = None
                self._pending_kwargs = {}
                self._fade_state = "in"
                self._fade_elapsed = 0.0
                self._fade_alpha = 1.0
        elif self._fade_state == "in":
            self._fade_elapsed += dt
            self._fade_alpha = max(0.0, 1.0 - (self._fade_elapsed / self._fade_duration))
            if self._fade_elapsed >= self._fade_duration:
                self._fade_state = "none"
                self._fade_alpha = 0.0
                self._fade_elapsed = 0.0

        screen = self._screens.get(self._current)
        if screen and hasattr(screen, "update"):
            result = screen.update(dt)
            if result:
                self._process_result(result)
        if self._quit_requested:
            return "quit"
        return None

    def render(self, renderer: _Renderer, text_renderer: _TextRenderer) -> None:
        screen = self._screens.get(self._current)
        if screen and hasattr(screen, "render"):
            screen.render(renderer, text_renderer)

    def _process_result(self, result: TransitionResult) -> None:
        if isinstance(result, str):
            if result == "quit":
                self._quit_requested = True
                return
            self.transition_to(result)
        elif len(result) == 2:
            name, kwargs = result
            self.transition_to(name, **kwargs)
