"""Gameplay screen — integrates game loop, HUD, visual cues."""

from __future__ import annotations
import pygame
from exca_dance.core.models import BeatMap
from exca_dance.rendering.theme import NeonTheme
from exca_dance.core.game_state import ScreenName
from exca_dance.core.game_loop import GameState as LoopState


class GameplayScreen:
    def __init__(
        self, renderer, text_renderer, game_loop, hud, visual_cues, viewport_layout
    ) -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._game_loop = game_loop
        self._hud = hud
        self._visual_cues = visual_cues
        self._layout = viewport_layout
        self._beatmap: BeatMap | None = None
        self._result_scoring = None

    def on_enter(self, beatmap: BeatMap | None = None, **kwargs) -> None:
        if beatmap:
            self._beatmap = beatmap
            self._hud.set_song_duration(len(beatmap.events) * 2000.0 if beatmap.events else 60000.0)
            self._game_loop.set_on_song_end(self._on_song_end)
            self._game_loop.start_song(beatmap)

    def _on_song_end(self, scoring) -> None:
        self._result_scoring = scoring

    def handle_event(self, event: pygame.event.Event):
        self._game_loop.handle_event(event)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F3:
                self._hud.toggle_fps()
        return None

    def update(self, dt: float):
        if self._result_scoring is not None:
            scoring = self._result_scoring
            self._result_scoring = None
            title = self._beatmap.title if self._beatmap else ""
            return (ScreenName.RESULTS, {"scoring": scoring, "song_title": title})

        hit_results = self._game_loop.tick(dt)
        for result in hit_results:
            combo = self._game_loop._scoring._combo
            self._hud.judgment_display.trigger(result, combo)
            if self._beatmap:
                self._hud.set_target_angles(
                    self._game_loop.get_upcoming_events(500)[0].target_angles
                    if self._game_loop.get_upcoming_events(500)
                    else {}
                )

        self._hud.update(dt)

        # Update visual cues
        upcoming = self._game_loop.get_upcoming_events(3000.0)
        self._visual_cues.update(
            self._game_loop.current_time_ms,
            self._game_loop.joint_angles,
            upcoming,
        )

        # Pause → show pause overlay
        if self._game_loop.state == LoopState.PAUSED:
            pass  # handled in render

        return None

    def render(self, renderer, text_renderer) -> None:
        # Render 3D excavator in all viewports
        self._layout.render_all(
            self._game_loop._excavator_model,
            self._game_loop.joint_angles,
        )

        # Ghost excavator overlay
        self._visual_cues.render_ghost(self._layout.mvp_3d)

        # HUD overlay
        self._hud.render(self._game_loop.joint_angles)

        # Pause overlay
        if self._game_loop.state == LoopState.PAUSED and text_renderer:
            W, H = renderer.width, renderer.height
            text_renderer.render(
                "PAUSED",
                W // 2,
                H // 2 - 60,
                color=NeonTheme.NEON_BLUE.as_tuple(),
                scale=3.0,
                align="center",
            )
            text_renderer.render(
                "ESC Resume  |  Q Quit",
                W // 2,
                H // 2 + 20,
                color=NeonTheme.TEXT_DIM.as_tuple(),
                scale=1.2,
                align="center",
            )
