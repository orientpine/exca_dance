"""Gameplay HUD: score, combo, judgment flash, progress bar, joint status."""

from __future__ import annotations
from exca_dance.core.models import JointName
from exca_dance.rendering.theme import NeonTheme
from exca_dance.core.hit_detection import JudgmentDisplay
from exca_dance.rendering.visual_cues import VisualCueRenderer


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

    def __init__(
        self,
        renderer,
        text_renderer,
        audio,
        scoring,
        visual_cues: VisualCueRenderer | None = None,
    ) -> None:
        self._renderer = renderer
        self._text = text_renderer
        self._audio = audio
        self._scoring = scoring
        self._visual_cues = visual_cues
        self._judgment_display = JudgmentDisplay()
        self._show_fps = False
        self._song_duration_ms: float = 60_000.0  # default 60s
        self._target_angles: dict[JointName, float] = {}
        self._combo_pulse_time: float = 0.0
        self._last_combo: int = 0

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
        self._combo_pulse_time = max(0.0, self._combo_pulse_time - dt)
        combo = self._scoring._combo
        if combo > self._last_combo and combo > 0:
            self._combo_pulse_time = 0.2
        self._last_combo = combo

    def render(self, joint_angles: dict[JointName, float]) -> None:
        """Render all HUD elements — resolution-aware modern layout."""
        if self._text is None:
            return

        W = self._renderer.width
        H = self._renderer.height
        s = H / 1080.0
        main_w = int(W * 0.55)
        main_center_x = main_w // 2
        current_ms = self._audio.get_position_ms()

        # ── Score panel (top-right) ───────────────────────────────
        score = self._scoring.get_total_score()
        sc_x = main_w - int(20 * s)
        sc_y = int(12 * s)
        sc_w = int(280 * s)
        sc_h = int(78 * s)
        self._draw_rect_2d(
            sc_x - sc_w,
            sc_y - int(4 * s),
            sc_w + int(8 * s),
            sc_h,
            NeonTheme.BG_PANEL,
            alpha=0.5,
        )
        self._text.render(
            "SCORE",
            sc_x,
            sc_y,
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=max(1.0 * s, 0.6),
            align="right",
        )
        self._text.render(
            f"{score:08d}",
            sc_x,
            sc_y + int(24 * s),
            color=NeonTheme.NEON_BLUE.as_tuple(),
            scale=max(2.5 * s, 1.4),
            align="right",
        )

        # ── Combo (top-center) ─────────────────────────────────────
        combo = self._scoring._combo
        if combo > 0:
            pulse = 1.0
            if self._combo_pulse_time > 0:
                t = self._combo_pulse_time / 0.2
                pulse = 1.0 + 0.3 * t

            if combo >= 50:
                combo_color = NeonTheme.NEON_PINK
                combo_scale = 3.5 * pulse
            elif combo >= 25:
                combo_color = NeonTheme.PERFECT
                combo_scale = 3.0 * pulse
            elif combo >= 10:
                combo_color = NeonTheme.NEON_GREEN
                combo_scale = 2.5 * pulse
            else:
                combo_color = NeonTheme.TEXT_WHITE
                combo_scale = 2.5 * pulse

            if combo in (10, 25, 50):
                if self._combo_pulse_time > 0.15:
                    combo_scale *= 1.15

            self._text.render(
                f"x{combo}",
                main_center_x,
                int(15 * s),
                color=combo_color.as_tuple(),
                scale=max(combo_scale * s, combo_scale * 0.55),
                align="center",
            )
            mult = self._scoring.get_combo_multiplier()
            if mult > 1:
                self._text.render(
                    f"{mult}× COMBO",
                    main_center_x,
                    int(68 * s),
                    color=NeonTheme.NEON_ORANGE.as_tuple(),
                    scale=max(1.5 * s, 0.85),
                    align="center",
                )

        flash_color, flash_alpha = self._judgment_display.current_flash
        if flash_color is not None and flash_alpha > 0.0:
            self._draw_rect_2d(
                0,
                0,
                W,
                H,
                flash_color,
                alpha=flash_alpha,
            )

        # ── Judgment flash (center) ────────────────────────────────
        self._judgment_display.render(self._renderer, self._text)

        # ── Progress bar (in timeline area) ────────────────────────
        bar_y = H - int(18 * s)
        bar_h = max(int(12 * s), 8)
        bar_x = int(20 * s)
        bar_w = W - int(40 * s)
        progress = min(
            1.0,
            current_ms / max(1.0, self._song_duration_ms),
        )
        filled_w = int(bar_w * progress)

        self._draw_rect_2d(
            bar_x,
            bar_y,
            bar_w,
            bar_h,
            NeonTheme.BG_PANEL,
        )
        if filled_w > 0:
            self._draw_rect_2d(
                bar_x,
                bar_y,
                filled_w,
                bar_h,
                NeonTheme.NEON_BLUE,
            )
        self._draw_rect_2d(
            bar_x,
            bar_y - 1,
            bar_w,
            2,
            NeonTheme.NEON_BLUE,
            alpha=0.15,
        )

        # Time text
        elapsed_s = int(current_ms / 1000)
        total_s = int(self._song_duration_ms / 1000)
        self._text.render(
            (
                f"{elapsed_s // 60:02d}:{elapsed_s % 60:02d} / "
                f"{total_s // 60:02d}:{total_s % 60:02d}"
            ),
            W - int(20 * s),
            H - int(58 * s),
            color=NeonTheme.TEXT_DIM.as_tuple(),
            scale=max(1.1 * s, 0.7),
            align="right",
        )

        # ── Joint status panel (left side) ────────────────────────
        panel_x = int(15 * s)
        panel_y = int(100 * s)
        line_h = max(int(55 * s), 36)
        bar_total_w = max(int(140 * s), 90)
        joint_colors = {
            JointName.SWING: NeonTheme.JOINT_SWING,
            JointName.BOOM: NeonTheme.JOINT_BOOM,
            JointName.ARM: NeonTheme.JOINT_ARM,
            JointName.BUCKET: NeonTheme.JOINT_BUCKET,
        }
        p_w = max(int(320 * s), 200)
        p_h = len(JointName) * line_h + int(20 * s)
        self._draw_rect_2d(
            panel_x - int(8 * s),
            panel_y - int(10 * s),
            p_w,
            p_h,
            NeonTheme.BG_PANEL,
            alpha=0.45,
        )

        for i, jname in enumerate(JointName):
            y = panel_y + i * line_h
            color = joint_colors[jname]
            angle = joint_angles.get(jname, 0.0)
            target = self._target_angles.get(jname)
            match_pct = 1.0
            angle_color = color.as_tuple()

            if self._visual_cues is not None:
                match_pct = self._visual_cues.get_angle_match_pct(
                    jname,
                )
                if match_pct >= 0.9:
                    angle_color = NeonTheme.NEON_GREEN.as_tuple()
                elif match_pct >= 0.6:
                    angle_color = (1.0, 0.9, 0.0, 1.0)
                else:
                    angle_color = NeonTheme.NEON_PINK.as_tuple()

            # Joint name
            self._text.render(
                jname.value.upper(),
                panel_x,
                y,
                color=color.as_tuple(),
                scale=max(1.2 * s, 0.75),
            )

            # Angle difference (current − target); raw angle if no target
            if target is not None:
                diff = angle - target
                line = f"{diff:+.1f}°"
            else:
                line = f"{angle:+.1f}°"
            self._text.render(
                line,
                panel_x + int(95 * s),
                y,
                color=angle_color,
                scale=max(1.2 * s, 0.75),
            )

            # Match percentage bar
            bar_y_pos = y + int(26 * s)
            bar_h_bar = max(int(6 * s), 4)
            self._draw_rect_2d(
                panel_x,
                bar_y_pos,
                bar_total_w,
                bar_h_bar,
                NeonTheme.BG_PANEL,
            )
            fill_w = int(bar_total_w * match_pct)
            if fill_w > 0:
                if match_pct >= 0.9:
                    bar_color = NeonTheme.NEON_GREEN
                elif match_pct >= 0.6:
                    bar_color = NeonTheme.PERFECT
                else:
                    bar_color = NeonTheme.NEON_PINK
                self._draw_rect_2d(
                    panel_x,
                    bar_y_pos,
                    fill_w,
                    bar_h_bar,
                    bar_color,
                )

        # ── FPS counter (top-left, debug) ──────────────────────────
        if self._show_fps:
            fps = self._renderer.get_fps()
            fps_color = NeonTheme.NEON_GREEN if fps >= 55 else NeonTheme.MISS
            self._text.render(
                f"FPS: {fps:.0f}",
                10,
                10,
                color=fps_color.as_tuple(),
                scale=max(1.0 * s, 0.7),
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
