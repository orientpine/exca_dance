"""Visual cue system: ghost excavator + beat timeline indicators."""

from __future__ import annotations

# pyright: reportPrivateUsage=false, reportUnknownMemberType=false
import math
import time
from typing import Protocol, cast
import numpy as np
import moderngl
from exca_dance.core.kinematics import ExcavatorFK
from exca_dance.core.models import JointName, BeatEvent
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


class _BlendFuncContext(Protocol):
    blend_func: tuple[int, int] | int


class VisualCueRenderer:
    """
    Renders visual cues for the rhythm game:
    - Ghost excavator: semi-transparent target pose
    - Joint angle indicators: arc showing current vs target
    - Beat timeline: scrolling event markers at bottom
    """

    GHOST_FADE_MS: float = 1500.0  # fade in over 2 beats before event

    def __init__(
        self,
        renderer: GameRenderer,
        excavator_model_class: type[ExcavatorModel],
        fk: ExcavatorFK,
    ) -> None:
        self._renderer: GameRenderer = renderer
        self._fk: ExcavatorFK = fk
        # Ghost model uses distinct violet/purple colors
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
        self._ghost_glow_base: np.ndarray | None = None
        self._ghost_glow_vbo: moderngl.Buffer | None = None
        self._ghost_glow_vao: moderngl.VertexArray | None = None

    def _rebuild_ghost_glow(self) -> None:
        if self._ghost_model._vbo is None or self._ghost_model._vertex_count <= 0:
            self._ghost_glow_base = None
            return

        raw = np.frombuffer(self._ghost_model._vbo.read(), dtype="f4")
        if raw.size % 9 != 0:
            self._ghost_glow_base = None
            return

        raw_9 = raw.reshape(-1, 9).copy()
        positions = raw_9[:, :3]
        colors = raw_9[:, 3:6]

        ctx = self._renderer.ctx
        if self._ghost_glow_vbo is not None:
            self._ghost_glow_vbo.release()
        if self._ghost_glow_vao is not None:
            self._ghost_glow_vao.release()

        self._ghost_glow_base = np.column_stack((positions, colors)).astype("f4", copy=False)
        glow_data = np.column_stack(
            (positions, colors, np.zeros((positions.shape[0], 1), dtype="f4"))
        )
        self._ghost_glow_vbo = ctx.buffer(glow_data.tobytes())
        self._ghost_glow_vao = ctx.vertex_array(
            self._renderer.prog_additive,
            [(self._ghost_glow_vbo, "3f 4f", "in_position", "in_color")],
        )

    def _extract_edges(self, vertices_9: np.ndarray) -> np.ndarray:
        if vertices_9.shape[0] < 3:
            return np.empty((0, 3), dtype="f4")

        positions = vertices_9[:, :3]
        edge_keys: set[frozenset[tuple[float, float, float]]] = set()
        edge_segments: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []

        triangle_count = positions.shape[0] // 3

        def _vec3(row: np.ndarray) -> tuple[float, float, float]:
            return (float(row[0]), float(row[1]), float(row[2]))

        def _round_vec3(v: tuple[float, float, float]) -> tuple[float, float, float]:
            return (round(v[0], 4), round(v[1], 4), round(v[2], 4))

        for idx in range(triangle_count):
            tri = positions[idx * 3 : idx * 3 + 3]
            v0 = _vec3(tri[0])
            v1 = _vec3(tri[1])
            v2 = _vec3(tri[2])
            for a, b in ((v0, v1), (v1, v2), (v2, v0)):
                key: frozenset[tuple[float, float, float]] = frozenset(
                    {_round_vec3(a), _round_vec3(b)}
                )
                if key in edge_keys:
                    continue
                edge_keys.add(key)
                edge_segments.append((a, b))

        if not edge_segments:
            return np.empty((0, 3), dtype="f4")

        edge_positions = np.empty((len(edge_segments) * 2, 3), dtype="f4")
        out_i = 0
        for a, b in edge_segments:
            edge_positions[out_i] = a
            edge_positions[out_i + 1] = b
            out_i += 2
        return edge_positions

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
                self._rebuild_ghost_glow()
        else:
            self._active_target = None
            self._prev_ghost_angles = None

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

        glow_alpha = alpha * 0.5
        if glow_alpha > 0.01 and self._ghost_glow_vao is not None:
            if self._ghost_glow_vbo is not None and self._ghost_glow_base is not None:
                glow_data = np.empty((self._ghost_glow_base.shape[0], 7), dtype="f4")
                glow_data[:, :6] = self._ghost_glow_base
                glow_data[:, 6] = glow_alpha
                self._ghost_glow_vbo.write(glow_data.tobytes())

            ctx = cast(_BlendFuncContext, cast(object, self._renderer.ctx))
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
            try:
                mvp_uniform = cast(moderngl.Uniform, self._ghost_glow_vao.program["mvp"])
                mvp_uniform.write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())
                self._ghost_glow_vao.render(moderngl.TRIANGLES)
            finally:
                ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

    def render_outline(self, mvp: np.ndarray) -> None:
        if self._active_target is None:
            return
        if self._ghost_model._vbo is None:
            return

        raw = np.frombuffer(self._ghost_model._vbo.read(), dtype="f4").reshape(-1, 9)
        edge_positions = self._extract_edges(raw)
        if edge_positions.size == 0:
            return

        t = time.perf_counter()
        outline = NeonTheme.GHOST_OUTLINE
        base = (NeonTheme.GHOST_OUTLINE_PULSE_MIN + outline.a) / 2.0
        amp = (outline.a - NeonTheme.GHOST_OUTLINE_PULSE_MIN) / 2.0
        alpha = base + amp * math.sin(t * NeonTheme.GHOST_OUTLINE_PULSE_SPEED * 2.0 * math.pi)

        line_data = np.empty((edge_positions.shape[0], 7), dtype="f4")
        line_data[:, :3] = edge_positions
        line_data[:, 3] = outline.r
        line_data[:, 4] = outline.g
        line_data[:, 5] = outline.b
        line_data[:, 6] = alpha

        ctx = self._renderer.ctx
        vbo = ctx.buffer(line_data.tobytes())
        vao = ctx.vertex_array(
            self._renderer.prog_additive,
            [(vbo, "3f 4f", "in_position", "in_color")],
        )

        ctx.enable(moderngl.BLEND)
        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
        ctx.disable(moderngl.DEPTH_TEST)
        try:
            mvp_uniform = cast(moderngl.Uniform, self._renderer.prog_additive["mvp"])
            mvp_uniform.write(np.ascontiguousarray(mvp.astype("f4").T).tobytes())
            vao.render(moderngl.LINES)
        finally:
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
            ctx.enable(moderngl.DEPTH_TEST)
            vbo.release()
            vao.release()

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

        # Background bar
        self._draw_highway_rect(
            renderer, bar_x, bar_y, bar_w, bar_h,
            NeonTheme.BG_PANEL.as_rgb(), alpha=0.6, additive=False,
        )

        # Subtle lane dividers (horizontal)
        lane_count = 4
        for i in range(1, lane_count):
            lane_y = bar_y + int(bar_h * i / lane_count)
            self._draw_highway_rect(
                renderer, bar_x, lane_y, bar_w, 1,
                NeonTheme.NEON_BLUE.as_rgb(), alpha=0.08, additive=False,
            )

        # Hit-line: prominent center marker
        hit_w = 6
        self._draw_highway_rect(
            renderer, hit_x - hit_w // 2, bar_y, hit_w, bar_h,
            NeonTheme.NEON_BLUE.as_rgb(), alpha=0.95, additive=False,
        )
        # Hit-line glow
        glow_w = 24
        self._draw_highway_rect(
            renderer, hit_x - glow_w // 2, bar_y, glow_w, bar_h,
            NeonTheme.NEON_BLUE.as_rgb(), alpha=0.25, additive=True,
        )

        t = time.perf_counter()
        for event in self._upcoming_events:
            time_to_event = float(event.time_ms) - self._current_time_ms
            if not (-500.0 < time_to_event < 3000.0):
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
            self._draw_highway_rect(
                renderer, event_x - 8, event_y - 6,
                base_w + 16, event_h + 12,
                color, alpha=glow_alpha, additive=True,
            )

            # Layer 2: Core note body
            self._draw_highway_rect(
                renderer, event_x, event_y, base_w, event_h,
                color, alpha=0.85 + 0.15 * proximity, additive=False,
            )

            # Layer 3: Bright inner highlight
            inner_w = max(6, base_w - 10)
            inner_h = max(12, event_h - 12)
            self._draw_highway_rect(
                renderer,
                event_x + (base_w - inner_w) // 2,
                event_y + (event_h - inner_h) // 2,
                inner_w, inner_h,
                (1.0, 1.0, 1.0),
                alpha=0.15 + 0.25 * proximity, additive=True,
            )

    def _draw_highway_rect(
        self,
        renderer: GameRenderer,
        x: int,
        y: int,
        w: int,
        h: int,
        color: tuple[float, float, float],
        *,
        alpha: float,
        additive: bool,
    ) -> None:
        if w <= 0 or h <= 0 or alpha <= 0.0:
            return

        ctx = renderer.ctx
        W = renderer.width
        H = renderer.height

        x0_ndc = (x / W) * 2.0 - 1.0
        x1_ndc = ((x + w) / W) * 2.0 - 1.0
        y0_ndc = 1.0 - (y / H) * 2.0
        y1_ndc = 1.0 - ((y + h) / H) * 2.0
        r, g, b = color

        if additive:
            verts = np.array(
                [
                    x0_ndc,
                    y1_ndc,
                    0.0,
                    r,
                    g,
                    b,
                    alpha,
                    x1_ndc,
                    y1_ndc,
                    0.0,
                    r,
                    g,
                    b,
                    alpha,
                    x1_ndc,
                    y0_ndc,
                    0.0,
                    r,
                    g,
                    b,
                    alpha,
                    x0_ndc,
                    y1_ndc,
                    0.0,
                    r,
                    g,
                    b,
                    alpha,
                    x1_ndc,
                    y0_ndc,
                    0.0,
                    r,
                    g,
                    b,
                    alpha,
                    x0_ndc,
                    y0_ndc,
                    0.0,
                    r,
                    g,
                    b,
                    alpha,
                ],
                dtype="f4",
            )
            vbo = ctx.buffer(verts.tobytes())
            vao = ctx.vertex_array(
                renderer.prog_additive,
                [(vbo, "3f 4f", "in_position", "in_color")],
            )
            identity = np.eye(4, dtype="f4")
            mvp_uniform = cast(moderngl.Uniform, renderer.prog_additive["mvp"])
            mvp_uniform.write(np.ascontiguousarray(identity.T).tobytes())
            ctx.disable(moderngl.DEPTH_TEST)
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
            try:
                vao.render(moderngl.TRIANGLES)
            finally:
                ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
                vao.release()
                vbo.release()
            return

        verts = np.array(
            [
                x0_ndc,
                y1_ndc,
                0.0,
                r,
                g,
                b,
                x1_ndc,
                y1_ndc,
                0.0,
                r,
                g,
                b,
                x1_ndc,
                y0_ndc,
                0.0,
                r,
                g,
                b,
                x0_ndc,
                y1_ndc,
                0.0,
                r,
                g,
                b,
                x1_ndc,
                y0_ndc,
                0.0,
                r,
                g,
                b,
                x0_ndc,
                y0_ndc,
                0.0,
                r,
                g,
                b,
            ],
            dtype="f4",
        )
        vbo = ctx.buffer(verts.tobytes())
        vao = ctx.vertex_array(renderer.prog_solid, [(vbo, "3f 3f", "in_position", "in_color")])
        identity = np.eye(4, dtype="f4")
        mvp_uniform = cast(moderngl.Uniform, renderer.prog_solid["mvp"])
        alpha_uniform = cast(moderngl.Uniform, renderer.prog_solid["alpha"])
        mvp_uniform.write(np.ascontiguousarray(identity.T).tobytes())
        alpha_uniform.value = alpha
        ctx.disable(moderngl.DEPTH_TEST)
        try:
            vao.render(moderngl.TRIANGLES)
        finally:
            vao.release()
            vbo.release()

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
