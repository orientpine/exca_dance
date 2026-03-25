"""Main menu screen."""

from __future__ import annotations
import pygame
from exca_dance.rendering.theme import NeonTheme
from exca_dance.core.game_state import ScreenName


MENU_ITEMS = [
    ("PLAY", ScreenName.SONG_SELECT),
    ("EDITOR", ScreenName.EDITOR),
    ("LEADERBOARD", ScreenName.LEADERBOARD),
    ("SETTINGS", ScreenName.SETTINGS),
    ("QUIT", "quit"),
]


class MainMenuScreen:
    def __init__(self, renderer, text_renderer, mode_label: str = "VIRTUAL") -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._selected = 0
        self._mode_label = mode_label

    def on_enter(self, **kwargs) -> None:
        self._selected = 0

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self._selected = (self._selected - 1) % len(MENU_ITEMS)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._selected = (self._selected + 1) % len(MENU_ITEMS)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                _, target = MENU_ITEMS[self._selected]
                return target
        return None

    def update(self, dt: float):
        return None

    def render(self, renderer, text_renderer) -> None:
        if text_renderer is None:
            return
        W, H = renderer.width, renderer.height

        # Title
        text_renderer.render(
            "EXCA DANCE",
            W // 2,
            H // 4,
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=4.0,
            align="center",
        )
        text_renderer.render(
            "EXCAVATOR RHYTHM TRAINING",
            W // 2,
            H // 4 + 80,
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=1.2,
            align="center",
        )

        # Menu items
        start_y = H // 2 - 20
        for i, (label, _) in enumerate(MENU_ITEMS):
            y = start_y + i * 60
            if i == self._selected:
                color = NeonTheme.NEON_PINK.as_tuple()
                scale = 1.8
                prefix = "▶ "
            else:
                color = NeonTheme.TEXT_WHITE.as_tuple()
                scale = 1.4
                prefix = "  "
            text_renderer.render(
                prefix + label,
                W // 2,
                y,
                color=color,
                scale=scale,
                align="center",
            )

        # Mode indicator
        text_renderer.render(
            f"MODE: {self._mode_label}",
            W // 2,
            H - 40,
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=0.9,
            align="center",
        )
