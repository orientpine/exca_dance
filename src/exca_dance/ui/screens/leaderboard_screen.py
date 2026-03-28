"""Leaderboard screen + 3-character initials entry."""

from __future__ import annotations
import pygame
from exca_dance.rendering.theme import NeonTheme
from exca_dance.core.game_state import ScreenName

CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


class LeaderboardScreen:
    def __init__(self, renderer, text_renderer, leaderboard) -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._lb = leaderboard
        self._mode = "view"  # "view" or "enter"
        self._scoring = None
        self._song_title = ""
        # Initials entry state
        self._slots = [0, 0, 0]  # index into CHARS
        self._cursor = 0

    def on_enter(self, mode: str = "view", scoring=None, song_title: str = "", **kwargs) -> None:
        self._mode = mode
        self._scoring = scoring
        self._song_title = song_title
        self._slots = [0, 0, 0]
        self._cursor = 0

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if self._mode == "enter":
                return self._handle_entry(event)
            else:
                if event.key == pygame.K_ESCAPE:
                    return ScreenName.MAIN_MENU
        return None

    def _handle_entry(self, event: pygame.event.Event):
        if event.key == pygame.K_UP:
            self._slots[self._cursor] = (self._slots[self._cursor] + 1) % len(CHARS)
        elif event.key == pygame.K_DOWN:
            self._slots[self._cursor] = (self._slots[self._cursor] - 1) % len(CHARS)
        elif event.key == pygame.K_RIGHT:
            self._cursor = min(2, self._cursor + 1)
        elif event.key == pygame.K_LEFT:
            self._cursor = max(0, self._cursor - 1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            initials = "".join(CHARS[s] for s in self._slots)
            if self._scoring:
                score = self._scoring.get_total_score()
                self._lb.add_entry(initials, score, self._song_title)
            return ScreenName.MAIN_MENU
        elif event.key == pygame.K_ESCAPE:
            return ScreenName.MAIN_MENU
        return None

    def update(self, dt: float):
        return None

    def render(self, renderer, text_renderer) -> None:
        if text_renderer is None:
            return
        W, H = renderer.width, renderer.height
        s = H / 1080.0

        if self._mode == "enter":
            self._render_entry(renderer, text_renderer, W, H, s)
        else:
            self._render_view(renderer, text_renderer, W, H, s)

    def _render_entry(self, renderer, text_renderer, W, H, s) -> None:
        text_renderer.render(
            "ENTER YOUR INITIALS",
            W // 2,
            int(80 * s),
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=max(1.1 * s, 0.6),
            large=True,
            align="center",
        )
        if self._scoring:
            text_renderer.render(
                f"SCORE: {self._scoring.get_total_score():,}",
                W // 2,
                int(140 * s),
                color=NeonTheme.NEON_GREEN.as_tuple(),
                scale=max(1.6 * s, 0.9),
                align="center",
            )

        # 3 character slots
        slot_y = int(H * 0.44)
        slot_spacing = int(max(100 * s, 60))
        char_scale = max(4.0 * s, 2.0)
        arrow_scale = max(1.6 * s, 0.9)
        for i in range(3):
            x = W // 2 + (i - 1) * slot_spacing
            char = CHARS[self._slots[i]]
            color = NeonTheme.NEON_PINK if i == self._cursor else NeonTheme.TEXT_WHITE
            text_renderer.render(
                char,
                x,
                slot_y,
                color=color.as_tuple(),
                scale=char_scale,
                align="center",
                large=True,
            )
            if i == self._cursor:
                text_renderer.render(
                    "\u25b2",
                    x,
                    slot_y - int(60 * s),
                    color=NeonTheme.NEON_PINK.as_tuple(),
                    scale=arrow_scale,
                    align="center",
                )
                text_renderer.render(
                    "\u25bc",
                    x,
                    slot_y + int(80 * s),
                    color=NeonTheme.NEON_PINK.as_tuple(),
                    scale=arrow_scale,
                    align="center",
                )

        text_renderer.render(
            "\u2191\u2193 Change  |  \u2190\u2192 Move  |  ENTER Confirm",
            W // 2,
            H - int(60 * s),
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=max(0.95 * s, 0.6),
            align="center",
        )

    def _render_view(self, renderer, text_renderer, W, H, s) -> None:
        text_renderer.render(
            "LEADERBOARD",
            W // 2,
            int(40 * s),
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=max(1.25 * s, 0.65),
            large=True,
            align="center",
        )

        entries = self._lb.get_top_scores(limit=10)
        if not entries:
            text_renderer.render(
                "No scores yet!",
                W // 2,
                H // 2,
                color=NeonTheme.TEXT_DIM.as_tuple(),
                scale=max(1.6 * s, 0.9),
                align="center",
            )
        else:
            rank_colors = [NeonTheme.PERFECT, NeonTheme.TEXT_DIM, NeonTheme.NEON_ORANGE]
            entry_start_y = int(120 * s)
            entry_spacing = int(max(55 * s, 32))
            for i, entry in enumerate(entries):
                y = entry_start_y + i * entry_spacing
                color = rank_colors[i] if i < 3 else NeonTheme.TEXT_WHITE
                text_renderer.render(
                    f"#{i + 1:2d}  {entry.initials}  {entry.score:>10,}  {entry.song_title[:20]}",
                    W // 2,
                    y,
                    color=color.as_tuple(),
                    scale=max(1.2 * s, 0.7),
                    align="center",
                )

        text_renderer.render(
            "ESC Back",
            W // 2,
            H - int(40 * s),
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=max(0.95 * s, 0.6),
            align="center",
        )
