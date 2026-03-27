"""Visual cue system: ghost excavator + beat timeline indicators.

Performance-optimised variant:
* Ghost glow uses ``render_glow()`` with additive blend (no per-frame VBO rewrite).
* Outline edge VBO is cached; only rebuilt when ghost pose changes.
* Timeline rectangles are batched into two pre-allocated VBOs (solid + additive).
"""

from __future__ import annotations

# pyright: reportPrivateUsage=false, reportUnknownMemberType=false
import math
import time
from typing import Protocol

import moderngl
import numpy as np

from exca_dance.core.kinematics import ExcavatorFK
from exca_dance.core.models import BeatEvent, JointName
from exca_dance.rendering.excavator_model import ExcavatorModel
from exca_dance.rendering.renderer import GameRenderer
from exca_dance.rendering.theme import NeonTheme


class TextRendererProtocol(Protocol):
    def render(
        self,
        text: str,
        x: int,
        y: int,
        color: tuple[float, float, float, float],
        scale: float = 1.0,
        align: str = "left",
    ) -> None: ...


class VisualCueRenderer:
    """
    Renders visual cues for the rhythm game:
    - Ghost excavator: semi-transparent target pose
    - Joint angle indicators: arc showing current vs target
    - Beat timeline: scrolling event markers at bottom
    """

    GHOST_FADE_MS: float = 5000.0  # fade in over ~5 s before event

    # Pre-allocated buffer sizes (vertices)
    _TL_SOLID_RESERVE: int = 256  # ~42 solid rects
    _TL_ADD_RESERVE: int = 256  # ~36 additive rects

    def __init__(
        self,
        renderer: GameRenderer,
        excavator_model_class: type[ExcavatorModel],
        fk: ExcavatorFK,
    ) -> None:
        self._renderer: GameRenderer = renderer
        self._fk: ExcavatorFK = fk
        # Ghost model uses distinct blue colors for target pose visibility
        ghost_colors = {
            "base": NeonTheme.GHOST_SWING.as_rgb(),
            "turret": NeonTheme.GHOST_SWING.as_rgb(),
            JointName.BOOM: NeonTheme.GHOST_BOOM.as_rgb(),
            JointName.ARM: NeonTheme.GHOST_ARM.as_rgb(),
            JointName.BUCKET: NeonTheme.GHOST_BUCKET.as_rgb(),
        }
        self._ghost_model: ExcavatorModel = excavator_model_class(
            renderer, fk, joint_colors=ghost_colors
        )
        self._active_target: dict[JointName, float] | None = None
        self._next_event_time_ms: float = 0.0
        self._current_time_ms: float = 0.0
        self._current_angles: dict[JointName, float] = {j: 0.0 for j in JointName}
        self._upcoming_events: list[BeatEvent] = []
        self._prev_ghost_angles: dict[JointName, float] | None = None

        # ── Cached outline VBO (rebuilt only when ghost angles change) ──
        self._outline_vbo: moderngl.Buffer | None = None
        self._outline_vao: moderngl.VertexArray | None = None
        self._outline_vertex_count: int = 0

        # ── Pre-allocated timeline buffers ──
        ctx = renderer.ctx
        self._tl_solid_vbo: moderngl.Buffer = ctx.buffer(reserve=self._TL_SOLID_RESERVE * 6 * 4)
        self._tl_solid_vao: moderngl.VertexArray = ctx.vertex_array(
            renderer.prog_solid,
            [(self._tl_solid_vbo, "3f 3f", "in_position", "in_color")],
        )
        self._tl_add_vbo: moderngl.Buffer = ctx.buffer(reserve=self._TL_ADD_RESERVE * 7 * 4)
        self._tl_add_vao: moderngl.VertexArray = ctx.vertex_array(
            renderer.prog_additive,
            [(self._tl_add_vbo, "3f 4f", "in_position", "in_color")],
        )

        # ── Pre-computed constants ──
        self._identity_mvp_bytes: bytes = np.ascontiguousarray(np.eye(4, dtype="f4").T).tobytes()

    # ------------------------------------------------------------------
    # Outline cache (rebuilt only when ghost pose changes)
    # ------------------------------------------------------------------

    def _rebuild_outline_cache(self) -> None:
        """Build outline edge VBO from ghost model (fully vectorized, no Python loops)."""
        raw_9 = self._ghost_model.get_transformed_vertices()
        if raw_9.shape[0] < 3:
            self._outline_vertex_count = 0
            return

        positions = raw_9[:, :3]
        n_tris = positions.shape[0] // 3
        tris = positions[: n_tris * 3].reshape(n_tris, 3, 3)

        # 3 edges per triangle, 2 vertices per edge = 6 verts per tri (LINES)
        # Duplicate edges overdraw harmlessly under additive blend.
        n_edge_verts = n_tris * 6
        edge_verts = np.empty((n_edge_verts, 3), dtype="f4")
        edge_verts[0::6] = tris[:, 0]
        edge_verts[1::6] = tris[:, 1]
        edge_verts[2::6] = tris[:, 1]
        edge_verts[3::6] = tris[:, 2]
        edge_verts[4::6] = tris[:, 2]
        edge_verts[5::6] = tris[:, 0]

        outline = NeonTheme.GHOST_OUTLINE
        line_data = np.empty((n_edge_verts, 7), dtype="f4")
        line_data[:, :3] = edge_verts
        line_data[:, 3] = outline.r
        line_data[:, 4] = outline.g
        line_data[:, 5] = outline.b
        line_data[:, 6] = 1.0  # pulse applied via alpha_mult uniform

        ctx = self._renderer.ctx
        data_bytes = line_data.tobytes()

        if self._outline_vbo is not None:
            self._outline_vbo.release()
        if self._outline_vao is not None:
            self._outline_vao.release()

        self._outline_vbo = ctx.buffer(data_bytes)
        self._outline_vao = ctx.vertex_array(
            self._renderer.prog_additive,
            [(self._outline_vbo, "3f 4f", "in_position", "in_color")],
        )
        self._outline_vertex_count = n_edge_verts

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(
        self,
        current_time_ms: float,
        current_angles: dict[JointName, float],
        upcoming_events: list[BeatEvent],
    ) -> None:
        """Update cue state each frame."""
        self._current_time_ms = current_time_ms
        self._current_angles = dict(current_angles)
        self._upcoming_events = upcoming_events

        # Find the nearest upcoming event for ghost
        if upcoming_events:
            nearest = min(upcoming_events, key=lambda e: e.time_ms)
            self._active_target = dict(nearest.target_angles)
            self._next_event_time_ms = float(nearest.time_ms)
            # Update ghost model to target pose
            ghost_angles: dict[JointName, float] = {j: 0.0 for j in JointName}
            ghost_angles.update(nearest.target_angles)
            if self._prev_ghost_angles is None or any(
                abs(ghost_angles.get(k, 0) - self._prev_ghost_angles.get(k, 0)) > 0.01
                for k in ghost_angles
            ):
                self._ghost_model.update(ghost_angles)
                self._prev_ghost_angles = dict(ghost_angles)
                self._rebuild_outline_cache()
        else:
            self._active_target = None
            self._prev_ghost_angles = None

    # ------------------------------------------------------------------
    # Ghost rendering (model + glow via additive blend)
    # ------------------------------------------------------------------

    def render_ghost(self, mvp: np.ndarray) -> None:
        """Render semi-transparent ghost excavator at target pose."""
        if self._active_target is None:
            return
        time_to_event = self._next_event_time_ms - self._current_time_ms
        if time_to_event > self.GHOST_FADE_MS or time_to_event < 0:
            return
        # Fade in: alpha 0 → GHOST_ALPHA as event approaches
        ghost_alpha = NeonTheme.GHOST_ALPHA
        alpha = ghost_alpha * (1.0 - time_to_event / self.GHOST_FADE_MS)
        alpha = max(0.0, min(ghost_alpha, alpha))
        self._ghost_model.render_3d(mvp, alpha=alpha)

        # Additive glow pass — reuses existing static VBOs via render_glow()
        glow_alpha = alpha * 0.23
        if glow_alpha > 0.01:
            ctx = self._renderer.ctx
            ctx.enable(moderngl.DEPTH_TEST)
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
            try:
                # mvp is already set on prog_solid from render_3d above
                self._ghost_model.render_glow(glow_alpha)
            finally:
                ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
                ctx.disable(moderngl.DEPTH_TEST)

    # ------------------------------------------------------------------
    # Outline rendering (cached VBO + pulsing alpha_mult uniform)
    # ------------------------------------------------------------------

    def render_outline(self, mvp: np.ndarray) -> None:
        if self._active_target is None or self._outline_vertex_count == 0:
            return
        if self._outline_vao is None:
            return

        # Pulse via alpha_mult uniform — no VBO rewrite needed
        t = time.perf_counter()
        outline = NeonTheme.GHOST_OUTLINE
        base = (NeonTheme.GHOST_OUTLINE_PULSE_MIN + outline.a) / 2.0
        amp = (outline.a - NeonTheme.GHOST_OUTLINE_PULSE_MIN) / 2.0
        pulse_alpha = base + amp * math.sin(t * NeonTheme.GHOST_OUTLINE_PULSE_SPEED * 2.0 * math.pi)

        ctx = self._renderer.ctx
        prog = self._renderer.prog_additive

        ctx.enable(moderngl.BLEND)
        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
        ctx.disable(moderngl.DEPTH_TEST)
        try:
            prog["mvp"].write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())
            prog["alpha_mult"].value = pulse_alpha
            self._outline_vao.render(moderngl.LINES, vertices=self._outline_vertex_count)
        finally:
            prog["alpha_mult"].value = 1.0
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
            ctx.enable(moderngl.DEPTH_TEST)

    # ------------------------------------------------------------------
    # Timeline rendering (batched into pre-allocated VBOs)
    # ------------------------------------------------------------------

    def render_timeline(
        self,
        renderer: GameRenderer,
        text_renderer: TextRendererProtocol | None,
        song_duration_ms: float,
    ) -> None:
        _ = text_renderer
        _ = song_duration_ms
        W = renderer.width
        H = renderer.height

        # Timeline occupies bottom 28% of screen (matches ViewportManager)
        timeline_h = int(H * 0.28)
        margin = 12
        bar_w = W - margin * 2
        bar_h = timeline_h - margin * 2
        bar_x = margin
        bar_y = H - timeline_h + margin  # screen coords (top-left origin)
        hit_x = bar_x + bar_w // 2

        inv_w = 2.0 / W
        inv_h = 2.0 / H

        # Accumulate vertex data for batched rendering
        # solid_ranges: list of (first_vertex, count, alpha) for sub-range draws
        solid_verts: list[float] = []
        solid_ranges: list[tuple[int, int, float]] = []
        add_verts: list[float] = []

        def _add_solid(
            x: int,
            y: int,
            w: int,
            h: int,
            color: tuple[float, float, float],
            alpha: float,
        ) -> None:
            if w <= 0 or h <= 0 or alpha <= 0.0:
                return
            x0 = x * inv_w - 1.0
            x1 = (x + w) * inv_w - 1.0
            y0 = 1.0 - y * inv_h
            y1 = 1.0 - (y + h) * inv_h
            r, g, b = color
            first = len(solid_verts) // 6
            solid_verts.extend(
                [
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
            )
            solid_ranges.append((first, 6, alpha))

        def _add_additive(
            x: int,
            y: int,
            w: int,
            h: int,
            color: tuple[float, float, float],
            alpha: float,
        ) -> None:
            if w <= 0 or h <= 0 or alpha <= 0.0:
                return
            x0 = x * inv_w - 1.0
            x1 = (x + w) * inv_w - 1.0
            y0 = 1.0 - y * inv_h
            y1 = 1.0 - (y + h) * inv_h
            r, g, b = color
            add_verts.extend(
                [
                    x0,
                    y1,
                    0.0,
                    r,
                    g,
                    b,
                    alpha,
                    x1,
                    y1,
                    0.0,
                    r,
                    g,
                    b,
                    alpha,
                    x1,
                    y0,
                    0.0,
                    r,
                    g,
                    b,
                    alpha,
                    x0,
                    y1,
                    0.0,
                    r,
                    g,
                    b,
                    alpha,
                    x1,
                    y0,
                    0.0,
                    r,
                    g,
                    b,
                    alpha,
                    x0,
                    y0,
                    0.0,
                    r,
                    g,
                    b,
                    alpha,
                ]
            )

        # Background bar
        _add_solid(bar_x, bar_y, bar_w, bar_h, NeonTheme.BG_PANEL.as_rgb(), 0.6)

        # Subtle lane dividers (horizontal)
        lane_count = 4
        for i in range(1, lane_count):
            lane_y = bar_y + int(bar_h * i / lane_count)
            _add_solid(bar_x, lane_y, bar_w, 1, NeonTheme.NEON_BLUE.as_rgb(), 0.08)

        # Hit-line: prominent center marker
        hit_w = 6
        _add_solid(
            hit_x - hit_w // 2,
            bar_y,
            hit_w,
            bar_h,
            NeonTheme.NEON_BLUE.as_rgb(),
            0.95,
        )
        # Hit-line glow
        glow_w = 24
        _add_additive(
            hit_x - glow_w // 2,
            bar_y,
            glow_w,
            bar_h,
            NeonTheme.NEON_BLUE.as_rgb(),
            0.25,
        )

        t = time.perf_counter()
        for event in self._upcoming_events:
            time_to_event = float(event.time_ms) - self._current_time_ms
            if not (-500.0 < time_to_event < 6000.0):
                continue

            x_offset = int((time_to_event / 3000.0) * (bar_w // 2))
            n_joints = len(event.target_angles)

            # Proximity-based scaling: notes grow as they approach
            proximity = max(0.0, 1.0 - abs(time_to_event) / 1500.0)
            base_w = 24 + int(16 * proximity)  # 24px → 40px
            event_h = max(40, int((bar_h - 20) * 0.7 * (0.5 + 0.5 * n_joints / 4)))
            event_h = int(event_h * (0.85 + 0.15 * proximity))
            event_x = hit_x + x_offset - base_w // 2
            event_y = bar_y + (bar_h - event_h) // 2

            # Color: orange→white as it approaches, with pulse
            brightness = 0.5 + 0.5 * proximity
            pulse = 0.5 + 0.5 * math.sin(t * 4.0 + float(event.time_ms) * 0.01)
            orange = NeonTheme.NEON_ORANGE
            color = (
                min(1.0, orange.r * brightness + 0.3 * proximity),
                min(1.0, orange.g * brightness + 0.15 * proximity),
                min(1.0, orange.b * brightness),
            )

            # Layer 1: Outer glow (additive, wide)
            glow_alpha = (0.08 + 0.35 * proximity) * (0.7 + 0.3 * pulse)
            _add_additive(
                event_x - 8,
                event_y - 6,
                base_w + 16,
                event_h + 12,
                color,
                glow_alpha,
            )

            # Layer 2: Core note body
            _add_solid(
                event_x,
                event_y,
                base_w,
                event_h,
                color,
                0.85 + 0.15 * proximity,
            )

            # Layer 3: Bright inner highlight
            inner_w = max(6, base_w - 10)
            inner_h = max(12, event_h - 12)
            _add_additive(
                event_x + (base_w - inner_w) // 2,
                event_y + (event_h - inner_h) // 2,
                inner_w,
                inner_h,
                (1.0, 1.0, 1.0),
                0.15 + 0.25 * proximity,
            )

        ctx = renderer.ctx
        ctx.disable(moderngl.DEPTH_TEST)

        # ── Flush solid rects (one VBO write, alpha-grouped draws) ──────
        if solid_verts:
            data = np.array(solid_verts, dtype="f4").tobytes()
            buf_size = len(data)
            if buf_size > self._tl_solid_vbo.size:
                self._tl_solid_vao.release()
                self._tl_solid_vbo.release()
                self._tl_solid_vbo = ctx.buffer(reserve=buf_size * 2)
                self._tl_solid_vao = ctx.vertex_array(
                    renderer.prog_solid,
                    [(self._tl_solid_vbo, "3f 3f", "in_position", "in_color")],
                )
            self._tl_solid_vbo.write(data)
            prog_s = renderer.prog_solid
            prog_s["mvp"].write(self._identity_mvp_bytes)
            for first, count, alpha in solid_ranges:
                prog_s["alpha"].value = alpha
                self._tl_solid_vao.render(moderngl.TRIANGLES, vertices=count, first=first)

        # ── Flush additive rects (one VBO write, one draw call) ─────────
        if add_verts:
            data = np.array(add_verts, dtype="f4").tobytes()
            buf_size = len(data)
            if buf_size > self._tl_add_vbo.size:
                self._tl_add_vao.release()
                self._tl_add_vbo.release()
                self._tl_add_vbo = ctx.buffer(reserve=buf_size * 2)
                self._tl_add_vao = ctx.vertex_array(
                    renderer.prog_additive,
                    [(self._tl_add_vbo, "3f 4f", "in_position", "in_color")],
                )
            self._tl_add_vbo.write(data)
            prog_a = renderer.prog_additive
            prog_a["mvp"].write(self._identity_mvp_bytes)
            prog_a["alpha_mult"].value = 1.0
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
            try:
                add_vertex_count = len(add_verts) // 7
                self._tl_add_vao.render(moderngl.TRIANGLES, vertices=add_vertex_count)
            finally:
                ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

        ctx.enable(moderngl.DEPTH_TEST)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_angle_match_pct(self, joint: JointName) -> float:
        """Return 0-1 how close current angle is to target (1=perfect match)."""
        if self._active_target is None or joint not in self._active_target:
            return 1.0
        target = self._active_target[joint]
        current = self._current_angles.get(joint, 0.0)
        diff = abs(current - target)
        return max(0.0, 1.0 - diff / 30.0)  # 30° = 0% match

    def destroy(self) -> None:
        self._ghost_model.destroy()
        if self._outline_vbo is not None:
            self._outline_vbo.release()
        if self._outline_vao is not None:
            self._outline_vao.release()
        self._tl_solid_vao.release()
        self._tl_solid_vbo.release()
        self._tl_add_vao.release()
        self._tl_add_vbo.release()
