"""Gameplay HUD: score, combo, judgment flash, progress bar, joint status."""

from __future__ import annotations
from exca_dance.core.models import JointName
from exca_dance.rendering.theme import NeonTheme
from exca_dance.core.hit_detection import JudgmentDisplay


class GameplayHUD:
    """
    Renders the gameplay overlay:
    - Score (top-right)
    - Combo counter (top-center)
    - Judgment flash (center)
    - Progress bar (bottom)
    - Joint status panel (left side)
    - FPS counter (top-left, debug, toggle F3)
    """

    def __init__(self, renderer, text_renderer, audio, scoring) -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._audio = audio
        self._scoring = scoring
        self._judgment_display = JudgmentDisplay()
        self._show_fps = False
        self._song_duration_ms: float = 60_000.0  # default 60s
        self._target_angles: dict[JointName, float] = {}

    def set_song_duration(self, ms: float) -> None:
        self._song_duration_ms = ms

    def set_target_angles(self, angles: dict[JointName, float]) -> None:
        self._target_angles = dict(angles)

    def toggle_fps(self) -> None:
        self._show_fps = not self._show_fps

    @property
    def judgment_display(self) -> JudgmentDisplay:
        return self._judgment_display

    def update(self, dt: float) -> None:
        self._judgment_display.update(dt)

    def render(self, joint_angles: dict[JointName, float]) -> None:
        """Render all HUD elements."""
        if self._text is None:
            return

        W = self._renderer.width
        H = self._renderer.height
        current_ms = self._audio.get_position_ms()

        # ── Score (top-right) ──────────────────────────────────────────
        score = self._scoring.get_total_score()
        self._text.render(
            f"{score:08d}",
            W - 20,
            20,
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=1.8,
            align="right",
        )

        # ── Combo (top-center) ─────────────────────────────────────────
        combo = self._scoring._combo
        if combo > 0:
            mult = self._scoring.get_combo_multiplier()
            if combo in (10, 25, 50):
                combo_color = NeonTheme.NEON_PINK
                combo_scale = 2.0
            else:
                combo_color = NeonTheme.NEON_GREEN if mult > 1 else NeonTheme.TEXT_WHITE
                combo_scale = 1.5
            self._text.render(
                f"x{combo}",
                W // 2,
                20,
                color=combo_color.as_tuple(),
                scale=combo_scale,
                align="center",
            )
            if mult > 1:
                self._text.render(
                    f"{mult}× COMBO",
                    W // 2,
                    60,
                    color=NeonTheme.NEON_ORANGE.as_tuple(),
                    scale=1.0,
                    align="center",
                )

        flash_color, flash_alpha = self._judgment_display.current_flash
        if flash_color is not None and flash_alpha > 0.0:
            self._draw_rect_2d(0, 0, W, H, flash_color, alpha=flash_alpha)

        # ── Judgment flash (center) ────────────────────────────────────
        self._judgment_display.render(self._renderer, self._text)

        # ── Progress bar (bottom) ──────────────────────────────────────
        bar_y = H - 30
        bar_h = 8
        bar_x = 20
        bar_w = W - 40
        progress = min(1.0, current_ms / max(1.0, self._song_duration_ms))
        filled_w = int(bar_w * progress)

        # Background bar (dim)
        self._draw_rect_2d(bar_x, bar_y, bar_w, bar_h, NeonTheme.BG_PANEL)
        # Filled bar (neon blue)
        if filled_w > 0:
            self._draw_rect_2d(bar_x, bar_y, filled_w, bar_h, NeonTheme.NEON_BLUE)

        # Time text
        elapsed_s = int(current_ms / 1000)
        total_s = int(self._song_duration_ms / 1000)
        self._text.render(
            f"{elapsed_s // 60:02d}:{elapsed_s % 60:02d} / {total_s // 60:02d}:{total_s % 60:02d}",
            W // 2,
            H - 50,
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=0.9,
            align="center",
        )

        # ── Joint status panel (left side) ────────────────────────────
        panel_x = 20
        panel_y = 120
        joint_colors = {
            JointName.SWING: NeonTheme.JOINT_SWING,
            JointName.BOOM: NeonTheme.JOINT_BOOM,
            JointName.ARM: NeonTheme.JOINT_ARM,
            JointName.BUCKET: NeonTheme.JOINT_BUCKET,
        }
        for i, jname in enumerate(JointName):
            y = panel_y + i * 70
            color = joint_colors[jname]
            angle = joint_angles.get(jname, 0.0)
            target = self._target_angles.get(jname)

            self._text.render(
                jname.value.upper(),
                panel_x,
                y,
                color=color.as_tuple(),
                scale=0.9,
            )
            self._text.render(
                f"{angle:+.1f}°",
                panel_x,
                y + 22,
                color=NeonTheme.TEXT_WHITE.as_tuple(),
                scale=0.85,
            )
            if target is not None:
                diff = abs(angle - target)
                match_color = NeonTheme.NEON_GREEN if diff < 10 else NeonTheme.NEON_ORANGE
                self._text.render(
                    f"→ {target:+.1f}°",
                    panel_x,
                    y + 44,
                    color=match_color.as_tuple(),
                    scale=0.8,
                )

        # ── FPS counter (top-left, debug) ──────────────────────────────
        if self._show_fps:
            fps = self._renderer.get_fps()
            fps_color = NeonTheme.NEON_GREEN if fps >= 55 else NeonTheme.MISS
            self._text.render(
                f"FPS: {fps:.0f}",
                10,
                10,
                color=fps_color.as_tuple(),
                scale=0.8,
            )

    def _draw_rect_2d(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        color,
        *,
        alpha: float = 1.0,
    ) -> None:
        import moderngl
        import numpy as np

        ctx = self._renderer.ctx
        W = self._renderer.width
        H = self._renderer.height

        x0 = (x / W) * 2.0 - 1.0
        x1 = ((x + w) / W) * 2.0 - 1.0
        y0 = 1.0 - (y / H) * 2.0
        y1 = 1.0 - ((y + h) / H) * 2.0

        if hasattr(color, "r"):
            r, g, b = color.r, color.g, color.b
        else:
            r, g, b = color[0], color[1], color[2]

        verts = [
            x0,
            y1,
            0.0,
            r,
            g,
            b,
            x1,
            y1,
            0.0,
            r,
            g,
            b,
            x1,
            y0,
            0.0,
            r,
            g,
            b,
            x0,
            y1,
            0.0,
            r,
            g,
            b,
            x1,
            y0,
            0.0,
            r,
            g,
            b,
            x0,
            y0,
            0.0,
            r,
            g,
            b,
        ]
        data = np.array(verts, dtype="f4")
        vbo = ctx.buffer(data)
        prog = self._renderer.prog_solid
        vao = ctx.vertex_array(prog, [(vbo, "3f 3f", "in_position", "in_color")])

        identity = np.eye(4, dtype="f4")
        prog["mvp"].write(np.ascontiguousarray(identity).tobytes())
        prog["alpha"].value = alpha

        ctx.disable(moderngl.DEPTH_TEST)
        vao.render(moderngl.TRIANGLES)

        vao.release()
        vbo.release()
