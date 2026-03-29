"""Song selection screen."""

from __future__ import annotations
import os
import pygame
from exca_dance.core.beatmap import load_beatmap
from exca_dance.core.models import BeatMap
from exca_dance.rendering.theme import NeonTheme
from exca_dance.core.game_state import ScreenName


class SongSelectScreen:
    def __init__(
        self, renderer, text_renderer, leaderboard, beatmaps_dir: str = "assets/beatmaps"
    ) -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._leaderboard = leaderboard
        self._beatmaps_dir = beatmaps_dir
        self._songs: list[tuple[BeatMap, bool]] = []  # (beatmap, audio_exists)
        self._selected = 0

    def on_enter(self, **kwargs) -> None:
        self._load_songs()
        self._selected = 0

    def _load_songs(self) -> None:
        self._songs = []
        if not os.path.isdir(self._beatmaps_dir):
            return
        for fname in sorted(os.listdir(self._beatmaps_dir)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self._beatmaps_dir, fname)
            try:
                bm = load_beatmap(path)
                audio_ok = os.path.isfile(bm.audio_file)
                self._songs.append((bm, audio_ok))
            except Exception:
                pass

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self._selected = max(0, self._selected - 1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._selected = min(len(self._songs) - 1, self._selected + 1)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self._songs:
                    bm, audio_ok = self._songs[self._selected]
                    if audio_ok:
                        return (ScreenName.GAMEPLAY, {"beatmap": bm})
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

        text_renderer.render(
            "SELECT SONG",
            W // 2,
            int(50 * s),
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=max(0.55 * s, 0.30),
            title=True,
            align="center",
        )

        if not self._songs:
            text_renderer.render(
                "No songs found in assets/beatmaps/",
                W // 2,
                H // 2,
                color=NeonTheme.MISS.as_tuple(),
                scale=max(0.7 * s, 0.42),
                large=True,
                align="center",
            )
            return

        start_y = int(140 * s)
        item_spacing = int(max(100 * s, 60))
        for i, (bm, audio_ok) in enumerate(self._songs):
            y = start_y + i * item_spacing
            if i == self._selected:
                color = NeonTheme.NEON_PINK.as_tuple()
                scale = max(0.8 * s, 0.48)
            else:
                color = (NeonTheme.TEXT_WHITE if audio_ok else NeonTheme.TEXT_DIM).as_tuple()
                scale = max(0.65 * s, 0.4)

            text_renderer.render(
                f"{bm.title} [{getattr(bm, 'difficulty', 'NORMAL')}]",
                W // 2,
                y,
                color=color,
                scale=scale,
                large=True,
                align="center",
            )
            text_renderer.render(
                f"{bm.artist}  |  {bm.bpm:.0f} BPM  |  {len(bm.events)} events",
                W // 2,
                y + int(40 * s),
                color=NeonTheme.TEXT_DIM.as_tuple(),
                scale=max(0.55 * s, 0.35),
                large=True,
                align="center",
            )
            if not audio_ok:
                text_renderer.render(
                    "[AUDIO MISSING]",
                    W // 2,
                    y + int(65 * s),
                    color=NeonTheme.MISS.as_tuple(),
                    scale=max(0.50 * s, 0.33),
                    large=True,
                    align="center",
                )

        text_renderer.render(
            "\u2191\u2193 Navigate  |  ENTER Play  |  ESC Back",
            W // 2,
            H - int(45 * s),
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=max(0.55 * s, 0.35),
            large=True,
            align="center",
        )
