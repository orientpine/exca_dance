"""Gameplay screen — integrates game loop, HUD, visual cues."""

from __future__ import annotations
import numpy as np
import pygame
import moderngl
from exca_dance.core.models import BeatMap, Judgment, JointName
from exca_dance.rendering.theme import NeonTheme
from exca_dance.core.game_state import ScreenName
from exca_dance.core.game_loop import GameState as LoopState


class GameplayScreen:
    def __init__(
        self,
        renderer,
        text_renderer,
        game_loop,
        hud,
        visual_cues,
        viewport_layout,
        hit_sounds: dict[Judgment, pygame.mixer.Sound],
        *,
        overlay_2d=None,
    ) -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._game_loop = game_loop
        self._hud = hud
        self._visual_cues = visual_cues
        self._layout = viewport_layout
        self._hit_sounds: dict[Judgment, pygame.mixer.Sound] = hit_sounds
        self._beatmap: BeatMap | None = None
        self._overlay_2d = overlay_2d
        self._result_scoring = None
        self._pause_selected: int = 0

    def on_enter(self, beatmap: BeatMap | None = None, **kwargs) -> None:
        self._beatmap = beatmap
        if beatmap is not None:
            if beatmap.events:
                last_event = beatmap.events[-1]
                duration_ms = last_event.time_ms + last_event.duration_ms + 3000.0
            else:
                duration_ms = 60000.0
            self._hud.set_song_duration(duration_ms)
            self._game_loop.set_on_song_end(self._on_song_end)
            self._game_loop.start_song(beatmap)

    def _on_song_end(self, scoring) -> None:
        self._result_scoring = scoring

    def _draw_pause_panel(self, renderer) -> None:
        ctx = renderer.ctx
        W, H = renderer.width, renderer.height
        panel_w, panel_h = 400, 300
        panel_x = (W - panel_w) // 2
        panel_y = (H - panel_h) // 2
        x, y, w, h = panel_x, panel_y, panel_w, panel_h
        x0 = (x / W) * 2 - 1
        x1 = ((x + w) / W) * 2 - 1
        y0 = 1 - (y / H) * 2
        y1 = 1 - ((y + h) / H) * 2
        verts = [
            x0,
            y1,
            0,
            0.0,
            0.0,
            0.0,
            x1,
            y1,
            0,
            0.0,
            0.0,
            0.0,
            x1,
            y0,
            0,
            0.0,
            0.0,
            0.0,
            x0,
            y1,
            0,
            0.0,
            0.0,
            0.0,
            x1,
            y0,
            0,
            0.0,
            0.0,
            0.0,
            x0,
            y0,
            0,
            0.0,
            0.0,
            0.0,
        ]
        vbo = ctx.buffer(np.array(verts, dtype="f4"))
        prog = renderer.prog_solid
        vao = ctx.vertex_array(prog, [(vbo, "3f 3f", "in_position", "in_color")])
        identity = np.eye(4, dtype="f4")
        prog["mvp"].write(np.ascontiguousarray(identity).tobytes())
        prog["alpha"].value = 0.8
        ctx.disable(moderngl.DEPTH_TEST)
        vao.render(moderngl.TRIANGLES)
        vao.release()
        vbo.release()

    def handle_event(self, event: pygame.event.Event):
        paused = self._game_loop.state == LoopState.PAUSED
        if paused and event.type == pygame.KEYUP:
            self._game_loop.handle_event(event)
            return None

        if paused and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F3:
                self._hud.toggle_fps()
            elif event.key == pygame.K_UP:
                self._pause_selected = max(0, self._pause_selected - 1)
            elif event.key == pygame.K_DOWN:
                self._pause_selected = min(3, self._pause_selected + 1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                if self._pause_selected == 0:
                    self._game_loop.resume()
                elif self._pause_selected == 1:
                    self._game_loop.stop()
                    if self._beatmap is not None:
                        self._game_loop.start_song(self._beatmap)
                elif self._pause_selected == 2:
                    return ScreenName.SETTINGS
                else:
                    self._game_loop.stop()
                    return ScreenName.MAIN_MENU
            elif event.key == pygame.K_ESCAPE:
                self._game_loop.resume()
            elif event.key == pygame.K_q:
                self._game_loop.stop()
                return ScreenName.MAIN_MENU
            return None

        self._game_loop.handle_event(event)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F3:
                self._hud.toggle_fps()
            elif event.key == pygame.K_q and self._game_loop.state == LoopState.PAUSED:
                self._game_loop.stop()
                return ScreenName.MAIN_MENU
        return None

    def update(self, dt: float):
        if self._result_scoring is not None:
            scoring = self._result_scoring
            self._result_scoring = None
            title = self._beatmap.title if self._beatmap else ""
            return (
                ScreenName.RESULTS,
                {"scoring": scoring, "song_title": title, "beatmap": self._beatmap},
            )

        hit_results = self._game_loop.tick(dt)
        for result in hit_results:
            combo = self._game_loop._scoring._combo
            self._hud.judgment_display.trigger(result, combo)
            hit_sound = self._hit_sounds.get(result.judgment)
            if hit_sound is not None:
                hit_sound.play()
            if self._beatmap:
                _upcoming = self._game_loop.get_upcoming_events(500)
                self._hud.set_target_angles(_upcoming[0].target_angles if _upcoming else {})

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
        beat_phase = getattr(self._game_loop, "_beat_phase", 0.0)
        self._layout.render_gameplay_background(beat_phase)

        # Render 3D excavator in main viewport (2D panels cleared for overlay)
        self._layout.render_all(
            self._game_loop._excavator_model,
            self._game_loop.joint_angles,
        )

        self._layout.render_2d_grid("top_2d")

        # Ghost overlay — render in each viewport separately
        ctx = renderer.ctx
        vm = self._layout.viewport_manager
        ctx.enable_direct(moderngl.DEPTH_TEST)

        vm.set_viewport(ctx, "main_3d")
        self._visual_cues.render_ghost(self._layout.mvp_3d)
        self._visual_cues.render_outline(self._layout.mvp_3d)

        # Prepare data for overlay + side-view 3D rendering
        cur = self._game_loop.joint_angles
        tgt = self._visual_cues._active_target
        mpct = (
            {j: self._visual_cues.get_angle_match_pct(j) for j in JointName}
            if tgt is not None
            else None
        )

        # 2D panels — overlay renders the schematic
        vm.set_viewport(ctx, "top_2d")
        if self._overlay_2d is not None:
            self._overlay_2d.render(
                "top_2d",
                self._layout.mvp_top,
                cur,
                tgt,
                text_renderer,
                mpct,
            )

        # Side view — 3D excavator + ghost with swing-compensated camera
        vm.set_viewport(ctx, "side_2d")
        current_swing = cur.get(JointName.SWING, 0.0)
        side_mvp = self._layout.get_side_mvp_for_swing(current_swing)
        self._game_loop._excavator_model.render_3d(side_mvp)

        # Ghost in side view (counter-rotate by the ghost's own swing)
        ghost_swing = tgt.get(JointName.SWING, 0.0) if tgt else 0.0
        side_mvp_ghost = self._layout.get_side_mvp_for_swing(ghost_swing)
        self._visual_cues.render_ghost(side_mvp_ghost)
        self._visual_cues.render_outline(side_mvp_ghost)

        # 2D overlay schematic on top (uses static mvp_side, FK zeroes swing)
        if self._overlay_2d is not None:
            self._overlay_2d.render(
                "side_2d",
                self._layout.mvp_side,
                cur,
                tgt,
                text_renderer,
                mpct,
            )
        # Reset to full viewport
        ctx.viewport = (0, 0, renderer.width, renderer.height)

        self._layout.render_viewport_decorations(text_renderer)
        self._visual_cues.render_timeline(
            self._renderer,
            self._text,
            self._hud._song_duration_ms,
        )

        # HUD overlay
        self._hud.render(self._game_loop.joint_angles)

        # Pause overlay
        if self._game_loop.state == LoopState.PAUSED and text_renderer:
            self._draw_pause_panel(renderer)
            W, H = renderer.width, renderer.height
            text_renderer.render(
                "PAUSED",
                W // 2,
                H // 2 - 95,
                color=NeonTheme.NEON_BLUE.as_tuple(),
                scale=3.0,
                align="center",
            )
            items = ["RESUME", "RESTART", "SETTINGS", "QUIT TO MENU"]
            start_y = H // 2 - 20
            for i, label in enumerate(items):
                color = (
                    NeonTheme.NEON_PINK.as_tuple()
                    if i == self._pause_selected
                    else NeonTheme.TEXT_WHITE.as_tuple()
                )
                text_renderer.render(
                    label,
                    W // 2,
                    start_y + i * 60,
                    color=color,
                    scale=1.5,
                    align="center",
                )
