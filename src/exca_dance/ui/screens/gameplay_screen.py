"""Gameplay screen — integrates game loop, HUD, visual cues."""

from __future__ import annotations
import numpy as np
import pygame
import moderngl
from exca_dance.core.models import BeatMap, Judgment, JointName
from exca_dance.rendering.theme import NeonTheme
from exca_dance.core.game_state import ScreenName
from exca_dance.core.game_loop import GameState as LoopState
from exca_dance.core.constants import DEFAULT_JOINT_ANGLES


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
        camera_settings=None,
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
        self._camera = camera_settings
        self._mouse_dragging: bool = False
        self._mouse_prev: tuple[int, int] = (0, 0)
        self._result_scoring = None
        self._pause_selected: int = 0

    def on_enter(self, beatmap: BeatMap | None = None, **kwargs) -> None:
        self._beatmap = beatmap
        if self._camera is not None:
            self._layout.rebuild_camera()
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
        """Draw pause overlay panel with neon border glow — resolution-aware."""
        ctx = renderer.ctx
        W, H = renderer.width, renderer.height
        s = H / 1080.0
        panel_w = int(max(520 * s, 340))
        panel_h = int(max(400 * s, 270))
        panel_x = (W - panel_w) // 2
        panel_y = (H - panel_h) // 2

        # Border glow (slightly larger rect in NEON_BLUE)
        border = int(max(3 * s, 2))
        self._draw_panel_rect(
            ctx,
            renderer,
            panel_x - border,
            panel_y - border,
            panel_w + 2 * border,
            panel_h + 2 * border,
            NeonTheme.NEON_BLUE,
            0.25,
        )

        # Inner panel (dark background)
        self._draw_panel_rect(
            ctx,
            renderer,
            panel_x,
            panel_y,
            panel_w,
            panel_h,
            NeonTheme.BG,
            0.88,
        )

    def _draw_panel_rect(
        self,
        ctx,
        renderer,
        x: int,
        y: int,
        w: int,
        h: int,
        color,
        alpha: float,
    ) -> None:
        """Draw a 2D rectangle in NDC via prog_solid."""
        W, H = renderer.width, renderer.height
        x0 = (x / W) * 2 - 1
        x1 = ((x + w) / W) * 2 - 1
        y0 = 1 - (y / H) * 2
        y1 = 1 - ((y + h) / H) * 2
        r, g, b = color.r, color.g, color.b
        verts = [
            x0,
            y1,
            0,
            r,
            g,
            b,
            x1,
            y1,
            0,
            r,
            g,
            b,
            x1,
            y0,
            0,
            r,
            g,
            b,
            x0,
            y1,
            0,
            r,
            g,
            b,
            x1,
            y0,
            0,
            r,
            g,
            b,
            x0,
            y0,
            0,
            r,
            g,
            b,
        ]
        vbo = ctx.buffer(np.array(verts, dtype="f4"))
        prog = renderer.prog_solid
        vao = ctx.vertex_array(prog, [(vbo, "3f 3f", "in_position", "in_color")])
        identity = np.eye(4, dtype="f4")
        prog["mvp"].write(np.ascontiguousarray(identity).tobytes())
        prog["alpha"].value = alpha
        ctx.disable(moderngl.DEPTH_TEST)
        vao.render(moderngl.TRIANGLES)
        vao.release()
        vbo.release()

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            self._mouse_dragging = True
            self._mouse_prev = event.pos
            return None
        if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self._mouse_dragging = False
            if self._camera is not None:
                self._camera.save()
            return None
        if event.type == pygame.MOUSEMOTION and self._mouse_dragging:
            if self._camera is not None:
                dx = event.pos[0] - self._mouse_prev[0]
                dy = event.pos[1] - self._mouse_prev[1]
                self._camera.azimuth += dx * 0.3
                self._camera.elevation += dy * 0.3
                self._layout.rebuild_camera()
            self._mouse_prev = event.pos
            return None

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

        # Sync HUD target — merge ALL upcoming events (nearest wins per joint).
        # Fallback: keep last processed event’s target for its duration window.
        if self._beatmap:
            _upcoming = self._game_loop.get_upcoming_events(6000.0)
            merged: dict[JointName, float] = {}
            for ev in _upcoming:
                for jn, ang in ev.target_angles.items():
                    if jn not in merged:
                        merged[jn] = ang
            if not merged:
                try:
                    last = self._game_loop.last_processed_event
                    if last is not None:
                        elapsed = self._game_loop.current_time_ms - last.time_ms
                        if elapsed <= last.duration_ms:
                            merged = dict(last.target_angles)
                except (TypeError, AttributeError):
                    pass
            if merged:
                full = dict(DEFAULT_JOINT_ANGLES)
                full.update(merged)
                merged = full
            self._hud.set_target_angles(merged)
        self._hud.update(dt)

        # Update visual cues
        upcoming = self._game_loop.get_upcoming_events(6000.0)
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

        # Side view — 2D overlay schematic only (no 3D model)
        vm.set_viewport(ctx, "side_2d")
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

        # Pause overlay (resolution-aware)
        if self._game_loop.state == LoopState.PAUSED and text_renderer:
            self._draw_pause_panel(renderer)
            W, H = renderer.width, renderer.height
            s = H / 1080.0

            panel_h = int(max(430 * s, 285))
            panel_y = (H - panel_h) // 2

            # "PAUSED" title
            title_scale = max(1.3125 * s, 0.675)
            text_renderer.render(
                "PAUSED",
                W // 2,
                panel_y + int(40 * s),
                color=NeonTheme.NEON_BLUE.as_tuple(),
                scale=title_scale,
                align="center",
                title=True,
            )

            items = ["RESUME", "RESTART", "SETTINGS", "QUIT TO MENU"]
            item_start_y = panel_y + int(140 * s)
            item_spacing = int(max(72 * s, 45))
            item_scale = max(0.9 * s, 0.5)

            for i, label in enumerate(items):
                iy = item_start_y + i * item_spacing

                if i == self._pause_selected:
                    # Highlight bar behind selected item
                    bar_h = int(max(32 * s, 22))
                    bar_w = int(max(320 * s, 200))
                    self._draw_panel_rect(
                        renderer.ctx,
                        renderer,
                        (W - bar_w) // 2,
                        iy - int(3 * s),
                        bar_w,
                        bar_h,
                        NeonTheme.NEON_PINK,
                        0.12,
                    )
                    color = NeonTheme.NEON_PINK.as_tuple()
                else:
                    color = NeonTheme.TEXT_WHITE.with_alpha(0.7).as_tuple()

                text_renderer.render(
                    label,
                    W // 2,
                    iy,
                    color=color,
                    scale=item_scale,
                    large=True,
                    align="center",
                )

            # Footer hint
            hint_y = panel_y + panel_h - int(25 * s)
            text_renderer.render(
                "ESC Resume  |  Q Quit",
                W // 2,
                hint_y,
                color=NeonTheme.TEXT_DIM.with_alpha(0.4).as_tuple(),
                scale=max(0.8 * s, 0.55),
                align="center",
            )
