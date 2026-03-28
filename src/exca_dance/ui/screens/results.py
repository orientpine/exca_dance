"""Score results screen."""

from __future__ import annotations

import pygame

from exca_dance.core.game_state import ScreenName
from exca_dance.core.models import Judgment
from exca_dance.rendering.theme import NeonTheme


class ResultsScreen:
    def __init__(self, renderer, text_renderer) -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._scoring = None
        self._song_title = ""
        self._beatmap = None
        self._selected = 0
        self._options = [
            ("SAVE SCORE", "save"),
            ("RETRY", "retry"),
            ("MAIN MENU", ScreenName.MAIN_MENU),
        ]

    def on_enter(self, scoring=None, song_title: str = "", beatmap=None, **kwargs) -> None:
        self._scoring = scoring
        self._song_title = song_title
        self._beatmap = beatmap
        self._selected = 0

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return ScreenName.MAIN_MENU
            if event.key in (pygame.K_UP, pygame.K_w):
                self._selected = (self._selected - 1) % len(self._options)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._selected = (self._selected + 1) % len(self._options)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                _, action = self._options[self._selected]
                if action == "save":
                    return (
                        ScreenName.LEADERBOARD,
                        {
                            "mode": "enter",
                            "scoring": self._scoring,
                            "song_title": self._song_title,
                        },
                    )
                elif action == "retry":
                    if self._beatmap is not None:
                        return (ScreenName.GAMEPLAY, {"beatmap": self._beatmap})
                    return ScreenName.SONG_SELECT
                else:
                    return action
        return None

    def update(self, dt: float):
        return None

    def render(self, renderer, text_renderer) -> None:
        if text_renderer is None or self._scoring is None:
            return
        W, H = renderer.width, renderer.height
        s = H / 1080.0

        # ── Title ────────────────────────────────────────────────
        text_renderer.render(
            "RESULTS",
            W // 2,
            int(30 * s),
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=max(0.55 * s, 0.30),
            title=True,
            align="center",
        )

        # ── Song title ───────────────────────────────────────────
        text_renderer.render(
            self._song_title,
            W // 2,
            int(100 * s),
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=max(0.7 * s, 0.42),
            large=True,
            align="center",
        )

        # ── Score data ───────────────────────────────────────────
        score = self._scoring.get_total_score()
        max_score = self._scoring.get_max_possible_score(
            sum(self._scoring.get_judgment_counts().values())
        )
        grade = self._scoring.get_grade(score, max_score)

        # ── Grade (large, left-center) ───────────────────────────
        grade_colors = {
            "S": NeonTheme.PERFECT,
            "A": NeonTheme.NEON_GREEN,
            "B": NeonTheme.NEON_BLUE,
            "C": NeonTheme.NEON_ORANGE,
            "D": NeonTheme.TEXT_DIM,
            "F": NeonTheme.MISS,
        }
        grade_color = grade_colors.get(grade, NeonTheme.TEXT_WHITE)
        text_renderer.render(
            grade,
            int(W * 0.28),
            int(H * 0.30),
            color=grade_color.as_tuple(),
            scale=max(1.5 * s, 0.8),
            title=True,
            align="center",
        )

        # ── Score (large, right-center) ──────────────────────────
        text_renderer.render(
            f"{score:,}",
            int(W * 0.68),
            int(H * 0.32),
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=max(0.65 * s, 0.38),
            title=True,
            align="center",
        )

        # ── Judgment breakdown ───────────────────────────────────
        counts = self._scoring.get_judgment_counts()
        jy = int(H * 0.52)
        j_spacing = int(max(42 * s, 28))

        for j, label, color in [
            (Judgment.PERFECT, "PERFECT", NeonTheme.PERFECT),
            (Judgment.GREAT, "GREAT", NeonTheme.GREAT),
            (Judgment.GOOD, "GOOD", NeonTheme.GOOD),
            (Judgment.MISS, "MISS", NeonTheme.MISS),
        ]:
            text_renderer.render(
                f"{label}: {counts.get(j, 0)}",
                W // 2,
                jy,
                color=color.as_tuple(),
                scale=max(0.65 * s, 0.4),
                large=True,
                align="center",
            )
            jy += j_spacing

        # ── Max combo ────────────────────────────────────────────
        text_renderer.render(
            f"MAX COMBO: {self._scoring.get_max_combo()}",
            W // 2,
            jy + int(12 * s),
            color=NeonTheme.NEON_GREEN.as_tuple(),
            scale=max(0.65 * s, 0.4),
            large=True,
            align="center",
        )

        # ── Options ──────────────────────────────────────────────
        opt_y = H - int(160 * s)
        opt_spacing = int(max(48 * s, 32))
        for i, (label, _) in enumerate(self._options):
            color = NeonTheme.NEON_PINK if i == self._selected else NeonTheme.TEXT_WHITE
            sc = max(0.8 * s, 0.48) if i == self._selected else max(0.65 * s, 0.4)
            text_renderer.render(
                label,
                W // 2,
                opt_y + i * opt_spacing,
                color=color.as_tuple(),
                scale=sc,
                large=True,
                align="center",
            )
